"""Outils communs à tous les scripts du skill.

- Dossier de campagne : chaque script prend --campagne <dossier>, le dossier créé à l'étape 1 qui contient
  campagne.toml (copie complétée de config/campagne.exemple.toml). Toutes les sorties vont dans ce dossier, jamais
  dans le dossier du skill.
- Configuration : campagne.toml, fusionnée avec les valeurs par défaut DEFAUTS ci-dessous.
- Fichiers CSV : lus en utf-8-sig (virgule ou point-virgule), écrits en utf-8-sig.
- Clé Apollo : variable d'environnement APOLLO_API_KEY, sinon fichier .env du dossier courant ou d'un dossier
  parent, sinon .env du dossier du skill.
- Recherche DuckDuckGo (paquet ddgs) avec relances, et répertoire officiel des localités suisses (swisstopo).

Bibliothèque standard seulement (tomllib : Python 3.11 ou plus), sauf recherche_web (ddgs) et session (requests).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
import tomllib
import unicodedata
from datetime import date
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 ou plus est requis (voir README.md, « Installation »).")

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
LOCALITES = SKILL / "donnees" / "localites-suisse.csv"
CONFIG_EXEMPLE = SKILL / "config" / "campagne.exemple.toml"

# ---------------------------------------------------------------- contrat entre étapes (voir reference/contrat.md)

# Liste d'entreprises : entreprises.csv (étape 2), entreprises-enrichi.csv (étape 3), entreprises-verifie.csv
# (étape 4). Mêmes colonnes dans les trois fichiers, remplies au fil des étapes ; d'autres colonnes peuvent suivre.
COLONNES_ENTREPRISES = [
    "nom", "nom_officiel", "pays", "ville", "canton", "region",
    "site", "site_statut", "site_confiance",
    "linkedin", "linkedin_statut", "linkedin_source", "linkedin_confiance",
    "secteur", "activite", "taille", "technologies",
    "source", "preuve", "a_revoir", "exclure", "deja_connue", "note",
]
# Contacts Apollo : apollo/contacts-crees.csv (étape 6) et apollo/contacts-importes.csv (étape 2, export de contacts).
COLONNES_CONTACTS = [
    "tier", "entreprise", "entreprise_id", "ordre", "cibles", "prenom", "nom", "titre", "seniorite",
    "email", "statut_email", "linkedin", "ville", "pays", "contact_id", "statut",
]
ORDRE_ENTREE, ORDRE_RELAIS = "entrée", "relais"

# ---------------------------------------------------------------- configuration

DEFAUTS: dict = {
    "campagne": {"nom": "", "date_reference": ""},
    "offre": {
        "societe": "", "description": "", "argument_cle": "", "preuves": [], "appelant": "",
        "presentation_appelant": "", "question_ouverte": "", "cta": "", "lien_agenda": "",
        "signature_email": "", "concurrents": "", "ne_jamais_dire": [],
    },
    "cible": {
        "description": "", "pays": [], "regions_prioritaires": [], "pays_voisins": [],
        "taille_min": 10, "taille_max": 200, "taille_limite": 1000,
        "profil_secteurs": "industrie", "secteurs": [], "exclusions": [],
    },
    "persona": {"entree": "direction", "relais": [], "titres": {}},
    "signaux": {"fenetre_mois": 24, "registre_suisse": True, "logiciels": []},
    "apollo": {"liste_comptes": "", "liste_contacts": "", "pays_contacts": [], "mobiles": False},
    "appels": {"langues": ["fr"]},
}


def _fusionner(base: dict, ajout: dict) -> dict:
    out = dict(base)
    for k, v in ajout.items():
        out[k] = _fusionner(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def charger_config(chemin: Path) -> dict:
    if not chemin.exists():
        raise SystemExit(
            f"Configuration absente : {chemin}\n"
            f"Copiez {CONFIG_EXEMPLE} dans le dossier de la campagne sous le nom campagne.toml, "
            "puis complétez-le (README.md, « Fichiers à compléter »).")
    try:
        with chemin.open("rb") as f:
            lu = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{chemin} : erreur de syntaxe TOML ({e}). Vérifiez les guillemets et les crochets.")
    return _fusionner(DEFAUTS, lu)


class Campagne:
    """Le dossier d'une campagne et sa configuration."""

    def __init__(self, dossier: str | Path, config_obligatoire: bool = True):
        self.dossier = Path(dossier).expanduser().resolve()
        if not self.dossier.is_dir():
            raise SystemExit(f"Dossier de campagne introuvable : {self.dossier} (étape 1, README.md).")
        fichier = self.dossier / "campagne.toml"
        self.config = charger_config(fichier) if (config_obligatoire or fichier.exists()) else _fusionner(DEFAUTS, {})
        self.nom = self.config["campagne"]["nom"] or self.dossier.name

    # dossiers de travail (créés au besoin)
    def sous_dossier(self, *parties: str) -> Path:
        p = self.dossier.joinpath(*parties)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def donnees(self) -> Path:
        return self.sous_dossier("donnees")

    @property
    def cache(self) -> Path:
        return self.sous_dossier("donnees", "cache")

    @property
    def signaux(self) -> Path:
        return self.sous_dossier("donnees", "signaux")

    @property
    def verification(self) -> Path:
        return self.sous_dossier("donnees", "verification")

    @property
    def apollo(self) -> Path:
        return self.sous_dossier("apollo")

    @property
    def appels(self) -> Path:
        return self.sous_dossier("appels")

    # fichiers du contrat
    def fichier(self, nom: str) -> Path:
        return self.dossier / nom

    def liste_entreprises(self) -> Path:
        """La liste la plus avancée : entreprises-verifie.csv, sinon -enrichi.csv, sinon entreprises.csv."""
        for nom in ("entreprises-verifie.csv", "entreprises-enrichi.csv", "entreprises.csv"):
            if (self.dossier / nom).exists():
                return self.dossier / nom
        raise SystemExit(f"Aucune liste d'entreprises dans {self.dossier} : faire l'étape 2 (etapes/02-trouver-les-entreprises.md).")

    def date_reference(self) -> date:
        d = (self.config["campagne"].get("date_reference") or "").strip() or os.environ.get("PROSPECTION_DATE", "")
        return date.fromisoformat(d) if d else date.today()


