"""Étape 5 : page LinkedIn publique de chaque entreprise (vue invité, sans connexion ni clé).

Récupère : secteur, tranche de taille, salariés sur LinkedIn, abonnés, siège, fondation, spécialités,
description, et les ~10 derniers posts (date exacte + texte). Les posts passent dans le lexique
(lexique.detect, sur signaux.fenetre_mois) : annonces de nomination, levée, rachat, IA / industrie 4.0, recrutement...
Si l'URL de la liste répond 404 ou est numérique, le bon slug est cherché sur DuckDuckGo et validé (site ou nom).

Ordre : pays de la cible d'abord (cible.pays, ou registre suisse trouvé), puis pays inconnu, puis pays voisins,
puis les entreprises exclues. Les entreprises d'un autre pays (hors cible.pays et pays_voisins) sont ignorées,
sauf avec --tous (traitées en dernier).
Politesse : séquentiel, 4-8 s entre pages ; si LinkedIn bloque (999 / authwall), pause puis reprise ; arrêt après
5 blocages d'affilée. Lent (environ 2 pages par minute) : ne pas lancer en même temps que des agents qui ouvrent
LinkedIn depuis la même adresse.
Cache : donnees/signaux/linkedin.json (relance = ne refait que les manquants ; --retry pour les échecs).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_linkedin.py --campagne campagnes/<nom> \\
      [--retry] [--limit N] [--tous]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import argument_campagne, code_pays
from lexique import detect, tech_counts
from signaux_commun import (HEADERS, Store, aujourdhui, clip, config, ddg, domain, donnees, fenetre_mois, iso,
                            load_entities, load_json, months_ago, name_tokens, norm, ouvrir, polite_sleep, to_date)

# nombre avec séparateur de milliers éventuel : « 10 001 », « 10.001 » (de), « 10,001 » (en), « 10'001 »
NB = r"\d{1,3}(?:[\s\u202f\xa0'\u2019.,]\d{3})+(?!\d)|\d+"
SIZE_RE = re.compile(rf"({NB})\s*(?:-|\u2013|à)\s*({NB})|"
                     rf"({NB})\s*(?:employés et plus|\+|employees or more|or more)")
FOLLOW_RE = re.compile(rf"({NB})\s*(?:abonnés|followers|Follower)")
# Libellés de la page invité (taille, secteur) en français, sinon en anglais, comme dans l'original : ce sont
# ceux que lisent parse_size et les règles de secteur d'icp.py. Indépendant de appels.langues.
ACCEPT_LANGUAGE = "fr,en;q=0.8,de;q=0.6"


def to_int(s: str) -> int | None:
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def parse_size(txt: str) -> tuple[int | None, int | None]:
    m = SIZE_RE.search(txt or "")
    if not m:
        return None, None
    if m.group(3):
        return to_int(m.group(3)), None
    return to_int(m.group(1)), to_int(m.group(2))


def canon(url: str) -> str | None:
    m = re.search(r"linkedin\.com/(company|school|showcase)/([^/?#]+)", url or "", re.I)
    return f"https://www.linkedin.com/{m.group(1).lower()}/{m.group(2)}/" if m else None


def parse(html: str) -> dict | None:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    org, posts = {}, []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        for node in d.get("@graph", [d]) if isinstance(d, dict) else []:
            t = node.get("@type")
            if t in ("Organization", "EducationalOrganization", "Corporation"):
                org = node
            elif t == "SocialMediaPosting":
                posts.append({
                    "date": (node.get("datePublished") or "")[:10],
                    "auteur": (node.get("author") or {}).get("name", ""),
                    "texte": clip(node.get("text") or "", 1500),
                    "url": node.get("url") or node.get("mainEntityOfPage") or "",
                    "likes": ((node.get("interactionStatistic") or {}).get("userInteractionCount")),
                })
    if not org and not soup.select('[data-test-id^="about-us__"]'):
        return None
    about = {}
    for div in soup.select('[data-test-id^="about-us__"]'):
        key = div.get("data-test-id").split("__", 1)[1]
        dd = div.find("dd")
        val = dd.get_text(" ", strip=True) if dd else div.get_text(" ", strip=True)
        about[key] = clip(val, 400)
    text = soup.get_text(" ", strip=True)
    fm = FOLLOW_RE.search(text)
    addr = org.get("address") or {}
    size_txt = about.get("size", "")
    smin, smax = parse_size(size_txt)
    emp = (org.get("numberOfEmployees") or {}).get("value")
    return {
        "nom": org.get("name") or (soup.title.get_text(strip=True).split("|")[0].strip() if soup.title else ""),
        "description": clip(org.get("description") or about.get("description", ""), 1200),
        "secteur": about.get("industry", ""),
        "taille": size_txt,
        "taille_min": smin, "taille_max": smax,
        "salaries_linkedin": emp,
        "abonnes": to_int(fm.group(1)) if fm else None,
        "siege": about.get("headquarters", ""),
        "ville": addr.get("addressLocality", ""), "region": addr.get("addressRegion", ""),
        "pays": addr.get("addressCountry", ""),
        "fondation": about.get("foundedOn", ""),
        "specialites": about.get("specialties", ""),
        "site": (re.findall(r"https?://\S+", about.get("website", "")) or [""])[0],
        "type": about.get("organizationType", ""),
        "posts": posts,
    }


def analyse(p: dict) -> dict:
    """Cadence de publication + signaux détectés dans les posts (fenêtre signaux.fenetre_mois, 24 mois par défaut)."""
    dates = sorted((d for d in (to_date(x["date"]) for x in p["posts"] if x.get("date")) if d), reverse=True)
    jour = aujourdhui()
    p["dernier_post"] = iso(dates[0]) if dates else ""
    p["posts_90j"] = sum(1 for d in dates if (jour - d).days <= 90)
    p["posts_365j"] = sum(1 for d in dates if (jour - d).days <= 365)
    sig, tech = [], {}
    for x in p["posts"]:
        d = to_date(x.get("date"))
        if not d or months_ago(d) > fenetre_mois():
            continue
        for h in detect(x["texte"]):
            sig.append({**h, "date": x["date"], "source": "linkedin_post", "url": x["url"]})
        for k, v in tech_counts(x["texte"]).items():
            tech[k] = tech.get(k, 0) + v
    p["signaux"] = sig
    p["tech_posts"] = tech
    return p


def fetch(url: str) -> tuple[str, dict | None]:
    """Requête SANS cookies : avec une session réutilisée, LinkedIn répond 999 dès la 2e page."""
    import requests
    try:
        r = requests.get(url, headers={**HEADERS, "Accept-Language": ACCEPT_LANGUAGE}, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return "erreur_reseau", None
    if r.status_code in (999, 429) or "authwall" in r.url or "/login" in r.url or "signup" in r.url:
        return f"bloque_{r.status_code}", None
    if r.status_code == 404:
        return "404", None
    if r.status_code != 200:
        return f"http_{r.status_code}", None
    data = parse(r.text)
    return ("ok", data) if data else ("page_sans_donnees", None)


def candidate_slugs(e: dict, exclude: str) -> list[str]:
    """Slugs LinkedIn plausibles via DuckDuckGo quand l'URL de la liste répond 404."""
    toks = set(name_tokens(e["nom_court"]))
    out = []
    for q in (f"{e['nom_court']} linkedin company", f'site:linkedin.com/company "{e["nom_court"]}"'):
        for r in ddg(q, n=10):
            u = canon(r.get("href", ""))
            if not u or "/company/" not in u or u == exclude or u in out:
                continue
            slug_toks = set(norm(u.rstrip("/").rsplit("/", 1)[-1]).split())
            if toks & (slug_toks | set(norm(r.get("title", "")).split())):
                out.append(u)
        if out:
            break
    return out[:3]


