"""Étape 7 : prioriser puis réinjecter dans Apollo un score A / B / C par compte, son signal daté et sourcé et la
première phrase du message, rangés dans des champs personnalisés des contacts Apollo, qui servent de variables dans
les séquences ({{phrase_signal}}).

Score A / B / C, lu dans les sorties de l'étape 5 :
- A, on contacte : tier A ou B ET au moins un signal positif de moins de 12 mois, de poids au moins 1, venu du
  registre ou d'une recherche par agent (les détections automatiques ne comptent pas), sans signal négatif grave de
  moins de 12 mois, et l'entreprise n'est pas un concurrent (elle ne vend pas ce que nous vendons) ;
- B, en veille : le reste de la cible (tiers C et D, pas de signal récent, signal négatif récent, concurrent) ;
- C, retirée : hors cible (motifs d'exclusion de l'étape 5).
Les tiers A à D restent le classement fin ; ce score est celui que l'on réinjecte.

Entrées, dans le dossier de campagne : prospection-signaux.csv et donnees/signaux/signaux.json (étape 5),
donnees/signaux/recherche.json s'il existe (adoption_tech.concurrent) ; les contacts : --contacts (aussi un export
de contacts Apollo), sinon apollo/contacts-crees.csv (étape 6), sinon apollo/contacts-importes.csv
(importer_liste.py), rattachés à leur entreprise par entreprise_id, sinon par le nom, sinon par le domaine ;
facultatif : --phrases <csv> (colonnes id ou nom, et phrase_signal), phrases écrites seulement à la demande.
Sorties, dans le dossier de campagne :
- base-abc.csv : une ligne par entreprise (score, raison, signal et date, source, phrase) ;
- apollo/reinjection.csv : une ligne par contact Apollo, prête pour l'import CSV ou pour --go ;
- phrases-a-rediger.csv : les comptes A sans phrase, avec leur signal et sa source.
--go, seulement après l'accord explicite de l'utilisateur (écriture externe, 0 crédit) : crée au besoin les champs de
contact signal_et_date, source_signal, phrase_signal et score_abc, puis met à jour les contacts par lots de 100
(contacts/bulk_update), sans jamais envoyer de valeur vide. Tester d'abord avec --limite 1. Clé APOLLO_API_KEY
(commun.cle_apollo), jamais affichée ; droits : clé master, ou api/v1/typed_custom_fields/index, api/v1/fields/create
et api/v1/contacts/bulk_update.

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne <dossier>
            [--date AAAA-MM-JJ] [--phrases <csv>] [--contacts <csv>] [--go [--limite N]]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import Campagne, argument_campagne, domaine, ecrire_csv, lire_csv, norm

FIABLES = {"registre", "vérifié", "agent"}
GRAVES = {"faillite", "sursis_concordataire", "dissolution", "difficultes"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre"]
# libellés du registre du commerce suisse (signaux de confiance « registre ») : « Inscription : Nom Prénom (...) »
REGISTRE = {"Inscription": "Nouveau dirigeant inscrit au registre", "Radiation": "Départ inscrit au registre",
            "Promotion": "Promotion inscrite au registre", "Entrée CA": "Entrée au conseil d'administration",
            "Sortie CA": "Sortie du conseil d'administration"}
NEGATIF = re.compile(r"faillite|liquidation|licenciement|sursis concordataire|cyberattaque|difficultés financières|"
                     r"restructuration|insolvab", re.I)
TIRETS = re.compile("[\u2013\u2014]")  # tiret demi-cadratin et cadratin, refusés dans les phrases
CHAMPS = [("signal_et_date", "textarea"), ("source_signal", "textarea"), ("phrase_signal", "textarea"),
          ("score_abc", "string")]
ALIAS = {"prenom": ["prenom", "First Name"], "nom": ["nom", "Last Name"], "email": ["email", "Email"],
         "entreprise": ["entreprise", "Company Name", "Company"], "contact_id": ["contact_id", "Apollo Contact Id"],
         "site_entreprise": ["site_entreprise", "Website"], "ordre": ["ordre"], "entreprise_id": ["entreprise_id"]}
COLONNES_BASE = ["rang", "score_abc", "raison_abc", "tier", "nom", "signal_et_date", "source_signal", "phrase_signal",
                 "pourquoi_maintenant", "site", "id"]
COLONNES_REINJ = ["contact_id", "First Name", "Last Name", "Email", "Company Name", "ordre", "entreprise_id"] + \
    [k for k, _ in CHAMPS]


def jour(d: str) -> date | None:
    d = (d or "").strip()
    try:
        return date.fromisoformat(d[:10]) if len(d) >= 10 else date.fromisoformat(d[:7] + "-01") if len(d) >= 7 else None
    except ValueError:
        return None


def recent(s: dict, ref: date) -> bool:
    d = jour(s.get("date"))
    return d is not None and 0 <= (ref - d).days <= 365


def couper(t: str, n: int) -> str:
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def libelle(s: dict) -> str:
    """« Ouverture d'un site à Sion, septembre 2026 » : le résumé du signal suivi du mois."""
    r = re.sub(r"\s+", " ", s.get("resume") or s.get("terme") or "").strip().rstrip(".…")
    if s.get("confiance") == "registre" and " : " in r:          # « Inscription : Nom Prénom (? -> directeur) »
        prefixe, reste = r.split(" : ", 1)
        reste = re.sub(r"\(([^()]*?) -> ([^()]*)\)", r"(\2)", reste)
        r = f"{REGISTRE.get(prefixe, prefixe)} : {reste}"
    d = jour(s.get("date"))
    return f"{couper(r, 180)}, {MOIS[d.month - 1]} {d.year}" if d else couper(r, 180)