def argument_campagne(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--campagne", required=True,
                    help="dossier de la campagne (contient campagne.toml), par exemple campagnes/ma-campagne")


# ---------------------------------------------------------------- fichiers CSV

def lire_csv(chemin: str | Path) -> list[dict]:
    """Lignes d'un CSV (utf-8 avec ou sans BOM, séparateur virgule ou point-virgule deviné)."""
    with open(chemin, encoding="utf-8-sig", newline="") as h:
        echantillon = h.read(8192)
        h.seek(0)
        sep = ";" if echantillon.count(";") > echantillon.count(",") else ","
        return [{(k or "").strip(): (v or "") for k, v in r.items()} for r in csv.DictReader(h, delimiter=sep)]


def ecrire_csv(chemin: str | Path, colonnes: list[str], lignes: list[dict]) -> None:
    """Écrit en utf-8-sig (lisible par Excel) ; les colonnes absentes d'une ligne restent vides."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        w.writeheader()
        for l in lignes:
            w.writerow({c: ("" if l.get(c) is None else l.get(c)) for c in colonnes})


# ---------------------------------------------------------------- noms, sites, LinkedIn

FORMES_JURIDIQUES = {"sa", "ag", "gmbh", "sarl", "sas", "sasu", "ltd", "holding", "co", "kg", "group", "groupe", "the",
                     "et", "und", "and", "cie", "inc", "sagl", "spa", "srl", "s", "a", "g", "succursale", "filiale"}


def norm(s: str) -> str:
    """Clé de comparaison d'un nom d'entreprise : minuscules, sans accents ni forme juridique."""
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w not in FORMES_JURIDIQUES)


def domaine(url: str) -> str:
    url = (url or "").strip().lower()
    url = re.sub(r"^https?://", "", url).split("/")[0].split("?")[0]
    return url[4:] if url.startswith("www.") else url


def site_propre(url: str) -> str:
    d = domaine(url)
    return f"https://{d}" if d else ""


def slug_linkedin(url: str) -> str:
    m = re.search(r"linkedin\.com/company/([^/?#\s]+)", url or "", re.I)
    return m[1].lower() if m else ""


def linkedin_company(url: str) -> str:
    s = slug_linkedin(url)
    return f"https://www.linkedin.com/company/{s}/" if s else ""


def charger_noms(fichiers: list[str]) -> tuple[set, set]:
    """Noms (normalisés) et domaines d'une ou plusieurs listes CSV : colonnes de nom et de site devinées.
    Sert à --deja (nos listes existantes) et --exclure (nos clients et partenaires actuels)."""
    noms, doms = set(), set()
    for f in fichiers:
        for r in lire_csv(f):
            for k, v in r.items():
                kl = k.lower()
                if not v:
                    continue
                if kl in ("nom", "entreprise", "company", "company name", "name", "nom_officiel", "raison sociale"):
                    noms.add(norm(v))
                elif kl in ("site", "website", "site web", "domaine", "domain", "company website"):
                    doms.add(domaine(v))
    return noms - {""}, doms - {""}


# ---------------------------------------------------------------- localités suisses

def charger_localites(chemin: Path = LOCALITES) -> dict:
    """norm(localité ou commune) -> (canton, langue) depuis le répertoire officiel des localités (swisstopo)."""
    loc = {}
    if not chemin.exists():
        print(f"! répertoire des localités absent ({chemin}) : canton et région restent vides", file=sys.stderr)
        return loc
    for r in lire_csv(chemin):
        for nom in (r.get("Ortschaftsname", ""), r.get("Gemeindename", ""), *r.get("Ortschaftsname", "").split("/")):
            k = norm(re.sub(r"\s+\d+$", "", nom))
            if k and k not in loc:
                loc[k] = (r.get("Kantonskürzel", ""), r.get("Sprache", ""))
    return loc


def region(ville: str, pays: str, loc: dict) -> tuple[str, str]:
    """(canton, région linguistique) d'une ville suisse ; vide hors de Suisse."""
    if (pays or "").upper() != "CH":
        return "", ""
    k = norm(ville)
    c = loc.get(k) or (loc.get(k.split()[0]) if k else None)
    if not c:
        return "", "inconnue"
    return c[0], {"fr": "romande", "de": "alémanique", "it": "italienne"}.get(c[1], "plurilingue")


