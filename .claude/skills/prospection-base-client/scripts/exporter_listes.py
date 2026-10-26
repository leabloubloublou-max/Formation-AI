"""Étape 6, fin : exporte en CSV (0 crédit) chaque liste de contacts Apollo dont le nom commence par un préfixe.

Préfixe par défaut : [apollo] liste_contacts de campagne.toml, donc les listes « <nom> », « <nom> - entrée » et
« <nom> - relais » créées par enrichir_et_creer.py. Les contacts sont lus dans Apollo (la liste fait foi : à relancer
après toute modification des listes), avec email, statut, LinkedIn, téléphones (standard, ligne directe, mobile),
ville et pays, puis complétés par nos colonnes locales (tier, entreprise, entreprise_id, ordre, cibles, et
l'historique : statut, stage, dernier_contact, que lit ordre_appel.py) de apollo/contacts-crees.csv et, s'il existe,
apollo/contacts-importes.csv (importer_liste.py). Un contact sans ligne locale est rattaché à son entreprise par le
nom (prospection-signaux.csv) ; son ordre se déduit du nom de la liste.
Sorties : apollo/listes/<nom-de-la-liste>.csv (nom en minuscules sans accents), triées par tier, entreprise, entrée
d'abord.

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/exporter_listes.py --campagne <dossier>
            [--prefixe NOM]
"""
from __future__ import annotations

import argparse
import sys

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne, code_pays, ecrire_csv, lire_csv, norm

CHAMPS = ["tier", "entreprise", "entreprise_id", "ordre", "prenom", "nom", "titre", "email", "statut_email",
          "linkedin", "telephone_standard", "telephone_direct", "mobile", "ville", "pays", "cibles", "contact_id",
          "statut", "stage", "dernier_contact"]
RANG = {"A": 0, "B": 1, "C": 2, "D": 3}


def numero(c, genre):
    """premier numéro du genre demandé : mobile, direct (ligne directe) ou standard (tout autre numéro)."""
    for p in c.get("phone_numbers") or []:
        t = (p.get("type") or p.get("type_cd") or "").lower()
        if ("mobile" if t.startswith("mobile") else "direct" if "direct" in t else "standard") == genre:
            return p.get("sanitized_number") or p.get("raw_number") or ""
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Exporte les listes de contacts Apollo de la campagne en CSV (0 crédit).")
    argument_campagne(ap)
    ap.add_argument("--prefixe", help="début du nom des listes (défaut : [apollo] liste_contacts)")
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    prefixe = (args.prefixe or camp.config["apollo"].get("liste_contacts") or "").strip()
    if not prefixe:
        raise SystemExit("Préfixe absent : renseignez [apollo] liste_contacts dans campagne.toml ou passez --prefixe.")
    nos = {}
    for nom in ("contacts-importes.csv", "contacts-crees.csv"):  # contacts-crees.csv l'emporte, colonne par colonne
        f = camp.apollo / nom
        if f.exists():
            for r in lire_csv(f):
                if r.get("contact_id"):
                    nos.setdefault(r["contact_id"], {}).update({k: v for k, v in r.items() if v})
    src = camp.fichier("prospection-signaux.csv")
    fiches = {norm(r.get("nom", "")): r for r in lire_csv(src)} if src.exists() else {}

    from apollo_api import Apollo, fichier_liste
    api = Apollo(camp.apollo / "cache")
    dossier = camp.sous_dossier("apollo", "listes")
    n_listes = 0
    for l in api.listes():
        if l.get("modality") != "contacts" or not l["name"].startswith(prefixe):
            continue
        n_listes += 1
        ordre_liste = ORDRE_ENTREE if l["name"].endswith(f"- {ORDRE_ENTREE}") else \
            ORDRE_RELAIS if l["name"].endswith(f"- {ORDRE_RELAIS}") else ""
        contacts, page = [], 1
        while True:
            d = api.contacts_search([l["id"]], page=page, per_page=100)
            contacts += d.get("contacts") or []
            if page >= ((d.get("pagination") or {}).get("total_pages") or 1):
                break
            page += 1
        lignes = []
        for c in contacts:
            r = nos.get(c["id"], {})
            f = fiches.get(norm(r.get("entreprise") or c.get("organization_name") or ""), {})
            lignes.append({
                "tier": r.get("tier") or f.get("tier", ""),
                "entreprise": r.get("entreprise") or c.get("organization_name") or "",
                "entreprise_id": r.get("entreprise_id") or f.get("id", ""),
                "ordre": r.get("ordre") or ordre_liste, "prenom": c.get("first_name") or "",
                "nom": c.get("last_name") or "", "titre": c.get("title") or "", "email": c.get("email") or "",
                "statut_email": (c.get("email_status") or "").lower(), "linkedin": c.get("linkedin_url") or "",
                "telephone_standard": numero(c, "standard"), "telephone_direct": numero(c, "direct"),
                "mobile": numero(c, "mobile"), "ville": c.get("city") or "",
                "pays": code_pays(c.get("country") or "") or c.get("country") or "", "cibles": r.get("cibles", ""),
                "contact_id": c["id"],
                # historique local (« déjà dans Apollo, ajouté aux listes », étape et dernier contact de l'import)
                "statut": r.get("statut", ""), "stage": r.get("stage", ""),
                "dernier_contact": r.get("dernier_contact", "")})
        lignes.sort(key=lambda x: (RANG.get(x["tier"], 9), x["entreprise"], x["ordre"] != ORDRE_ENTREE, x["nom"]))
        ecrire_csv(dossier / fichier_liste(l["name"]), CHAMPS, lignes)
        sans_info = sum(1 for x in lignes if not x["entreprise_id"])
        print(f"{l['name']} : {len(lignes)} contacts -> apollo/listes/{fichier_liste(l['name'])}"
              + (f" ({sans_info} sans entreprise de la campagne)" if sans_info else ""))
    if not n_listes:
        print(f"Aucune liste de contacts ne commence par « {prefixe} » dans Apollo (enrichir_et_creer.py --go les crée).")


if __name__ == "__main__":
    main()
