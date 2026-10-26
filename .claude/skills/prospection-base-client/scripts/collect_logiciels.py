"""Étape 5 (après scorer.py) : cherche sur le web le logiciel de chaque entreprise des tiers A à D, sans rien deviner.

Logiciels cherchés : la liste signaux.logiciels de campagne.toml (par exemple SAP, Odoo, Microsoft Dynamics). Les
éditeurs courants ont un motif précis ci-dessous (EDITEURS : sensible à la casse quand le nom existe aussi dans la
langue courante, comme Sage ou Exact) ; un autre nom est cherché tel qu'il est écrit dans la configuration.
Pour chaque entreprise, 3 ou 4 requêtes DuckDuckGo : « "<nom>" <mot> », « site:<domaine> <mot> », le nom avec les
logiciels de la liste, et une offre d'emploi dans la langue de l'entreprise (<mot> = --mot, ERP par défaut).
Un résultat ne compte que s'il cite un logiciel de la liste ET parle de l'entreprise (domaine dans l'URL, ou nom dans le
titre ou l'extrait). Langue : en Suisse, celle de la localité ou du canton ; ailleurs, celle du pays. Région DuckDuckGo :
commun.region_recherche.

Entrées : <campagne>/prospection-signaux.csv (tier, id, nom, site, pays, canton), donnees/signaux/entites.json (ville).
Sortie : <campagne>/donnees/signaux/logiciels.json, {id: {logiciel, statut, source, url, extrait, autres[], relu,
preuves[{logiciels[], url, titre, extrait, sur_domaine, cite_nom, requete}], nom, nom_recherche, domaine, region,
requetes[], collecte}}.
  - statut : « indice » (au moins une preuve web, à relire), « aucun » (rien trouvé). Un indice web n'est pas une
    confirmation : relire les preuves, puis passer statut à « probable » ou « confirmé » (ou « aucun »), corriger
    logiciel, url et extrait si besoin, et mettre relu à « oui ». Seuls « probable » et « confirmé » peuvent être cités
    à un prospect (fichier_appel.py) ;
  - cache : une relance ne traite que les entreprises absentes ; --refresh refait tout, mais ne touche jamais aux champs
    principaux (logiciel, statut, source, url, extrait) d'une entrée relue (relu = oui, ou statut probable ou confirmé).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_logiciels.py --campagne campagnes/<nom>
      [--workers 3] [--refresh] [--mot ERP] [--tiers A,B,C,D] [--max N]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

# Éditeurs connus : (nom, alias normalisés, motif). Un nom de signaux.logiciels qui correspond à un alias prend le motif.
EDITEURS = [
    ("SAP", {"sap", "sap s 4hana", "sap business one"}, r"\bSAP(?: S/4 ?HANA| Business One| B1| ERP| R/3| ECC| ByDesign)?\b"),
    ("ProConcept", {"proconcept"}, r"\bPro[Cc]oncept\b"),
    ("Microsoft Dynamics", {"microsoft dynamics", "dynamics", "dynamics 365", "business central", "navision"},
     r"\b(?:Microsoft )?Dynamics (?:365|NAV|AX)\b|\bBusiness Central\b|\bNavision\b|\bAxapta\b"),
    ("Odoo", {"odoo"}, r"\bOdoo\b"),
    ("Sage", {"sage", "sage x3"}, r"\bSage (?:X3|100|200|50|300|1000|ERP|Business Cloud)\b"),
    ("Infor", {"infor", "baan"}, r"\bInfor (?:M3|LN|CloudSuite|Visual|ERP|SyteLine|XA|Baan)\b|\bBaan\b"),
    ("proALPHA", {"proalpha"}, r"\bpro[Aa][Ll][Pp][Hh][Aa]\b"),
    ("abas", {"abas", "abas erp"}, r"\b(?:abas|ABAS) ERP\b|\babas Software\b"),
    ("Opacc", {"opacc"}, r"\bOpacc\b"),
    ("Proffix", {"proffix"}, r"\bPROFFIX\b|\bProffix\b"),
    ("WinBIZ", {"winbiz"}, r"\bWinBIZ\b"),
    ("SelectLine", {"selectline"}, r"\bSelect[Ll]ine\b"),
    ("Oracle", {"oracle", "oracle netsuite", "netsuite", "jd edwards", "oracle erp"},
     r"\bOracle (?:E-Business|EBS|ERP|Fusion|Cloud ERP)\b|\bJD ?Edwards\b|\bNetSuite\b"),
    ("Epicor", {"epicor"}, r"\bEpicor\b"),
    ("IFS", {"ifs"}, r"\bIFS (?:Applications|Cloud|ERP)\b"),
    ("QAD", {"qad"}, r"\bQAD\b"),
    ("PSIpenta", {"psipenta", "psi penta"}, r"\bPSI ?penta\b"),
    ("Sylob", {"sylob"}, r"\bSylob\b"),
    ("Divalto", {"divalto"}, r"\bDivalto\b"),
    ("Silog", {"silog"}, r"\bSilog\b"),
    ("Clipper", {"clipper"}, r"\bClipper (?:ERP|Industrie|Software|V\d)\b"),
    ("Cegid", {"cegid"}, r"\bCegid\b"),
    ("Exact", {"exact", "exact online"}, r"\bExact (?:Online|Globe|Synergy)\b"),
    ("Visma", {"visma"}, r"\bVisma\b"),
    ("myfactory", {"myfactory"}, r"\bmyfactory\b"),
    ("Topix", {"topix"}, r"\btopix ?(?:8|ERP)\b"),
    ("Bexio", {"bexio"}, r"\bbexio\b"),
]
QUERY_EMPLOI = {"fr": "offre d'emploi {mot}", "de": "Stelle {mot} Kenntnisse", "it": "offerta lavoro {mot}", "en": "job {mot}"}
STATUTS_RELUS = {"probable", "confirmé"}
CHAMPS_PRINCIPAUX = ("logiciel", "statut", "source", "url", "extrait")


def motifs(noms: list[str]) -> list[tuple[str, re.Pattern]]:
    """(nom tel qu'écrit dans la configuration, motif compilé) pour chaque logiciel de signaux.logiciels."""
    from signaux_commun import norm
    out = []
    for nom in noms:
        nom = str(nom).strip()
        if not nom:
            continue
        connu = next((rx for _, alias, rx in EDITEURS if norm(nom) in alias), None)
        if connu is None:   # nom libre : tel qu'il est écrit, mots entiers, espaces souples
            connu = r"(?<![\w])" + r"\s+".join(re.escape(t) for t in nom.split()) + r"(?![\w])"
        out.append((nom, re.compile(connu)))
    return out


def requete_editeurs(noms: list[str]) -> str:
    return " OR ".join(f'"{n}"' if " " in n else n for n in noms[:10])


def langue(row: dict, ville: str) -> str:
    from commun import LANGUES_PAYS
    from icp import langue_suisse
    from signaux_commun import langue_principale
    pays = (row.get("pays") or "").upper()
    if pays == "CH":
        return langue_suisse([ville], (row.get("canton") or "").upper()) or langue_principale()
    lg = LANGUES_PAYS.get(pays, "en")
    return lg if lg in QUERY_EMPLOI else "en"


def logiciels_dans(texte: str, rx: list) -> list[str]:
    return [nom for nom, r in rx if r.search(texte or "")]


def collect(row: dict, ville: str, rx: list, noms: list[str], mot: str) -> dict:
    from commun import region_recherche
    from signaux_commun import clip, ddg, domain, norm, polite_sleep, short_name
    nom = short_name(row["nom"])
    dom = domain(row["site"]) if row.get("site") else ""
    lg = langue(row, ville)
    region = region_recherche(row.get("pays", ""), lg)
    requetes = [f'"{nom}" {mot}', f'"{nom}" {requete_editeurs(noms)}', f'"{nom}" {QUERY_EMPLOI[lg].format(mot=mot)}']
    if dom:
        requetes.insert(1, f"site:{dom} {mot}")
    nom_n = norm(nom)
    preuves, vus = [], set()
    for q in requetes:
        for r in ddg(q, n=10, region=region):
            href, titre, extrait = r.get("href") or "", r.get("title") or "", r.get("body") or ""
            if not href or href in vus:
                continue
            vus.add(href)
            sur_domaine = bool(dom) and dom in domain(href)
            cite_nom = bool(nom_n) and nom_n in norm(f"{titre} {extrait}")
            trouves = logiciels_dans(f"{titre} {extrait}", rx)
            if trouves and (sur_domaine or cite_nom):
                preuves.append({"logiciels": trouves, "url": href, "titre": clip(titre, 160), "extrait": clip(extrait, 400),
                                "sur_domaine": sur_domaine, "cite_nom": cite_nom, "requete": q})
        polite_sleep(0.8, 1.6)
    return {"nom": row["nom"], "nom_recherche": nom, "domaine": dom, "region": region, "requetes": requetes,
            "preuves": preuves}


def synthese(res: dict) -> dict:
    """Champs principaux tirés des preuves : le logiciel le plus cité (preuve sur le site de l'entreprise d'abord)."""
    from signaux_commun import domain
    preuves = res["preuves"]
    if not preuves:
        return {"logiciel": "", "statut": "aucun", "source": "", "url": "", "extrait": "", "autres": []}
    n = Counter(l for p in preuves for l in p["logiciels"])
    sur = Counter(l for p in preuves if p["sur_domaine"] for l in p["logiciels"])
    ordre = sorted(n, key=lambda l: (-sur[l], -n[l]))
    best = min((p for p in preuves if ordre[0] in p["logiciels"]), key=lambda p: (not p["sur_domaine"], not p["cite_nom"]))
    return {"logiciel": ordre[0], "statut": "indice",
            "source": "site de l'entreprise" if best["sur_domaine"] else domain(best["url"]),
            "url": best["url"], "extrait": best["extrait"], "autres": ordre[1:]}


def main() -> None:
    from commun import argument_campagne
    ap = argparse.ArgumentParser(description="Étape 5 : logiciels des entreprises des tiers A à D, cherchés sur le web "
                                             "(donnees/signaux/logiciels.json, à relire).")
    argument_campagne(ap)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--refresh", action="store_true", help="tout refaire (les entrées relues gardent leurs champs principaux)")
    ap.add_argument("--mot", default="ERP", help="type de logiciel cherché dans les requêtes : ERP, CRM, GMAO... (défaut ERP)")
    ap.add_argument("--tiers", default="A,B,C,D", help="tiers de prospection-signaux.csv à traiter (défaut A,B,C,D)")
    ap.add_argument("--max", type=int, help="seulement les N premières entreprises (essai)")
    a = ap.parse_args()

    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime

    from commun import lire_csv
    from signaux_commun import Store, config, donnees, load_json, ouvrir
    camp = ouvrir(a.campagne)
    noms = [str(x).strip() for x in config()["signaux"].get("logiciels") or [] if str(x).strip()]
    if not noms:
        raise SystemExit("signaux.logiciels est vide dans campagne.toml : aucun logiciel à chercher (README.md, "
                         "« Fichiers à compléter »). Rien n'est écrit.")
    src = camp.fichier("prospection-signaux.csv")
    if not src.is_file():
        raise SystemExit(f"{src} absent : lancer d'abord scorer.py --campagne {camp.dossier}")
    tiers = {t.strip() for t in a.tiers.split(",") if t.strip()}
    rows = [r for r in lire_csv(src) if r.get("tier") in tiers and r.get("id")]
    if a.max:
        rows = rows[:a.max]
    villes = {e["id"]: e.get("ville", "") for e in load_json(donnees() / "entites.json", []) or []}
    rx = motifs(noms)
    store = Store(donnees() / "logiciels.json")
    todo = [r for r in rows if a.refresh or r["id"] not in store]
    print(f"{len(rows)} entreprises (tiers {', '.join(sorted(tiers))}), {len(todo)} à chercher ; logiciels : {', '.join(noms)}")

    def run(r: dict) -> None:
        res = collect(r, villes.get(r["id"], ""), rx, noms, a.mot)
        res.update(synthese(res))
        ancien = store.get(r["id"]) or {}
        relu = str(ancien.get("relu", "")).lower() in ("oui", "true", "1") or ancien.get("statut") in STATUTS_RELUS
        if relu:     # relu à la main : seules les preuves sont rafraîchies
            res.update({k: ancien.get(k, "") for k in CHAMPS_PRINCIPAUX}, relu="oui")
        else:
            res["relu"] = ""
        res["collecte"] = datetime.now().isoformat(timespec="seconds")
        store.put(r["id"], res)
        print(f"- {r['nom'][:40]:40} {len(res['preuves'])} preuve(s) {res['logiciel'] or '-'} ({res['statut']})", flush=True)

    with ThreadPoolExecutor(max(1, a.workers)) as ex:
        list(ex.map(run, todo))
    store.flush()
    stats = Counter((store.get(r["id"]) or {}).get("statut", "") for r in rows)
    print(f"terminé : {sum(v for k, v in stats.items() if k and k != 'aucun')} entreprises sur {len(rows)} avec au moins "
          f"un indice de logiciel nommé ({dict(stats)}) -> {donnees() / 'logiciels.json'} (à relire)")


if __name__ == "__main__":
    main()
