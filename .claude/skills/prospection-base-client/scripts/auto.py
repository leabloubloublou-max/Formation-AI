"""Signaux automatiques recalculés depuis les textes stockés, avec le lexique COURANT.

Les collecteurs gardent le texte brut (posts LinkedIn, titres + extraits d'actualités, extraits de pages) :
corriger lexique.py suffit, sans refaire la collecte. Utilisé par dossiers.py et scorer.py.
Fenêtre de récence : signaux.fenetre_mois de la campagne (24 mois par défaut).
"""
from __future__ import annotations

import unicodedata

from lexique import detect
from signaux_commun import fenetre_mois, months_ago, to_date

AGREGATEURS = ("crunchbase.", "tracxn.", "cbinsights.", "pitchbook.", "zoominfo.", "rocketreach.", "leadiq.", "owler.",
               "craft.co", "dnb.com", "apollo.io", "signalhire.", "lusha.", "contactout.", "f6s.", "growjo.", "theorg.",
               "companieslist", "datanyze.", "6sense.", "comparably.", "dealroom.", "startupranking.")


def _recent(date: str, months: int | None = None) -> bool:
    d = to_date(date)
    return d is None or months_ago(d) <= (months if months is not None else fenetre_mois())


def linkedin(li: dict) -> list[dict]:
    out = []
    for p in (li or {}).get("posts", []):
        if not p.get("date") or not _recent(p["date"]):
            continue
        for h in detect(p.get("texte", "")):
            out.append({**h, "date": p["date"], "source": "linkedin_post", "url": p.get("url", ""),
                        "texte": unicodedata.normalize("NFKC", p.get("texte", ""))})   # 𝗡𝗲𝘄 -> New
    return out


def news(nw: dict) -> list[dict]:
    out = []
    for r in (nw or {}).get("resultats", []):
        if not _recent(r.get("date")) or any(a in r.get("url", "").lower() for a in AGREGATEURS):
            continue
        for h in detect(f"{r.get('titre', '')}. {r.get('extrait', '')}"):
            out.append({**h, "date": r.get("date", ""), "source": f"web_{r.get('type', 'text')}", "url": r.get("url", ""),
                        "titre": r.get("titre", "")})
    return out


def site(st: dict) -> list[dict]:
    """Garde les détections de la collecte qui tiennent toujours avec le lexique courant."""
    out = []
    for h in (st or {}).get("signaux", []):
        again = {(x["famille"], x["sous_type"]) for x in detect(h.get("extrait", ""))}
        if (h["famille"], h["sous_type"]) in again:
            out.append(h)
    return out
