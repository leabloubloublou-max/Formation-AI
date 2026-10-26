"""Étape 6, 1re partie : structure le persona de chaque entreprise en cibles Apollo, sans LLM ni appel réseau.

Périmètre : tiers A, B, C, D de prospection-signaux.csv (les lignes « Hors cible » ont un motif d'exclusion).
Pour chaque entreprise, d'abord les cibles structurées de donnees/signaux/recherche.json (« cibles » : entree et relais,
chacune une liste de {nom, role}), sinon le texte persona_cible :
- personnes nommées : « Prénom Nom (rôle) », recoupées avec la colonne dirigeants ;
- rôles génériques : « responsable qualité », « l'IT », « SAV »... -> famille de rôle (persona.py et [persona.titres]) ;
- ordre : « entrée » (le texte avant le premier « relais », « puis » ou « routage ») ou « relais » (après).
Format attendu de persona_cible : « Entrée : Prénom Nom (CEO) ; relais : responsable qualité, responsable IT ».
Rien de reconnu : la famille d'entrée de [persona] (entree), puis ses relais ; aucune entrée : la famille d'entrée.
Sorties : apollo/cibles.json et apollo/cibles-apercu.csv (une ligne par cible, à relire avant la recherche).

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/extraire_personas.py --campagne <dossier>
            [--tiers A,B,C,D]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne, domaine, ecrire_csv, lire_csv
from persona import Persona, norm_ascii

NOM_RE = re.compile(r"([A-ZÀ-Ý][a-zà-ÿ'’\-]+(?:\s+(?:de|du|des|von|van|der|di|da|le|la|dos)?\s*[A-ZÀ-Ý][A-Za-zà-ÿ'’\-]+){1,3})\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
# premiers mots qui annoncent un rôle ou un sigle, pas une personne (les logiciels de [signaux] logiciels s'ajoutent)
PAS_UN_NOM = ["Entr[ée]e", "Relais", "Puis", "Head", "Business", "Chief", "Design", "Quality", "Sales", "Service", "ISO",
              "SAV", "CEO", "COO", "CTO", "CFO", "CIO", "IT", "Dirigeant", "Directeur", "Directrice", "Direction",
              "Responsable", "Chef", "Leiter"]
# « responsable Exemple Parc (IT) » : un rôle suivi d'un nom d'entité, pas une personne
ROLE_AVANT = re.compile(r"(responsable|directeur|directrice|chef|head of|leiter|du|de la|de l')\s*$", re.I)
# « … pour l'assistant support » : la suite (jusqu'à la virgule) décrit un cas d'usage, pas un rôle
BUT_INCISE = re.compile(r"\b(pour|afin d|car)\b[^,;]*", re.I)
COUPURE = re.compile(r"\brelais\b|\bpuis\b|\broutage\b", re.I)
COLONNES_APERCU = ["tier", "entreprise", "id", "domaine", "source", "type", "personne", "famille", "role_texte", "ordre",
                   "vu_dans_dirigeants"]


def depuis_texte(txt: str, dirigeants: str, P: Persona, pas_un_nom: re.Pattern) -> list[dict]:
    """Cibles lues dans le texte libre persona_cible (logique d'origine)."""
    m = COUPURE.search(txt)
    coupure = m.start() if m else len(txt)
    cibles, pris = [], []
    for nm in NOM_RE.finditer(txt):
        nom, role = nm.group(1).strip(), nm.group(2).strip()
        if pas_un_nom.match(nom) or len(nom.split()) < 2 or ROLE_AVANT.search(txt[:nm.start()]):
            continue
        cibles.append({
            "type": "personne", "nom": nom, "role_texte": role,
            "ordre": ORDRE_ENTREE if nm.start() < coupure else ORDRE_RELAIS,
            "vu_dans_dirigeants": norm_ascii(nom.split()[-1]) in dirigeants,
            "familles": P.familles_texte(role),
        })
        pris.append((nm.start(), nm.end()))
    # rôles génériques : le texte restant, découpé en segments
    reste = txt
    for a, b in sorted(pris, reverse=True):
        reste = reste[:a] + " | " + reste[b:]
    # les familles des personnes nommées ne bloquent pas les rôles : le rôle sert de repli si la personne n'est pas
    # dans Apollo (la recherche ignore le rôle quand une personne nommée trouvée le couvre déjà)
    deja = set()
    # une incise « pour … » court jusqu'à la virgule suivante : on la retire avant de découper sur « et »
    segments = [s for bloc in re.split(r"[;|]|\bpuis\b|\.\s+(?=[A-ZÀ-Ý])", reste, flags=re.I)
                for s in re.split(r"\bet\b|,", BUT_INCISE.sub(" ", bloc), flags=re.I)]
    for seg in segments:
        seg = seg.strip(" .:()")
        if len(seg) < 2 or re.search(r"hors cible|aucun|priorit|non prioritaire|à défaut|si un contact", seg, re.I):
            continue
        # mention négative (« l'IT est probablement pilotée par le groupe ») : pas une cible
        if re.search(r"est (probablement|possiblement|sans doute)|mutualis|pilot[ée]e par|au niveau d|v[ée]rifier|aborder|attention", seg, re.I):
            continue
        for f in P.familles_texte(seg):
            if f not in deja:
                pos = txt.find(seg)
                cibles.append({"type": "rôle", "famille": f, "role_texte": seg[:80],
                               "ordre": ORDRE_ENTREE if 0 <= pos < coupure else ORDRE_RELAIS})
                deja.add(f)
    return cibles


def depuis_recherche(cibles_rech: dict, dirigeants: str, P: Persona, pas_un_nom: re.Pattern) -> list[dict]:
    """Cibles structurées de recherche.json : {entree: [{nom, role}], relais: [{nom, role}]}."""
    cibles, deja = [], set()
    for ordre, cle in ((ORDRE_ENTREE, "entree"), (ORDRE_RELAIS, "relais")):
        for c in cibles_rech.get(cle) or cibles_rech.get(ordre) or []:
            c = {"role": c} if isinstance(c, str) else c
            nom = re.sub(r"\s+", " ", c.get("nom") or "").strip()
            role = re.sub(r"\s+", " ", c.get("role") or c.get("role_texte") or "").strip()
            if len(nom.split()) >= 2 and not re.search(r"\d", nom) and not pas_un_nom.match(nom):
                cibles.append({"type": "personne", "nom": nom, "role_texte": role, "ordre": ordre,
                               "vu_dans_dirigeants": norm_ascii(nom.split()[-1]) in dirigeants,
                               "familles": P.familles_texte(role)})
                continue
            for f in P.familles_texte(role or nom):
                if (f, ordre) not in deja:
                    cibles.append({"type": "rôle", "famille": f, "role_texte": (role or nom)[:80], "ordre": ordre})
                    deja.add((f, ordre))
    return cibles


def main() -> None:
    ap = argparse.ArgumentParser(description="Structure persona_cible en cibles Apollo (sans réseau).")
    argument_campagne(ap)
    ap.add_argument("--tiers", default="A,B,C,D", help="tiers traités (défaut : A,B,C,D)")
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    P = Persona(camp.config)
    src = camp.fichier("prospection-signaux.csv")
    if not src.exists():
        raise SystemExit(f"{src} absent : faire d'abord l'étape 5 (scorer.py).")
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    rows = [r for r in lire_csv(src) if r.get("tier") in tiers]
    if not rows:
        raise SystemExit(f"Aucune entreprise des tiers {', '.join(tiers)} dans {src} : vérifier la colonne tier.")
    f_rech = camp.signaux / "recherche.json"
    rech = json.loads(f_rech.read_text(encoding="utf-8")) if f_rech.exists() else {}
    logiciels = [re.escape(x) for x in camp.config["signaux"].get("logiciels") or [] if x]
    pas_un_nom = re.compile(r"^(" + "|".join(PAS_UN_NOM + logiciels) + r")\b")

    out, apercu = [], []
    for r in rows:
        txt = (r.get("persona_cible") or "").strip()
        dirigeants = norm_ascii(r.get("dirigeants"))
        structure = (rech.get(r.get("id")) or {}).get("cibles") or {}
        cibles, source = [], ""
        if isinstance(structure, dict) and structure:
            cibles, source = depuis_recherche(structure, dirigeants, P, pas_un_nom), "recherche.json"
        if not cibles:
            cibles, source = depuis_texte(txt, dirigeants, P, pas_un_nom), "persona_cible"
        if not cibles:  # rien d'exploitable : le persona de la campagne (règle par défaut)
            source = "défaut"
            cibles.append({"type": "rôle", "famille": P.entree, "ordre": ORDRE_ENTREE,
                           "role_texte": "défaut (persona_cible vide)" if not txt else "défaut (aucun rôle reconnu)"})
            cibles += [{"type": "rôle", "famille": f, "ordre": ORDRE_RELAIS, "role_texte": "défaut (relais du persona)"}
                       for f in P.relais if f != P.entree]
        elif not any(c["ordre"] == ORDRE_ENTREE for c in cibles):
            cibles.insert(0, {"type": "rôle", "famille": P.entree, "ordre": ORDRE_ENTREE,
                              "role_texte": "défaut (aucune entrée reconnue)"})
        site = r.get("site") or r.get("website") or ""
        hors = bool(re.search(r"hors cible|^aucun", txt, re.I))
        out.append({"id": r.get("id", ""), "nom": r.get("nom", ""), "tier": r["tier"], "pays": r.get("pays", ""),
                    "domaine": domaine(site), "site": site,
                    "linkedin": r.get("linkedin") or "",   # URL corrigée comprise (linkedin_corrige = « oui »)
                    "persona_cible": txt, "source_cibles": source, "hors_cible_selon_persona": hors,
                    "cibles": cibles})
        for c in cibles:
            apercu.append({"tier": r["tier"], "entreprise": r.get("nom", ""), "id": r.get("id", ""),
                           "domaine": domaine(site), "source": source, "type": c["type"],
                           "personne": c.get("nom", ""),
                           "famille": c.get("famille", ", ".join(c.get("familles", []))),
                           "role_texte": c["role_texte"], "ordre": c["ordre"],
                           "vu_dans_dirigeants": c.get("vu_dans_dirigeants", "")})
    (camp.apollo / "cibles.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ecrire_csv(camp.apollo / "cibles-apercu.csv", COLONNES_APERCU, apercu)

    n_pers = sum(1 for e in out for c in e["cibles"] if c["type"] == "personne")
    n_role = sum(1 for e in out for c in e["cibles"] if c["type"] == "rôle")
    sources = {s: sum(1 for e in out if e["source_cibles"] == s) for s in ("recherche.json", "persona_cible", "défaut")}
    print(f"{len(out)} entreprises ; {n_pers} personnes nommées ; {n_role} rôles génériques ; source des cibles : "
          f"{sources}")
    print(f"sans domaine : {[e['nom'] for e in out if not e['domaine']]}")
    print(f"persona par défaut (rien de reconnu) : {[e['nom'] for e in out if e['source_cibles'] == 'défaut']}")
    print(f"marquées hors cible dans persona_cible : {[e['nom'] for e in out if e['hors_cible_selon_persona']]}")
    print(f"-> {camp.apollo / 'cibles.json'} et cibles-apercu.csv (à relire)")


if __name__ == "__main__":
    main()
