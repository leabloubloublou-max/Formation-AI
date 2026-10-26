"""Étape 5, premier script : une fiche par ENTREPRISE à partir de la liste de la campagne.

Entrée : la liste la plus avancée de la campagne (entreprises-verifie.csv, sinon -enrichi.csv, sinon
entreprises.csv ; colonnes commun.COLONNES_ENTREPRISES), ou --liste <csv>. Une ligne = une entreprise ; les lignes
marquées « doublon » dans la colonne exclure sont ignorées.
Fusion des doublons restants (union-find) si : même nom, même nom officiel, ou même site ET même page LinkedIn
avec un mot distinctif commun dans les noms.
Drapeaux : exclure (colonne exclure non vide), particulier, administration, non_identifie, fermee_ou_liquidation,
renommee_ou_absorbee.

Sortie : <campagne>/donnees/signaux/entites.json, liste de fiches dans l'ordre de la liste :
  {id, nom, nom_court, autres_noms[], pays, ville, canton, activite, secteur, taille, site, linkedin, site_statut,
   linkedin_statut, a_revoir, exclure, flags[], note}
id = slug(nom_court) : clé de tous les caches et fichiers suivants (ne pas le changer en cours de campagne).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/entites.py --campagne campagnes/<nom> [--liste <csv>]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import argument_campagne, code_pays, lire_csv
from signaux_commun import domain, donnees, name_tokens, norm, ouvrir, save_json, short_name, slug

INDIVIDUEL = re.compile(r"personne physique|entreprise individuelle|(?:développeur|travailleur) indépendant|freelance", re.I)
NON_IDENT = re.compile(r"non identifi|inconnu|non confirmé|compte générique", re.I)
FERMEE = re.compile(r"en liquidation|radiée|radié\b|dissoute", re.I)
RENOMMEE = re.compile(r"aujourd.hui|\bex-|anciennement", re.I)
DOUBLON = re.compile(r"^\s*doublon", re.I)

# motif de la colonne exclure -> drapeau (les autres motifs donnent seulement le drapeau « exclure »)
EXCLURE_DRAPEAUX = [
    ("particulier", re.compile(r"particulier|individuel", re.I)),
    ("administration", re.compile(r"administration", re.I)),
    ("non_identifie", re.compile(r"non identifi", re.I)),
    ("fermee_ou_liquidation", re.compile(r"ferm[ée]|radi[ée]|liquidation|dissoute", re.I)),
]


def drapeaux_exclure(motif: str) -> set[str]:
    """Drapeaux portés par un motif d'exclusion (« particulier », « fermée »...) ; vide pour les autres motifs."""
    return {fl for fl, rx in EXCLURE_DRAPEAUX if motif and rx.search(motif)}


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", norm(s))


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def fiches(rows: list[dict]) -> list[dict]:
    """Lignes de la liste (déjà sans doublons marqués) -> fiches entreprises fusionnées."""
    uf = UF(len(rows))
    by = {}
    for i, r in enumerate(rows):
        # nom et nom officiel dans le même espace : le nom d'une ligne peut être le nom officiel d'une autre
        keys = [("n", alnum(r.get("nom", "")))] if alnum(r.get("nom", "")) else []
        nom = r.get("nom_officiel", "")
        if nom and not NON_IDENT.search(nom) and ("n", alnum(nom)) not in keys:
            keys.append(("n", alnum(nom)))
        for k in keys:
            if k in by:
                uf.union(i, by[k])
            else:
                by[k] = i
        # même site + même LinkedIn : fusion seulement si les noms partagent un mot distinctif
        # (« Exemple Europe SA » et « Autre Asia Ltd » peuvent pointer vers la même page de groupe)
        if r.get("site") and r.get("linkedin"):
            wl = ("wl", domain(r["site"]), r["linkedin"].rstrip("/").lower())
            toks = set(name_tokens(short_name(nom or r.get("nom", ""))))
            for j in by.get(wl, []):
                if toks & set(name_tokens(short_name(rows[j].get("nom_officiel") or rows[j].get("nom", "")))):
                    uf.union(i, j)
            by.setdefault(wl, []).append(i)

    groups = {}
    for i, r in enumerate(rows):            # dans l'ordre de la liste : la première ligne d'un groupe le place
        groups.setdefault(uf.find(i), []).append(r)

    ents, used = [], Counter()
    for members in groups.values():
        best = members[0]

        def first(field):
            for r in members:
                if (r.get(field) or "").strip():
                    return r[field].strip()
            return ""

        def most(field):
            c = Counter(r[field].strip() for r in members if (r.get(field) or "").strip())
            return c.most_common(1)[0][0] if c else ""

        nom = next((r["nom_officiel"].strip() for r in members
                    if (r.get("nom_officiel") or "").strip() and not NON_IDENT.search(r["nom_officiel"])),
                   (best.get("nom_officiel") or best.get("nom") or "").strip())
        statuts = {r.get("site_statut", "") for r in members} | {r.get("linkedin_statut", "") for r in members}
        exclure = first("exclure")
        texte = " ".join([nom, first("activite"), first("note")])
        flags = []
        if exclure:
            flags.append("exclure")
        if "particulier" in statuts or INDIVIDUEL.search(texte) or "particulier" in drapeaux_exclure(exclure):
            flags.append("particulier")
        if "administration" in statuts or "administration" in drapeaux_exclure(exclure):
            flags.append("administration")
        if NON_IDENT.search(nom) or not nom.strip() or "non_identifie" in drapeaux_exclure(exclure):
            flags.append("non_identifie")
        if FERMEE.search(nom) or FERMEE.search(first("note")) or "fermee_ou_liquidation" in drapeaux_exclure(exclure):
            flags.append("fermee_ou_liquidation")
        if RENOMMEE.search(nom):
            flags.append("renommee_ou_absorbee")
        base = slug(short_name(nom)) or slug(best.get("nom", ""))
        used[base] += 1
        eid = base if used[base] == 1 else f"{base}-{used[base]}"
        noms = [x.strip() for r in members for x in (r.get("nom", ""), r.get("nom_officiel", "")) if (x or "").strip()]
        ents.append({
            "id": eid,
            "nom": nom,
            "nom_court": short_name(nom),
            "autres_noms": [x for x in dict.fromkeys(noms) if x != nom and not NON_IDENT.search(x)],
            "pays": code_pays(first("pays")),
            "ville": first("ville"),
            "canton": first("canton"),
            "activite": first("activite"),
            "secteur": first("secteur"),
            "taille": first("taille"),
            "site": most("site"),
            "linkedin": most("linkedin"),
            "site_statut": best.get("site_statut", ""),
            "linkedin_statut": best.get("linkedin_statut", ""),
            "a_revoir": "oui" if any((r.get("a_revoir") or "").strip().lower() == "oui" for r in members) else first("a_revoir"),
            "exclure": exclure,
            "flags": flags,
            "note": " | ".join(dict.fromkeys(r["note"].strip() for r in members if (r.get("note") or "").strip())),
        })
    return ents


