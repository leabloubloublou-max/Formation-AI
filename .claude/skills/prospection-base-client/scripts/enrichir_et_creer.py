"""Étape 6, partie payante : enrichit les personnes validées (garder = oui) puis les crée en contacts Apollo.

- Lit apollo/contacts-a-valider.csv, ou le fichier passé en argument (export Excel ou Google Sheets, virgules ou
  points-virgules).
- Sans --go : aucun appel, la clé n'est pas lue ; affiche le nombre de personnes et le plafond de crédits.
- Avec --go (après accord) :
  1. enrichissement par lots de 10 (bulk_match) : par id Apollo, ou, pour les personnes trouvées sur le web, par URL
     LinkedIn (sinon nom + domaine). 1 crédit par personne trouvée, 0 sinon ; jamais d'email personnel ; mobiles
     seulement si [apollo] mobiles = true ou --mobiles (8 crédits par numéro, résultat lu en différé). Réponses en
     cache : une relance identique ne recrédite rien. Pour une personne trouvée sur le web, l'email n'est gardé que
     si Apollo la place bien chez l'entreprise (sinon c'est l'adresse d'un ancien poste) ;
  2. création des contacts (lots de 100, dédoublonnage Apollo), rattachés au compte de la liste de comptes, dans les
     listes « <liste> », « <liste> - entrée » et « <liste> - relais » ([apollo] liste_contacts) ; un contact qui
     existait déjà est ajouté à ces listes sans perdre les siennes. Une personne trouvée sur le web mais inconnue
     d'Apollo est créée sans email, avec son LinkedIn. Une personne basée hors de [apollo] pays_contacts (à défaut,
     [cible] pays et pays_voisins, comme chercher_contacts.py) n'est pas créée, sauf un vrai dirigeant de
     l'entreprise (direction, ni poste régional ni filiale étrangère). Les trois listes vides : aucun filtre de pays.
Sortie : apollo/contacts-crees.csv (colonnes du contrat des contacts ; les lignes d'un passage précédent dont le
contact n'est pas repris sont gardées).

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne <dossier>
            [fichier.csv] [--go] [--liste NOM] [--limite N] [--mobiles {non,entree,tous}]
  Test : --limite 10 --go (exactement le 1er lot du passage complet, relu ensuite depuis le cache).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import (COLONNES_CONTACTS, ORDRE_ENTREE, ORDRE_RELAIS, Campagne, argument_campagne, ecrire_csv, lire_csv,
                    site_propre)
from persona import Persona, jetons, seniorite

OUI = {"oui", "o", "x", "1", "yes", "y", "true"}
COLONNES = COLONNES_CONTACTS + ["site_entreprise"]
CREDITS_MOBILE = 8


def lire(chemin):
    choix = {}
    for r in lire_csv(chemin):
        if (r.get("garder") or "").strip().lower() not in OUI:
            continue
        cle = r.get("apollo_id") or r.get("linkedin") or f"{r.get('prenom')} {r.get('nom_masque')} {r.get('entreprise')}"
        if cle in choix:  # même personne retenue deux fois : l'étape d'entrée l'emporte
            if r.get("ordre") == ORDRE_ENTREE:
                choix[cle]["ordre"] = ORDRE_ENTREE
            continue
        choix[cle] = dict(r)
    return list(choix.values())


def detail(r):
    """critère d'enrichissement : id Apollo, sinon URL LinkedIn, sinon nom + domaine."""
    if r.get("apollo_id"):
        return {"id": r["apollo_id"]}
    d = {"first_name": r.get("prenom"), "last_name": r.get("nom_masque"), "domain": r.get("domaine")}
    if r.get("linkedin"):
        d["linkedin_url"] = r["linkedin"]
    return {k: v for k, v in d.items() if v}


def groupes(sel, mobile_pour):
    """lots d'enrichissement : par id Apollo d'abord, puis par LinkedIn ou nom ; mobiles demandés à part."""
    out = []
    for par_id in (True, False):
        for mob in (True, False):
            g = [r for r in sel if bool(r.get("apollo_id")) == par_id and mobile_pour(r) == mob]
            if g:
                out.append((mob, g))
    return out


