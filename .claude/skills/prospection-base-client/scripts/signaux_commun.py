"""Outils partagés de la détection de signaux, étape 5 (campagne, HTTP, normalisation, dates, caches).

Tous les scripts de l'étape 5 s'appuient dessus (entites.py, collect_*.py, dossiers.py, scorer.py...). Chacun
ouvre d'abord la campagne passée par --campagne avec ouvrir() :
  - les caches JSON vont dans <campagne>/donnees/signaux/ (donnees()), jamais dans le dossier du skill ;
  - la date de référence des fenêtres de récence est celle de la campagne (aujourdhui(), TODAY) : champ
    campagne.date_reference de campagne.toml, sinon variable PROSPECTION_DATE, sinon la date du jour ;
  - la fenêtre des signaux vient de signaux.fenetre_mois (fenetre_mois()).

Attention : TODAY change à l'ouverture de la campagne. Dans un autre module, lire aujourdhui() (ou
signaux_commun.TODAY) au moment du calcul, jamais `from signaux_commun import TODAY`.

Lancement, depuis la racine du projet :
    .venv/bin/python .claude/skills/prospection-base-client/scripts/<script>.py --campagne campagnes/<nom>
"""
from __future__ import annotations

import html
import json
import re
import threading
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from commun import DEFAUTS, Campagne, recherche_web

# ---------------------------------------------------------------- campagne

_campagne: Campagne | None = None
TODAY: date = date.today()        # remplacée par la date de référence de la campagne dans ouvrir()


def ouvrir(dossier: str | Path | Campagne) -> Campagne:
    """Ouvre la campagne (--campagne) : date de référence, langues des requêtes HTTP, dossier des caches."""
    global _campagne, TODAY
    _campagne = dossier if isinstance(dossier, Campagne) else Campagne(dossier)
    TODAY = _campagne.date_reference()
    HEADERS["Accept-Language"] = _accept_language(_campagne.config["appels"].get("langues") or [])
    return _campagne


def campagne() -> Campagne:
    if _campagne is None:
        raise RuntimeError("campagne non ouverte : appeler signaux_commun.ouvrir(--campagne) au début du script")
    return _campagne


def config() -> dict:
    """Configuration de la campagne ouverte ; valeurs par défaut si aucune (tests, outils des agents)."""
    return _campagne.config if _campagne is not None else DEFAUTS


def donnees() -> Path:
    """<campagne>/donnees/signaux/ : entites.json, zefix.json, linkedin.json, site.json, news.json..."""
    return campagne().signaux


def aujourdhui() -> date:
    return TODAY


def fenetre_mois() -> int:
    """Ancienneté maximale d'un signal (signaux.fenetre_mois, 24 par défaut)."""
    try:
        return int(config()["signaux"].get("fenetre_mois") or 24)
    except (TypeError, ValueError):
        return 24


def langue_principale() -> str:
    """Première langue de l'appelant (appels.langues), « fr » à défaut."""
    langues = config()["appels"].get("langues") or ["fr"]
    return str(langues[0]).lower()[:2] if langues else "fr"


# ---------------------------------------------------------------- HTTP

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "fr,en;q=0.8,de;q=0.6"}


def _accept_language(langues: list[str]) -> str:
    """Langues de l'appelant d'abord, puis anglais et allemand : ["fr"] -> « fr,en;q=0.8,de;q=0.6 »."""
    vues = [str(l).lower()[:2] for l in langues if l] or ["fr"]
    vues = list(dict.fromkeys(vues + ["en", "de"]))[:5]
    return ",".join(l if i == 0 else f"{l};q={max(0.2, 1 - 0.2 * i):.1f}" for i, l in enumerate(vues))


_tls = threading.local()


def session():
    """Une session HTTP par thread (requests importé à l'usage : --help marche sans dépendances)."""
    s = getattr(_tls, "s", None)
    if s is None:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        s = requests.Session()
        s.headers.update(HEADERS)
        _tls.s = s
    return s


