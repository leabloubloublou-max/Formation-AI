"""Étape 3 : site officiel et page LinkedIn des entreprises d'une liste qui n'en a pas (ou pas toutes).

Entrée : <campagne>/entreprises.csv (étape 2, colonnes commun.COLONNES_ENTREPRISES). Seules les lignes sans site ou
sans LinkedIn sont cherchées ; les lignes à exclure (colonne exclure remplie) sont recopiées telles quelles.
Méthode, par entreprise (dédoublonnée par nom) :
1. Site : DuckDuckGo, jusqu'à 3 requêtes ("<nom>" exact, <nom>, <nom> official website) ; annuaires, registres,
   réseaux sociaux, places de marché et sites d'emploi écartés (BAD_DOMAINS). Premier domaine qui contient un mot
   distinctif du nom : confiance « haute » ; sinon premier candidat de la première requête non vide : « basse ».
2. LinkedIn : lien /company/ lu sur le site (accueil, puis contact, à propos... : linkedin_site.find_for_site)
   quand le site est sûr (donné par la liste, ou trouvé avec une confiance haute) : source « site web », confiance
   « haute » ; sinon DuckDuckGo "<nom> linkedin company" : « haute » si le slug ou le titre contient un mot
   distinctif du nom, sinon premier lien, « basse » (source « duckduckgo »).
3. Corrections manuelles facultatives : <campagne>/corrections.csv (colonnes nom, site, linkedin), appliquées à
   l'écriture sans refaire les recherches, à toutes les lignes du même nom. Valeur d'une cellule : vide = rien à
   corriger ; une URL = remplace (statut « corrigé », confiance haute) ; « - » = vide le champ (confiance « à
   vérifier ») ; « ? » = garde la valeur trouvée avec une confiance basse ; linkedin = « site » relit la page
   LinkedIn sur le site (corrigé ou trouvé). Un nom de corrections.csv absent de la liste est signalé.
Région DuckDuckGo par entreprise : commun.region_recherche(pays, langue) ; pays vide = premier pays de cible.pays
de campagne.toml ; langue, pour la Suisse, par la région linguistique de la commune.
Sortie : <campagne>/entreprises-enrichi.csv (mêmes colonnes ; site_statut et linkedin_statut « trouvé » ou
« introuvable », confiances, linkedin_source, a_revoir = oui sans site sûr). Caches : donnees/cache/enrichir-sites.json
(recherches DuckDuckGo) et donnees/cache/linkedin-sites.json (pages lues, par domaine, partagé avec
linkedin_site.py) : une relance ne refait que ce qui manque ; supprimer une clé force une nouvelle recherche.
À savoir : sur une campagne précédente, environ un lien sur quatre trouvé ainsi était faux ou imparfait
(homonymes, filiales d'un autre pays, annuaires) : ce sont des candidats, la vérification fiable est l'étape 4.

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_sites.py --campagne campagnes/<nom> \\
      [--workers 4] [--limite N]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import (COLONNES_ENTREPRISES, LANGUES_PAYS, Campagne, argument_campagne, code_pays, domaine, ecrire_csv,
                    linkedin_company, lire_csv, norm, recherche_web, region_recherche, site_propre)
from linkedin_site import CACHE_NOM, find_for_site

# Domaines qui ne sont jamais le site de l'entreprise
BAD_DOMAINS = (
    "linkedin.", "facebook.", "instagram.", "twitter.", "x.com", "youtube.", "wikipedia.",
    "moneyhouse.", "zefix.", "easymonitoring.", "northdata.", "kompass.", "local.ch", "search.ch",
    "yelp.", "glassdoor.", "indeed.", "jobs.", "kununu.", "dnb.com", "zoominfo.", "crunchbase.",
    "bloomberg.", "pitchbook.", "rocketreach.", "apollo.io", "societe.com", "pappers.",
    "infogreffe.", "verif.com", "manageo.", "opencorporates.", "companyhouse.", "firmenwissen.",
    "help.ch", "monetas.", "swissfirms.", "uid.admin.ch", "amazon.", "ebay.", "alibaba.",
    "made-in-china.", "tiktok.", "pinterest.", "google.", "mapcarta.", "yellowpages.",
    "europages.", "datanyze.", "craft.co", "owler.", "cbinsights.", "signalhire.", "lusha.",
    "trustpilot.", "reddit.", "quora.", "medium.com", "github.com", "baidu.", "zhihu.",
    "octopart.", "findchips.", "datasheet", "alldatasheet.", "infobel.", "cylex.",
    "firmania.", "dasoertliche.", "gelbeseiten.", "wlw.de", "b2bhint.", "ensun.",
    "jobup.", "jobs.ch", "jobscout24.", "stepstone.", "monster.", "welcometothejungle.",
    "topjobs.", "jobsuchmaschine.", "jooble.", "careerjet.", "talent.com",
)
# Mots trop courants pour distinguer une entreprise (formes juridiques, pays, mots de secteur)
STOP = {
    "sa", "ag", "gmbh", "ltd", "limited", "inc", "co", "sarl", "sas", "srl", "bv", "the", "and",
    "group", "de", "des", "du", "la", "le", "et", "of", "und", "electronic", "electronics",
    "elektronik", "technology", "technologies", "international", "europe", "schweiz", "suisse",
    "swiss", "switzerland", "systems", "industrie", "components", "company", "france", "china",
    "services", "service", "kg", "ohg", "corp", "corporation",
}
COMPANY_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/company/[^\s?#/]+", re.I)
LANGUE_REGION = {"romande": "fr", "alémanique": "de", "italienne": "it"}
COLONNES_ENRICHIES = ["site", "site_statut", "site_confiance", "linkedin", "linkedin_statut", "linkedin_source",
                      "linkedin_confiance", "a_revoir"]

_lock = threading.Lock()


def normaliser(s: str) -> str:
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def key_tokens(name: str) -> list[str]:
    toks = [t for t in normaliser(name).split() if len(t) >= 3 and t not in STOP]
    return toks or [t for t in normaliser(name).split() if len(t) >= 2]


def domain(url: str) -> str:
    h = urlparse(url).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def canon_lk(url: str) -> str:
    """fr.linkedin.com/company/x/... -> https://www.linkedin.com/company/x/ ; school et showcase laissés tels quels."""
    return linkedin_company(url) or (url or "").split("?")[0].rstrip("/")


