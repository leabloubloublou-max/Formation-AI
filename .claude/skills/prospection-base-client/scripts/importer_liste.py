"""Étape 2, liste existante : met une liste d'entreprises au contrat (entreprises.csv), avec une version lisible.

Lit un export Apollo (comptes ou contacts) ou toute liste CSV qui a une colonne de nom d'entreprise (exposants d'un
salon, annuaire, scraping). Typiquement : filtres Apollo (zone, effectif, secteur, technologies, fonction et
séniorité, entreprises qui recrutent), puis export CSV des comptes ou des contacts depuis l'interface.

Entrées : un ou plusieurs CSV (virgule ou point-virgule). Colonnes reconnues sans tenir compte de la casse (export
Apollo d'abord, puis noms usuels) : Company Name, Website, Company Linkedin Url, Company City, Company Country,
# Employees, Industry, Short Description, Keywords, Technologies, Apollo Account Id ; pour un export de contacts,
en plus : First Name, Last Name, Title, Seniority, Email, Email Status, Person Linkedin Url, City, Country,
Apollo Contact Id, Stage, Last Contacted.
Options : --exclure <csv> (répétable ; défaut <campagne>/exclure.csv s'il existe) : nos clients et partenaires
actuels, retirés de la liste ; --deja <csv> (répétable) : nos listes existantes, marquées « déjà connue » ;
--col-nom : en-tête du nom d'entreprise s'il n'est pas reconnu ; --ajouter : garder les fichiers existants et n'y
ajouter que les entreprises et les contacts nouveaux (pour combiner avec une découverte web ou un autre export) ; une
entreprise déjà écartée dans entreprises-toutes.csv et retenue cette fois y est marquée « ajoutée par », une
entreprise déjà exclue comme client ou partenaire actuel le reste.
Sorties, dans le dossier de la campagne :
- entreprises-toutes.csv : une ligne par entreprise (dédoublonnée par domaine puis par nom) avec son statut
  (retenue, exclue, déjà connue) : à relire ;
- entreprises.csv : les entreprises retenues, au contrat (commun.COLONNES_ENTREPRISES, puis compte_apollo et
  n_contacts). Site et LinkedIn de la liste, à contrôler par échantillon ; étape 3 si la liste n'a pas de sites ;
- s'il y a des contacts : apollo/contacts-importes.csv (commun.COLONNES_CONTACTS, puis site_entreprise, stage,
  dernier_contact). ordre = entrée si l'intitulé relève de la famille d'entrée de [persona] dans campagne.toml
  (persona.py, mêmes familles qu'à l'étape 6 ; par défaut la direction, plus la séniorité Apollo owner, founder ou
  partner), relais sinon : à relire. tier, entreprise_id et cibles restent vides (étapes 5 et 6). Avec --ajouter,
  les contacts déjà présents (même id Apollo, même email ou même nom dans la même entreprise) sont gardés tels quels.
  Sans --ajouter et sans contact dans l'import, un ancien contacts-importes.csv est renommé en
  contacts-importes.precedent.csv : il ne correspond plus à entreprises.csv.
Sans réseau ni LLM.

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/importer_liste.py \\
      --campagne campagnes/<nom> <export1.csv> [<export2.csv> ...] [--exclure <csv>]... [--deja <liste.csv>]...
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import (COLONNES_CONTACTS, COLONNES_ENTREPRISES, ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne,
                    charger_localites, charger_noms, code_pays, domaine, ecrire_csv, linkedin_company, lire_csv, norm,
                    region, site_propre)
from consolider_decouverte import (MOTIF_CLIENT, avertir_listes_suivantes, clients_deja_exclus,
                                   ecarter_contacts_importes, fusionner, verifier_fichiers)
from persona import Persona

# champ -> en-têtes reconnus (en minuscules), par ordre de préférence
COLONNES = {
    "nom": ["company name", "company", "account name", "entreprise", "raison sociale", "nom", "name"],
    "site": ["website", "company website", "site", "site web", "site internet", "site_internet", "domaine", "domain"],
    "linkedin": ["company linkedin url", "linkedin", "linkedin_company", "page linkedin"],
    "ville": ["company city", "ville", "localité", "city"],
    "pays": ["company country", "pays", "country"],
    "taille": ["# employees", "employees", "taille", "effectif"],
    "secteur": ["industry", "secteur"],
    "description": ["short description", "description", "activite", "activité"],
    "mots_cles": ["keywords"],
    "technologies": ["technologies"],
    "compte_apollo": ["apollo account id"],
    "prenom": ["first name", "prénom", "prenom"],
    "nom_personne": ["last name", "nom de famille"],
    "titre": ["title", "poste", "titre"],
    "seniorite": ["seniority"],
    "email": ["email", "e-mail"],
    "statut_email": ["email status"],
    "linkedin_personne": ["person linkedin url"],
    "ville_personne": ["city"],
    "pays_personne": ["country"],
    "contact_id": ["apollo contact id", "contact_id"],
    "stage": ["stage"],
    "dernier_contact": ["last contacted"],
}
COLONNES_TOUTES = ["nom", "autres_noms", "pays", "pays_source", "ville", "canton", "region", "site", "linkedin",
                   "secteur", "taille", "activite", "technologies", "compte_apollo", "n_contacts", "fichiers",
                   "deja_connue", "exclure", "statut"]
COLONNES_LISTE = COLONNES_ENTREPRISES + ["compte_apollo", "n_contacts"]
COLONNES_CONTACTS_IMPORTES = COLONNES_CONTACTS + ["site_entreprise", "stage", "dernier_contact"]

# séniorité Apollo qui suffit pour la direction ; c_suite seul ne suffit pas : CFO, CTO, COO vont en relais
SENIORITE_DIRIGEANT = {"owner", "founder", "partner"}


def regle_entree(config: dict):
    """Fonction (séniorité, intitulé) -> ordre : entrée si l'intitulé relève de la famille d'entrée de [persona]
    (persona.py, familles fournies complétées par [persona.titres]), ou pour la direction si la séniorité Apollo
    est owner, founder ou partner ; relais sinon."""
    p = Persona(config)   # une famille inconnue dans [persona] arrête le script avec un message clair

    def ordre(seniorite: str, titre: str) -> str:
        s = (seniorite or "").strip().lower().replace(" ", "_")      # API : c_suite ; export de l'interface : C suite
        entree = p.entree in p.familles_titre(titre or "") or (p.entree == "direction" and s in SENIORITE_DIRIGEANT)
        return ORDRE_ENTREE if entree else ORDRE_RELAIS
    return ordre


def lire(fichier: str, col_nom: str | None) -> tuple[list[dict], dict]:
    """Lignes du CSV et correspondance champ -> en-tête trouvé."""
    lignes = lire_csv(fichier)
    entetes = {k.lower(): k for k in (lignes[0].keys() if lignes else [])}
    champs = {}
    for champ, noms in COLONNES.items():
        for n in noms:
            if n in entetes:
                champs[champ] = entetes[n]
                break
    if col_nom:
        if lignes and col_nom.strip().lower() not in entetes:
            raise SystemExit(f"{fichier} : colonne « {col_nom} » absente (en-têtes : {', '.join(entetes.values())})")
        champs["nom"] = entetes.get(col_nom.strip().lower(), col_nom)
    if lignes and "nom" not in champs:
        raise SystemExit(f"{fichier} : colonne du nom d'entreprise introuvable (option --col-nom)")
    return lignes, champs


def cles_contact(c: dict) -> set[str]:
    """Clés d'un contact, comme au dédoublonnage de la lecture : id Apollo, email en minuscules, nom normalisé avec
    l'entreprise (les clés vides sont ignorées)."""
    cles = {(c.get("contact_id") or "").strip(), (c.get("email") or "").strip().lower()}
    if (c.get("prenom") or "").strip() or (c.get("nom") or "").strip():
        cles.add(norm(f"{c.get('prenom', '')} {c.get('nom', '')} {c.get('entreprise', '')}"))
    return cles - {""}