# ---------------------------------------------------------------- pays et langues

PAYS = {"switzerland": "CH", "suisse": "CH", "schweiz": "CH", "svizzera": "CH", "france": "FR", "germany": "DE",
        "allemagne": "DE", "deutschland": "DE", "italy": "IT", "italie": "IT", "italia": "IT", "austria": "AT",
        "autriche": "AT", "österreich": "AT", "liechtenstein": "LI", "belgium": "BE", "belgique": "BE",
        "luxembourg": "LU", "netherlands": "NL", "pays-bas": "NL", "spain": "ES", "espagne": "ES",
        "portugal": "PT", "united kingdom": "GB", "royaume-uni": "GB", "ireland": "IE", "irlande": "IE",
        "united states": "US", "états-unis": "US", "etats-unis": "US", "canada": "CA", "sweden": "SE",
        "suède": "SE", "denmark": "DK", "danemark": "DK", "norway": "NO", "norvège": "NO", "finland": "FI",
        "finlande": "FI", "poland": "PL", "pologne": "PL", "czech republic": "CZ", "czechia": "CZ",
        "tchéquie": "CZ", "hungary": "HU", "hongrie": "HU", "romania": "RO", "roumanie": "RO",
        "slovenia": "SI", "slovénie": "SI", "slovakia": "SK", "slovaquie": "SK", "greece": "GR", "grèce": "GR",
        "israel": "IL", "israël": "IL", "china": "CN", "chine": "CN", "japan": "JP", "japon": "JP",
        "singapore": "SG", "singapour": "SG", "india": "IN", "inde": "IN", "brazil": "BR", "brésil": "BR",
        "argentina": "AR", "argentine": "AR", "mexico": "MX", "mexique": "MX"}