def validate(e: dict, data: dict) -> bool:
    """La page trouvée est-elle bien la bonne boîte ? site identique, sinon nom proche."""
    if e.get("site") and data.get("site"):
        if domain(e["site"]).split(".")[-2:] == domain(data["site"]).split(".")[-2:]:
            return True
    a, b = set(name_tokens(e["nom_court"])), set(name_tokens(data.get("nom", "")))
    need = len(a) if len(a) <= 2 else len(a) - 1      # « Exemple Mécanique » ≠ « Exemple Systèmes »
    return bool(a) and len(a & b) >= need


def fetch_entity(e: dict) -> tuple[str, str, dict | None, str]:
    """(statut, url, données, correction). Gère blocages (pause) et 404 (recherche du bon slug)."""
    url = canon(e["linkedin"])
    numeric = bool(re.search(r"/company/\d+/?$", url))
    statut, data = fetch(url)
    if numeric and statut != "ok":
        statut = "404"                     # URL numérique : LinkedIn renvoie vers la connexion -> chercher le slug
    tries = 0
    while statut.startswith("bloque") and tries < 3:
        # page de connexion sur un slug : souvent passager ; 999 = vrai blocage
        wait = 25 if (statut == "bloque_200" and tries == 0) else 90 * tries + 60
        print(f"  bloqué ({statut}) : pause {wait}s", flush=True)
        time.sleep(wait)
        statut, data = fetch(url)
        tries += 1
    if statut != "404":
        return statut, url, data, ""
    for cand in candidate_slugs(e, url):
        polite_sleep(2, 4)
        st2, d2 = fetch(cand)
        if st2 == "ok" and validate(e, d2):
            return "ok", cand, d2, f"slug corrigé (liste : {url} -> {'URL numérique' if numeric else '404'})"
    return "404", url, None, ""


