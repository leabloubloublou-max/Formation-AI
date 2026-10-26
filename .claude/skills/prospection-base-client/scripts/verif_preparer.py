"""Étape 4, passe 1 : prépare les lots de la vérification par agents (workflows/verification.js).

Entrée : la liste de l'étape 2 ou 3, entreprises-enrichi.csv, sinon entreprises.csv. Jamais entreprises-verifie.csv :
verif_appliquer.py le reconstruit à chaque fois à partir de cette liste. Les lignes dont la colonne exclure est
remplie (clients actuels, hors cible...) ne sont pas vérifiées.

Une entité = un nom (colonne nom ; deux lignes au même nom, à la casse et aux espaces près, n'en font qu'une, clé
partagée). Catégorie de l'entité, celle de sa ligne la plus douteuse :
- solide : site sûr (confiance haute, ou déjà confirmé ou corrigé) et page LinkedIn sûre (lue sur le site officiel,
  confiance haute, ou déjà confirmée) ; jamais une ligne à revoir ;
- probable : site sûr seul ; faible : site douteux, ou cherché sans succès ; non recherché : ni site ni recherche.
Mode auto (défaut) : les solides en contrôle léger, le reste en profondeur ; --mode leger : toute entité dont chaque
ligne a un site et n'est pas à revoir en contrôle léger (par exemple juste après une découverte web dont les sites
ont été vus par les agents) ; --mode profond : tout en profondeur.
Lots « D » (profonds, --taille-profond entités) et « L » (légers, --taille-leger entités), jamais vides. Les entités
sont classées par incertitude (celle de leur ligne la plus incertaine : site absent, site douteux, ligne à revoir,
LinkedIn absent ou douteux), puis dans l'ordre de la liste, et réparties en tourniquet entre les lots pour équilibrer
la charge des agents ; dans chaque lot, les plus incertaines viennent en premier. --max N ne garde que les N
premières (essai à petit coût).

Sorties, dans <campagne>/donnees/verification/ :
- lots/D01.json, ..., L01.json, ... : les entités de chaque lot, lues par les agents (les anciens lots D et L sont
  effacés) ;
- manifeste-passe1.json : [{id, mode (deep|light), n, file, cles}], file relatif au dossier de la campagne ;
- args-passe1.json : les args complets du workflow (racine, campagne, python, skill, cible, contexte, registres,
  batches), à passer tels quels à l'outil Workflow.

Usage (depuis la racine du projet, celle qui contient .venv) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_preparer.py --campagne campagnes/<nom>
      [--mode auto|leger|profond] [--taille-profond 25] [--taille-leger 90] [--max N]
Ensuite, avec l'accord de l'utilisateur (multi-agents) : outil Workflow, scriptPath =
<skill>/workflows/verification.js, args = contenu de args-passe1.json ; puis verif_appliquer.py avec le journal du run.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import SKILL, Campagne, argument_campagne, lire_csv

# catégories, de la plus douteuse à la plus sûre
CATEGORIES = ["non recherché", "faible", "probable", "solide"]
# champs d'une ligne recopiés dans le lot (les champs vides sont omis pour alléger la lecture des agents)
CHAMPS_LOT = ["nom", "nom_officiel", "pays", "ville", "secteur", "activite", "taille", "site", "site_statut",
              "site_confiance", "linkedin", "linkedin_statut", "linkedin_source", "linkedin_confiance", "source",
              "preuve", "a_revoir", "note"]
# marqueurs d'une entité que les agents n'ont pas su identifier (nom officiel laissé en clair par un agent)
NON_IDENTIFIE = re.compile(r"non identifi|inconnu", re.I)
MANIFESTES = {1: "manifeste-passe1.json", 2: "manifeste-passe2.json"}
# registres du commerce consultables en ligne, cités aux agents pour la raison sociale, l'adresse et une radiation
REGISTRES = {
    "CH": "zefix.ch (registre du commerce suisse), moneyhouse.ch",
    "FR": "annuaire-entreprises.data.gouv.fr, pappers.fr",
    "DE": "handelsregister.de, northdata.de",
    "AT": "firmenbuch (via northdata.com)",
    "IT": "registroimprese.it",
    "BE": "kbopub.economie.fgov.be (BCE)",
    "LU": "lbr.lu (RCS)",
    "LI": "oera.li (registre du commerce du Liechtenstein)",
    "NL": "kvk.nl",
    "GB": "find-and-update.company-information.service.gov.uk (Companies House)",
}
# repères mesurés sur une campagne réelle (tokens de sous-agents par entité, contre-vérification comprise)
TOKENS_PAR_ENTITE = {1: 4500, 2: 10000}


# ---------------------------------------------------------------- outils partagés (verif_passe2, verif_appliquer)

def cle(nom: str) -> str:
    """Clé d'entité : le nom, casse et espaces ignorés (comme les clés rendues par les agents)."""
    return " ".join((nom or "").split()).casefold()