def personne(s: dict) -> str:
    """Nom de la personne d'un signal du registre (« Entrée CA : Nom Prénom »), sinon vide."""
    r = s.get("resume") or ""
    return norm(r.split(" : ", 1)[1].split(" (")[0]) if s.get("confiance") == "registre" and " : " in r else ""


def score(r: dict, sigs: list[dict], concurrent: bool, ref: date) -> tuple[str, str, dict | None]:
    if r["tier"] == "Hors cible" or r.get("motifs_exclusion"):
        return "C", f"hors cible : {r.get('motifs_exclusion') or 'motif non précisé'}", None
    positifs = [s for s in sigs if s.get("famille") != "negatif" and s.get("confiance") in FIABLES
                and (s.get("poids") or 0) >= 1 and recent(s, ref)]
    # un départ est un changement, pas une accroche : il ne suffit pas à mettre le compte en A ; une arrivée suivie
    # du départ de la même personne (registre) n'est plus une accroche non plus
    depart = lambda s: s.get("sous_type") == "depart_dirigeant" or (s.get("resume") or "").startswith(("Radiation", "Sortie CA"))
    partis = {}
    for s in sigs:
        if depart(s) and personne(s):
            partis[personne(s)] = max(partis.get(personne(s), ""), s.get("date") or "")
    accroches = sorted((s for s in positifs if not depart(s) and partis.get(personne(s), "") <= (s.get("date") or "")),
                       key=lambda s: (-(s.get("poids") or 0), -jour(s["date"]).toordinal()))
    top = accroches[0] if accroches else None
    if not top:
        return "B", (f"tier {r['tier']}, seul signal récent : un départ, pas une accroche : en veille" if positifs
                     else f"tier {r['tier']}, aucun signal de moins de 12 mois : en veille"), None
    if any(s.get("famille") == "negatif" and s.get("sous_type") in GRAVES and s.get("confiance") in FIABLES
           and recent(s, ref) for s in sigs):
        return "B", "signal négatif grave de moins de 12 mois : en veille, ne pas l'évoquer", top
    if concurrent:
        return "B", "concurrent (vend ce que nous vendons) : en veille", top
    if r["tier"] not in ("A", "B"):
        return "B", f"tier {r['tier']} (fit moyen ou faible), malgré un signal récent : en veille", top
    return "A", f"tier {r['tier']}, signal de moins de 12 mois", top