def pick_website(name: str, region: str) -> tuple[str, str]:
    toks = key_tokens(name)
    first = []
    # requête exacte, puis libre, puis « official website » tant qu'aucun domaine ne colle au nom
    for q in (f'"{name}"', name, f"{name} official website"):
        cands = [r.get("href", "") for r in recherche_web(q, 10, region)]
        cands = [u for u in cands if u.startswith("http") and not any(b in domain(u) for b in BAD_DOMAINS)]
        first = first or cands
        for u in cands:
            if any(t in normaliser(domain(u)).replace(" ", "") for t in toks):
                return f"https://{urlparse(u).netloc}", "haute"
    if first:
        return f"https://{urlparse(first[0]).netloc}", "basse"
    return "", ""


def pick_linkedin_ddg(name: str, region: str) -> tuple[str, str]:
    toks = key_tokens(name)
    found = []
    for r in recherche_web(f"{name} linkedin company", 10, region):
        m = COMPANY_RE.search(r.get("href", ""))
        if m:
            found.append((canon_lk(m.group(0)), normaliser(r.get("title", ""))))
    for url, title in found:
        slug = normaliser(url.rstrip("/").rsplit("/", 1)[-1]).replace(" ", "")
        if any(t in slug or t in title for t in toks):
            return url, "haute"
    if found:
        return found[0][0], "basse"
    return "", ""


class Caches:
    """Recherches DuckDuckGo par nom et région, pages LinkedIn lues par domaine ; écrits sous verrou."""

    def __init__(self, dossier: Path):
        self.f_recherches = dossier / "enrichir-sites.json"
        self.f_sites = dossier / CACHE_NOM
        self.recherches = self._lire(self.f_recherches)
        self.sites = self._lire(self.f_sites)

    @staticmethod
    def _lire(f: Path) -> dict:
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except json.JSONDecodeError:
            return {}

    def sauver(self) -> None:
        with _lock:
            self.f_recherches.write_text(json.dumps(self.recherches, ensure_ascii=False, indent=1), encoding="utf-8")
            self.f_sites.write_text(json.dumps(self.sites, ensure_ascii=False, indent=0), encoding="utf-8")

    def linkedin_du_site(self, site: str) -> str:
        """Page LinkedIn company lue sur le site (cache par domaine, même format que linkedin_site.py)."""
        d = domaine(site)
        if d not in self.sites:
            try:
                res = find_for_site(site if site.startswith("http") else site_propre(site))   # www gardé
            except Exception as e:  # noqa: BLE001
                res = {"linkedin_company": "", "linkedin_companies_all": "", "linkedin_profiles": "",
                       "reachable": False, "error": str(e)}
            with _lock:
                self.sites[d] = res
        return canon_lk(self.sites[d].get("linkedin_company", ""))


