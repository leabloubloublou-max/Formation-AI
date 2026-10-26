"""Pages LinkedIn d'entreprises lues sur leur propre site web (sans moteur de recherche ni clé).

Pour chaque domaine unique : page d'accueil, puis, si elle ne donne rien, des pages de repli (contact, à propos,
mentions légales, impressum...). On en extrait les liens LinkedIn company (school, showcase compris) et les profils
/in/ présents dans l'en-tête, le pied de page ou la page contact.

- find_for_site(site) : importable, sert à enrichir_sites.py ;
- en ligne de commande, sur un CSV : écrit <csv sans extension>-linkedin.csv à côté du CSV, avec trois colonnes
  ajoutées : linkedin_company (premier lien company, school ou showcase par ordre alphabétique), linkedin_profiles
  et linkedin_companies_all (séparés par « | »). consolider_decouverte.py le lit avec --linkedin pour compléter
  les pages que les agents n'ont pas vues.
Colonne du site devinée (website, site_internet, url, site, web) ou --col-site ; colonne du nom (name, nom,
raison_sociale, company, entreprise) ou --col-nom, pour le journal seulement.
Cache par domaine : <campagne>/donnees/cache/linkedin-sites.json (sans --campagne : linkedin-sites.json à côté du
CSV) ; une relance ne relit que les domaines nouveaux.
Un site au certificat SSL invalide est relu sans vérification du certificat (avertissements masqués).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py --campagne campagnes/<nom>
      (CSV par défaut : <campagne>/entreprises.csv -> <campagne>/entreprises-linkedin.csv)
  .venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py <fichier.csv> \\
      [--campagne campagnes/<nom>] [--col-site site] [--col-nom nom] [--workers 12] [--limite 5]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import UA

# autoriser de gros champs (descriptions, etc.)
csv.field_size_limit(10_000_000)

HEADERS = {"User-Agent": UA, "Accept-Language": "fr,en;q=0.8,de;q=0.6"}
TIMEOUT = 12
CACHE_NOM = "linkedin-sites.json"
# pages secondaires testées seulement si la page d'accueil ne donne rien
FALLBACK_PATHS = [
    "/contact", "/contactez-nous", "/contact-us", "/nous-contacter",
    "/about", "/a-propos", "/about-us", "/qui-sommes-nous",
    "/mentions-legales", "/impressum", "/kontakt",
]

LINKEDIN_COMPANY_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:company|school|showcase)/[\w\-%.]+", re.I)
LINKEDIN_PROFILE_RE = re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[\w\-%.]+", re.I)

# détection automatique des colonnes
WEBSITE_COLS = ["website", "site_internet", "url", "site", "web"]
NAME_COLS = ["name", "nom", "raison_sociale", "company", "entreprise"]

_print_lock = threading.Lock()
_cache_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def normalize_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw or raw.lower() in ("nan", "none", "-", "n/a"):
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        p = urlparse(raw)
        if not p.netloc or "." not in p.netloc:
            return None
        return raw
    except Exception:  # noqa: BLE001
        return None


def domain_key(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def clean_lk(url: str) -> str:
    # enlève les paramètres de suivi et la barre finale
    return url.split("?")[0].split("#")[0].rstrip("/")


def fetch(url: str) -> str | None:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    for verify in (True, False):  # second essai sans vérification du certificat (certificats mal configurés)
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=verify, allow_redirects=True)
            if r.status_code < 400 and r.text:
                return r.text
            return None
        except requests.exceptions.SSLError:
            continue
        except requests.RequestException:
            return None
    return None


def extract_linkedin(html: str) -> tuple[set[str], set[str]]:
    from bs4 import BeautifulSoup
    companies, profiles = set(), set()
    # 1) expression régulière sur tout le HTML (capte aussi les liens hors <a>)
    for m in LINKEDIN_COMPANY_RE.findall(html):
        companies.add(clean_lk(m))
    for m in LINKEDIN_PROFILE_RE.findall(html):
        profiles.add(clean_lk(m))
    # 2) href des <a> (capte les href relatifs ou encodés)
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "linkedin.com" not in href.lower():
                continue
            if LINKEDIN_COMPANY_RE.search(href):
                companies.add(clean_lk(LINKEDIN_COMPANY_RE.search(href).group(0)))
            elif LINKEDIN_PROFILE_RE.search(href):
                profiles.add(clean_lk(LINKEDIN_PROFILE_RE.search(href).group(0)))
    except Exception:  # noqa: BLE001
        pass
    return companies, profiles


def find_for_site(website: str) -> dict:
    """Lit la page d'accueil puis quelques pages de repli. Rend la page entreprise et les profils trouvés."""
    companies, profiles = set(), set()
    home = fetch(website)
    if home:
        c, p = extract_linkedin(home)
        companies |= c
        profiles |= p
    # pages de repli seulement si rien n'a été trouvé sur la page d'accueil
    if not companies and not profiles:
        base = f"{urlparse(website).scheme}://{urlparse(website).netloc}"
        for path in FALLBACK_PATHS:
            html = fetch(urljoin(base, path))
            if not html:
                continue
            c, p = extract_linkedin(html)
            companies |= c
            profiles |= p
            if companies:  # on s'arrête dès qu'on a la page entreprise
                break
    return {
        "linkedin_company": sorted(companies)[0] if companies else "",
        "linkedin_companies_all": " | ".join(sorted(companies)),
        "linkedin_profiles": " | ".join(sorted(profiles)),
        "reachable": bool(home),
    }