def mobiles_du_resultat(data) -> dict:
    """{id de personne: mobile} dans un résultat d'enrichissement asynchrone (format lu avec tolérance)."""
    out = {}

    def numero(v):
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("sanitized_number") or v.get("raw_number") or v.get("number") or ""
        if isinstance(v, list):
            return next((n for n in (numero(x) for x in v) if n), "")
        return ""

    def parcourir(x):
        if isinstance(x, dict):
            pid = x.get("id") or x.get("person_id")
            mob = numero(x.get("mobile_phone")) or next(
                (numero(p) for p in x.get("phone_numbers") or []
                 if isinstance(p, dict) and str(p.get("type_cd") or p.get("type") or "").startswith("mobile")), "")
            if pid and mob:
                out.setdefault(pid, mob)
            for v in x.values():
                parcourir(v)
        elif isinstance(x, list):
            for v in x:
                parcourir(v)

    parcourir(data)
    return out


def base(r):
    return {"tier": r.get("tier", ""), "entreprise": r.get("entreprise", ""), "entreprise_id": r.get("entreprise_id", ""),
            "ordre": r.get("ordre", ""), "cibles": r.get("cibles", ""), "prenom": r.get("prenom", ""),
            "titre": r.get("titre", ""), "site_entreprise": site_propre(r.get("domaine", ""))}


def retrouver(contact, lot):
    """relie un contact renvoyé par Apollo à sa ligne (par email, LinkedIn, sinon prénom + nom)."""
    for cle in ("email", "linkedin_url"):
        for r, m, statut, c in lot:
            if contact.get(cle) and contact.get(cle) == c.get(cle):
                return r, m, statut, c
    for r, m, statut, c in lot:
        if (contact.get("first_name"), contact.get("last_name")) == (c.get("first_name"), c.get("last_name")):
            return r, m, statut, c
    return None, None, None, None


