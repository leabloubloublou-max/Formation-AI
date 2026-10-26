"""Outils compacts pour les agents du workflow de recherche de signaux (sorties courtes, environ 1 000 tokens).

N'écrit aucun fichier, sans clé ni compte. Usage (depuis la racine du projet ; S = .claude/skills/prospection-base-client) :
    .venv/bin/python $S/scripts/outils_signaux.py zefix "<nom de société>" [--langue fr]
        registre du commerce suisse : fiche, absorptions et publications officielles récentes (Suisse seulement)
    .venv/bin/python $S/scripts/outils_signaux.py li <url linkedin company>
        profil LinkedIn public et derniers posts datés
    .venv/bin/python $S/scripts/outils_signaux.py news "<requête>" [--region ch-fr]
        actualités datées (DuckDuckGo)
Compléments : $S/scripts/outils_web.py search "<requête>" | peek <url> | linkedin "<nom>".
Hors de Suisse, pas de sous-commande registre : chercher le registre du pays avec outils_web.py search.
--region : région DuckDuckGo (ch-fr, ch-de, fr-fr, de-de...) ou code pays à deux lettres (CH, FR...) ; défaut wt-wt.
La sous-commande zefix affiche l'URL de la fiche, à citer comme source d'un signal du registre.
"""
from __future__ import annotations

import argparse
import sys

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

API = "https://www.zefix.ch/ZefixREST/api/v1"


def region_ddg(valeur: str | None) -> str:
    """'ch-fr' tel quel ; 'CH' -> région du pays (commun.region_recherche) ; vide -> wt-wt (monde)."""
    from commun import region_recherche
    v = (valeur or "").strip()
    if not v:
        return "wt-wt"
    return v.lower() if "-" in v else region_recherche(v)


def cmd_zefix(name: str, langue: str) -> None:
    import collect_zefix as z
    from signaux_commun import clip, session
    try:
        r = session().post(f"{API}/firm/search.json", json={"name": name, "languageKey": langue, "maxEntries": 15,
                                                            "deletedFirms": True},
                           headers={"Accept": "application/json"}, timeout=20)
        lst = (r.json().get("list") or []) if r.ok else []
    except Exception as e:  # noqa: BLE001 (réseau, réponse illisible)
        print(f"(registre indisponible : {clip(str(e), 120)})")
        return
    if not lst:
        print("(aucune société trouvée ; essayer un nom plus court, sans ponctuation)")
        return
    for f in lst[:8]:
        print(f"- {f['name']} | {f['legalSeat']} | {f['status']} | radiation {f.get('deleteDate') or '-'} | ehraid {f['ehraid']}")
    best = max(lst, key=lambda f: z.score(name, f))   # meilleure correspondance (existante de préférence)
    try:
        firm = session().get(f"{API}/firm/{best['ehraid']}.json", timeout=25).json()
    except Exception as e:  # noqa: BLE001
        print(f"(fiche indisponible : {clip(str(e), 120)})")
        return
    print(f"\n== {firm.get('name')} ({firm.get('legalSeat')}) {firm.get('uidFormatted')} état {firm.get('status')}")
    print(f"url : https://www.zefix.ch/{langue}/search/entity/list/firm/{best['ehraid']}")
    print(f"but : {clip(firm.get('purpose') or '', 300)}")
    if firm.get("hasTakenOver"):
        print("a absorbé : " + ", ".join(x.get("name", "") for x in firm["hasTakenOver"]))
    if firm.get("wasTakenOverBy"):
        print("absorbée par : " + ", ".join(x.get("name", "") for x in firm["wasTakenOverBy"]))
    for ev in z.events_from(firm)[:12]:
        pers = "; ".join(f"{p['action']} {p['nom']} ({p['role'] or p['niveau'] or '?'})"
                         for p in ev["personnes"] if p["niveau"] != "revision")
        extra = []
        if ev.get("capital"):
            c = ev["capital"]
            extra.append(f"capital {c['ancien']} -> {c['nouveau']} {c['devise']}")
        for k in ("fusion", "raison_sociale", "siege", "but", "dissolution", "radiation", "kapitalband"):
            if ev.get(k):
                extra.append(k)
        print(f"[{ev['date']}] {pers or '-'} {' | '.join(extra)}")
        if not pers and not extra:
            print(f"    {clip(ev['texte'], 220)}")


def cmd_li(url: str) -> None:
    import collect_linkedin as cl
    from signaux_commun import clip
    u = cl.canon(url) or url
    st, d = cl.fetch(u)
    if not d:
        print(f"statut : {st} ({u})")
        return
    print(f"{d['nom']} | {d['secteur']} | {d['taille']} | {d.get('salaries_linkedin')} salariés sur LinkedIn | "
          f"{d.get('abonnes')} abonnés | {d['siege']} | fondée {d['fondation']}")
    print(f"site : {d.get('site')} | spécialités : {clip(d.get('specialites', ''), 200)}")
    print(f"description : {clip(d.get('description', ''), 400)}")
    for p in d["posts"][:10]:
        print(f"- [{p['date']}] {clip(p['texte'], 260)} ({p['url']})")


def cmd_news(query: str, region: str) -> None:
    from signaux_commun import clip, ddg
    res = ddg(query, kind="news", n=15, region=region)
    if not res:
        print("(aucune actualité)")
    for r in res:
        print(f"- [{(r.get('date') or '')[:10]}] {clip(r.get('title'), 110)} | {r.get('source', '')} | {r.get('url')}\n"
              f"    {clip(r.get('body'), 200)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Outils du registre suisse, de LinkedIn et des actualités pour les agents "
                                             "de recherche de signaux (workflows/signaux-recherche.js).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zefix", help="registre du commerce suisse : fiche et publications récentes")
    z.add_argument("name", help="nom de la société")
    z.add_argument("--langue", default="fr", choices=["fr", "de", "it", "en"], help="langue des libellés (défaut fr)")
    sub.add_parser("li", help="profil LinkedIn public et derniers posts").add_argument("url")
    n = sub.add_parser("news", help="actualités datées (DuckDuckGo)")
    n.add_argument("query")
    n.add_argument("--region", help="région DuckDuckGo (ch-fr, de-de...) ou code pays (CH, FR...) ; défaut wt-wt")
    a = ap.parse_args()
    if a.cmd == "zefix":
        cmd_zefix(a.name, a.langue)
    elif a.cmd == "li":
        cmd_li(a.url)
    else:
        cmd_news(a.query, region_ddg(a.region))


if __name__ == "__main__":
    sys.exit(main())