def liste_de_base(camp: Campagne) -> Path:
    """La liste que la vérification part de : entreprises-enrichi.csv, sinon entreprises.csv."""
    for nom in ("entreprises-enrichi.csv", "entreprises.csv"):
        if camp.fichier(nom).exists():
            return camp.fichier(nom)
    raise SystemExit(f"Ni entreprises-enrichi.csv ni entreprises.csv dans {camp.dossier} : faire d'abord l'étape 2 "
                     "(etapes/02-trouver-les-entreprises.md).")


def entites_de(lignes: list[dict]) -> dict[str, dict]:
    """clé -> {key, rang, lignes} dans l'ordre de la liste ; les lignes sans nom sont ignorées."""
    ents: dict[str, dict] = {}
    for i, r in enumerate(lignes):
        nom = (r.get("nom") or "").strip()
        if not nom:
            continue
        e = ents.setdefault(cle(nom), {"key": nom, "rang": i, "lignes": []})
        e["lignes"].append(r)
    return ents


def site_sur(r: dict) -> bool:
    return bool(r.get("site")) and (r.get("site_confiance") == "haute" or r.get("site_statut") in ("confirmé", "corrigé"))


def linkedin_sur(r: dict) -> bool:
    return bool(r.get("linkedin")) and (r.get("linkedin_source") == "site web" or r.get("linkedin_confiance") == "haute"
                                        or r.get("linkedin_statut") in ("confirmé", "corrigé"))


def categorie(r: dict) -> str:
    if not r.get("site"):
        return "faible" if r.get("site_statut") == "introuvable" else "non recherché"
    if not site_sur(r):
        return "faible"
    return "solide" if linkedin_sur(r) and r.get("a_revoir") != "oui" else "probable"


def incertitude(r: dict) -> int:
    """Plus c'est haut, plus l'entité a besoin d'être vérifiée : sert à l'ordre de passage."""
    n = 3 if not r.get("site") else (0 if site_sur(r) else 2)
    n += 1 if r.get("a_revoir") == "oui" else 0
    n += 0 if linkedin_sur(r) else 1
    return n


def repartir(items: list, taille: int) -> list[list]:
    """Tourniquet sur ceil(n / taille) lots : jamais de lot vide, l'ordre d'entrée est gardé dans chaque lot."""
    if not items:
        return []
    lots = [[] for _ in range(math.ceil(len(items) / max(1, taille)))]
    for i, e in enumerate(items):
        lots[i % len(lots)].append(e)
    return lots


def ecrire_lots(camp: Campagne, lots: list[list], prefixe: str, mode: str) -> list[dict]:
    """Écrit lots/<prefixe>NN.json ; rend les entrées du manifeste (file relatif au dossier de la campagne)."""
    dossier = camp.verification / "lots"
    dossier.mkdir(parents=True, exist_ok=True)
    out = []
    for i, lot in enumerate(lots, 1):
        bid = f"{prefixe}{i:02d}"
        chemin = dossier / f"{bid}.json"
        chemin.write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
        entree = {"id": bid, "mode": mode, "n": len(lot), "file": chemin.relative_to(camp.dossier).as_posix(),
                  "cles": [e["key"] for e in lot]}
        alias = {a: e["key"] for e in lot for a in e.get("alias", [])}
        if alias:
            entree["alias"] = alias
        out.append(entree)
    return out


def effacer_lots(camp: Campagne, prefixes: str) -> None:
    """Retire les lots d'une préparation précédente de la même passe (préfixes D et L, ou R et C)."""
    for p in (camp.verification / "lots").glob("*.json"):
        if re.fullmatch(rf"[{prefixes}]\d+", p.stem):
            p.unlink()


def registres(cfg: dict) -> str:
    pays = [p.upper() for p in [*cfg["cible"]["pays"], *cfg["cible"]["pays_voisins"]]]
    vus = [f"{p} : {REGISTRES[p]}" for p in dict.fromkeys(pays) if p in REGISTRES]
    return " ; ".join(vus) or "le registre du commerce du pays de l'entreprise"


def args_workflow(camp: Campagne, manifeste: list[dict]) -> dict:
    """Les args du workflow : chemins absolus, contexte tiré de campagne.toml."""
    cfg = camp.config
    cible = (cfg["cible"]["description"] or "").strip()
    if not cible:
        pays = ", ".join(cfg["cible"]["pays"]) or "non précisés"
        cible = f"entreprises de la liste de la campagne {camp.nom} (pays visés : {pays})"
        print("! cible.description est vide dans campagne.toml : les agents n'auront qu'une cible vague "
              "(README.md, « Fichiers à compléter »)", file=sys.stderr)
    offre = cfg["offre"]
    contexte = " : ".join(x for x in (offre["societe"].strip(), offre["description"].strip()) if x)
    return {"racine": str(Path.cwd()), "campagne": str(camp.dossier), "python": sys.executable, "skill": str(SKILL),
            "cible": cible, "contexte": contexte, "registres": registres(cfg), "batches": manifeste}