def main() -> None:
    ap = argparse.ArgumentParser(description="Enrichit (crédits) et crée les contacts validés dans Apollo.")
    argument_campagne(ap)
    ap.add_argument("fichier", nargs="?", help="fichier de revue (défaut : apollo/contacts-a-valider.csv)")
    ap.add_argument("--go", action="store_true", help="lancer l'enrichissement (crédits) et la création des contacts")
    ap.add_argument("--liste", help="nom de base des listes de contacts (défaut : [apollo] liste_contacts)")
    ap.add_argument("--limite", type=int, help="ne traiter que les N premières personnes (test)")
    ap.add_argument("--mobiles", choices=["non", "entree", "tous"],
                    help="mobiles à demander (défaut : [apollo] mobiles, true = tous ; 8 crédits par numéro)")
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    P = Persona(camp.config)
    cfg = camp.config["apollo"]
    fichier = Path(args.fichier) if args.fichier else camp.apollo / "contacts-a-valider.csv"
    if not fichier.is_file():
        raise SystemExit(f"{fichier} : fichier introuvable. " + (
            "Vérifier le chemin du fichier de revue." if args.fichier else
            "Lancer d'abord chercher_contacts.py (fichier de revue, colonne garder à relire)."))
    nom_liste = (args.liste or cfg.get("liste_contacts") or "").strip()
    if not nom_liste:
        raise SystemExit("Nom des listes de contacts absent : renseignez [apollo] liste_contacts dans campagne.toml "
                         "(« Segment · Persona · Mois ») ou passez --liste.")
    mobiles = args.mobiles or ("tous" if cfg.get("mobiles") else "non")
    mobile_pour = lambda r: mobiles == "tous" or (mobiles == "entree" and r.get("ordre") == ORDRE_ENTREE)
    from apollo_api import pays_contacts
    pays_ok = pays_contacts(camp.config)
    sel = lire(fichier)
    if args.limite:  # test : exactement le premier lot du passage complet (relu ensuite depuis le cache, sans recrédit)
        premiers = groupes([r for r in sel if r.get("apollo_id")], mobile_pour)
        sel = premiers[0][1][:args.limite] if premiers else []
    hors = sum(1 for r in sel if not r.get("apollo_id"))
    n_mob = sum(1 for r in sel if mobile_pour(r))
    print(f"{len(sel)} personnes retenues ({hors} trouvées hors Apollo, enrichies par LinkedIn ou nom + domaine) -> "
          f"{len(sel) + CREDITS_MOBILE * n_mob} crédits au maximum (1 par personne trouvée"
          + (f", plus {CREDITS_MOBILE} par mobile trouvé pour {n_mob} personnes" if n_mob else ", sans téléphone")
          + f", jamais d'email personnel) ; listes : « {nom_liste} » + entrée/relais")
    print(f"pays acceptés pour un contact (sauf dirigeant) : {', '.join(sorted(pays_ok))}" if pays_ok else
          "pays acceptés : aucun filtre ([apollo] pays_contacts, [cible] pays et pays_voisins vides)")
    if not args.go:
        print("Aperçu seulement : rien n'a été appelé. Relancer avec --go pour lancer (après accord).")
        return

    from apollo_api import Apollo, code_pays_apollo, noms_listes
    from chercher_contacts import prenom_ok, regional
    api = Apollo(camp.apollo / "cache")
    src = camp.fichier("prospection-signaux.csv")
    fiches = {r["id"]: r for r in lire_csv(src)} if src.exists() else {}

    # 1. enrichissement : lots séparés (par id d'un côté, par LinkedIn ou nom de l'autre, reliés par leur rang)
    enrichis, credits, demandes = {}, 0, []
    for mob, groupe in groupes(sel, mobile_pour):
        for i in range(0, len(groupe), 10):
            lot = groupe[i:i + 10]
            d = api.enrichir([detail(r) for r in lot], mobiles=mob)
            credits += d.get("credits_consumed") or 0
            if mob and d.get("request_id"):
                demandes.append(d["request_id"])
            for r, m in zip(lot, d.get("matches") or []):
                if not m:
                    continue
                if r.get("apollo_id") and m.get("id") != r["apollo_id"]:
                    m = next((x for x in d["matches"] if x and x.get("id") == r["apollo_id"]), None)
                elif not r.get("apollo_id") and not prenom_ok(r.get("prenom") or "", m.get("first_name")):
                    m = None
                if m:
                    enrichis[id(r)] = m
    numeros = {}
    for rid in demandes:  # mobiles : résultat asynchrone, lu une fois prêt
        numeros.update(mobiles_du_resultat(api.resultat_webhook(rid)))
    print(f"enrichis : {len(enrichis)}/{len(sel)} ; avec email : {sum(1 for m in enrichis.values() if m.get('email'))}"
          + (f" ; mobiles trouvés : {sum(1 for m in enrichis.values() if numeros.get(m.get('id')))}" if demandes else "")
          + f" ; crédits annoncés par Apollo (réponses relues du cache comprises) : {credits}")

    # 2. création des contacts, par étape (entrée / relais) pour les listes
    existantes = {l["name"] for l in api.listes() if l.get("modality") == "contacts"}
    for nom in noms_listes(nom_liste):
        if nom not in existantes:
            api.creer_liste(nom)
    f_sortie = camp.apollo / "contacts-crees.csv"
    precedents = {r["contact_id"]: r for r in lire_csv(f_sortie) if r.get("contact_id")} if f_sortie.exists() else {}
    sortie, par_ordre = [], defaultdict(list)
    for r in sel:
        m = enrichis.get(id(r)) or {}
        statut = "créé"
        email = m.get("email")
        employeur = (m.get("organization") or {}).get("name") or ""
        if m and not r.get("apollo_id"):  # trouvé sur le web : Apollo le place-t-il bien chez l'entreprise ?
            if not jetons(employeur) & (jetons(r.get("entreprise")) | jetons(r.get("compte_apollo"))):
                email, statut = None, f"créé sans email (Apollo le place chez « {employeur} »)"
        pays = code_pays_apollo(m.get("country") or "")
        if not m:
            if r.get("apollo_id"):
                sortie.append({**base(r), "statut": "non enrichi (introuvable)"})
                continue
            statut = "créé sans email (inconnu d'Apollo)"
        elif pays_ok and m.get("country") and pays not in pays_ok:
            # exception : un vrai dirigeant de l'entreprise basé à l'étranger reste un contact d'entrée
            titre = m.get("title") or r.get("titre") or ""
            pays_ent = fiches.get(r.get("entreprise_id"), {}).get("pays", "")
            dirigeant = (seniorite(titre) >= 5 and "direction" in P.familles_titre(titre)
                         and not regional(titre, pays_ent) and not regional(employeur, pays_ent)
                         and (not employeur or bool(jetons(employeur) & (jetons(r.get("entreprise")) | jetons(r.get("compte_apollo"))))))
            if not dirigeant:
                sortie.append({**base(r), "nom": m.get("last_name") or "", "email": m.get("email") or "",
                               "linkedin": m.get("linkedin_url") or "", "pays": pays or m["country"],
                               "statut": f"non créé (basé à l'étranger : {m['country']})"})
                continue
            statut = f"créé (dirigeant basé à l'étranger : {m['country']})"
        contact = {"first_name": m.get("first_name") or r.get("prenom"),
                   "last_name": m.get("last_name") or (r.get("nom_masque") if not r.get("apollo_id") else None),
                   "title": m.get("title") or r.get("titre"), "organization_name": r.get("compte_apollo") or r.get("entreprise"),
                   "account_id": r.get("account_id"), "linkedin_url": m.get("linkedin_url") or r.get("linkedin"),
                   "present_raw_address": ", ".join(x for x in (m.get("city"), m.get("state"), m.get("country")) if x),
                   "email": email, "mobile_phone": numeros.get(m.get("id"))}
        par_ordre[r.get("ordre") or ORDRE_RELAIS].append((r, m, statut, {k: v for k, v in contact.items() if v}))
    for ordre, items in par_ordre.items():
        listes = [nom_liste, f"{nom_liste} - {ordre}"]
        for i in range(0, len(items), 100):
            lot = items[i:i + 100]
            d = api.creer_contacts([c for _, _, _, c in lot], listes)
            crees = d.get("created_contacts") or d.get("contacts") or []
            existants = d.get("existing_contacts") or []
            # créés ou déjà présents : ajout explicite aux listes (sans retirer le contact de ses autres listes)
            ids = [c["id"] for c in crees + existants if c.get("id")]
            if ids:
                api.ajouter_aux_listes(ids, listes)
            for deja, contacts in ((False, crees), (True, existants)):
                for c in contacts:
                    r, m, statut, envoye = retrouver(c, lot)
                    avant = precedents.get(c.get("id"), {}).get("statut", "")
                    # créé par un passage précédent (test --limite) : son statut d'origine est gardé
                    final = avant if deja and avant.startswith("créé") else \
                        "déjà dans Apollo, ajouté aux listes" if deja else statut
                    if r:
                        sortie.append({**base(r), "nom": envoye.get("last_name") or "", "email": envoye.get("email") or "",
                                       "statut_email": (m.get("email_status") or "").lower(),
                                       "linkedin": envoye.get("linkedin_url") or "", "ville": m.get("city") or "",
                                       "pays": code_pays_apollo(m.get("country") or "") or m.get("country") or "",
                                       "seniorite": m.get("seniority") or "", "contact_id": c.get("id"),
                                       "statut": final})
    # lignes d'un passage précédent (test --limite, ajouts à la main) dont le contact n'est pas repris : gardées
    repris = {s["contact_id"] for s in sortie if s.get("contact_id")}
    anciens = [r for i, r in precedents.items() if i not in repris]
    ecrire_csv(f_sortie, COLONNES, sortie + anciens)
    stats = defaultdict(int)
    for s in sortie:
        stats[s["statut"].split(" (")[0]] += 1
    tailles = {}  # compte exact (le compteur des listes Apollo est mis à jour en différé)
    for l in api.listes():
        if l["name"] in noms_listes(nom_liste) and l.get("modality") == "contacts":
            d = api.contacts_search([l["id"]], per_page=1)
            tailles[l["name"]] = (d.get("pagination") or {}).get("total_entries")
    print(f"contacts : {dict(stats)} ; gardés d'un passage précédent : {len(anciens)} -> {f_sortie}")
    print(f"listes Apollo : {tailles} (recompter quelques secondes plus tard si besoin) ; {api.appels} appels API")


if __name__ == "__main__":
    main()
