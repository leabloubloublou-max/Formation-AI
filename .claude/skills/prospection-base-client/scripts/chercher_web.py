"""Étape 6, complément gratuit : cherche sur le web (DuckDuckGo) les profils qu'Apollo ne trouve pas.

D'après apollo/couverture.csv et apollo/contacts-a-valider.csv (chercher_contacts.py) :
- personne nommée absente d'Apollo, ou placée ailleurs par Apollo : « "Prénom Nom" entreprise » ; un profil LinkedIn
  au nom de la personne et à l'entreprise confirme qu'elle y est (et donne son URL) ;
- entreprise sans contact d'entrée retenu : mêmes requêtes pour les dirigeants de la fiche (registre) ;
- rôle manquant : « site:linkedin.com/in "entreprise" mot-clé » ; le titre du profil doit citer le rôle et l'entreprise.
Langue des requêtes : celle du pays de l'entreprise (en Suisse, celle du canton) ; région DuckDuckGo assortie.
Sortie : apollo/trouves-web.json, relu par chercher_contacts.py (qui recherche ces personnes dans Apollo, puis garde
l'URL LinkedIn pour l'enrichissement si Apollo ne les a pas). Les résultats d'un passage précédent qui ne sont pas
recherchés de nouveau sont gardés. Cache : apollo/cache/web.json (par région et requête).
Ordre conseillé : chercher_contacts.py, chercher_web.py, puis chercher_contacts.py de nouveau (une seule fois).

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_web.py --campagne <dossier>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import LANGUES_PAYS, ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne, lire_csv, recherche_web, \
    region_recherche
from persona import Persona, dirigeants, jetons, norm_texte as norm

# langue de travail d'un canton suisse (cantons bilingues : langue majoritaire)
LANGUE_CANTON = {"GE": "fr", "VD": "fr", "NE": "fr", "JU": "fr", "FR": "fr", "VS": "fr", "TI": "it"}
FORMES = r"\(.*|\b(SA|AG|GmbH|SAS|S\.r\.l\.|Srl|SARL|Sàrl|Sagl|S\.A\.|SpA|S\.p\.A\.|Ltd|Inc|KG)\b"


class Web:
    def __init__(self, cache):
        self.fichier = cache / "web.json"
        self.cache = json.loads(self.fichier.read_text(encoding="utf-8")) if self.fichier.exists() else {}
        self.n = 0

    def chercher(self, q, region, n=8):
        cle = f"{region}|{q}"
        if cle in self.cache:
            return self.cache[cle]
        res = [{"url": r.get("href") or "", "titre": r.get("title") or "", "extrait": r.get("body") or ""}
               for r in recherche_web(q, n=n, region=region)]
        self.n += 1
        time.sleep(1.2)
        self.cache[cle] = res
        if self.n % 20 == 0:
            self.sauver()
        return res

    def sauver(self):
        self.fichier.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")


def profil_linkedin(r):
    """« Prénom Nom - Poste - Entreprise | LinkedIn » -> (nom, poste, entreprise) ; None si ce n'est pas un profil."""
    if not re.search(r"linkedin\.com/in/", r["url"]):
        return None
    tete = re.split(r"\s+\|\s+LinkedIn", r["titre"])[0]
    parts = [p.strip() for p in re.split("\\s+[\u2013\u2014-]\\s+", tete) if p.strip()]
    if not parts:
        return None
    if len(parts) >= 3:
        return parts[0], " - ".join(parts[1:-1]), parts[-1]
    return parts[0], "", parts[1] if len(parts) == 2 else ""


def nom_dans(nom, texte):
    t = f" {norm(texte)} "
    toks = [x for x in norm(nom).replace("-", " ").split() if len(x) > 1]
    return len(toks) >= 2 and all(f" {x} " in t or f" {x}-" in t for x in toks[:1] + toks[-1:])


def chercher_personne(web, region, nom, entreprise, noms_ent):
    """renvoie {statut, linkedin, poste, source} ; statut = confirmé / cité / ailleurs / introuvable."""
    court = re.sub(FORMES, "", entreprise).strip()
    res = web.chercher(f'"{nom}" {court}', region) + web.chercher(f'"{nom}" linkedin', region)
    meilleur = {"statut": "introuvable", "linkedin": "", "poste": "", "source": ""}
    for r in res:
        texte = f"{r['titre']} {r['extrait']}"
        p = profil_linkedin(r)
        if p and nom_dans(nom, p[0]):
            ici = bool(jetons(f"{p[2]} {p[1]}") & noms_ent)
            cand = {"statut": "confirmé" if ici else "ailleurs", "linkedin": r["url"].split("?")[0],
                    "poste": p[1] or "", "entreprise_linkedin": p[2], "source": r["url"]}
            if ici:
                return cand
            if meilleur["statut"] == "introuvable":
                meilleur = cand
        elif nom_dans(nom, texte) and jetons(texte) & noms_ent and meilleur["statut"] in ("introuvable", "ailleurs"):
            m = re.search(re.escape(nom.split()[-1]) + r"[^.]{0,8}?,?\s+([^,.;]{3,60}?)\s+(?:at|chez|bei|di|de)\s", r["extrait"])
            meilleur = {"statut": "cité", "linkedin": meilleur.get("linkedin", ""), "poste": m.group(1) if m else "",
                        "source": r["url"]}
    return meilleur


