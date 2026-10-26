"""Étape 8 : ordre d'appel d'une liste de contacts pour le phoning (aucun appel réseau, 0 crédit).

Tri, dans cet ordre :
1. en fin de liste, seulement les personnes qui ont répondu et décliné (étape Apollo « Not Interested » avec une
   réponse) ; les contacts déjà touchés sans réponse gardent leur rang, leur historique est noté (deja_contacte) ;
2. langue : d'abord les personnes qui parlent probablement une langue de l'appelant (appels.langues) ;
3. téléphone déjà connu : mobile ou ligne directe, puis standard de l'entreprise, puis aucun ;
4. tier de l'entreprise (A, B, C, D), puis son rang dans prospection-signaux.csv.

Langue (score, chaque indice est noté dans la colonne indices_langue ; barème rodé avec un appelant francophone en
Suisse, étendu aux autres langues de appels.langues) :
- lieu de la personne : en Suisse, langue officielle de sa commune (répertoire des localités du skill) ; commune
  plurilingue (Biel/Bienne...) ou inconnue : son canton ; +3 si l'appelant parle la langue, +1 pour un canton bi- ou
  trilingue dont il parle une langue, -2 sinon. Ailleurs, langue du pays (commun.LANGUES_PAYS) : +3 parlée ; non
  parlée : -3 en France, Belgique, Luxembourg, Monaco, Allemagne et Autriche, -2 en Italie, -1 dans tout autre pays
  (langue inconnue comprise) ;
- lieu de l'entreprise (export de l'interface Apollo, sinon fiche de l'étape 5) : en Suisse, commune ou canton, +1 si
  la langue est parlée, 0 pour un canton bilingue dont l'appelant parle une langue ou pour une commune plurilingue
  ou romanche, -1 sinon ; ailleurs, +1 ou -1 seulement en France, Belgique, Allemagne, Autriche et Italie, 0 dans
  les autres pays ;
- intitulé de poste en français, en allemand (+2 si l'appelant parle la langue, -2 sinon) ou en italien (+1, -1) ;
- indicatif du mobile, seulement +33, +32, +49, +43, +39 : +1 si l'appelant parle la langue du pays, -1 sinon.
Classe : >= 3 parle la langue (« francophone » pour un appelant francophone), 1 à 2 probablement, 0 incertain,
< 0 autre langue. Sans langue dans appels.langues, pas de tri par langue. La colonne langue_principale donne la
langue la mieux appuyée par les indices, cohérente avec la classe : une langue de l'appelant pour « oui » et
« probable », une autre langue pour « autre langue ».
Facultatif : appels/langue-contacts.json, l'avis d'agents sur la langue de chaque contact ({contact_id: {parle:
oui | probable | incertain | peu probable | non, langue_principale, raison}}) ; s'il existe, il remplace ce classement
automatique (les indices automatiques restent dans indices_langue).

Clé des contacts (colonne contact_id) : l'id Apollo, sinon un id local « local-<entreprise>-<email ou prénom-nom> »
pour un contact importé absent d'Apollo. Les briefs, les cartes et les rédactions des étapes 8 et 9 s'y rattachent.

Entrées, dans le dossier de campagne :
- les contacts : --contacts, sinon l'export de la liste « <apollo.liste_contacts> - entrée » (ou « - relais »)
  fait par exporter_listes.py dans apollo/listes/, sinon apollo/contacts-crees.csv, sinon apollo/contacts-importes.csv ;
- prospection-signaux.csv (étape 5) : tier, rang, pays, canton, fenêtre d'opportunité, pourquoi maintenant, angle ;
- facultatif : --export, l'export CSV de la même liste fait depuis l'interface Apollo (téléphones révélés, étape,
  dernier contact, emails envoyés, ouverts, rebondis, réponses ; en-têtes anglais d'Apollo) ;
  apollo/comptes-apollo.json (standard du compte quand le contact n'a pas de numéro).
Sortie : appels/ordre-appel.csv (appels/ordre-appel-relais.csv avec --liste relais), à relire par scripts_appel.py
et fichier_appel.py.

Ce module sert aussi aux autres scripts des étapes 8 et 9 (chargement des contacts, clé des contacts, jointure à la
fiche de l'entreprise, pays de l'entreprise).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/ordre_appel.py --campagne campagnes/<nom>
      [--liste entree|relais] [--contacts <csv>] [--export <csv>]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import (LANGUES_PAYS, ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne, charger_localites,
                    code_pays, domaine, ecrire_csv, lire_csv, norm)

# libellé de canton (Apollo, LinkedIn) -> code
CANTONS = {"geneva": "GE", "geneve": "GE", "genf": "GE", "vaud": "VD", "waadt": "VD", "neuchatel": "NE",
           "neuenburg": "NE", "jura": "JU", "fribourg": "FR", "freiburg": "FR", "valais": "VS", "wallis": "VS",
           "bern": "BE", "berne": "BE", "zurich": "ZH", "aargau": "AG", "argovie": "AG", "lucerne": "LU",
           "luzern": "LU", "zug": "ZG", "zoug": "ZG", "basel-landschaft": "BL", "basel-stadt": "BS",
           "solothurn": "SO", "soleure": "SO", "thurgau": "TG", "thurgovie": "TG", "schwyz": "SZ",
           "st. gallen": "SG", "st gallen": "SG", "ticino": "TI", "tessin": "TI", "graubunden": "GR",
           "grisons": "GR", "schaffhausen": "SH", "glarus": "GL", "nidwalden": "NW", "obwalden": "OW", "uri": "UR",
           "appenzell": "AR"}
CODES_CANTONS = set(CANTONS.values()) | {"AI"}
# langues officielles d'un canton ; plusieurs : canton bi- ou trilingue, la commune tranche. Autres cantons : allemand.
LANGUES_CANTON = {"GE": ("fr",), "VD": ("fr",), "NE": ("fr",), "JU": ("fr",), "FR": ("fr", "de"),
                  "VS": ("fr", "de"), "BE": ("de", "fr"), "TI": ("it",), "GR": ("de", "rm", "it")}
TITRE_FR = r"\b(directeur|directrice|responsable|president|presidente|administrat\w+|gerant\w*|fondat\w+|associe\w*|chef|cheffe|ingenieur\w*|delegue\w*|proprietaire|dirigeant\w*|direction|general|generale)\b"
TITRE_DE = r"\b(geschaftsfuhr\w*|geschaeftsfuehr\w*|leiter\w*|leitung|inhaber\w*|verwaltungsrat\w*|grunder\w*|vorstand\w*|prokurist\w*|abteilung\w*|bereich\w*|praesident\w*|prasident\w*|mitglied)\b"
TITRE_IT = r"\b(amministrator\w*|direttore|titolare|socio|responsabile|presidente del)\b"
# barème d'origine : pénalité quand la personne vit dans un pays dont l'appelant ne parle pas la langue (pays d'une
# langue nette : 3 ; Italie : 2 ; tout autre pays : 1)
PENALITE_PAYS = {"FR": 3, "BE": 3, "LU": 3, "MC": 3, "DE": 3, "AT": 3, "IT": 2}
# pays voisins dont le lieu de l'entreprise et l'indicatif du mobile comptent (±1) ; ailleurs, 0
PAYS_NOTES = {"FR", "BE", "DE", "AT", "IT"}
# indicatif du mobile -> pays (+41 : la Suisse ne dit rien de la langue)
INDICATIFS = [("+33", "FR"), ("+32", "BE"), ("+49", "DE"), ("+43", "AT"), ("+39", "IT")]
NOMS_LANGUES = {"fr": "français", "de": "allemand", "it": "italien", "rm": "romanche", "en": "anglais",
                "es": "espagnol", "pt": "portugais", "nl": "néerlandais"}
LOCUTEURS = {"fr": "francophone", "de": "germanophone", "it": "italophone", "rm": "romanchophone",
             "en": "anglophone", "es": "hispanophone", "pt": "lusophone", "nl": "néerlandophone"}
# étapes Apollo par défaut (en anglais) : neutres, et refus
ETAPES_NEUTRES = ("", "Cold", "Approaching")
ETAPE_REFUS = "Not Interested"
RANG_TIER = {"A": 0, "B": 1, "C": 2, "D": 3}
PREFIXE_LOCAL = "local-"           # id local d'un contact absent d'Apollo

COLONNES = ["priorite", "langue", "parle_langue_appel", "langue_principale", "avis_langue", "score_langue",
            "indices_langue", "telephone", "type_telephone", "tier", "rang_entreprise", "fenetre_opportunite",
            "entreprise", "entreprise_id", "pays_entreprise", "prenom", "nom", "titre", "email", "statut_email",
            "linkedin", "ville", "pays", "deja_contacte", "a_eviter", "pourquoi_maintenant", "angle", "ordre",
            "cibles", "contact_id"]


# ---------------------------------------------------------------- outils partagés (étapes 8 et 9)

def plat(s: str) -> str:
    """Minuscules sans accents, ponctuation réduite (intitulés, libellés de canton)."""
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 /.-]", " ", s)).strip()


def slug_liste(nom: str) -> str:
    """Nom de fichier d'une liste Apollo exportée (même règle qu'exporter_listes.py) : « A · B - entrée » -> a-b-entree."""
    s = unicodedata.normalize("NFD", nom or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def ordre_normalise(v: str) -> str:
    v = plat(v)
    return ORDRE_ENTREE if v.startswith("entree") else ORDRE_RELAIS if v.startswith("relais") else ""


def fichier_liste(camp: Campagne, ordre: str) -> Path | None:
    """Export de la liste « <apollo.liste_contacts> - entrée » (ou « - relais ») dans apollo/listes/, s'il existe."""
    dossier = camp.dossier / "apollo" / "listes"
    nom = (camp.config["apollo"].get("liste_contacts") or "").strip()
    if nom and (dossier / f"{slug_liste(f'{nom} - {ordre}')}.csv").exists():
        return dossier / f"{slug_liste(f'{nom} - {ordre}')}.csv"
    autres = sorted(dossier.glob(f"*-{slug_liste(ordre)}.csv"), key=lambda p: p.stat().st_mtime) if dossier.is_dir() else []
    return autres[-1] if autres else None