def main() -> None:
    ap = argparse.ArgumentParser(description="Fiches entreprises de l'étape 5 (donnees/signaux/entites.json).")
    argument_campagne(ap)
    ap.add_argument("--liste", help="CSV à lire à la place de la liste la plus avancée de la campagne")
    a = ap.parse_args()

    camp = ouvrir(a.campagne)
    source = Path(a.liste).expanduser().resolve() if a.liste else camp.liste_entreprises()
    if not source.is_file():
        raise SystemExit(f"Liste introuvable : {source}")
    lignes = lire_csv(source)
    if lignes and "nom" not in lignes[0]:
        raise SystemExit(f"{source} : colonne « nom » absente (contrat : commun.COLONNES_ENTREPRISES).")
    rows = [r for r in lignes if (r.get("nom") or r.get("nom_officiel") or "").strip()
            and not DOUBLON.search(r.get("exclure") or "")]
    ents = fiches(rows)
    save_json(donnees() / "entites.json", ents)
    f = Counter(fl for e in ents for fl in e["flags"])
    pays = Counter(e["pays"] or "vide" for e in ents)
    print(f"{source.name} : {len(lignes)} lignes, {len(lignes) - len(rows)} "
          f"ignorées (doublons ou sans nom) -> {len(ents)} entreprises | drapeaux {dict(f)}")
    print(f"site : {sum(1 for e in ents if e['site'])} | linkedin : {sum(1 for e in ents if e['linkedin'])} | "
          f"pays : {dict(pays.most_common())}")
    print(f"-> {donnees() / 'entites.json'}")


if __name__ == "__main__":
    main()