def chercher(nom: str, region: str, site_connu: str, chercher_site: bool, chercher_lk: bool, caches: Caches) -> dict:
    """Site puis LinkedIn d'une entreprise ; les recherches DuckDuckGo passent par le cache."""
    cle = f"{nom}|{region}"
    res = dict(caches.recherches.get(cle, {}))
    reseau = False
    if chercher_site and "site" not in res:
        res["site"], res["site_confiance"] = pick_website(nom, region)
        reseau = True
    site = site_connu or res.get("site", "")
    sur = bool(site_connu) or res.get("site_confiance") == "haute"
    if chercher_lk:
        lk = caches.linkedin_du_site(site) if site and sur else ""
        if lk:
            res.update(linkedin=lk, linkedin_source="site web", linkedin_confiance="haute")
        else:
            if "linkedin_ddg" not in res:
                res["linkedin_ddg"] = list(pick_linkedin_ddg(nom, region))
                reseau = True
            lk, conf = res["linkedin_ddg"]
            res.update(linkedin=lk, linkedin_source="duckduckgo" if lk else "", linkedin_confiance=conf)
    with _lock:
        caches.recherches[cle] = {k: v for k, v in res.items() if k in ("site", "site_confiance", "linkedin_ddg")}
    if reseau:
        time.sleep(random.uniform(0.8, 2.0))
    return res


# ---------------------------------------------------------------- corrections manuelles

def charger_corrections(chemin: Path) -> dict:
    """norm(nom) -> {nom, site, linkedin} depuis corrections.csv (facultatif)."""
    if not chemin.exists():
        return {}
    corr = {}
    for r in lire_csv(chemin):
        r = {k.lower(): v.strip() for k, v in r.items()}
        if norm(r.get("nom", "")):
            corr[norm(r["nom"])] = {"nom": r["nom"], "site": r.get("site", ""), "linkedin": r.get("linkedin", "")}
    return corr


def corriger(l: dict, c: dict, caches: Caches) -> None:
    site = c["site"]
    if site == "-":
        l.update(site="", site_statut="", site_confiance="à vérifier", a_revoir="oui")
    elif site == "?":
        if l.get("site"):
            l["site_confiance"] = "basse"
            l["a_revoir"] = "oui"
    elif site:
        l.update(site=site_propre(site), site_statut="corrigé", site_confiance="haute", a_revoir="non")
    lk = c["linkedin"]
    if lk == "-":
        l.update(linkedin="", linkedin_statut="", linkedin_source="", linkedin_confiance="à vérifier")
    elif lk == "?":
        if l.get("linkedin"):
            l["linkedin_confiance"] = "basse"
    elif lk.lower() == "site":
        page = caches.linkedin_du_site(l["site"]) if l.get("site") else ""
        l.update(linkedin=page, linkedin_statut="corrigé" if page else "introuvable",
                 linkedin_source="site web" if page else "", linkedin_confiance="haute" if page else "à vérifier")
    elif lk:
        l.update(linkedin=canon_lk(lk), linkedin_statut="corrigé", linkedin_source="liste", linkedin_confiance="haute")


# ---------------------------------------------------------------- principal

