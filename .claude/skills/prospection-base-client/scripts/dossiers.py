"""Étape 5 : dossiers compacts par entreprise (périmètre ICP) et lots pour les agents de recherche.

Chaque dossier réunit ce que les collecteurs ont trouvé (registre du commerce, LinkedIn, site, actualités) avec les
signaux CANDIDATS déjà détectés ; l'agent de recherche confirme, complète, date et source, puis un contre-vérificateur
tente de réfuter les signaux forts (workflows/signaux-recherche.js).
Périmètre : aucun motif d'exclusion (icp.qualify) et fit au moins --fit-min, comme collect_news.py. Priorité :
fit + 0,2 x min(signaux candidats, 6) ; les dossiers sont répartis en tourniquet entre les lots (charge équilibrée,
priorités réparties).

Entrées : donnees/signaux/entites.json (entites.py), zefix.json, linkedin.json, site.json, news.json (facultatifs) ;
avec --complement : lots/manifest.json et recherche.json (entreprises déjà confiées aux agents).
Sorties, dans <campagne>/donnees/signaux/lots/ :
  - L01.json, L02.json... : les dossiers de chaque lot (clés citées par le prompt du workflow : site_web, icp_pre,
    registre, linkedin_profil, linkedin_posts, site, actualites, signaux_web_candidats, signaux_linkedin_candidats) ;
  - manifest.json : [{id, n, file (chemin absolu), ids[]}] ;
  - args-recherche.json : les args complets du workflow (racine, campagne, python, skill, lots, date_reference,
    fenetre_mois, offre, cible, exclusions, concurrents, categories, langue, zone, taille, persona...), à passer
    tels quels à l'outil Workflow. En mode --complement, seulement les nouveaux lots.
Attention : sans --complement, les lots précédents (L*.json, manifeste, args) sont effacés. Si campagne.toml ne dit pas
qui prospecte ni pour vendre quoi (offre.societe et offre.description vides), le script s'arrête avant tout effacement :
le workflow refuserait ces args.

Usage (depuis la racine du projet, celle qui contient .venv) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/dossiers.py --campagne campagnes/<nom>
      [--lots N | --par-lot 15] [--fit-min 5] [--complement] [--max N]
Ensuite, avec l'accord de l'utilisateur (multi-agents) : outil Workflow, scriptPath =
<skill>/workflows/signaux-recherche.js, args = contenu de args-recherche.json ; puis apply_recherche.py.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

# repère mesuré sur une campagne réelle : tokens de sous-agents par entreprise, contre-vérification comprise
TOKENS_PAR_ENTREPRISE = 35000
LANGUES = {"fr": "français", "de": "allemand", "it": "italien", "en": "anglais", "es": "espagnol", "pt": "portugais",
           "nl": "néerlandais"}


def recent(sigs: list[dict], months: int, dated_only: bool = False) -> list[dict]:
    from signaux_commun import months_ago, to_date
    out = []
    for s in sigs:
        d = to_date(s.get("date"))
        if d is None and dated_only:
            continue
        if d is not None and months_ago(d) > months:
            continue
        out.append(s)
    return out


def url_registre(z: dict) -> str:
    """URL de la fiche au registre (celle des signaux, sinon reconstruite depuis l'identifiant Zefix)."""
    for s in z.get("signaux") or []:
        if s.get("url"):
            return s["url"]
    if z.get("ehraid"):
        from collect_zefix import langue
        return f"https://www.zefix.ch/{langue()}/search/entity/list/firm/{z['ehraid']}"
    return ""


def dossier(e: dict, q: dict, z: dict, li: dict, site: dict, news: dict) -> dict:
    import auto
    from signaux_commun import clip, fenetre_mois
    li = li if li.get("statut") == "ok" else {}
    site = site if site.get("statut") == "ok" else {}
    d = {
        "id": e["id"], "nom": e["nom"], "site_web": e.get("site", ""), "linkedin": li.get("url") or e.get("linkedin", ""),
        "icp_pre": {k: q[k] for k in ("pays", "canton", "secteur", "taille", "fit")},
        "activite_liste": e.get("activite", ""),
    }
    if e.get("ville"):
        d["ville"] = e["ville"]
    if e.get("autres_noms"):
        d["autres_noms"] = e["autres_noms"][:4]
    if li:
        d["linkedin_profil"] = {k: li.get(k) for k in ("nom", "secteur", "taille", "salaries_linkedin", "abonnes", "siege",
                                                       "fondation", "posts_90j", "dernier_post")}
        d["linkedin_profil"]["specialites"] = clip(li.get("specialites", ""), 200)
        d["linkedin_profil"]["description"] = clip(li.get("description", ""), 350)
        d["linkedin_posts"] = [{"date": p["date"], "texte": clip(p["texte"], 240), "url": p["url"]}
                               for p in sorted(li.get("posts", []), key=lambda p: p["date"], reverse=True)[:6]]
    if z.get("statut") in ("ok", "ambigu"):
        d["registre"] = {"statut_correspondance": z["statut"], "nom": z.get("nom"), "uid": z.get("uid"),
                         "siege": z.get("siege"), "canton": z.get("canton"), "etat": z.get("etat"),
                         "radiation": z.get("radiation"), "but": clip(z.get("but", ""), 250), "url": url_registre(z),
                         "evenements": [{"date": s["date"], "type": f"{s['famille']}/{s['sous_type']}",
                                         "resume": s["resume"]} for s in z.get("signaux", [])][:12]}
    elif z.get("statut"):
        d["registre"] = {"statut_correspondance": z["statut"],
                         "candidats": [f"{x['nom']} ({x['siege']}, {x['statut']})" for x in z.get("candidats", [])[:3]]}
    if site:
        d["site"] = {"url": site.get("url"), "stack": site.get("stack"), "langues": site.get("langues"),
                     "derniere_date": site.get("derniere_date"), "carrieres": site.get("carrieres") or {},
                     "mentions_tech": site.get("tech"),
                     "signaux_dates": [{"date": s["date"], "type": f"{s['famille']}/{s['sous_type']}", "terme": s["terme"],
                                        "extrait": clip(s["extrait"], 200), "url": s["url"]}
                                       for s in recent(auto.site(site), fenetre_mois(), dated_only=True)
                                       if s["famille"] != "tech" and s["source"] != "site_a_propos"][:6]}
    if news:
        d["actualites"] = [{"date": r["date"], "titre": r["titre"], "url": r["url"]}
                           for r in sorted(news.get("resultats", []), key=lambda r: r["date"] or "0", reverse=True)[:10]]
        d["signaux_web_candidats"] = [{"date": s["date"], "type": f"{s['famille']}/{s['sous_type']}", "terme": s["terme"],
                                       "titre": clip(s.get("titre", ""), 120), "url": s["url"]}
                                      for s in auto.news(news) if s["famille"] != "tech"][:10]
    if li:
        d["signaux_linkedin_candidats"] = [{"date": s["date"], "type": f"{s['famille']}/{s['sous_type']}", "terme": s["terme"],
                                            "extrait": clip(s["extrait"], 200), "url": s["url"]}
                                           for s in auto.linkedin(li) if s["famille"] != "tech"][:8]
        d["tech_posts"] = li.get("tech_posts")
    return d


# ---------------------------------------------------------------- args du workflow

def _n(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def zone_texte(cfg: dict) -> str:
    c = cfg["cible"]
    pays = ", ".join(str(p) for p in c.get("pays") or [])
    if not pays:
        return "pas de zone imposée"
    out = f"pays visés : {pays}"
    if c.get("regions_prioritaires"):
        out += f" (régions prioritaires : {', '.join(str(r) for r in c['regions_prioritaires'])})"
    if c.get("pays_voisins"):
        out += f" ; pays voisins acceptés : {', '.join(str(p) for p in c['pays_voisins'])} ; tout autre pays est hors zone"
    else:
        out += " ; tout autre pays est hors zone"
    return out


def taille_texte(cfg: dict) -> str:
    c = cfg["cible"]
    return (f"effectif idéal de {_n(float(c['taille_min']))} à {_n(float(c['taille_max']))} personnes ; au-delà de "
            f"{_n(float(c['taille_limite']))} personnes : grand groupe, hors cible")


def contexte_workflow(camp) -> dict:
    """Les args de workflows/signaux-recherche.js sauf les lots : chemins absolus, contexte tiré de campagne.toml.
    Arrête le script (avant d'effacer quoi que ce soit) si un argument obligatoire du workflow manque."""
    from commun import SKILL
    from icp import categories
    from persona import Persona
    from signaux_commun import aujourdhui, fenetre_mois, langue_principale
    from verif_preparer import registres
    cfg = camp.config
    offre, cible = cfg["offre"], cfg["cible"]
    texte_offre = " : ".join(x for x in (str(offre["societe"]).strip(), str(offre["description"]).strip()) if x)
    if not texte_offre:
        raise SystemExit(f"offre.societe et offre.description sont vides dans {camp.fichier('campagne.toml')} : le "
                         "workflow de recherche les exige (qui prospecte, pour vendre quoi). Complétez-les "
                         "(README.md, « Fichiers à compléter »), puis relancez. Rien n'a été modifié.")
    if fenetre_mois() < 1:
        raise SystemExit("signaux.fenetre_mois doit être un nombre entier de mois, 1 ou plus "
                         f"({camp.fichier('campagne.toml')}). Rien n'a été modifié.")
    if not str(offre["description"]).strip():
        print("! offre.description est vide dans campagne.toml : les agents ne sauront pas ce que vous vendez "
              "(angle, concurrents ; README.md, « Fichiers à compléter »)", file=sys.stderr)
    texte_cible = (cible["description"] or "").strip()
    if not texte_cible:
        texte_cible = f"entreprises de la liste de la campagne {camp.nom} ({zone_texte(cfg)})"
        print("! cible.description est vide dans campagne.toml : les agents n'auront qu'une cible vague "
              "(README.md, « Fichiers à compléter »)", file=sys.stderr)
    P = Persona(cfg)
    langue = langue_principale()
    # registre suisse utile si la zone est libre ou si la Suisse est visée (pays ou voisins)
    pays = {str(p).upper() for p in [*(cible.get("pays") or []), *(cible.get("pays_voisins") or [])]} \
        if cible.get("pays") else set()
    return {
        "racine": str(Path.cwd()), "campagne": str(camp.dossier), "python": sys.executable, "skill": str(SKILL),
        "date_reference": aujourdhui().isoformat(), "fenetre_mois": fenetre_mois(),
        "offre": texte_offre, "cible": texte_cible,
        "exclusions": [str(x) for x in cible.get("exclusions") or []],
        "concurrents": (offre.get("concurrents") or "").strip(),
        "categories": list(categories()),
        "langue": LANGUES.get(langue, langue),
        "zone": zone_texte(cfg), "taille": taille_texte(cfg),
        "persona": {"entree": P.libelle(P.entree), "relais": [P.libelle(f) for f in P.relais]},
        "cas_usage": [str(p.get("cas")) for p in offre.get("preuves") or [] if isinstance(p, dict) and p.get("cas")],
        "registre_suisse": bool(cfg["signaux"].get("registre_suisse")) and (not pays or "CH" in pays),
        "registres": registres(cfg),
    }


def args_workflow(contexte: dict, lots: list[dict]) -> dict:
    """Le contexte (contexte_workflow) avec les lots, placés après les chemins."""
    args = {}
    for k, v in contexte.items():
        args[k] = v
        if k == "skill":
            args["lots"] = [{"id": l["id"], "file": l["file"], "n": l["n"]} for l in lots]
    return args


# ---------------------------------------------------------------- main

def main() -> None:
    from commun import argument_campagne
    ap = argparse.ArgumentParser(description="Étape 5 : dossiers par entreprise et lots pour le workflow de recherche "
                                             "de signaux (donnees/signaux/lots/).")
    argument_campagne(ap)
    ap.add_argument("--lots", type=int, help="nombre de lots (défaut : un lot par tranche de --par-lot entreprises)")
    ap.add_argument("--par-lot", type=int, default=15, help="entreprises par lot quand --lots est absent (défaut 15)")
    ap.add_argument("--fit-min", type=float, default=5.0, help="fit ICP minimal sur 9 (défaut 5, comme collect_news.py)")
    ap.add_argument("--complement", action="store_true",
                    help="lots supplémentaires pour les entreprises pas encore envoyées aux agents (garde les anciens)")
    ap.add_argument("--max", type=int, help="ne garder que les N dossiers prioritaires (essai à petit coût)")
    a = ap.parse_args()

    from icp import qualify
    from signaux_commun import donnees, load_entities, load_json, ouvrir, save_json
    camp = ouvrir(a.campagne)
    contexte = contexte_workflow(camp)   # contrôle des args du workflow avant d'effacer ou d'écrire quoi que ce soit
    data = donnees()
    lots_dir = data / "lots"
    old_manifest = load_json(lots_dir / "manifest.json", []) or []
    deja = set()
    if a.complement:
        deja = {i for m in old_manifest for i in m.get("ids", [])} | set(load_json(data / "recherche.json", {}) or {})
    zf, lk, st, nw = (load_json(data / f"{n}.json", {}) or {} for n in ("zefix", "linkedin", "site", "news"))
    items = []
    for e in load_entities():
        q = qualify(e, zf.get(e["id"]), lk.get(e["id"]), st.get(e["id"]))
        if q["motifs_exclusion"] or q["fit"] < a.fit_min or e["id"] in deja:
            continue
        d = dossier(e, q, zf.get(e["id"], {}), lk.get(e["id"], {}), st.get(e["id"], {}), nw.get(e["id"], {}))
        n_sig = len(d.get("registre", {}).get("evenements", [])) + len(d.get("signaux_web_candidats", [])) \
            + len(d.get("signaux_linkedin_candidats", []))
        items.append((q["fit"] + min(n_sig, 6) * 0.2, d))
    items.sort(key=lambda x: -x[0])
    if a.max:
        items = items[:a.max]
    if not items:
        raise SystemExit(f"Aucun dossier à préparer (périmètre : aucun motif d'exclusion et fit >= {a.fit_min:g}"
                         + (", pas encore confié aux agents" if a.complement else "") + ").")

    if not a.complement:
        anciens = [p for p in lots_dir.glob("*.json") if re.fullmatch(r"L\d+", p.stem)]
        if anciens:
            print(f"! {len(anciens)} anciens lots effacés (relancer avec --complement pour les garder)")
        for p in anciens + [lots_dir / "manifest.json", lots_dir / "args-recherche.json"]:
            if p.exists():
                p.unlink()
        old_manifest = []
    n_lots = max(1, min(len(items), a.lots or math.ceil(len(items) / max(1, a.par_lot))))
    lots = [[] for _ in range(n_lots)]
    for i, (_, d) in enumerate(items):   # tourniquet : charge équilibrée, priorités réparties
        lots[i % n_lots].append(d)
    premier = max([int(m["id"][1:]) for m in old_manifest if re.fullmatch(r"L\d+", m.get("id", ""))] + [0]) + 1
    nouveaux = []
    for i, lot in enumerate([x for x in lots if x], premier):
        lid = f"L{i:02d}"
        f = lots_dir / f"{lid}.json"
        save_json(f, lot)
        nouveaux.append({"id": lid, "n": len(lot), "file": str(f.resolve()), "ids": [d["id"] for d in lot]})
    manifest = list(old_manifest) + nouveaux
    save_json(lots_dir / "manifest.json", manifest)
    args_f = lots_dir / "args-recherche.json"
    args_f.write_text(json.dumps(args_workflow(contexte, nouveaux), ensure_ascii=False, indent=1), encoding="utf-8")

    n = sum(m["n"] for m in nouveaux)
    print(f"{n} dossiers -> lots : " + ", ".join(f"{m['id']}={m['n']}" for m in nouveaux))
    t = n * TOKENS_PAR_ENTREPRISE
    t = f"{t / 1e6:.1f} M" if t >= 1e6 else f"{round(t / 1000)} k"
    print(f"Ordre de grandeur : {t} tokens de sous-agents (repère : environ {TOKENS_PAR_ENTREPRISE} par entreprise, "
          "contre-vérification comprise). Multi-agents : accord explicite de l'utilisateur avant de lancer.")
    from commun import SKILL
    print(f"Lancer : outil Workflow, scriptPath = {SKILL / 'workflows' / 'signaux-recherche.js'}, "
          f"args = contenu de {args_f}")


if __name__ == "__main__":
    main()
