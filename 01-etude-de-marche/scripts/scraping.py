#!/usr/bin/env python3
"""Recherche web en série via DuckDuckGo, sans clé API, résultats rangés dans un CSV.

Chaque ligne garde la requête, le lien et la date de collecte : c'est la trace que le vérificateur relit.
Une requête déjà faite n'est pas relancée (le CSV sert de cache) : relancer le script est gratuit.

Exemples, depuis la racine du repo :

    .venv/bin/python 01-etude-de-marche/scripts/scraping.py \\
        --requete "fiduciaire intelligence artificielle Lausanne" \\
        --requete "intégrateur IA PME Genève"

    .venv/bin/python 01-etude-de-marche/scripts/scraping.py \\
        --fichier 01-etude-de-marche/scripts/requetes.exemple.txt --max 15

Options utiles : --region (ch-fr par défaut), --pause (secondes entre deux requêtes, 4 par défaut),
--sortie (01-etude-de-marche/resultats/scraping.csv par défaut), --refaire (ignore le cache).
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

COLONNES = ["requete", "rang", "titre", "url", "domaine", "extrait", "date_collecte", "methode"]
SORTIE_DEFAUT = Path(__file__).resolve().parent.parent / "resultats" / "scraping.csv"


def lire_requetes(args: argparse.Namespace) -> list[str]:
    requetes = list(args.requete or [])
    if args.fichier:
        for ligne in Path(args.fichier).read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#"):
                requetes.append(ligne)
    vues, uniques = set(), []
    for r in requetes:
        if r.lower() not in vues:
            vues.add(r.lower())
            uniques.append(r)
    return uniques


def requetes_deja_faites(sortie: Path) -> set[str]:
    if not sortie.exists():
        return set()
    with sortie.open(encoding="utf-8", newline="") as f:
        return {ligne["requete"].lower() for ligne in csv.DictReader(f)}


def chercher(ddgs, requete: str, region: str, maximum: int, essais: int = 3) -> list[dict]:
    from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

    for essai in range(1, essais + 1):
        try:
            return ddgs.text(requete, region=region, max_results=maximum, backend="duckduckgo") or []
        except (RatelimitException, TimeoutException) as e:
            attente = 15 * essai + random.uniform(0, 5)
            print(f"  ! {type(e).__name__}, nouvel essai dans {attente:.0f} s ({essai}/{essais})", file=sys.stderr)
            time.sleep(attente)
        except DDGSException as e:
            if "No results" in str(e):
                return []
            print(f"  ! erreur DuckDuckGo : {e}", file=sys.stderr)
            return []
    print("  ! abandon de cette requête après plusieurs essais : relancez plus tard", file=sys.stderr)
    return []


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--requete", action="append", help="une requête (répétable)")
    p.add_argument("--fichier", help="fichier texte, une requête par ligne (# pour un commentaire)")
    p.add_argument("--max", type=int, default=10, help="résultats par requête (10 par défaut, 30 au plus)")
    p.add_argument("--region", default="ch-fr", help="ch-fr, fr-fr, be-fr, wt-wt (monde)...")
    p.add_argument("--pause", type=float, default=4.0, help="secondes entre deux requêtes")
    p.add_argument("--sortie", default=str(SORTIE_DEFAUT), help="fichier CSV de sortie (complété, jamais écrasé)")
    p.add_argument("--refaire", action="store_true", help="relancer aussi les requêtes déjà présentes")
    args = p.parse_args()

    requetes = lire_requetes(args)
    if not requetes:
        p.error("donnez au moins une --requete ou un --fichier")
    maximum = max(1, min(args.max, 30))

    try:
        from ddgs import DDGS
    except ImportError:
        print("Le paquet ddgs manque. Depuis la racine du repo : .venv/bin/pip install -r requirements.txt",
              file=sys.stderr)
        return 1

    sortie = Path(args.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    deja = set() if args.refaire else requetes_deja_faites(sortie)
    a_faire = [r for r in requetes if r.lower() not in deja]
    if len(a_faire) < len(requetes):
        print(f"{len(requetes) - len(a_faire)} requête(s) déjà dans {sortie.name}, ignorée(s) (--refaire pour relancer)")
    if not a_faire:
        return 0

    nouveau = not sortie.exists()
    ddgs = DDGS(timeout=10)
    total = 0
    with sortie.open("a", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        if nouveau:
            ecrivain.writeheader()
        for i, requete in enumerate(a_faire, 1):
            print(f"[{i}/{len(a_faire)}] {requete}")
            resultats = chercher(ddgs, requete, args.region, maximum)
            for rang, r in enumerate(resultats, 1):
                url = r.get("href") or r.get("url") or ""
                ecrivain.writerow({
                    "requete": requete,
                    "rang": rang,
                    "titre": (r.get("title") or "").strip(),
                    "url": url,
                    "domaine": urlparse(url).netloc.removeprefix("www."),
                    "extrait": " ".join((r.get("body") or "").split()),
                    "date_collecte": date.today().isoformat(),
                    "methode": f"DuckDuckGo, region={args.region}, top {maximum}",
                })
            f.flush()
            total += len(resultats)
            print(f"  {len(resultats)} résultat(s)")
            if i < len(a_faire):
                time.sleep(args.pause + random.uniform(0, 1.5))

    print(f"\n{total} ligne(s) ajoutée(s) à {sortie}")
    print("Rappel : un extrait de moteur n'est pas une source. Ouvrez la page avant de citer un chiffre.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