def ecrire_manifeste(camp: Campagne, passe: int, manifeste: list[dict]) -> tuple[Path, Path]:
    m = camp.verification / MANIFESTES[passe]
    m.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1), encoding="utf-8")
    a = camp.verification / f"args-passe{passe}.json"
    a.write_text(json.dumps(args_workflow(camp, manifeste), ensure_ascii=False, indent=1), encoding="utf-8")
    return m, a


def resume(manifeste: list[dict], passe: int, workflow: str, a: Path) -> None:
    n = sum(b["n"] for b in manifeste)
    for b in manifeste:
        print(f"  {b['id']} {b['mode']:8} {b['n']:3}  {b['file']}")
    t = n * TOKENS_PAR_ENTITE[passe]
    t = f"{t / 1e6:.1f} M" if t >= 1e6 else f"{round(t / 1000)} k"
    print(f"{len(manifeste)} lots, {n} entités ; ordre de grandeur : {t} tokens de sous-agents (repère : environ "
          f"{TOKENS_PAR_ENTITE[passe]} par entité). Multi-agents : accord explicite de l'utilisateur avant de lancer.")
    print(f"Lancer : outil Workflow, scriptPath = {SKILL / 'workflows' / workflow}, args = contenu de {a}")


def extrait(r: dict, n: int = 400) -> dict:
    """Champs non vides d'une ligne, textes longs coupés."""
    return {c: (r[c] if len(r[c]) <= n else r[c][:n] + "...") for c in CHAMPS_LOT if (r.get(c) or "").strip()}


# ---------------------------------------------------------------- passe 1

def main() -> None:
    ap = argparse.ArgumentParser(description="Étape 4, passe 1 : prépare les lots de vérification par agents.")
    argument_campagne(ap)
    ap.add_argument("--mode", choices=["auto", "leger", "profond"], default="auto",
                    help="auto : solides en contrôle léger, le reste en profondeur (défaut) ; leger : toute entité "
                         "avec un site, sauf à revoir, en contrôle léger ; profond : tout en profondeur")
    ap.add_argument("--taille-profond", type=int, default=25, help="entités par lot profond (défaut 25)")
    ap.add_argument("--taille-leger", type=int, default=90, help="entités par lot léger (défaut 90)")
    ap.add_argument("--max", type=int, default=0, help="ne garder que les N entités les plus incertaines (essai)")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    base = liste_de_base(camp)
    ents = entites_de(lire_csv(base))
    stats, profond, leger, exclues = Counter(), [], [], Counter()
    for e in ents.values():
        lignes = e["lignes"]
        r = lignes[0]
        motif = next((l["exclure"] for l in lignes if (l.get("exclure") or "").strip()), "")
        if motif:
            exclues[motif.split(" (")[0]] += 1
            continue
        # plusieurs lignes sous la même clé : la plus douteuse décide (verif_appliquer étend le résultat à toutes)
        cat = min((categorie(l) for l in lignes), key=CATEGORIES.index)
        stats[cat] += 1
        fiche = {"key": e["key"], **{k: v for k, v in extrait(r).items() if k != "nom" or v != e["key"]},
                 "categorie": cat}
        if len(lignes) > 1:
            fiche["lignes"] = len(lignes)
        if a.mode == "leger":
            leg = all(l.get("site") and l.get("a_revoir") != "oui" for l in lignes)
        else:
            leg = a.mode == "auto" and cat == "solide"
        (leger if leg else profond).append((-max(incertitude(l) for l in lignes), e["rang"], fiche))
    profond.sort(key=lambda t: t[:2])
    leger.sort(key=lambda t: t[:2])
    if a.max:
        garde = {t[2]["key"] for t in sorted(profond + leger, key=lambda t: t[:2])[:a.max]}
        profond = [t for t in profond if t[2]["key"] in garde]
        leger = [t for t in leger if t[2]["key"] in garde]

    effacer_lots(camp, "DL")
    manifeste = (ecrire_lots(camp, repartir([t[2] for t in profond], a.taille_profond), "D", "deep")
                 + ecrire_lots(camp, repartir([t[2] for t in leger], a.taille_leger), "L", "light"))
    m, fa = ecrire_manifeste(camp, 1, manifeste)

    print(f"Liste : {base.name}, {len(ents)} entités ; catégories : "
          + ", ".join(f"{c} {stats[c]}" for c in CATEGORIES if stats[c]))
    if exclues:
        print("Non vérifiées (colonne exclure) : " + ", ".join(f"{k} {v}" for k, v in exclues.most_common()))
    print(f"Mode {a.mode} : {len(profond)} en profondeur, {len(leger)} en contrôle léger"
          + (f" (--max {a.max})" if a.max else ""))
    if not manifeste:
        print("Rien à vérifier.")
        return
    print(f"Manifeste : {m}")
    resume(manifeste, 1, "verification.js", fa)


if __name__ == "__main__":
    main()
