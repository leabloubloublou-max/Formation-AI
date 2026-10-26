"""Étape 6, préalable : la liste de COMPTES Apollo de la campagne (tiers A à D de prospection-signaux.csv).

La recherche des contacts (chercher_contacts.py) part de cette liste : elle fixe le périmètre. Deux façons de la créer :
- à la main : le script écrit apollo/comptes-a-importer.csv (en-têtes des exports Apollo : Company Name, Website,
  Company Linkedin Url), à trier dans Excel puis à importer dans Apollo comme liste de comptes, sous le nom
  [apollo] liste_comptes de campagne.toml ;
- par l'API, avec --go (écriture dans Apollo, 0 crédit) : comptes créés par lots de 100 (dédoublonnage Apollo : un
  compte qui existe déjà est repris tel quel), puis tous ajoutés à la liste, créée au besoin. Deux entreprises du
  même domaine ne donnent qu'un compte (Apollo les regrouperait de toute façon).
Sans --go : aperçu chiffré, aucun appel, la clé n'est pas lue.

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/creer_comptes.py --campagne <dossier>
            [--tiers A,B,C,D] [--liste NOM] [--go]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import Campagne, argument_campagne, domaine, ecrire_csv, lire_csv, linkedin_company, site_propre

COLONNES = ["rang", "tier", "Company Name", "Website", "Company Linkedin Url", "pays", "canton", "pourquoi_maintenant",
            "id", "account_id", "statut"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Liste de comptes Apollo de la campagne (aperçu, CSV d'import ou --go).")
    argument_campagne(ap)
    ap.add_argument("--tiers", default="A,B,C,D", help="tiers à mettre dans la liste (défaut : A,B,C,D)")
    ap.add_argument("--liste", help="nom de la liste de comptes (défaut : [apollo] liste_comptes de campagne.toml)")
    ap.add_argument("--go", action="store_true", help="créer les comptes et la liste dans Apollo (après accord)")
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    src = camp.fichier("prospection-signaux.csv")
    if not src.exists():
        raise SystemExit(f"{src} absent : faire d'abord l'étape 5 (scorer.py).")
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    lignes = [r for r in lire_csv(src) if r.get("tier") in tiers]
    if not lignes:
        raise SystemExit(f"Aucune entreprise des tiers {', '.join(tiers)} dans {src}.")
    nom_liste = (args.liste or camp.config["apollo"].get("liste_comptes") or "").strip()

    rows, par_dom = [], {}
    for r in lignes:
        site = site_propre(r.get("site") or r.get("website") or "")
        row = {"rang": r.get("rang", ""), "tier": r["tier"], "Company Name": r.get("nom", ""), "Website": site,
               # linkedin porte déjà l'URL corrigée ; linkedin_corrige n'est qu'un indicateur (« oui »)
               "Company Linkedin Url": linkedin_company(r.get("linkedin") or ""),
               "pays": r.get("pays", ""), "canton": r.get("canton", ""),
               "pourquoi_maintenant": r.get("pourquoi_maintenant", ""), "id": r.get("id", ""),
               "account_id": "", "statut": ""}
        d = domaine(site)
        if d and d in par_dom:
            row["statut"] = f"même domaine que {par_dom[d]['Company Name']} (un seul compte)"
        elif d:
            par_dom[d] = row
        rows.append(row)
    sortie = camp.apollo / "comptes-a-importer.csv"
    ecrire_csv(sortie, COLONNES, rows)

    n = Counter(r["tier"] for r in rows)
    sans_site = [r["Company Name"] for r in rows if not r["Website"]]
    doublons = [r["Company Name"] for r in rows if r["statut"]]
    print(f"{len(rows)} entreprises ({', '.join(f'{t} {n[t]}' for t in tiers)}) -> {sortie}")
    if sans_site:
        print(f"  sans site ({len(sans_site)}, rapprochées par le nom seulement) : {', '.join(sans_site[:10])}"
              + (" ..." if len(sans_site) > 10 else ""))
    if doublons:
        print(f"  même domaine qu'une autre ligne ({len(doublons)}) : {', '.join(doublons)}")
    if not args.go:
        print(f"Aperçu seulement : rien n'a été envoyé. Import à la main : ce CSV dans Apollo (liste de comptes "
              f"« {nom_liste or 'nom à choisir'} »). Par l'API, après accord : --go (0 crédit).")
        return
    if not nom_liste:
        raise SystemExit("Nom de la liste de comptes absent : renseignez [apollo] liste_comptes dans campagne.toml "
                         "(ou --liste).")

    from apollo_api import Apollo
    api = Apollo(camp.apollo / "cache")
    a_envoyer = [r for r in rows if not r["statut"]]
    ids, crees, existants = [], 0, 0
    for i in range(0, len(a_envoyer), 100):
        lot = a_envoyer[i:i + 100]
        comptes = [{k: v for k, v in (("name", r["Company Name"]), ("domain", domaine(r["Website"]))) if v}
                   for r in lot]
        d = api.creer_comptes(comptes)
        for deja, liste in ((False, d.get("created_accounts") or d.get("accounts") or []),
                            (True, d.get("existing_accounts") or [])):
            for c in liste:
                r = retrouver(c, lot)
                if c.get("id"):
                    ids.append(c["id"])
                if r is not None:
                    r["account_id"] = c.get("id") or ""
                    r["statut"] = "déjà dans Apollo, ajouté à la liste" if deja else "créé"
                existants += deja
                crees += not deja
        print(f"  lot {i // 100 + 1} : {len(lot)} comptes envoyés")
    for i in range(0, len(ids), 100):  # créés et existants : ajout explicite à la liste (créée au besoin)
        api.ajouter_aux_listes(ids[i:i + 100], [nom_liste], modality="accounts")
    for r in rows:
        if not r["statut"]:
            r["statut"] = "non retrouvé dans la réponse d'Apollo"
    ecrire_csv(sortie, COLONNES, rows)
    print(f"comptes créés : {crees} ; déjà présents : {existants} ; liste « {nom_liste} » : {len(set(ids))} comptes "
          f"(compteur Apollo mis à jour en différé) ; {api.appels} appels API -> {sortie}")


def retrouver(compte: dict, lot: list[dict]) -> dict | None:
    """Relie un compte renvoyé par Apollo à sa ligne : par domaine, sinon par nom."""
    d = domaine(compte.get("domain") or compte.get("primary_domain") or compte.get("website_url") or "")
    for r in lot:
        if d and domaine(r["Website"]) == d:
            return r
    return next((r for r in lot if (compte.get("name") or "").strip().lower() == r["Company Name"].strip().lower()),
                None)


if __name__ == "__main__":
    main()