def lire_phrases(fichier: str) -> tuple[dict, list]:
    """Phrases écrites à la demande ; refusées : tiret long ou demi-cadratin, plus de 30 mots, signal négatif."""
    ok, refus = {}, []
    for r in lire_csv(fichier):
        p = re.sub(r"\s+", " ", r.get("phrase_signal") or r.get("premiere_phrase") or "").strip()
        cle = r.get("id") or norm(r.get("nom") or r.get("entreprise") or "")
        if not p or not cle:
            continue
        motif = ("tiret long" if TIRETS.search(p) else "plus de 30 mots" if len(p.split()) > 30
                 else "signal négatif" if NEGATIF.search(p) else "")
        if motif:
            refus.append(f"{r.get('nom') or cle} ({motif})")
        else:
            ok[cle] = p
    return ok, refus


def champ(c: dict, k: str) -> str:
    return next(((c.get(x) or "").strip() for x in ALIAS[k] if (c.get(x) or "").strip()), "")


def rang(b: dict) -> float:
    try:
        return float(b.get("rang") or 0)
    except ValueError:
        return 0.0


def envoyer(lignes: list[dict], cache: Path, journal: Path) -> None:
    from apollo_api import Apollo
    api = Apollo(cache)
    ids = api.champs("contact")   # seulement les champs de contact (un champ de compte homonyme ne remplit rien)
    for label, type_ in CHAMPS:
        if label not in ids:
            ids[label] = api.creer_champ(label, "contact", type_)
            print(f"champ de contact créé dans Apollo : {label}")
    journal.write_text(json.dumps({k: ids[k] for k, _ in CHAMPS}, indent=1), encoding="utf-8")
    faits = 0
    for i in range(0, len(lignes), 100):
        lot = [{"id": l["contact_id"], "typed_custom_fields": {ids[k]: l[k] for k, _ in CHAMPS if l[k]}}
               for l in lignes[i:i + 100]]
        lot = [x for x in lot if x["typed_custom_fields"]]
        if not lot:
            continue
        rep = api.maj_contacts(lot)
        faits += len(rep["contacts"]) if "contacts" in rep else len(lot) if rep.get("entity_progress_job") else 0
        print(f"lot {i // 100 + 1} : {len(lot)} contacts envoyés")
    print(f"{faits} contacts mis à jour dans Apollo ; recompter dans Apollo (filtre sur score_abc) quelques secondes "
          f"plus tard ; {api.appels} appels API")