def get(url: str, timeout: int = 15, **kw):
    """GET tolérant : repli sans vérification TLS, None si injoignable."""
    import requests
    for verify in (True, False):
        try:
            return session().get(url, timeout=timeout, verify=verify, allow_redirects=True, **kw)
        except requests.exceptions.SSLError:
            continue
        except requests.RequestException:
            return None
    return None


# ---------------------------------------------------------------- texte

LEGAL = {
    "sa", "ag", "gmbh", "sarl", "sàrl", "ltd", "limited", "inc", "llc", "sas", "srl", "s.r.l", "bv", "b.v",
    "kg", "co", "ohg", "se", "spa", "sp", "z", "o", "oo", "sdn", "bhd", "uab", "corp", "corporation",
    "company", "cie", "holding", "group", "groupe", "the",
}


def fix_mojibake(s: str) -> str:
    """'Ã¶' -> 'ö' (texte UTF-8 relu en latin-1, fréquent dans les publications officielles récentes)."""
    if not s or ("Ã" not in s and "Â" not in s):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def clean_text(s: str) -> str:
    s = fix_mojibake(html.unescape(s or ""))
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str) -> str:
    """Clé de comparaison : minuscules, sans accents (ä -> ae), mots séparés par une espace.
    Contrairement à commun.norm, garde les formes juridiques (sert aussi aux identifiants)."""
    s = (s or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def name_tokens(name: str) -> list[str]:
    """Tokens distinctifs d'un nom d'entreprise (sans formes juridiques)."""
    return [t for t in norm(name).split() if t not in LEGAL and len(t) >= 2]


def short_name(nom: str) -> str:
    """'Exemple Mécanique SA (Exemple Group)' -> 'Exemple Mécanique' ; 'Entreprise A Sàrl' -> 'Entreprise A'."""
    s = re.sub(r"\(.*?\)|\(.*$", "", nom or "").strip()
    s = re.split(r"\s[-\u2013]\s|,", s)[0].strip()
    toks = s.split()
    while toks and norm(toks[-1]) in LEGAL | {""}:
        toks.pop()
    return " ".join(toks) or (nom or "").strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")[:60] or "x"


def domain(url: str) -> str:
    h = urlparse(url if "//" in (url or "") else f"https://{url}").netloc.lower()
    return h[4:] if h.startswith("www.") else h


def clip(s: str, n: int) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- dates

MOIS = {
    "janvier": 1, "janv": 1, "january": 1, "jan": 1, "januar": 1, "jänner": 1, "gennaio": 1,
    "fevrier": 2, "février": 2, "fevr": 2, "févr": 2, "february": 2, "feb": 2, "februar": 2, "febbraio": 2,
    "mars": 3, "march": 3, "mar": 3, "maerz": 3, "märz": 3, "marzo": 3,
    "avril": 4, "avr": 4, "april": 4, "apr": 4, "aprile": 4,
    "mai": 5, "may": 5, "maggio": 5,
    "juin": 6, "june": 6, "jun": 6, "juni": 6, "giugno": 6,
    "juillet": 7, "juil": 7, "july": 7, "jul": 7, "juli": 7, "luglio": 7,
    "aout": 8, "août": 8, "august": 8, "aug": 8, "agosto": 8,
    "septembre": 9, "sept": 9, "september": 9, "sep": 9, "settembre": 9,
    "octobre": 10, "oct": 10, "october": 10, "oktober": 10, "okt": 10, "ottobre": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "decembre": 12, "décembre": 12, "dec": 12, "déc": 12, "december": 12, "dezember": 12, "dez": 12, "dicembre": 12,
}
_MOIS_RE = "|".join(sorted((re.escape(k) for k in MOIS), key=len, reverse=True))
DATE_PATTERNS = [
    (re.compile(r"\b(20[0-3]\d)-(0[1-9]|1[0-2])-([0-3]\d)"), "ymd"),
    (re.compile(r"\b([0-3]?\d)[./]([01]?\d)[./](20[0-3]\d)\b"), "dmy"),
    (re.compile(rf"\b([0-3]?\d)\.?\s+({_MOIS_RE})\.?\s+(20[0-3]\d)\b", re.I), "d_month_y"),
    (re.compile(rf"\b({_MOIS_RE})\.?\s+([0-3]?\d),\s+(20[0-3]\d)\b", re.I), "month_d_y"),
    (re.compile(rf"\b({_MOIS_RE})\.?\s+(20[0-3]\d)\b", re.I), "month_y"),
]


def parse_date(s: str) -> date | None:
    """Première date lisible d'une chaîne (ISO, 17.08.2026, 17 août 2026, August 2026...)."""
    if not s:
        return None
    for rx, kind in DATE_PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "ymd":
                return date(int(m[1]), int(m[2]), int(m[3]))
            if kind == "dmy":
                return date(int(m[3]), int(m[2]), int(m[1]))
            if kind == "d_month_y":
                return date(int(m[3]), MOIS[m[2].lower()], int(m[1]))
            if kind == "month_d_y":
                return date(int(m[3]), MOIS[m[1].lower()], int(m[2]))
            if kind == "month_y":
                return date(int(m[2]), MOIS[m[1].lower()], 1)
        except (ValueError, KeyError):
            continue
    return None


def all_dates(s: str) -> list[date]:
    out = []
    for rx, kind in DATE_PATTERNS:
        for m in rx.finditer(s or ""):
            d = parse_date(m.group(0))
            if d and date(2000, 1, 1) <= d <= TODAY + timedelta(days=60):
                out.append(d)
    return out


def iso(d: date | datetime | None) -> str:
    if d is None:
        return ""
    return (d.date() if isinstance(d, datetime) else d).isoformat()


def to_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        if re.fullmatch(r"20\d\d-\d\d", s):
            return date.fromisoformat(s + "-01")
        if re.fullmatch(r"20\d\d", s):
            return date(int(s), 6, 30)
        return parse_date(s)


def months_ago(d: date | None) -> float | None:
    if d is None:
        return None
    return (TODAY - d).days / 30.44


# ---------------------------------------------------------------- JSON / cache

def load_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


class Store:
    """Dictionnaire JSON persistant, sûr entre threads (reprise gratuite des collectes)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = load_json(self.path, {}) or {}
        self.lock = threading.Lock()
        self._dirty = 0

    def __contains__(self, k):
        return k in self.data

    def get(self, k, default=None):
        return self.data.get(k, default)

    def put(self, k, v, flush_every: int = 1):
        with self.lock:
            self.data[k] = v
            self._dirty += 1
            if self._dirty >= flush_every:
                save_json(self.path, self.data)
                self._dirty = 0

    def flush(self):
        with self.lock:
            save_json(self.path, self.data)
            self._dirty = 0


def load_entities() -> list[dict]:
    """Fiches entreprises de la campagne (donnees/signaux/entites.json, écrit par entites.py)."""
    ents = load_json(donnees() / "entites.json")
    if not ents:
        raise SystemExit(f"{donnees() / 'entites.json'} absent ou vide : lancer d'abord "
                         f"scripts/entites.py --campagne {campagne().dossier}")
    return ents


def polite_sleep(a: float, b: float) -> None:
    import random
    time.sleep(random.uniform(a, b))


# ---------------------------------------------------------------- recherche web (DuckDuckGo via ddgs)

def ddg(query: str, kind: str = "text", n: int = 10, region: str = "wt-wt", tries: int = 4, **kw) -> list[dict]:
    """Recherche ddgs avec relances (commun.recherche_web). kind = « text » ou « news ». [] si tout échoue."""
    return recherche_web(query, n=n, region=region, actualites=(kind == "news"), essais=tries, **kw)