ALIAS = {
    "contact_id": ("contact_id", "Apollo Contact Id", "apollo_contact_id"),
    "prenom": ("prenom", "First Name"), "nom": ("nom", "Last Name"), "titre": ("titre", "Title"),
    "email": ("email", "Email"), "statut_email": ("statut_email", "Email Status"),
    "linkedin": ("linkedin", "Person Linkedin Url"), "ville": ("ville", "City"), "pays": ("pays", "Country"),
    "entreprise": ("entreprise", "Company Name", "Company"), "entreprise_id": ("entreprise_id",),
    "site_entreprise": ("site_entreprise", "Website", "Company Website"), "tier": ("tier",), "ordre": ("ordre",),
    "cibles": ("cibles",), "seniorite": ("seniorite", "Seniority"), "statut": ("statut",),
    "mobile": ("mobile", "Mobile Phone"), "telephone_direct": ("telephone_direct", "Work Direct Phone"),
    "telephone_standard": ("telephone_standard", "Corporate Phone", "Company Phone"),
    "stage": ("stage", "Stage"), "dernier_contact": ("dernier_contact", "Last Contacted"),
}


def contact_normalise(r: dict) -> dict:
    """Ligne de contacts (contrat de l'étape 6, export de liste ou export de l'interface Apollo) -> noms du contrat."""
    c = {k: next((r[a].strip() for a in alias if (r.get(a) or "").strip()), "") for k, alias in ALIAS.items()}
    for k in ("mobile", "telephone_direct", "telephone_standard"):
        c[k] = c[k].lstrip("'").strip()
    c["pays"] = code_pays(c["pays"]) or c["pays"]
    c["statut_email"] = c["statut_email"].lower()
    c["ordre"] = ordre_normalise(c["ordre"])
    return c