def chercher_role(web, region, P, famille, entreprise, noms_ent, langue):
    court = re.sub(FORMES, "", entreprise).strip()
    out = []
    for lg in dict.fromkeys([langue, "en"]):
        for r in web.chercher(f'site:linkedin.com/in "{court}" {P.requete(famille, lg)}', region):
            p = profil_linkedin(r)
            if not p:
                continue
            poste = p[1] or (re.search(r"^([^·]{3,80}?)\s+(?:at|chez|bei|presso)\s", r["extrait"]) or [None, ""])[1]
            if famille in P.familles_titre(poste) and jetons(f"{p[2]} {r['extrait'][:120]}") & noms_ent:
                out.append({"nom": p[0], "poste": poste, "linkedin": r["url"].split("?")[0]})
        if out:
            break
    return out


def langue_entreprise(fiche: dict, nom: str, defaut: str) -> str:
    """Langue des requêtes : pays de l'entreprise ; en Suisse, le canton (sinon AG/GmbH -> allemand)."""
    pays = (fiche.get("pays") or "").upper()
    if pays == "CH":
        canton = (fiche.get("canton") or "").upper()
        if canton:
            return LANGUE_CANTON.get(canton, "de")
        return "de" if re.search(r"\b(AG|GmbH)\b", nom) else defaut
    if pays:
        return LANGUES_PAYS.get(pays, "en")
    return "de" if re.search(r"\b(AG|GmbH)\b", nom) else defaut


def main() -> None:
    ap = argparse.ArgumentParser(description="Recherche web (DuckDuckGo) des contacts qu'Apollo n'a pas trouvés.")
    argument_campagne(ap)
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    P = Persona(camp.config)
    manquants = [camp.apollo / n for n in ("cibles.json", "couverture.csv", "contacts-a-valider.csv")
                 if not (camp.apollo / n).exists()]
    if manquants:
        raise SystemExit(f"Absent : {', '.join(str(m) for m in manquants)}. Lancer d'abord extraire_personas.py "
                         "puis chercher_contacts.py.")
    cibles = {e["id"]: e for e in json.loads((camp.apollo / "cibles.json").read_text(encoding="utf-8"))}
    src = camp.fichier("prospection-signaux.csv")
    fiches = {r["id"]: r for r in lire_csv(src)} if src.exists() else {}
    couv = [c for c in lire_csv(camp.apollo / "couverture.csv") if c.get("compte_apollo")]
    lignes = lire_csv(camp.apollo / "contacts-a-valider.csv")
    entree = {r["entreprise_id"] for r in lignes if r["garder"] == "oui" and r["ordre"] == ORDRE_ENTREE}
    defaut = (camp.config["appels"].get("langues") or ["fr"])[0]
    web, out = Web(camp.apollo / "cache"), []
    for i, c in enumerate(couv, 1):
        e = cibles.get(c.get("entreprise_id"))
        if not e:
            continue
        f = fiches.get(e["id"], {})
        noms_ent = jetons(e["nom"]) | jetons(c["compte_apollo"])
        langue = langue_entreprise(f, e["nom"], defaut)
        region = region_recherche(f.get("pays") or e.get("pays") or "", langue)
        for m in [m for m in c["non_trouvees"].split(" ; ") if m]:
            if m.startswith("rôle"):
                fam = P.famille_de_libelle(m.replace("rôle ", "", 1))
                if fam:
                    for r in chercher_role(web, region, P, fam, e["nom"], noms_ent, langue)[:2]:
                        out.append({"id": e["id"], "entreprise": e["nom"], "cible": m, "ordre": ORDRE_RELAIS, **r,
                                    "statut": "rôle trouvé (LinkedIn)"})
                continue
            if " : LinkedIn le place chez " in m:  # déjà un résultat web d'un passage précédent
                continue
            nom = re.sub(r"\s*\(.*", "", m)
            cible = next((x for x in e["cibles"] if x.get("nom") == nom), {})
            r = chercher_personne(web, region, nom, e["nom"], noms_ent)
            out.append({"id": e["id"], "entreprise": e["nom"], "cible": f"{nom} ({cible.get('role_texte', '')[:50]})",
                        "ordre": cible.get("ordre", ORDRE_ENTREE), "nom": nom, **r})
        if e["id"] not in entree:  # pas de contact d'entrée : dirigeants inscrits au registre
            deja = {norm(x.get("nom", "")) for x in e["cibles"]}
            for nom, role in dirigeants(f.get("dirigeants", ""))[:3]:
                if norm(nom) in deja:
                    continue
                r = chercher_personne(web, region, nom, e["nom"], noms_ent)
                out.append({"id": e["id"], "entreprise": e["nom"], "cible": f"{nom} ({role[:45]}) [registre]",
                            "ordre": ORDRE_ENTREE, "nom": nom, **r})
        if i % 20 == 0:
            print(f"  {i}/{len(couv)} entreprises ({web.n} requêtes)")
    web.sauver()
    # résultats d'un passage précédent, non recherchés cette fois (personnes déjà réintégrées) : gardés
    cle = lambda w: (w["id"], w.get("linkedin") or norm(w.get("nom", "")), w.get("cible", ""))
    f_out = camp.apollo / "trouves-web.json"
    nouveaux = {cle(w) for w in out}
    anciens = [w for w in json.loads(f_out.read_text(encoding="utf-8"))
               if cle(w) not in nouveaux] if f_out.exists() else []
    f_out.write_text(json.dumps(out + anciens, ensure_ascii=False, indent=1), encoding="utf-8")
    stats = {}
    for r in out:
        stats[r["statut"]] = stats.get(r["statut"], 0) + 1
    print(f"{len(out)} recherches web ({web.n} requêtes DuckDuckGo) : {stats} ; repris du passage précédent : "
          f"{len(anciens)} -> {f_out}")
    print("Relancer ensuite chercher_contacts.py pour réintégrer ces résultats.")


if __name__ == "__main__":
    main()