def priorite(e: dict, zfx: dict, pays_cible: set, voisins: set) -> int:
    """0 pays de la cible, 1 pays inconnu, 2 pays voisin, 3 autre pays, 4 entreprise exclue."""
    if set(e.get("flags") or []) & {"exclure", "particulier", "administration"}:
        return 4
    pays = code_pays(e.get("pays", ""))
    if (zfx.get(e["id"], {}).get("statut") == "ok" and "CH" in pays_cible) or pays in pays_cible:
        return 0
    if not pays:
        return 1
    return 2 if pays in voisins else 3


def main() -> None:
    ap = argparse.ArgumentParser(description="Pages LinkedIn publiques des entreprises de la campagne (vue invité).")
    argument_campagne(ap)
    ap.add_argument("--retry", action="store_true", help="refait aussi les échecs")
    ap.add_argument("--limit", type=int, default=0, help="ne traite que N entreprises (test)")
    ap.add_argument("--tous", action="store_true", help="traite aussi les entreprises d'un pays hors cible et hors voisins")
    a = ap.parse_args()
    ouvrir(a.campagne)
    store = Store(donnees() / "linkedin.json")
    ents = [e for e in load_entities() if canon(e.get("linkedin", ""))]
    todo = [e for e in ents if e["id"] not in store or (a.retry and store.get(e["id"], {}).get("statut") != "ok")]
    # priorité : pays de la cible d'abord (le collecteur est lent : ~2 pages / min)
    zfx = load_json(donnees() / "zefix.json", {}) or {}
    cible = config()["cible"]
    pays_cible = {code_pays(str(p)) for p in cible.get("pays") or []} - {""}
    voisins = {code_pays(str(p)) for p in cible.get("pays_voisins") or []} - {""}
    rang = {e["id"]: priorite(e, zfx, pays_cible, voisins) for e in todo}
    ignorees = 0
    if pays_cible and not a.tous:
        ignorees = sum(1 for e in todo if rang[e["id"]] == 3)
        todo = [e for e in todo if rang[e["id"]] != 3]
    todo.sort(key=lambda e: rang[e["id"]])
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(ents)} pages LinkedIn, {len(todo)} à récupérer"
          + (f", {ignorees} ignorées (pays hors cible et hors voisins ; --tous pour les inclure)" if ignorees else ""),
          flush=True)
    blocked_streak = 0
    for i, e in enumerate(todo, 1):
        statut, url, data, correction = fetch_entity(e)
        rec = {"url": url, "statut": statut, "correction": correction,
               "collecte": datetime.now().isoformat(timespec="seconds")}
        if data:
            rec.update(analyse(data))
        store.put(e["id"], rec)
        blocked_streak = blocked_streak + 1 if statut.startswith("bloque") else 0
        info = f"{rec.get('taille','')} | {rec.get('salaries_linkedin','')} sal. | {len(rec.get('posts', []))} posts" if data else ""
        print(f"[{i}/{len(todo)}] {e['id']} -> {statut} {info} {correction}", flush=True)
        if blocked_streak >= 5:
            print("5 blocages d'affilée : arrêt (relancer plus tard avec --retry)", file=sys.stderr)
            break
        polite_sleep(4, 8)
    store.flush()
    ok = sum(1 for v in store.data.values() if v.get("statut") == "ok")
    print(f"terminé : {ok}/{len(store.data)} pages OK")


if __name__ == "__main__":
    main()