# langues principales d'un pays (Suisse : par la commune, voir region())
LANGUES_PAYS = {"CH": "fr", "FR": "fr", "BE": "fr", "LU": "fr", "MC": "fr", "DE": "de", "AT": "de", "LI": "de",
                "IT": "it", "SM": "it", "ES": "es", "PT": "pt", "NL": "nl", "GB": "en", "IE": "en", "US": "en", "CA": "en"}


def code_pays(v: str) -> str:
    """'Switzerland', 'Suisse' ou 'CH' -> 'CH' ; vide si inconnu."""
    v = (v or "").strip()
    return v.upper() if len(v) == 2 and v.isalpha() else PAYS.get(v.lower(), "")


def region_recherche(pays: str = "", langue: str = "") -> str:
    """Région DuckDuckGo adaptée : ch-fr, ch-de, fr-fr, de-de, it-it... ; wt-wt (monde) à défaut."""
    pays, langue = (pays or "").upper(), (langue or "").lower()
    if pays == "CH":
        return {"de": "ch-de", "it": "ch-it"}.get(langue, "ch-fr")
    return {"FR": "fr-fr", "DE": "de-de", "AT": "at-de", "IT": "it-it", "BE": "be-fr", "ES": "es-es",
            "NL": "nl-nl", "GB": "uk-en", "US": "us-en"}.get(pays, "wt-wt")


# ---------------------------------------------------------------- web

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def session():
    """Session requests avec un navigateur courant pour en-tête."""
    import requests
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "fr,en;q=0.8,de;q=0.6"})
    return s


def recherche_web(requete: str, n: int = 10, region: str = "wt-wt", actualites: bool = False,
                  essais: int = 3, **kw) -> list[dict]:
    """Recherche DuckDuckGo (ddgs) : [{title, href, body}] ; [] si aucun résultat ou si le service reste
    indisponible après les relances (les moteurs échouent par intermittence)."""
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
    for essai in range(essais):
        try:
            with DDGS() as d:
                fn = d.news if actualites else d.text
                return fn(requete, region=region, max_results=n, **kw) or []
        except DDGSException as e:
            if "no results" in str(e).lower():
                return []
            time.sleep(3 * (essai + 1))
        except Exception:  # noqa: BLE001 (réseau, délai dépassé)
            time.sleep(3 * (essai + 1))
    return []


# ---------------------------------------------------------------- clé Apollo

def cle_apollo() -> str:
    """APOLLO_API_KEY : variable d'environnement, sinon .env du dossier courant ou d'un parent, sinon du skill.
    La clé n'est jamais affichée."""
    if os.environ.get("APOLLO_API_KEY", "").strip():
        return os.environ["APOLLO_API_KEY"].strip()
    candidats = [d / ".env" for d in (Path.cwd(), *Path.cwd().parents)] + [SKILL / ".env"]
    for f in candidats:
        if f.is_file():
            for ligne in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(r"\s*(?:export\s+)?APOLLO_API_KEY\s*=\s*[\"']?([^\"'\s#]+)", ligne)
                if m:
                    return m[1]
    raise SystemExit(
        "Clé Apollo introuvable. Dans Apollo : Settings > Integrations > API, créez une clé (master, ou avec les "
        "droits listés dans README.md), puis écrivez-la dans un fichier .env à la racine du projet : "
        "APOLLO_API_KEY=votre_cle (modèle : exemple.env du skill).")


def a_une_cle_apollo() -> bool:
    try:
        cle_apollo()
        return True
    except SystemExit:
        return False