def cle_contact(c: dict) -> str:
    """Clé stable d'un contact : son id Apollo, sinon un id local tiré de l'entreprise et de l'email (ou du prénom et
    du nom), pour un contact importé absent d'Apollo. Jamais vide : sans elle, tous les contacts sans id partageraient
    leurs briefs, cartes et rédactions."""
    cid = (c.get("contact_id") or c.get("apollo_contact_id") or c.get("Apollo Contact Id") or "").strip()
    if cid:
        return cid
    qui = (c.get("email") or "").strip().lower() or f"{c.get('prenom', '')} {c.get('nom', '')}"
    return f"{PREFIXE_LOCAL}{slug_liste(c.get('entreprise', '')) or 'entreprise'}-{slug_liste(qui) or 'contact'}"


def id_apollo(cle: str) -> str:
    """L'id Apollo d'une clé de contact ; vide pour un id local."""
    return "" if (cle or "").startswith(PREFIXE_LOCAL) else (cle or "")


def charger_contacts(camp: Campagne, chemin: str | None = None, ordre: str | None = None) -> tuple[list[dict], Path]:
    """Contacts d'une campagne, normalisés ; avec ordre, seulement l'entrée ou le relais. Sans colonne ordre remplie
    (liste importée), tous les contacts comptent comme entrée."""
    if chemin:
        p = Path(chemin)
        if not p.exists():
            raise SystemExit(f"Fichier de contacts introuvable : {p}")
    else:
        candidats = ([fichier_liste(camp, ordre)] if ordre else []) + [
            camp.dossier / "apollo" / "contacts-crees.csv", camp.dossier / "apollo" / "contacts-importes.csv"]
        p = next((x for x in candidats if x and x.exists()), None)
        if not p:
            raise SystemExit(f"Aucun fichier de contacts dans {camp.dossier / 'apollo'} : faire l'étape 6 "
                             "(contacts-crees.csv), exporter les listes (exporter_listes.py) ou passer --contacts.")
    lignes = [contact_normalise(r) for r in lire_csv(p)]
    if not any(c["ordre"] for c in lignes):
        for c in lignes:
            c["ordre"] = ORDRE_ENTREE
    if ordre:
        lignes = [c for c in lignes if c["ordre"] == ordre]
    return lignes, p


