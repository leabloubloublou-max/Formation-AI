"""Étape 5 : actualités et mentions web (DuckDuckGo via ddgs) des entreprises dans le périmètre ICP.

Périmètre : entreprises sans motif d'exclusion et de fit au moins --fit-min (5 par défaut) selon icp.qualify. À lancer
après collect_zefix.py (Suisse), collect_linkedin.py et collect_site.py, qui affinent zone, taille et secteur.
Par entreprise, dans sa langue (en Suisse, celle de la localité ; ailleurs, celle du pays) et dans la région
DuckDuckGo de son pays (commun.region_recherche) :
  q1  actualités datées du nom ;
  q2  nom + nomination / nouveau CEO / Geschäftsführer ;
  q3  nom + levée de fonds / rachat / Finanzierungsrunde / Übernahme ;
  q4  nom + intelligence artificielle / digitalisation / KI.
Noms ambigus (4 caractères ou moins, ou listés dans <campagne>/noms-ambigus.csv, colonne nom, facultatif) : la ville
ou le pays est ajouté à la requête.
Filtre anti-homonymes : le résultat doit citer un mot distinctif du nom (ou le domaine du site).
Chaque résultat passe dans le lexique -> signaux CANDIDATS (à confirmer par les agents), sur signaux.fenetre_mois.

Sortie : donnees/signaux/news.json (cache repris : une relance ne traite que les nouvelles entreprises).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_news.py --campagne campagnes/<nom> \\
      [--workers 3] [--refresh] [--fit-min 5]
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from auto import AGREGATEURS
from commun import LANGUES_PAYS, Campagne, argument_campagne, lire_csv, region_recherche
from icp import langue_suisse, qualify
from lexique import detect
from signaux_commun import (Store, clip, config, ddg, domain, donnees, fenetre_mois, iso, langue_principale,
                            load_entities, load_json, months_ago, name_tokens, norm, ouvrir, parse_date, polite_sleep,
                            short_name, to_date)

KW = {
    "fr": ("nomination directeur général CEO", "levée de fonds rachat acquisition", "intelligence artificielle digitalisation"),
    "de": ("neuer CEO Geschäftsführer", "Finanzierungsrunde Übernahme", "künstliche Intelligenz Digitalisierung"),
    "it": ("nuovo CEO direttore generale", "acquisizione finanziamento", "intelligenza artificiale"),
    "en": ("new CEO appointed", "funding round acquisition", "artificial intelligence"),
}
# nom du pays dans la langue des requêtes : précise un nom ambigu et sert d'indice anti-homonymes
NOMS_PAYS = {
    "CH": {"fr": "Suisse", "de": "Schweiz", "it": "Svizzera", "en": "Switzerland"},
    "FR": {"fr": "France", "de": "Frankreich", "it": "Francia", "en": "France"},
    "DE": {"fr": "Allemagne", "de": "Deutschland", "it": "Germania", "en": "Germany"},
    "AT": {"fr": "Autriche", "de": "Österreich", "it": "Austria", "en": "Austria"},
    "IT": {"fr": "Italie", "de": "Italien", "it": "Italia", "en": "Italy"},
    "BE": {"fr": "Belgique", "de": "Belgien", "it": "Belgio", "en": "Belgium"},
    "LU": {"fr": "Luxembourg", "de": "Luxemburg", "it": "Lussemburgo", "en": "Luxembourg"},
    "LI": {"fr": "Liechtenstein", "de": "Liechtenstein", "it": "Liechtenstein", "en": "Liechtenstein"},
}


def lang_of(q: dict, e: dict | None = None, z: dict | None = None, li: dict | None = None) -> str:
    """Langue des requêtes : en Suisse, celle de la localité (siège, ville ; localité bilingue : celle de l'appelant
    si elle y est parlée) ou du canton (icp.langue_suisse) ; ailleurs, celle du pays."""
    if q["pays"] == "CH":
        lg = langue_suisse([(z or {}).get("siege", ""), (e or {}).get("ville", ""), (li or {}).get("ville", "")],
                           q.get("canton", ""))
        return lg or (langue_principale() if langue_principale() in KW else "fr")
    lg = LANGUES_PAYS.get(q["pays"], "")
    return lg if lg in KW else "en"


def search_name(e: dict, li: dict) -> str:
    n = short_name(li.get("nom") or "") if li.get("nom") else ""
    if not n or len(norm(n)) < 3 or len(n) > 40:
        n = e["nom_court"]
    return n


def noms_ambigus(camp: Campagne) -> set[str]:
    """Noms à préciser par la ville ou le pays : <campagne>/noms-ambigus.csv (colonne nom), facultatif."""
    f = camp.fichier("noms-ambigus.csv")
    if not f.exists():
        return set()
    return {norm(r.get("nom") or next(iter(r.values()), "")) for r in lire_csv(f)} - {""}


BRUIT = ("tiktok.", "reverso.", "dailymotion.", "youtube.", "instagram.", "facebook.", "pinterest.", "tesnotes.",
         "wikipedia.", "wiktionary.", "spotify.", "music.", "lyrics", "imdb.")
LEGAL_SUFFIX = ("sa", "ag", "gmbh", "sarl", "ltd", "srl", "sas", "inc")


def relevant(r: dict, toks: set[str], dom: str, cues: set[str]) -> bool:
    url = (r.get("href") or r.get("url") or "").lower()
    if any(b in url for b in BRUIT):
        return False
    blob = norm(" ".join([r.get("title", ""), r.get("body", ""), url]))
    label = dom.split(".")[0].replace("-", "") if dom else ""
    if label and len(label) >= 4 and label in blob.replace(" ", ""):
        return True
    words = blob.split()
    ws = set(words)
    if not toks or not (toks & ws):
        return False
    if len(toks) >= 2:
        return len(toks & ws) >= 2
    # nom d'un seul mot : il faut un indice de plus (ville, forme juridique accolée, secteur, pays)
    t = next(iter(toks))
    if any(words[i] == t and i + 1 < len(words) and words[i + 1] in LEGAL_SUFFIX for i in range(len(words))):
        return True
    return bool(cues & ws)


def collect(e: dict, q: dict, li: dict, z: dict | None = None, ambigus: set[str] | frozenset = frozenset()) -> dict:
    lang = lang_of(q, e, z, li)
    region = region_recherche(q["pays"], lang)
    name = search_name(e, li)
    toks = set(name_tokens(name))
    quoted = f'"{name}"'
    pays_noms = [q["pays"]] if q["pays"] else sorted(set(config()["cible"].get("pays") or []))
    if norm(name) in ambigus or len(norm(name).replace(" ", "")) <= 4:
        lieu = li.get("ville") or e.get("ville") or NOMS_PAYS.get(q["pays"], {}).get(lang, "")
        quoted = f'"{name}" {lieu}'.strip()
    dom = domain(e.get("site", ""))
    cues = set(norm(" ".join([li.get("ville", ""), e.get("ville", ""), li.get("region", ""), q.get("canton", ""),
                              e.get("activite", ""), li.get("secteur", "")])).split()) - {"de", "et", "la", "le", "des", "du", "en", "and", "of"}
    cues = {c for c in cues if len(c) >= 4} | {"entreprise", "company", "firma"}
    cues |= {norm(n) for p in pays_noms for n in NOMS_PAYS.get(str(p).upper(), {}).values()}
    kw = KW[lang]
    queries = [("news", quoted), ("text", f"{quoted} {kw[0]}"), ("text", f"{quoted} {kw[1]}"), ("text", f"{quoted} {kw[2]}")]
    results, seen = [], set()
    for kind, qq in queries:
        res = ddg(qq, kind=kind, n=20 if kind == "news" else 10, region=region)
        for r in res:
            url = r.get("url") or r.get("href") or ""
            if not url or url in seen or not relevant(r, toks, dom, cues):
                continue
            seen.add(url)
            d = to_date(r.get("date")) if r.get("date") else parse_date(r.get("body", "") + " " + r.get("title", ""))
            results.append({"requete": qq, "type": kind, "date": iso(d), "titre": clip(r.get("title", ""), 160),
                            "extrait": clip(r.get("body", ""), 300), "url": url, "source": r.get("source", "")})
        polite_sleep(1.0, 2.2)
    signaux = []
    for r in results:
        d = to_date(r["date"])
        if (d and months_ago(d) > fenetre_mois()) or any(a in r["url"].lower() for a in AGREGATEURS):
            continue
        for h in detect(f"{r['titre']}. {r['extrait']}"):
            signaux.append({**h, "date": r["date"], "source": f"web_{r['type']}", "url": r["url"], "titre": r["titre"]})
    return {"nom_recherche": name, "langue": lang, "region": region, "requetes": [q for _, q in queries],
            "resultats": results[:40], "signaux": signaux, "collecte": datetime.now().isoformat(timespec="seconds")}


def main() -> None:
    ap = argparse.ArgumentParser(description="Actualités web (DuckDuckGo) des entreprises du périmètre ICP.")
    argument_campagne(ap)
    ap.add_argument("--workers", type=int, default=3, help="entreprises en parallèle (défaut 3)")
    ap.add_argument("--refresh", action="store_true", help="refait toutes les entreprises (sinon : seulement les nouvelles)")
    ap.add_argument("--fit-min", type=float, default=5.0, help="fit ICP minimal (sur 9) pour entrer dans le périmètre (défaut 5)")
    a = ap.parse_args()
    camp = ouvrir(a.campagne)
    ambigus = noms_ambigus(camp)
    store = Store(donnees() / "news.json")
    zf, lk, st = (load_json(donnees() / f"{n}.json", {}) or {} for n in ("zefix", "linkedin", "site"))
    todo, hors = [], 0
    for e in load_entities():
        q = qualify(e, zf.get(e["id"]), lk.get(e["id"]), st.get(e["id"]))
        if q["motifs_exclusion"] or q["fit"] < a.fit_min:
            hors += 1
            continue
        if a.refresh or e["id"] not in store:
            li = lk.get(e["id"]) if (lk.get(e["id"]) or {}).get("statut") == "ok" else {}
            todo.append((e, q, li or {}, zf.get(e["id"]) or {}))
    print(f"{len(todo)} entreprises à rechercher ({hors} hors périmètre : motif d'exclusion ou fit < {a.fit_min:g})",
          flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(collect, e, q, li, z, ambigus): e for e, q, li, z in todo}
        for i, f in enumerate(as_completed(futs), 1):
            e = futs[f]
            try:
                rec = f.result()
            except Exception as err:  # noqa: BLE001
                rec = {"erreur": f"{err.__class__.__name__}: {str(err)[:120]}", "resultats": [], "signaux": []}
            store.put(e["id"], rec, flush_every=5)
            fam = sorted({f"{s['famille']}/{s['sous_type']}" for s in rec.get("signaux", []) if s["famille"] != "tech"})
            print(f"[{i}/{len(todo)}] {e['id']} -> {len(rec.get('resultats', []))} résultats | {', '.join(fam)[:150]}", flush=True)
    store.flush()


if __name__ == "__main__":
    main()
