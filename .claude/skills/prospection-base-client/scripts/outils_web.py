"""Outils compacts pour les agents des workflows : recherche DuckDuckGo, pages LinkedIn, lecture d'une page.

Sorties volontairement courtes (environ 1 000 tokens) pour qu'un agent puisse traiter 25 à 30 entreprises.
N'écrit aucun fichier, sans clé ni compte.

Usage (depuis la racine du projet ; S = .claude/skills/prospection-base-client) :
    .venv/bin/python $S/scripts/outils_web.py search "<requête>" [-n 8] [--region ch-fr]
    .venv/bin/python $S/scripts/outils_web.py linkedin "<nom entreprise>" [--region ch-fr]
    .venv/bin/python $S/scripts/outils_web.py peek <url>

Formats de sortie :
- search   : « [i] titre | url | extrait », ou « (aucun résultat) » ;
- linkedin : « https://www.linkedin.com/company/<slug> | titre | extrait », ou « (aucune page LinkedIn company
  trouvée) » ;
- peek     : lignes « status : ... | url finale : ... », « title : », « description : », « og:site_name : »,
  « linkedin sur la page : », « indices pays/adresse : », « pages utiles : », « extrait : » ; « ERREUR : ... » si
  la page ne répond pas. Une page au certificat SSL invalide est relue sans vérification du certificat ;
- « (recherche indisponible : ...) » quand DuckDuckGo échoue trois fois de suite.
--region : région DuckDuckGo (ch-fr, ch-de, ch-it, fr-fr, de-de, it-it, wt-wt...) ou code pays à deux lettres
(CH, FR, DE...) ; sans --region, la région par défaut de ddgs.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from urllib.parse import urljoin

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import UA, region_recherche

HEADERS = {"User-Agent": UA, "Accept-Language": "fr,en;q=0.8,de;q=0.6"}
COUNTRY_RE = re.compile(
    r"\b(Suisse|Schweiz|Switzerland|Svizzera|Deutschland|Germany|Allemagne|France|Italia|Italy|Italie|"
    r"Österreich|Austria|Autriche|Liechtenstein|Luxembourg|Polska|Poland|China|Hong Kong|Taiwan|Malaysia|USA|"
    r"United States|United Kingdom|Nederland|Netherlands|Belgique|Belgium|Israel|Lithuania|Sweden|Japan|"
    r"Spain|España|Espagne|Portugal|Czech|Slovakia|Singapore|Thailand|Korea|Canada|India)\b", re.I)
POSTAL_RE = re.compile(r"\b(CH-?\s?\d{4}|D-?\s?\d{5}|F-?\s?\d{5}|[1-9]\d{3}\s+[A-ZÉ][\wéèàüöä\-]{2,})")
USEFUL_RE = re.compile(r"contact|impressum|kontakt|about|a-propos|qui-sommes|mentions|ueber-uns", re.I)
LK_RE = re.compile(r"linkedin\.com/(company|school|showcase)/([^\"'\s<>?#/]+)", re.I)


def clip(s: str, n: int) -> str:
    return re.sub(r"\s+", " ", s or "").strip()[:n]


def region_ddg(valeur: str | None) -> str | None:
    """'ch-fr' tel quel ; 'CH' -> région du pays (commun.region_recherche) ; vide -> défaut de ddgs."""
    v = (valeur or "").strip()
    if not v:
        return None
    return v.lower() if "-" in v else region_recherche(v)


def ddg(query: str, n: int, region: str | None = None) -> list[dict]:
    """Résultats DuckDuckGo ; « aucun résultat » rend [] tout de suite (ddgs le signale par une exception)."""
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
    kw = {"region": region} if region else {}
    err = None
    for attempt in range(3):
        try:
            with DDGS() as d:
                return d.text(query, max_results=n, **kw) or []
        except DDGSException as e:
            if "no results" in str(e).lower():
                return []
            err = e
        except Exception as e:  # noqa: BLE001 (réseau, délai dépassé)
            err = e
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    print(f"(recherche indisponible : {clip(str(err), 120)})")
    return []


def cmd_search(query: str, n: int, region: str | None) -> None:
    res = ddg(query, n, region)
    if not res:
        print("(aucun résultat)")
    for i, r in enumerate(res, 1):
        print(f"[{i}] {clip(r.get('title'), 90)} | {r.get('href', '')} | {clip(r.get('body'), 170)}")


def cmd_linkedin(name: str, region: str | None) -> None:
    seen = set()
    for q in (f"{name} linkedin company", f'site:linkedin.com/company "{name}"'):
        for r in ddg(q, 10, region):
            m = LK_RE.search(r.get("href", ""))
            if not m or m.group(1).lower() != "company":
                continue
            slug = m.group(2)
            if slug.lower() in seen:
                continue
            seen.add(slug.lower())
            print(f"https://www.linkedin.com/company/{slug} | {clip(r.get('title'), 90)} | {clip(r.get('body'), 200)}")
    if not seen:
        print("(aucune page LinkedIn company trouvée)")


def cmd_peek(url: str) -> None:
    import requests
    import urllib3
    from bs4 import BeautifulSoup
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if not url.startswith("http"):
        url = "https://" + url
    r = None
    for verify in (True, False):   # second essai sans vérification du certificat (certificats mal configurés)
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, verify=verify, allow_redirects=True)
            break
        except requests.exceptions.SSLError:
            continue
        except requests.RequestException as e:
            print(f"ERREUR : {e.__class__.__name__} : {clip(str(e), 150)}")
            return
    if r is None:
        print("ERREUR : SSL")
        return
    print(f"status : {r.status_code} | url finale : {r.url}")
    if "charset" not in r.headers.get("content-type", "").lower():
        r.encoding = r.apparent_encoding      # sans charset dans l'en-tête, requests suppose ISO-8859-1
    soup = BeautifulSoup(r.text, "html.parser")
    lk = []
    for kind, slug in LK_RE.findall(r.text):
        u = f"https://www.linkedin.com/{kind.lower()}/{slug}"
        if u not in lk:
            lk.append(u)
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    print(f"title : {clip(soup.title.get_text() if soup.title else '', 150)}")
    for key, val in (("name", "description"), ("property", "og:site_name")):
        m = soup.find("meta", attrs={key: val})
        if m and m.get("content"):
            print(f"{val} : {clip(m['content'], 220)}")
    print("linkedin sur la page : " + (" | ".join(lk[:5]) if lk else "aucun"))
    text = soup.get_text("\n", strip=True)
    hints = []
    for line in text.split("\n"):
        if (COUNTRY_RE.search(line) or POSTAL_RE.search(line)) and len(line) < 200:
            line = clip(line, 160)
            if line not in hints:
                hints.append(line)
        if len(hints) >= 8:
            break
    print("indices pays/adresse : " + (" || ".join(hints) if hints else "aucun"))
    links = []
    for a in soup.find_all("a", href=True):
        if USEFUL_RE.search(a["href"]):
            u = urljoin(r.url, a["href"])
            if u not in links:
                links.append(u)
    if links:
        print("pages utiles : " + " | ".join(links[:5]))
    print("extrait : " + clip(text, 400))


def main() -> None:
    ap = argparse.ArgumentParser(description="Outils DuckDuckGo et lecture de page pour les agents des workflows.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="résultats DuckDuckGo : titre | url | extrait")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=8, help="nombre de résultats (défaut 8)")
    s.add_argument("--region", help="région DuckDuckGo (ch-fr, de-de...) ou code pays (CH, FR...)")
    li = sub.add_parser("linkedin", help="pages LinkedIn company candidates pour un nom d'entreprise")
    li.add_argument("name")
    li.add_argument("--region", help="région DuckDuckGo (ch-fr, de-de...) ou code pays (CH, FR...)")
    sub.add_parser("peek", help="titre, description, LinkedIn, indices d'adresse d'une page").add_argument("url")
    a = ap.parse_args()
    if a.cmd == "search":
        cmd_search(a.query, a.n, region_ddg(a.region))
    elif a.cmd == "linkedin":
        cmd_linkedin(a.name, region_ddg(a.region))
    else:
        cmd_peek(a.url)


if __name__ == "__main__":
    main()