class Index:
    """Jointure d'un contact à une ligne d'entreprise : id (entreprise_id), sinon nom normalisé, sinon domaine."""

    def __init__(self, lignes: list[dict], cle_site: str = "site"):
        self.lignes = lignes
        self.par_id = {r["id"]: r for r in lignes if r.get("id")}
        self.par_nom = {norm(r.get("nom", "")): r for r in lignes if norm(r.get("nom", ""))}
        self.par_dom = {domaine(r.get(cle_site, "")): r for r in lignes if domaine(r.get(cle_site, ""))}

    def de(self, c: dict) -> dict:
        return (self.par_id.get(c.get("entreprise_id") or "") or self.par_nom.get(norm(c.get("entreprise", "")))
                or self.par_dom.get(domaine(c.get("site_entreprise", ""))) or {})


def charger_fiches(camp: Campagne, obligatoire: bool = False) -> Index:
    """prospection-signaux.csv (étape 5), indexé pour la jointure des contacts."""
    p = camp.fichier("prospection-signaux.csv")
    if not p.exists():
        if obligatoire:
            raise SystemExit(f"{p} absent : faire l'étape 5 (scorer.py).")
        print(f"! {p.name} absent : tier, rang et pays de l'entreprise viendront des contacts seulement")
        return Index([])
    return Index(lire_csv(p))


def pays_entreprise(fiche: dict, contact: dict | None = None) -> str:
    """Code pays de l'entreprise : fiche de l'étape 5, sinon pays du contact. Seule source du pays pour les
    scripts et le fichier d'appel."""
    return code_pays(fiche.get("pays", "")) or code_pays((contact or {}).get("pays", ""))


def lire_json(chemin: Path, defaut=None):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaut
    except json.JSONDecodeError as e:
        raise SystemExit(f"{chemin} : JSON invalide ({e}).")


# ---------------------------------------------------------------- langue

def canton_de(etat: str) -> str:
    e = plat(re.sub(r"(?i)canton (of|de|du) ", "", etat or ""))
    return e.upper() if e.upper() in CODES_CANTONS else CANTONS.get(e, "")