def main() -> None:
    ap = argparse.ArgumentParser(description="Score A/B/C par compte et réinjection dans les champs de contact Apollo.")
    argument_campagne(ap)
    ap.add_argument("--date", help="date de référence AAAA-MM-JJ pour les 12 mois (défaut : [campagne] date_reference, "
                                   "sinon aujourd'hui)")
    ap.add_argument("--contacts", help="contacts Apollo (contacts-crees.csv, contacts-importes.csv ou export Apollo)")
    ap.add_argument("--phrases", help="CSV des premières phrases (id ou nom, phrase_signal)")
    ap.add_argument("--go", action="store_true", help="écrire dans Apollo (après accord explicite)")
    ap.add_argument("--limite", type=int, help="avec --go : seulement les N premiers contacts (test)")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    for option, chemin in (("--contacts", a.contacts), ("--phrases", a.phrases)):
        if chemin and not Path(chemin).is_file():
            raise SystemExit(f"{option} : fichier introuvable ({chemin}). Vérifier le chemin (relatif au dossier courant).")
    ref = date.fromisoformat(a.date) if a.date else camp.date_reference()
    src = camp.fichier("prospection-signaux.csv")
    f_sig = camp.signaux / "signaux.json"
    for f in (src, f_sig):
        if not f.exists():
            raise SystemExit(f"{f} absent : faire d'abord l'étape 5 (scorer.py).")
    lignes = lire_csv(src)
    sig = json.loads(f_sig.read_text(encoding="utf-8"))
    f_rech = camp.signaux / "recherche.json"
    rech = json.loads(f_rech.read_text(encoding="utf-8")) if f_rech.exists() else {}
    phrases, refus = lire_phrases(a.phrases) if a.phrases else ({}, [])

    base = []
    for r in lignes:
        concurrent = bool(((rech.get(r["id"]) or {}).get("adoption_tech") or {}).get("concurrent"))
        abc, raison, top = score(r, sig.get(r["id"], []), concurrent, ref)
        base.append({"rang": r.get("rang", ""), "score_abc": abc, "raison_abc": raison, "tier": r["tier"],
                     "nom": r["nom"], "signal_et_date": "" if abc == "C" else libelle(top) if top else "aucun signal trouvé",
                     "source_signal": (top or {}).get("url", "") if abc != "C" else "",
                     "phrase_signal": "" if abc == "C" else phrases.get(r["id"]) or phrases.get(norm(r["nom"]), ""),
                     "pourquoi_maintenant": r.get("pourquoi_maintenant", ""),
                     "site": r.get("site") or r.get("website") or "", "id": r["id"]})
    base.sort(key=lambda b: ("ABC".index(b["score_abc"]), rang(b)))

    f_contacts = Path(a.contacts) if a.contacts else next(
        (p for p in (camp.apollo / "contacts-crees.csv", camp.apollo / "contacts-importes.csv") if p.exists()), None)
    contacts = lire_csv(f_contacts) if f_contacts else []
    par_id = {b["id"]: b for b in base}
    par_nom = {norm(b["nom"]): b for b in base}
    par_dom = {domaine(b["site"]): b for b in base if b["site"]}
    reinj, sans_id, orphelins = [], 0, 0
    for p in contacts:
        b = par_id.get(champ(p, "entreprise_id")) or par_nom.get(norm(champ(p, "entreprise")) or "-") \
            or par_dom.get(domaine(champ(p, "site_entreprise")) or "-")
        if not b:
            orphelins += 1
        elif not champ(p, "contact_id"):
            sans_id += 1
        else:
            reinj.append({"contact_id": champ(p, "contact_id"), "First Name": champ(p, "prenom"),
                          "Last Name": champ(p, "nom"), "Email": champ(p, "email"), "Company Name": b["nom"],
                          "ordre": champ(p, "ordre"), "entreprise_id": b["id"], **{k: b[k] for k, _ in CHAMPS}})

    f_base, f_phr, f_reinj = camp.fichier("base-abc.csv"), camp.fichier("phrases-a-rediger.csv"), \
        camp.apollo / "reinjection.csv"
    ecrire_csv(f_base, COLONNES_BASE, base)
    ecrire_csv(f_reinj, COLONNES_REINJ, reinj)
    a_rediger = [b for b in base if b["score_abc"] == "A" and not b["phrase_signal"]]
    ecrire_csv(f_phr, ["id", "nom", "signal_et_date", "source_signal", "phrase_signal"], a_rediger)

    n, nc = Counter(b["score_abc"] for b in base), Counter(x["score_abc"] for x in reinj)
    print(f"{len(base)} entreprises au {ref} : A {n['A']} (on contacte), B {n['B']} (en veille), C {n['C']} (hors cible)"
          f" -> {f_base}")
    print(f"comptes A sans première phrase : {len(a_rediger)} -> {f_phr}"
          + (f" ; phrases refusées : {', '.join(refus)}" if refus else ""))
    print(f"{len(reinj)} contacts à réinjecter (A {nc['A']}, B {nc['B']}, C {nc['C']}) ; sans id Apollo : {sans_id} ; "
          f"entreprise non reconnue : {orphelins} -> {f_reinj}"
          + ("" if f_contacts else " (aucun fichier de contacts : étape 6 à faire)"))
    if a.go:
        envoyer(reinj[:a.limite] if a.limite else reinj, camp.apollo / "cache", camp.apollo / "champs-apollo.json")
    else:
        print("Aperçu seulement : rien n'est écrit dans Apollo. Après accord : --go --limite 1, vérifier, puis --go.")


if __name__ == "__main__":
    main()