def region_de(l: dict, pays_defaut: str) -> str:
    pays = code_pays(l.get("pays", "")) or pays_defaut
    langue = LANGUE_REGION.get(l.get("region", ""), "") if pays == "CH" else LANGUES_PAYS.get(pays, "")
    return region_recherche(pays, langue)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Site et page LinkedIn par DuckDuckGo : entreprises.csv -> entreprises-enrichi.csv.")
    argument_campagne(ap)
    ap.add_argument("--workers", type=int, default=4, help="recherches en parallèle (défaut 4)")
    ap.add_argument("--limite", type=int, help="ne chercher que les N premières entreprises (test) ; les autres "
                                               "lignes sont recopiées telles quelles")
    a = ap.parse_args()

    camp = Campagne(a.campagne, config_obligatoire=False)
    entree = camp.fichier("entreprises.csv")
    if not entree.exists():
        raise SystemExit(f"Introuvable : {entree} (étape 2 : consolider_decouverte.py ou importer_liste.py)")
    lignes = lire_csv(entree)
    colonnes = list(dict.fromkeys([*COLONNES_ENTREPRISES, *(lignes[0].keys() if lignes else [])]))
    pays_cible = [code_pays(p) for p in camp.config["cible"].get("pays") or [] if code_pays(p)]
    pays_defaut = pays_cible[0] if pays_cible else ""
    caches = Caches(camp.cache)
    corrections = charger_corrections(camp.fichier("corrections.csv"))

    # entreprises à chercher, dédoublonnées par nom et région
    taches: dict[tuple, dict] = {}
    for l in lignes:
        if (l.get("exclure") or "").strip():
            continue
        besoin_site, besoin_lk = not l.get("site"), not l.get("linkedin")
        nom = (l.get("nom_officiel") or l.get("nom") or "").strip()
        if not nom or not (besoin_site or besoin_lk):
            continue
        cle = (nom, region_de(l, pays_defaut))
        if cle not in taches and a.limite is not None and len(taches) >= a.limite:
            continue
        t = taches.setdefault(cle, {"site": l.get("site", ""), "chercher_site": False, "chercher_lk": False})
        t["chercher_site"] |= besoin_site
        t["chercher_lk"] |= besoin_lk
        t["site"] = t["site"] or l.get("site", "")
        l["_cle"] = cle

    print(f"{len(lignes)} lignes, {len(taches)} entreprises à chercher"
          + (f" (pays par défaut : {pays_defaut})" if pays_defaut else ""))
    resultats = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(chercher, nom, reg, t["site"], t["chercher_site"], t["chercher_lk"], caches): (nom, reg)
                for (nom, reg), t in taches.items()}
        for i, fut in enumerate(as_completed(futs), 1):
            cle = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"  ! {cle[0]} : {e}", file=sys.stderr)
                continue
            resultats[cle] = res
            caches.sauver()
            print(f"[{i}/{len(taches)}] {cle[0]} -> {res.get('site') or taches[cle]['site'] or '-'} | "
                  f"{res.get('linkedin') or '-'}", flush=True)

    # écriture : résultats bruts, puis corrections manuelles
    stats = {"site trouvé": 0, "site introuvable": 0, "LinkedIn trouvé": 0, "LinkedIn introuvable": 0, "corrigées": 0}
    vues = set()
    for l in lignes:
        cle = l.pop("_cle", None)
        res = resultats.get(cle) if cle else None
        if res is not None:
            if not l.get("site") and taches[cle]["chercher_site"]:
                trouve = site_propre(res.get("site", ""))
                l.update(site=trouve, site_statut="trouvé" if trouve else "introuvable",
                         site_confiance=res.get("site_confiance", "") if trouve else "",
                         a_revoir="non" if res.get("site_confiance") == "haute" else "oui")
                stats["site trouvé" if trouve else "site introuvable"] += 1
            if not l.get("linkedin") and taches[cle]["chercher_lk"]:
                lk = res.get("linkedin", "")
                l.update(linkedin=lk, linkedin_statut="trouvé" if lk else "introuvable",
                         linkedin_source=res.get("linkedin_source", "") if lk else "",
                         linkedin_confiance=res.get("linkedin_confiance", "") if lk else "")
                stats["LinkedIn trouvé" if lk else "LinkedIn introuvable"] += 1
        for k in (norm(l.get("nom", "")), norm(l.get("nom_officiel", ""))):
            if k and k in corrections:
                corriger(l, corrections[k], caches)
                vues.add(k)
                stats["corrigées"] += 1
                break
    caches.sauver()   # garde aussi les pages relues pour les corrections « site »
    ecrire_csv(camp.fichier("entreprises-enrichi.csv"), colonnes, lignes)

    conf = lambda champ, v: sum(1 for l in lignes if l.get(champ) and l.get(f"{champ}_confiance") == v)
    print(", ".join(f"{k} {v}" for k, v in stats.items()))
    print(f"total : {sum(1 for l in lignes if l.get('site'))} sites (haute {conf('site', 'haute')}, basse "
          f"{conf('site', 'basse')}), {sum(1 for l in lignes if l.get('linkedin'))} LinkedIn (haute "
          f"{conf('linkedin', 'haute')}, basse {conf('linkedin', 'basse')}) sur {len(lignes)} lignes")
    oubliees = [c["nom"] for k, c in corrections.items() if k not in vues]
    if oubliees:
        print(f"! corrections.csv : {len(oubliees)} noms absents de la liste (ignorés) : {', '.join(oubliees[:20])}")
    print(f"-> {camp.fichier('entreprises-enrichi.csv')} (candidats à vérifier : étape 4)")


if __name__ == "__main__":
    main()