def lieu(pays: str, ville: str, etat: str, loc: dict, canton_fiche: str = "") -> tuple[tuple, str, str]:
    """(langues du lieu, lieu dit avec sa préposition, niveau) : commune suisse, sinon canton, sinon pays. Une commune
    plurilingue (langue « multiple » du répertoire) ou sans langue passe la main à son canton."""
    if pays == "CH":
        canton, plurilingue = "", ""
        if ville:
            v = loc.get(norm(ville)) or loc.get(norm(re.split(r"[/(]", ville)[0]))
            if v and v[1] in NOMS_LANGUES:
                return (v[1],), f"à {ville}", "commune"
            if v:
                canton, plurilingue = (v[0] or "").upper(), ville
        canton = canton or canton_de(etat) or (canton_fiche or "").upper()[:2]
        if canton in CODES_CANTONS:
            if plurilingue:
                return LANGUES_CANTON.get(canton, ("de",)), f"à {plurilingue}, commune plurilingue du canton {canton}", \
                    "plurilingue"
            return LANGUES_CANTON.get(canton, ("de",)), f"dans le canton {canton}", "canton"
        return (), "", ""
    if not pays:
        return (), "", ""
    l = LANGUES_PAYS.get(pays)
    return ((l,), f"en {pays}", "pays") if l else ((), f"en {pays}", "pays")


def points_personne(langues: tuple, niveau: str, pays: str, parle: set) -> int:
    """Lieu de la personne : commune ou canton suisse +3 / +1 (canton plurilingue) / -2 ; pays +3, ou -3, -2, -1."""
    if niveau == "pays":
        if langues and langues[0] in parle:
            return 3
        return -PENALITE_PAYS.get(pays, 1)              # langue inconnue comprise
    if not langues:
        return 0
    if len(langues) > 1:
        return 1 if parle & set(langues) else -2
    return 3 if langues[0] in parle else -2


def points_entreprise(langues: tuple, niveau: str, pays: str, parle: set) -> int:
    """Lieu de l'entreprise : Suisse +1 / 0 (canton plurilingue dont une langue est parlée) / -1 ; ailleurs ±1
    seulement dans les pays voisins notés (PAYS_NOTES). Une commune plurilingue ou romanche ne compte pas."""
    if not langues or (niveau == "pays" and pays not in PAYS_NOTES) or niveau == "plurilingue" \
            or (niveau == "commune" and langues == ("rm",)):
        return 0
    if len(langues) > 1:
        return 0 if parle & set(langues) else -1
    return 1 if langues[0] in parle else -1


def evaluer_langue(c: dict, ui: dict, fiche: dict, loc: dict, parle: set,
                   ville_entreprise: str = "") -> tuple[int, dict, str]:
    """(points, poids des langues, indices) d'un contact. Le poids d'une langue additionne la force des indices qui la
    désignent (1 par langue pour un lieu plurilingue)."""
    pts, indices, poids = 0, [], {}

    def noter(langues: tuple, p: int) -> None:
        for l in langues:
            poids[l] = poids.get(l, 0) + (max(abs(p), 1) if len(langues) == 1 else 1)

    # 1. lieu de la personne
    pays = code_pays(ui.get("Country", "")) or c.get("pays", "")
    langues, txt, niveau = lieu(pays, ui.get("City") or c.get("ville", ""), ui.get("State", ""), loc)
    if txt:
        p = points_personne(langues, niveau, pays, parle)
        pts += p
        noter(langues, p)
        indices.append(f"vit {txt} ({'/'.join(NOMS_LANGUES.get(l, l) for l in langues) or 'langue inconnue'})")
    # 2. lieu de l'entreprise (export de l'interface, sinon fiche de l'étape 5)
    cpays = code_pays(ui.get("Company Country", "")) or code_pays(fiche.get("pays", ""))
    cville = ui.get("Company City", "") or ville_entreprise
    langues, txt, niveau = lieu(cpays, cville, ui.get("Company State", ""), loc, fiche.get("canton", ""))
    p = points_entreprise(langues, niveau, cpays, parle)
    if p:
        pts += p
        noter(langues, p)
        indices.append(f"entreprise {txt} ({'/'.join(NOMS_LANGUES.get(l, l) for l in langues)})")
    # 3. langue de l'intitulé
    t = plat(ui.get("Title") or c.get("titre", ""))
    lt = ("fr", 2) if re.search(TITRE_FR, t) and not re.search(TITRE_DE, t) else ("de", 2) if re.search(TITRE_DE, t) \
        else ("it", 1) if re.search(TITRE_IT, t) else None
    if lt:
        p = lt[1] if lt[0] in parle else -lt[1]
        pts += p
        noter((lt[0],), p)
        indices.append(f"intitulé en {NOMS_LANGUES[lt[0]]}")
    # 4. indicatif du mobile
    mob = re.sub(r"[^\d+]", "", (ui.get("Mobile Phone") or c.get("mobile", "")).lstrip("'"))
    pm = next((p for ind, p in INDICATIFS if mob.startswith(ind)), "")
    if pm:
        p = 1 if LANGUES_PAYS[pm] in parle else -1
        pts += p
        noter((LANGUES_PAYS[pm],), p)
        indices.append(f"mobile {pm}")
    return pts, poids, " ; ".join(indices)