def fusionner_contacts(chemin: Path, nouveaux: list[dict]) -> tuple[list[dict], list[str], int]:
    """--ajouter : contacts existants de chemin (inchangés), puis les nouveaux qui n'y sont pas (même id Apollo, même
    email ou même nom dans la même entreprise). Rend (contacts, colonnes, nombre de nouveaux déjà présents)."""
    if not chemin.exists():
        return nouveaux, COLONNES_CONTACTS_IMPORTES, 0
    anciens = lire_csv(chemin)
    connues = set().union(*(cles_contact(c) for c in anciens))
    ajout = [c for c in nouveaux if not (cles_contact(c) & connues)]
    cols = list(dict.fromkeys([*COLONNES_CONTACTS_IMPORTES, *(anciens[0].keys() if anciens else [])]))
    return anciens + ajout, cols, len(nouveaux) - len(ajout)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Met un export Apollo ou une liste CSV au contrat : entreprises-toutes.csv et entreprises.csv.")
    argument_campagne(ap)
    ap.add_argument("fichiers", nargs="+", help="export Apollo (comptes ou contacts) ou liste CSV")
    ap.add_argument("--exclure", action="append", default=None,
                    help="nos clients et partenaires actuels (CSV), répétable ; défaut <campagne>/exclure.csv s'il existe")
    ap.add_argument("--deja", action="append", default=[], help="liste existante à reconnaître (CSV), répétable")
    ap.add_argument("--col-nom", help="en-tête de la colonne du nom d'entreprise, s'il n'est pas reconnu")
    ap.add_argument("--ajouter", action="store_true", help="ajouter aux fichiers existants au lieu de les remplacer")
    a = ap.parse_args()
    verifier_fichiers([*a.fichiers, *(a.exclure or []), *a.deja])

    camp = Campagne(a.campagne, config_obligatoire=False)
    if a.exclure is None:
        a.exclure = [str(camp.fichier("exclure.csv"))] if camp.fichier("exclure.csv").exists() else []
    for f in a.exclure:
        print(f"lu : {f}")
    ordre = regle_entree(camp.config)
    loc = charger_localites()
    excl_noms, excl_doms = charger_noms(a.exclure)
    deja_noms, deja_doms = charger_noms(a.deja)
    if a.ajouter:
        avant_noms, avant_doms = clients_deja_exclus(camp.fichier("entreprises-toutes.csv"))
        excl_noms, excl_doms = excl_noms | avant_noms, excl_doms | avant_doms
        if avant_noms:
            print(f"lu : {camp.fichier('entreprises-toutes.csv')} ({len(avant_noms)} clients ou partenaires "
                  "déjà exclus, qui le restent)")

    E, par_dom, personnes = {}, {}, {}
    for f in a.fichiers:
        donnees, ch = lire(f, a.col_nom)
        if not donnees:
            print(f"! {f} : aucune ligne")
            continue
        g = lambda r, champ: (r.get(ch[champ]) or "").strip() if champ in ch else ""
        for r in donnees:
            nom = g(r, "nom")
            k, d = norm(nom), domaine(g(r, "site"))
            if not k:
                continue
            if d and d in par_dom:
                k = par_dom[d]
            e = E.setdefault(k, {"noms": Counter(), "champs": {}, "fichiers": set(), "n_contacts": 0})
            if d and d not in par_dom:
                par_dom[d] = k
            e["noms"][nom] += 1
            e["fichiers"].add(Path(f).name)
            for champ in ("site", "linkedin", "ville", "pays", "taille", "secteur", "description", "mots_cles",
                          "technologies", "compte_apollo"):
                if g(r, champ) and not e["champs"].get(champ):
                    e["champs"][champ] = g(r, champ)
            if g(r, "prenom") or g(r, "nom_personne"):
                cle = g(r, "contact_id") or g(r, "email").lower() or norm(f"{g(r, 'prenom')} {g(r, 'nom_personne')} {nom}")
                if cle not in personnes:
                    e["n_contacts"] += 1
                    personnes[cle] = {
                        "_k": k, "ordre": ordre(g(r, "seniorite"), g(r, "titre")), "prenom": g(r, "prenom"),
                        "nom": g(r, "nom_personne"), "titre": g(r, "titre"), "seniorite": g(r, "seniorite"),
                        "email": g(r, "email"), "statut_email": g(r, "statut_email").lower(),
                        "linkedin": g(r, "linkedin_personne"), "ville": g(r, "ville_personne"),
                        "pays": code_pays(g(r, "pays_personne")) or g(r, "pays_personne"),
                        "contact_id": g(r, "contact_id"), "stage": g(r, "stage"),
                        "dernier_contact": g(r, "dernier_contact"),
                        "statut": "contact Apollo importé" if g(r, "contact_id") else "importé, absent d'Apollo"}

    lignes = []
    for k, e in E.items():
        c = e["champs"]
        nom = e["noms"].most_common(1)[0][0]
        site = site_propre(c.get("site", ""))
        pays = code_pays(c.get("pays", ""))
        canton, reg = region(c.get("ville", ""), pays, loc)
        exclue = k in excl_noms or (bool(site) and domaine(site) in excl_doms)
        deja = k in deja_noms or (bool(site) and domaine(site) in deja_doms)
        lignes.append({
            "nom": nom, "autres_noms": " | ".join(n for n in e["noms"] if n != nom)[:200], "pays": pays,
            "pays_source": c.get("pays", ""), "ville": c.get("ville", ""), "canton": canton, "region": reg,
            "site": site, "linkedin": linkedin_company(c.get("linkedin", "")), "secteur": c.get("secteur", ""),
            "taille": c.get("taille", ""),
            "activite": (c.get("description") or ", ".join(x for x in (c.get("secteur"), c.get("mots_cles")) if x))[:400],
            "technologies": c.get("technologies", "")[:300], "compte_apollo": c.get("compte_apollo", ""),
            "n_contacts": e["n_contacts"], "fichiers": " | ".join(sorted(e["fichiers"])),
            "deja_connue": "oui" if deja else "", "exclure": MOTIF_CLIENT if exclue else "",
            "statut": (f"exclue ({MOTIF_CLIENT})" if exclue else "retenue") + (" ; déjà dans nos listes" if deja else ""),
            "_k": k, "_exclue": exclue, "_retenue": not exclue, "_origine": f"liste {' | '.join(sorted(e['fichiers']))}",
        })
    lignes.sort(key=lambda l: (l["_exclue"], norm(l["nom"])))

    # --- entreprises.csv : le contrat des étapes suivantes
    retenues = [l for l in lignes if not l["_exclue"]]
    liste = []
    for l in retenues:
        apollo = bool(l["compte_apollo"])
        liste.append({
            "nom": l["nom"], "pays": l["pays"], "ville": l["ville"], "canton": l["canton"], "region": l["region"],
            "site": l["site"], "site_statut": "trouvé" if l["site"] else "",
            "site_confiance": "à vérifier" if l["site"] else "",
            "linkedin": l["linkedin"], "linkedin_statut": "trouvé" if l["linkedin"] else "",
            "linkedin_source": ("apollo" if apollo else "liste") if l["linkedin"] else "",
            "linkedin_confiance": "à vérifier" if l["linkedin"] else "",
            "secteur": l["secteur"], "activite": l["activite"], "taille": l["taille"],
            "technologies": l["technologies"],
            "source": "apollo" if apollo else f"liste {l['fichiers']}",
            "preuve": f"Apollo, compte {l['compte_apollo']}" if apollo else f"liste {l['fichiers']}",
            "a_revoir": "non" if l["site"] else "oui", "exclure": "", "deja_connue": l["deja_connue"],
            "note": f"Import {l['fichiers']}", "compte_apollo": l["compte_apollo"], "n_contacts": l["n_contacts"],
        })
    toutes, cols_toutes, cols_liste = lignes, COLONNES_TOUTES, COLONNES_LISTE
    n_deja_toutes = n_deja_liste = n_reprises = 0
    if a.ajouter:
        toutes, cols_toutes, n_deja_toutes, n_reprises = fusionner(
            camp.fichier("entreprises-toutes.csv"), lignes, COLONNES_TOUTES, reprendre=True)
        liste, cols_liste, n_deja_liste, _ = fusionner(camp.fichier("entreprises.csv"), liste, COLONNES_LISTE)
    avertir_listes_suivantes(camp)
    ecrire_csv(camp.fichier("entreprises-toutes.csv"), cols_toutes, toutes)
    ecrire_csv(camp.fichier("entreprises.csv"), cols_liste, liste)

    # --- contacts d'un export de contacts (sans ceux des entreprises exclues)
    exclues = {l["_k"] for l in lignes if l["_exclue"]}
    noms = {l["_k"]: l for l in lignes}
    contacts = [{**p, "entreprise": noms[p["_k"]]["nom"], "site_entreprise": noms[p["_k"]]["site"]}
                for p in personnes.values() if p["_k"] not in exclues]
    f_contacts = camp.dossier / "apollo" / "contacts-importes.csv"
    tous_contacts, cols_contacts, n_contacts_deja = contacts, COLONNES_CONTACTS_IMPORTES, 0
    if a.ajouter and contacts:
        tous_contacts, cols_contacts, n_contacts_deja = fusionner_contacts(f_contacts, contacts)
    if contacts:
        ecrire_csv(f_contacts, cols_contacts, tous_contacts)
    elif not a.ajouter:
        ecarter_contacts_importes(camp)

    print(f"{len(lignes)} entreprises uniques : {len(retenues)} retenues, {len(exclues)} exclues (clients ou partenaires), "
          f"{sum(1 for l in lignes if l['deja_connue'])} déjà dans nos listes ; "
          f"sans site : {sum(1 for l in retenues if not l['site'])}, sans LinkedIn : {sum(1 for l in retenues if not l['linkedin'])}, "
          f"pays non reconnu : {sum(1 for l in retenues if l['pays_source'] and not l['pays'])}")
    if a.ajouter:
        print(f"--ajouter : entreprises.csv + {len(retenues) - n_deja_liste} (déjà présentes : {n_deja_liste}) ; "
              f"entreprises-toutes.csv + {len(lignes) - n_deja_toutes}, dont écartées avant et retenues cette fois : "
              f"{n_reprises}")
    if contacts:
        o = Counter(p["ordre"] for p in contacts)
        print(f"{len(contacts)} contacts : {o[ORDRE_ENTREE]} en entrée, {o[ORDRE_RELAIS]} en relais, "
              f"{sum(1 for p in contacts if p['contact_id'])} avec un id Apollo, "
              f"{sum(1 for p in contacts if p['statut_email'] == 'verified')} emails vérifiés "
              f"-> {f_contacts} (ordre à relire)")
        if a.ajouter:
            print(f"--ajouter : contacts-importes.csv + {len(contacts) - n_contacts_deja} "
                  f"(déjà présents : {n_contacts_deja}) = {len(tous_contacts)} contacts")
    print(f"-> {camp.fichier('entreprises-toutes.csv')} (à relire)")
    print(f"-> {camp.fichier('entreprises.csv')} ({len(liste)} entreprises au contrat)")


if __name__ == "__main__":
    main()