def detect_col(fieldnames: list[str], candidates: list[str]) -> str | None:
    lower = {f.lower(): f for f in fieldnames}
    for c in candidates:
        if c in lower:
            return lower[c]
    return None


def load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(path: Path, cache: dict) -> None:
    with _cache_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Pages LinkedIn d'entreprises lues sur leur site : <csv>-linkedin.csv à côté du CSV.")
    ap.add_argument("csv", nargs="?", help="CSV à enrichir (défaut : <campagne>/entreprises.csv)")
    ap.add_argument("--campagne", help="dossier de la campagne : CSV par défaut et cache dans donnees/cache/")
    ap.add_argument("--col-site", "--website-col", dest="col_site", help="colonne du site, si elle n'est pas devinée")
    ap.add_argument("--col-nom", "--name-col", dest="col_nom", help="colonne du nom, si elle n'est pas devinée")
    ap.add_argument("--workers", type=int, default=12, help="sites lus en parallèle (défaut 12)")
    ap.add_argument("--limite", "--limit", dest="limite", type=int, help="ne traiter que les N premières lignes (test)")
    args = ap.parse_args()
    if not args.csv and not args.campagne:
        ap.error("donner un CSV ou --campagne")

    camp = cache_path = None
    if args.campagne:
        from commun import Campagne
        camp = Campagne(args.campagne, config_obligatoire=False)
        cache_path = camp.cache / CACHE_NOM
    in_path = Path(args.csv) if args.csv else camp.fichier("entreprises.csv")
    if not in_path.exists():
        sys.exit(f"Introuvable : {in_path}")
    out_path = in_path.with_name(in_path.stem + "-linkedin.csv")
    cache_path = cache_path or in_path.with_name(CACHE_NOM)

    with in_path.open(newline="", encoding="utf-8-sig") as f:
        echantillon = f.read(8192)
        f.seek(0)
        reader = csv.DictReader(f, delimiter=";" if echantillon.count(";") > echantillon.count(",") else ",")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    web_col = args.col_site or detect_col(fieldnames, WEBSITE_COLS)
    name_col = args.col_nom or detect_col(fieldnames, NAME_COLS)
    if not web_col:
        sys.exit(f"Aucune colonne de site détectée (option --col-site). Colonnes : {fieldnames}")
    log(f"CSV : {in_path.name} | {len(rows)} lignes | site = '{web_col}', nom = '{name_col}'")

    if args.limite:
        rows = rows[: args.limite]

    cache = load_cache(cache_path)

    # domaines uniques à lire (dédoublonnage, cache sauté)
    todo: dict[str, str] = {}  # domaine -> url du site
    for row in rows:
        url = normalize_url(row.get(web_col, ""))
        if not url:
            continue
        d = domain_key(url)
        if d in cache or d in todo:
            continue
        todo[d] = url

    log(f"À lire : {len(todo)} domaines uniques (cache : {len(cache)})")

    done = 0
    found = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(find_for_site, url): d for d, url in todo.items()}
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = {"linkedin_company": "", "linkedin_companies_all": "",
                       "linkedin_profiles": "", "reachable": False, "error": str(e)}
            cache[d] = res
            done += 1
            if res.get("linkedin_company") or res.get("linkedin_profiles"):
                found += 1
            if done % 25 == 0:
                save_cache(cache_path, cache)
                log(f"  {done}/{len(todo)} lus | {found} avec LinkedIn")
    save_cache(cache_path, cache)
    log(f"Lecture terminée : {done} domaines, {found} avec LinkedIn.")

    # écriture du CSV enrichi (utf-8-sig : lisible par Excel)
    new_cols = ["linkedin_company", "linkedin_profiles", "linkedin_companies_all"]
    out_fields = fieldnames + [c for c in new_cols if c not in fieldnames]
    n_company = 0
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            url = normalize_url(row.get(web_col, ""))
            res = cache.get(domain_key(url), {}) if url else {}
            row["linkedin_company"] = res.get("linkedin_company", "")
            row["linkedin_profiles"] = res.get("linkedin_profiles", "")
            row["linkedin_companies_all"] = res.get("linkedin_companies_all", "")
            if row["linkedin_company"]:
                n_company += 1
            w.writerow(row)

    log(f"\n-> {out_path}")
    log(f"   {n_company}/{len(rows)} lignes avec une page LinkedIn entreprise")


if __name__ == "__main__":
    main()