def langue_retenue(classe: str, poids: dict, parle: set) -> str:
    """Langue la plus probable, cohérente avec la classe : pour « oui » et « probable », la langue de l'appelant la
    mieux appuyée ; pour « non », l'autre langue la mieux appuyée ; sinon, la mieux appuyée de toutes."""
    if classe in ("oui", "probable"):
        cands = {l: p for l, p in poids.items() if l in parle}
    elif classe == "non":
        cands = {l: p for l, p in poids.items() if l not in parle}
    else:
        cands = poids
    return max(cands, key=cands.get) if cands else ""


def score_langue(c: dict, ui: dict, fiche: dict, loc: dict, parle: set, ville_entreprise: str = "") -> tuple[int, str, str]:
    """(points, langue la plus probable, indices) d'un contact."""
    pts, poids, indices = evaluer_langue(c, ui, fiche, loc, parle, ville_entreprise)
    return pts, langue_retenue(classe_langue(pts) if parle else "", poids, parle), indices


def classe_langue(pts: int) -> str:
    return "oui" if pts >= 3 else "probable" if pts >= 1 else "incertain" if pts == 0 else "non"


def libelle_langue(classe: str, langues: list[str]) -> str:
    loc = " ou ".join(LOCUTEURS.get(l, l) for l in langues) or "?"
    return {"oui": loc, "probable": f"probablement {loc}", "incertain": "incertain", "non": "autre langue",
            "": "non classé"}[classe]


# ---------------------------------------------------------------- historique et téléphone

def historique(ui: dict, c: dict) -> str:
    """Ce qu'Apollo sait des contacts passés : email envoyé, ouvert, rebondi, réponse, étape."""
    if ui:
        envoye = (ui.get("Email Sent") or "").lower() == "true"
        if not ui.get("Last Contacted") and not envoye:
            return ""
        d = (ui.get("Last Contacted") or "")[:10]
        d = f"{d[8:10]}.{d[5:7]}.{d[:4]}" if d else "date inconnue"
        if not envoye:
            h = f"contacté le {d} (hors email Apollo), sans suite"
        elif (ui.get("Email Bounced") or "").lower() == "true":
            h = f"email du {d} revenu en erreur (adresse invalide) : jamais reçu"
        elif (ui.get("Replied") or "").lower() == "true":
            h = f"email du {d} : a répondu"
        elif (ui.get("Email Open") or "").lower() == "true":
            h = f"email du {d} ouvert, sans réponse"
        else:
            h = f"email du {d} jamais ouvert, sans réponse"
        stage = ui.get("Stage") or ""
        return h + (f" ; étape Apollo « {stage} »" if stage not in ETAPES_NEUTRES else "")
    # sans export : colonnes de la liste (dernier contact, étape) et statut de l'étape 6
    bits = []
    if c.get("dernier_contact"):
        d = c["dernier_contact"][:10]
        bits.append(f"contacté le {d[8:10]}.{d[5:7]}.{d[:4]}" if re.match(r"\d{4}-\d\d-\d\d", d) else f"contacté : {d}")
    if c.get("stage") and c["stage"] not in ETAPES_NEUTRES:
        bits.append(f"étape Apollo « {c['stage']} »")
    if not bits and "deja" in plat(c.get("statut", "")):
        bits.append("déjà dans Apollo avant la campagne : vérifier son historique")
    return " ; ".join(bits)


def telephone(ui: dict, c: dict, compte: dict) -> tuple[str, str]:
    for col, k, typ in (("Mobile Phone", "mobile", "mobile"), ("Work Direct Phone", "telephone_direct", "ligne directe"),
                        ("Corporate Phone", "", "standard"), ("Company Phone", "telephone_standard", "standard")):
        v = (ui.get(col) or (c.get(k) if k else "") or "").lstrip("'").strip()
        if v:
            return v, typ
    v = (compte.get("sanitized_phone") or compte.get("phone") or "").strip()
    return (v, "standard") if v else ("", "aucun")


def comptes_apollo(camp: Campagne) -> tuple[dict, dict]:
    """apollo/comptes-apollo.json (facultatif) : par domaine et par nom normalisé."""
    par_dom, par_nom = {}, {}
    for a in lire_json(camp.dossier / "apollo" / "comptes-apollo.json", []) or []:
        if not isinstance(a, dict):
            continue
        par_nom[norm(a.get("name") or "")] = a
        for d in (a.get("domain"), a.get("primary_domain"), domaine(a.get("website_url") or "")):
            if d:
                par_dom[d] = a
    return par_dom, par_nom


# ---------------------------------------------------------------- programme

def main() -> None:
    ap = argparse.ArgumentParser(description="Ordre d'appel d'une liste de contacts (étape 8, aucun appel réseau).")
    argument_campagne(ap)
    ap.add_argument("--liste", choices=["entree", "relais"], default="entree",
                    help="liste à ordonner : entrée (défaut) ou relais")
    ap.add_argument("--contacts", help="CSV de contacts (défaut : export de la liste, sinon apollo/contacts-crees.csv)")
    ap.add_argument("--export", help="facultatif : export CSV de la liste fait depuis l'interface Apollo")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    ordre = ORDRE_ENTREE if a.liste == "entree" else ORDRE_RELAIS
    contacts, source = charger_contacts(camp, a.contacts, ordre)
    if not contacts:
        raise SystemExit(f"Aucun contact « {ordre} » dans {source}.")
    ui_par_id = {}
    if a.export:
        ui_par_id = {r.get("Apollo Contact Id", ""): r for r in lire_csv(a.export) if r.get("Apollo Contact Id")}
    fiches = charger_fiches(camp)
    entites = {e.get("id"): e for e in lire_json(camp.dossier / "donnees" / "signaux" / "entites.json", []) or []
               if isinstance(e, dict)}
    par_dom, par_nom = comptes_apollo(camp)
    langues = [l.strip().lower() for l in camp.config["appels"].get("langues") or [] if l.strip()]
    parle = set(langues)
    besoin_loc = any(c.get("pays") in ("CH", "") for c in contacts) or any(r.get("pays") == "CH" for r in fiches.lignes)
    loc = charger_localites() if besoin_loc else {}
    avis = lire_json(camp.appels / "langue-contacts.json", {}) or {}
    classe_avis = {"oui": "oui", "probable": "probable", "incertain": "incertain", "peu probable": "non", "non": "non"}
    rang_classe = {"oui": 0, "probable": 1, "incertain": 2, "non": 3, "": 0}
    rang_tel = {"mobile": 0, "ligne directe": 0, "standard": 1, "aucun": 2}

    out, vues = [], Counter()
    for c in contacts:
        cle = cle_contact(c)
        vues[cle] += 1
        if cle.startswith(PREFIXE_LOCAL) and vues[cle] > 1:   # deux contacts locaux sans email ni nom distincts
            cle = f"{cle}-{vues[cle]}"
        ui = ui_par_id.get(c["contact_id"], {})
        fiche = fiches.de(c)
        compte = par_dom.get(domaine(fiche.get("site") or c.get("site_entreprise", ""))) or par_nom.get(norm(c["entreprise"])) or {}
        ville_ent = (entites.get(fiche.get("id")) or {}).get("ville", "")
        pts, poids, indices = evaluer_langue(c, ui, fiche, loc, parle, ville_ent)
        classe = classe_langue(pts) if parle else ""
        av = avis.get(cle) or {}
        if av:
            classe = classe_avis.get(plat(av.get("parle") or av.get("parle_francais") or ""), classe)
        probable = langue_retenue(classe, poids, parle)
        tel, typ = telephone(ui, c, compte)
        tier = c.get("tier") or fiche.get("tier") or "?"
        stage = ui.get("Stage") or c.get("stage") or ""
        # écarté seulement si la personne a répondu et décliné (un refus sans réponse ne compte pas)
        exclu = stage == ETAPE_REFUS and (ui.get("Replied") or "").lower() == "true"
        rang = fiche.get("rang") or ""
        out.append({
            "_cle": (exclu, rang_classe[classe], rang_tel[typ], RANG_TIER.get(tier, 9),
                     int(rang) if rang.isdigit() else 999, -pts),
            "langue": libelle_langue(classe, langues), "parle_langue_appel": classe,
            "langue_principale": av.get("langue_principale") or probable,
            "avis_langue": (av.get("raison") or "")[:300], "score_langue": pts, "indices_langue": indices,
            "telephone": tel, "type_telephone": typ, "tier": tier, "rang_entreprise": rang,
            "fenetre_opportunite": fiche.get("fenetre_opportunite", ""),
            "entreprise": c["entreprise"] or fiche.get("nom", ""), "entreprise_id": c["entreprise_id"] or fiche.get("id", ""),
            "pays_entreprise": pays_entreprise(fiche, c), "prenom": c["prenom"], "nom": c["nom"], "titre": c["titre"],
            "email": c["email"], "statut_email": c["statut_email"], "linkedin": c["linkedin"], "ville": c["ville"],
            "pays": c["pays"], "deja_contacte": historique(ui, c),
            "a_eviter": f"{ETAPE_REFUS} dans Apollo, avec réponse" if exclu else "",
            "pourquoi_maintenant": fiche.get("pourquoi_maintenant", ""), "angle": fiche.get("angle", ""),
            "ordre": c["ordre"], "cibles": c["cibles"], "contact_id": cle})
    out.sort(key=lambda x: x["_cle"])
    for i, x in enumerate(out, 1):
        x["priorite"] = i
    dest = camp.appels / ("ordre-appel.csv" if ordre == ORDRE_ENTREE else "ordre-appel-relais.csv")
    ecrire_csv(dest, COLONNES, out)

    sans_fiche = sum(1 for x in out if not x["rang_entreprise"])
    print(f"{len(out)} contacts « {ordre} » (source : {source.name}) -> {dest}")
    if not parle:
        print("! appels.langues est vide : pas de tri par langue")
    else:
        print("langue :", Counter(x["langue"] for x in out).most_common())
        print("langue x téléphone :", Counter((x["parle_langue_appel"], x["type_telephone"]) for x in out).most_common())
        print("tiers de ceux qui parlent une langue de l'appelant (sûrs et probables) :",
              Counter(x["tier"] for x in out if x["parle_langue_appel"] in ("oui", "probable")).most_common())
    print("déjà contactés :", sum(1 for x in out if x["deja_contacte"]), "| à éviter :", sum(1 for x in out if x["a_eviter"]),
          "| sans numéro :", sum(1 for x in out if x["type_telephone"] == "aucun"))
    if sans_fiche:
        print(f"! {sans_fiche} contact(s) sans fiche dans prospection-signaux.csv (entreprise_id, nom ou site à vérifier)")
    locaux = sum(1 for x in out if x["contact_id"].startswith(PREFIXE_LOCAL))
    if locaux:
        print(f"! {locaux} contact(s) absent(s) d'Apollo : id local « {PREFIXE_LOCAL}... » dans contact_id (à créer dans "
              "Apollo pour les séquences)")
    if not a.export:
        print("  (sans --export : téléphones, étape et historique viennent seulement de la liste de contacts)")


if __name__ == "__main__":
    main()
