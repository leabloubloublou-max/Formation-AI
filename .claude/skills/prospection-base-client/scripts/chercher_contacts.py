"""Étape 6, 2e partie : trouve dans Apollo (0 crédit) les personnes à contacter, entreprise par entreprise.

Entrées : apollo/cibles.json (extraire_personas.py), prospection-signaux.csv (pays, dirigeants, et toute la ligne
pour reconnaître un employeur lié) et la liste de comptes Apollo [apollo] liste_comptes (creer_comptes.py ou import
à la main). Facultatifs : apollo/trouves-web.json (chercher_web.py) et apollo/comptes-manuels.csv (colonnes
entreprise, compte_apollo : une entreprise dont le compte Apollo porte un autre nom, rapprochée à la main).
Pour chaque compte :
- toutes les personnes de l'organisation Apollo (recherche par organization_id, jusqu'à 500), sinon par domaine
  ou par nom (filtrées sur le nom de l'employeur actuel, la recherche par domaine incluant les anciens salariés) ;
- personnes nommées : prénom + nom masqué Apollo (« Cu***n » = 2 premières lettres et dernière), puis recherche par nom ;
- rôles : intitulé de poste (FR/DE/EN/IT) de la famille demandée, le plus senior d'abord ; un rôle déjà tenu par une
  personne nommée trouvée (même étape entrée/relais) n'ajoute personne ;
- aucune entrée retenue : les dirigeants inscrits au registre (colonne dirigeants) ;
- personnes trouvées sur le web (chercher_web.py) : cherchées dans Apollo, sinon gardées avec leur URL LinkedIn.
Sorties : apollo/contacts-a-valider.csv (colonne garder à relire), apollo/couverture.csv (une ligne par entreprise),
apollo/comptes-apollo.json (comptes de la liste, tels qu'Apollo les renvoie).

Usage : .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne <dossier>
            [--entreprises "mot1,mot2"] [--liste-comptes NOM]
  --entreprises : test sur quelques entreprises (sous-chaîne du nom), sorties suffixées -test.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import ORDRE_ENTREE, ORDRE_RELAIS, PAYS, Campagne, argument_campagne, domaine, ecrire_csv, lire_csv
from persona import Persona, dirigeants, jetons, norm_texte as norm, seniorite

MAX_PAGES = 5
ORDRE_TIER = {"A": 0, "B": 1, "C": 2, "D": 3}
COLONNES_REVUE = ["garder", "tier", "entreprise", "entreprise_id", "cibles", "ordre", "confiance", "prenom",
                  "nom_masque", "titre", "email_dispo", "employeur_apollo", "apollo_id", "compte_apollo", "account_id",
                  "note", "domaine", "linkedin"]
COLONNES_COUVERTURE = ["tier", "entreprise", "entreprise_id", "compte_apollo", "recherche", "personnes_apollo",
                       "cibles", "trouvees", "nommees", "non_trouvees"]
CONFIANCE = {5: "rôle : dirigeant", 4: "rôle : responsable", 3: "rôle : manager", 2: "rôle : spécialiste"}

# zones citées dans un intitulé (« General Manager North America ») ; valeur = code du pays, vide = toujours étranger
REGIONS = {"north america": "", "americas": "", "latin america": "", "u s": "us", "usa": "us", "asia": "", "apac": "",
           "emea": "", "nordics": "", "benelux": "", "uk": "gb", "china": "cn", "india": "in", "japan": "jp",
           "singapore": "sg", "canada": "ca", "brazil": "br", "mexico": "mx", "australia": "au", "pty": "", "pte": "",
           "scandinavia": "", "spain": "es", "germany": "de", "deutschland": "de", "france": "fr", "italy": "it",
           "italia": "it", "austria": "at", "switzerland": "ch", "schweiz": "ch", "suisse": "ch", "poland": "pl",
           "netherlands": "nl", "belgium": "be", "portugal": "pt", "sweden": "se", "denmark": "dk"}


def prenom_ok(cible, apollo, souple=False):
    a, b = norm(cible.replace("-", " ")).split(), norm((apollo or "").replace("-", " ")).split()
    if not a or not b:
        return False
    if len(a) > 1 and len(b) > 1:
        return a[:2] == b[:2]
    if a[0] == b[0] or (len(a) == 1 and a[0] in b) or (len(b) == 1 and b[0] in a):
        return True
    # surnom (Beni / Benjamin) : seulement dans l'entreprise, le nom masqué faisant le reste
    return souple and len(a[0]) >= 3 and len(b[0]) >= 3 and a[0][:3] == b[0][:3]


def nom_ok(nom, masque, souple=False):
    """masque Apollo « Cu***n » : début et fin du nom de famille."""
    m = re.match(r"^([^*]*)\*+([^*]*)$", masque or "")
    variantes = {norm(nom), norm(nom).replace(" ", ""), norm(nom).split()[-1] if norm(nom) else ""}
    if not m:
        initiale = norm(masque).replace(" ", "")
        if souple and len(initiale) == 1:
            return norm(nom).startswith(initiale)
        return norm(masque) in variantes
    deb, fin = norm(m.group(1)).replace(" ", ""), norm(m.group(2)).replace(" ", "")
    return any(v and v.replace(" ", "").startswith(deb) and v.endswith(fin) for v in variantes)


def decoupes(nom):
    toks = [t for t in nom.replace(".", " ").split() if t.lower() not in ("dr", "prof", "ing", "dipl")]
    return [(" ".join(toks[:i]), " ".join(toks[i:])) for i in range(1, len(toks))]


def correspond(nom_cible, p, souple=False):
    prenom, masque = p.get("first_name"), p.get("last_name_obfuscated")
    return any((prenom_ok(pr, prenom, souple) and nom_ok(nm, masque, souple)) or
               (prenom_ok(nm, prenom) and nom_ok(pr, masque))  # ordre inversé dans Apollo
               for pr, nm in decoupes(nom_cible))


def meilleur(cands):
    """doublons Apollo : on préfère le profil avec email puis le plus récent."""
    return sorted(cands, key=lambda p: (bool(p.get("has_email")), p.get("last_refreshed_at") or ""), reverse=True)[0]


def employeur(p):
    return (p.get("organization") or {}).get("name") or ""


def regional(titre, pays):
    """intitulé (ou employeur) rattaché à une autre zone que le pays de l'entreprise (« General Manager APAC »)."""
    t, pays = f" {norm(titre)} ", (pays or "").lower()
    return any(f" {r.strip()} " in t and not (v and v == pays) for r, v in REGIONS.items())


def domaines_compte(compte, lignes):
    return sorted({domaine(compte.get("primary_domain") or compte.get("domain") or "")} | {e["domaine"] for e in lignes}
                  - {""})


def charger_manuels(chemin) -> list[tuple[str, str]]:
    """apollo/comptes-manuels.csv (facultatif) : (sous-chaîne du nom de l'entreprise, sous-chaîne du nom du compte)."""
    if not chemin.exists():
        return []
    out = []
    for r in lire_csv(chemin):
        e = (r.get("entreprise") or r.get("nom") or "").strip()
        c = (r.get("compte_apollo") or r.get("compte") or "").strip()
        if e and c:
            out.append((e, c))
    return out


def rapprocher_comptes(cibles, comptes, manuels):
    par_dom = {}
    for c in comptes:
        for d in (c.get("primary_domain"), c.get("domain"), c.get("website_url")):
            if domaine(d or ""):
                par_dom.setdefault(domaine(d), c)
    lien, pris = {}, set()
    for e in cibles:
        c = par_dom.get(e["domaine"]) if e["domaine"] else None
        if not c:
            man = next((v for k, v in manuels if k.lower() in e["nom"].lower()), None)
            if man:
                c = next((x for x in comptes if man.lower() in (x.get("name") or "").lower()), None)
                if not c:
                    print(f"  ! comptes-manuels.csv : aucun compte « {man} » dans la liste (pour {e['nom']})")
        if not c:
            score = sorted(((len(jetons(e["nom"]) & jetons(x["name"])) / max(1, len(jetons(e["nom"]) | jetons(x["name"]))), x)
                            for x in comptes if x["id"] not in pris), key=lambda s: -s[0])
            if score and score[0][0] > 0:
                c = score[0][1]
        if c:
            lien[e["id"]] = c
            pris.add(c["id"])
    return lien


class Recherche:
    def __init__(self, api, P: Persona, pays_apollo):
        self.api, self.P, self.pays_apollo = api, P, pays_apollo

    def organisation(self, compte, lignes, pays=""):
        """personnes actuellement chez l'employeur, plus celles qu'Apollo rattache à une société sœur (même domaine,
        même pays, nom d'employeur proche) ; renvoie (personnes, total, mode)."""
        noms = jetons(compte["name"]) | {t for e in lignes for t in jetons(e["nom"])}
        doms = domaines_compte(compte, lignes)
        gens, total, mode = [], 0, ("domaine" if doms else "nom d'entreprise")
        if compte.get("organization_id"):
            page, mode = 1, "organisation"
            while True:
                d = self.api.personnes(organization_ids=[compte["organization_id"]], page=page)
                gens += d.get("people") or []
                total = d.get("total_entries") or 0
                if len(gens) >= total or page >= MAX_PAGES or not d.get("people"):
                    break
                page += 1
        # la recherche par domaine inclut les anciens salariés : on ne garde que l'employeur actuel au nom proche
        lieu = self.pays_apollo(pays) if compte.get("organization_id") else None
        q = dict(domaines=doms, lieux=[lieu] if lieu else None) if doms else \
            dict(mots=re.sub(r"\(.*", "", compte["name"]).strip())
        vus, extra = {p["id"] for p in gens}, []
        for page in range(1, 4):
            d = self.api.personnes(page=page, **q)
            for p in d.get("people") or []:
                if p["id"] not in vus and jetons(employeur(p)) & noms:
                    vus.add(p["id"])
                    extra.append(p)
            if len(d.get("people") or []) < 100:
                break
        if extra and compte.get("organization_id"):
            mode += f" + {len(extra)} via domaine"
        return gens + extra, total + len(extra), mode

    def par_nom(self, nom, compte, noms_employeur, doms=()):
        """recherche par nom : dans l'organisation, partout, sans accents, puis nom de famille seul dans l'entreprise
        ou son domaine (prénom d'usage différent) ; renvoie (personne, employeur, portée)."""
        org = [compte["organization_id"]] if compte.get("organization_id") else None
        sans_accents = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode()
        famille = decoupes(nom)[-1][1] if decoupes(nom) else ""
        essais = ([("organisation", dict(nom=nom, organization_ids=org), False)] if org else []) + \
            [("partout", dict(nom=nom), False)] + \
            ([("partout", dict(nom=sans_accents), False)] if sans_accents != nom else []) + \
            ([("organisation", dict(nom=famille, organization_ids=org), True)] if org and famille else []) + \
            ([("domaine", dict(nom=famille, domaines=list(doms)), True)] if doms and famille else [])
        ailleurs = []
        for portee, q, souple in essais:
            d = self.api.personnes(per_page=25, **q)
            cands = [p for p in d.get("people") or [] if correspond(nom, p, souple)]
            chez = [p for p in cands if jetons(employeur(p)) & noms_employeur]
            if chez:
                return meilleur(chez), "même employeur", portee
            if portee == "partout":
                ailleurs += cands
        if ailleurs:
            p = meilleur(ailleurs)
            return p, employeur(p) or "?", "partout"
        return None, None, None

    def candidats(self, gens, familles, pays=""):
        """personnes dont l'intitulé relève d'une des familles, la plus senior d'abord (puis email disponible) ;
        un poste régional étranger perd 2 crans."""
        return sorted(((seniorite(p.get("title")) - 2 * regional(p.get("title"), pays), bool(p.get("has_email")), p)
                       for p in gens if familles & self.P.familles_titre(p.get("title"))),
                      key=lambda x: (x[0], x[1]), reverse=True)


def traiter(rech, compte, lignes, fiches, web, regle_web):
    P = rech.P
    doms = domaines_compte(compte, lignes)
    gens, total, mode = rech.organisation(compte, lignes, fiches.get(lignes[0]["id"], {}).get("pays", ""))
    noms_employeur = jetons(compte["name"]) | {t for e in lignes for t in jetons(e["nom"])} | \
        {t for p in gens[:20] for t in jetons((p.get("organization") or {}).get("name"))}
    choix = {}  # apollo_id -> ligne de revue
    couverture = []

    def ajouter(p, e, cible, ordre, confiance, note="", garder="oui"):
        r = choix.get(p["id"])
        if r:
            if cible not in r["cibles"].split(" + "):  # deux entreprises du même compte : même rôle cité une fois
                r["cibles"] += " + " + cible
            r["ordre"] = ORDRE_ENTREE if ORDRE_ENTREE in (r["ordre"], ordre) else ordre
            if garder == "oui":
                r["garder"] = "oui"
            return
        choix[p["id"]] = {
            "garder": garder, "tier": e["tier"], "entreprise": e["nom"], "entreprise_id": e["id"], "cibles": cible,
            "ordre": ordre, "confiance": confiance, "prenom": p.get("first_name") or "",
            "nom_masque": p.get("last_name_obfuscated") or "", "titre": p.get("title") or "",
            "email_dispo": "oui" if p.get("has_email") else "non",
            "employeur_apollo": (p.get("organization") or {}).get("name") or "", "apollo_id": p["id"],
            "compte_apollo": compte["name"], "account_id": compte["id"], "note": note,
            "domaine": e["domaine"], "linkedin": ""}

    def ajouter_web(e, w, confiance, garder):
        """personne trouvée sur le web mais pas dans Apollo : gardée avec son URL LinkedIn (enrichie par l'URL)."""
        cle = w.get("linkedin") or norm(w["nom"])
        if cle in choix:
            if w["cible"] not in choix[cle]["cibles"].split(" + "):
                choix[cle]["cibles"] += " + " + w["cible"]
            return
        toks = w["nom"].split()
        choix[cle] = {
            "garder": garder, "tier": e["tier"], "entreprise": e["nom"], "entreprise_id": e["id"], "cibles": w["cible"],
            "ordre": w["ordre"], "confiance": confiance, "prenom": toks[0], "nom_masque": " ".join(toks[1:]),
            "titre": w.get("poste") or "", "email_dispo": "?", "employeur_apollo": "", "apollo_id": "",
            "compte_apollo": compte["name"], "account_id": compte["id"], "note": w.get("source") or "",
            "domaine": e["domaine"], "linkedin": w.get("linkedin") or ""}

    def chercher_role(e, familles, libelle, ordre, seuil_garder=2):
        """meilleur profil pour un rôle (plus une alternative) ; renvoie True si quelqu'un est proposé."""
        pays = fiches.get(e["id"], {}).get("pays", "")
        cands = rech.candidats(gens, familles, pays)
        if not cands and total > len(gens) and compte.get("organization_id"):
            for f in sorted(familles):
                if not P.titres_api(f):
                    continue
                d = rech.api.personnes(organization_ids=[compte["organization_id"]], titres=P.titres_api(f), per_page=25)
                cands += rech.candidats(d.get("people") or [], familles, pays)
            cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if not cands:
            return False
        s, _, p = cands[0]
        if regional(p.get("title"), pays):  # seul candidat = un poste à l'étranger : à vérifier
            ajouter(p, e, libelle, ordre, "rôle : poste régional", garder="")
        else:
            ajouter(p, e, libelle, ordre, CONFIANCE.get(s, "rôle : junior/autre"), garder="oui" if s >= seuil_garder else "")
        alt = next((c for c in cands[1:] if c[0] >= 2 and c[2]["id"] not in choix), None)
        if alt:
            ajouter(alt[2], e, libelle + " (alternative)", ordre, "alternative", garder="")
        return True

    for e in lignes:
        fiche = jetons(" ".join(fiches.get(e["id"], {}).values()))
        trouves, manquants = [], []
        nommes_ok = []  # (familles, ordre) déjà tenus par une personne nommée (ou son repli)
        n_nommes = 0
        for c in [c for c in e["cibles"] if c["type"] == "personne"]:
            libelle = f"{c['nom']} ({c['role_texte'][:50]})"
            p, chez, conf, note, garder = None, None, "nom : sûr", "", "oui"
            locaux = [q for q in gens if correspond(c["nom"], q, souple=True)]
            if locaux:
                p = meilleur(locaux)
            else:
                q, chez, portee = rech.par_nom(c["nom"], compte, noms_employeur, doms)
                if q and chez == "même employeur":
                    p = q
                    if portee != "organisation":
                        note = f"rattaché à « {employeur(q)} » dans Apollo"
                elif q:
                    lie = {t for t in jetons(chez) if len(t) >= 4} & fiche
                    p = q
                    if lie:
                        conf, note = "nom : employeur lié", f"Apollo le place chez « {chez} », cité dans la fiche"
                    else:
                        conf, garder, note = "nom : autre employeur", "", f"Apollo le place chez « {chez} » : homonyme ou départ ?"
            if p:
                ajouter(p, e, libelle, c["ordre"], conf, note, garder)
            if p and garder == "oui":
                n_nommes += 1
                trouves.append(c["nom"])
                nommes_ok.append((set(c.get("familles", [])) | P.familles_titre(p.get("title")), c["ordre"]))
                continue
            manquants.append(f"{c['nom']} ({'à vérifier : Apollo le place chez ' + chez if p else 'absent d’Apollo'})")
            # repli : le meilleur profil sur le rôle de la personne (la famille d'entrée pour une entrée sans rôle reconnu)
            fams = set(c.get("familles", [])) or ({P.entree} if c["ordre"] == ORDRE_ENTREE else set())
            if fams and chercher_role(e, fams, f"repli pour {c['nom']} ({c['role_texte'][:40]})", c["ordre"], seuil_garder=3):
                trouves.append(f"repli pour {c['nom']}")
                nommes_ok.append((fams, c["ordre"]))
        for c in [c for c in e["cibles"] if c["type"] == "rôle"]:
            f, libelle = c["famille"], f"rôle {P.libelle(c['famille'])}"
            if any(f in fams and o == c["ordre"] for fams, o in nommes_ok):
                continue  # déjà tenu par une personne nommée trouvée
            if chercher_role(e, {f}, libelle, c["ordre"]):
                trouves.append(libelle)
                continue
            hauts = sorted(((seniorite(q.get("title")), bool(q.get("has_email")), q) for q in gens
                            if seniorite(q.get("title")) >= 4 and q["id"] not in choix), key=lambda x: (x[0], x[1]), reverse=True)
            if f == "direction" and hauts:
                ajouter(hauts[0][2], e, "rôle direction (repli : profil le plus haut placé)", c["ordre"], "repli", garder="")
                trouves.append(libelle + " (repli)")
            else:
                manquants.append(libelle)
        # aucune entrée retenue : on tente les dirigeants inscrits au registre (colonne dirigeants de la fiche)
        if not any(r["entreprise_id"] == e["id"] and r["garder"] == "oui" and r["ordre"] == ORDRE_ENTREE
                   for r in choix.values()):
            deja = {norm(c.get("nom", "")) for c in e["cibles"]}
            for nom_d, role_d in dirigeants(fiches.get(e["id"], {}).get("dirigeants", "")):
                if norm(nom_d) in deja:
                    continue
                locaux = [q for q in gens if correspond(nom_d, q, souple=True)]
                p = meilleur(locaux) if locaux else None
                if not p:
                    q, chez, _ = rech.par_nom(nom_d, compte, noms_employeur, doms)
                    p = q if chez == "même employeur" else None
                if p:
                    ajouter(p, e, f"{nom_d} ({role_d[:45]}) [registre]", ORDRE_ENTREE, "nom : dirigeant inscrit")
                    trouves.append(f"{nom_d} (registre)")
                    break
        # trouvés sur le web (chercher_web.py) : d'abord recherchés dans Apollo, sinon gardés avec leur URL LinkedIn
        for w in (web or {}).get(e["id"], []):
            w = dict(w)
            lieu = regle_web["lieu"].search(norm(w.get("entreprise_linkedin")))
            if w["statut"] == "ailleurs" and lieu:  # LinkedIn affiche un lieu, pas un employeur
                w["statut"], w["source"] = "cité", w.get("linkedin") or ""
            elif w["statut"] == "ailleurs":
                manquants.append(f"{w['nom']} : LinkedIn le place chez {w.get('entreprise_linkedin') or '?'}")
            if w["statut"] == "rôle trouvé (LinkedIn)":  # profil du pays de l'entreprise (ou d'un pays accepté) seulement
                sous = (re.match(r"https?://(\w\w)\.linkedin", w.get("linkedin") or "") or [None, ""])[1]
                pays = fiches.get(e["id"], {}).get("pays", "")
                if sous not in regle_web["sous_domaines"] | ({sous_domaine(pays)} if pays else set()):
                    continue
            if w["statut"] not in ("confirmé", "cité", "rôle trouvé (LinkedIn)"):
                continue
            # une citation ne vaut confirmation que sur le site de l'entreprise
            site = w["statut"] == "cité" and e["domaine"] and \
                ".".join(domaine(w.get("source") or "").split(".")[-2:]) == ".".join(e["domaine"].split(".")[-2:])
            locaux = [q for q in gens if correspond(w["nom"], q, souple=True)]
            p = meilleur(locaux) if locaux else None
            if not p:
                q, chez, _ = rech.par_nom(w["nom"], compte, noms_employeur, doms)
                p = q if chez == "même employeur" else None
            garder = "oui" if w["statut"] == "confirmé" or site else ""
            if p and p["id"] in choix and choix[p["id"]]["garder"] == "oui":
                continue  # déjà retenu par Apollo
            if p:
                ajouter(p, e, w["cible"], w["ordre"], "web + Apollo", note=w.get("source") or "", garder=garder)
                choix[p["id"]]["linkedin"] = w.get("linkedin") or ""
            else:
                ajouter_web(e, w, "web : " + ("profil LinkedIn" if w["statut"] == "confirmé" else "site de l'entreprise" if site
                                              else "rôle LinkedIn, à vérifier" if w["statut"].startswith("rôle")
                                              else "cité ailleurs, à vérifier") + " (hors Apollo)", garder)
            if garder == "oui":
                trouves.append(f"{w['nom']} (web)")
        couverture.append({"tier": e["tier"], "entreprise": e["nom"], "entreprise_id": e["id"],
                           "compte_apollo": compte["name"], "recherche": mode, "personnes_apollo": total,
                           "cibles": len(e["cibles"]), "trouvees": len(trouves),
                           "nommees": f"{n_nommes}/{sum(c['type'] == 'personne' for c in e['cibles'])}",
                           "non_trouvees": " ; ".join(manquants)})
    return list(choix.values()), couverture


def sous_domaine(pays: str) -> str:
    """sous-domaine LinkedIn d'un pays (uk pour GB)."""
    return {"GB": "uk"}.get(pays.upper(), pays.lower())


def regle_web(config) -> dict:
    """Lieux affichés par LinkedIn à la place d'un employeur ; pays dont un profil de rôle est accepté ([apollo]
    pays_contacts, sinon [cible] pays et pays_voisins : même règle qu'enrichir_et_creer.py)."""
    from apollo_api import pays_contacts
    pays = pays_contacts(config)
    noms = sorted({norm(n) for n in PAYS} | {"swiss"}, key=len, reverse=True)
    lieu = re.compile(r"profil|region|area|metropol|\b(?:" + "|".join(re.escape(n) for n in noms if n) + r")\b")
    sous = {sous_domaine(p) for p in pays}
    if "US" in pays:
        sous.add("")  # profils américains : www.linkedin.com, sans sous-domaine de pays
    return {"lieu": lieu, "sous_domaines": sous}


def main() -> None:
    ap = argparse.ArgumentParser(description="Recherche gratuite des contacts dans Apollo (fichier de revue).")
    argument_campagne(ap)
    ap.add_argument("--entreprises", help="liste de mots séparés par des virgules (test sur quelques entreprises)")
    ap.add_argument("--liste-comptes", help="liste de comptes Apollo (défaut : [apollo] liste_comptes)")
    args = ap.parse_args()

    camp = Campagne(args.campagne)
    P = Persona(camp.config)
    f_cibles = camp.apollo / "cibles.json"
    if not f_cibles.exists():
        raise SystemExit(f"{f_cibles} absent : lancer d'abord extraire_personas.py.")
    nom_liste = (args.liste_comptes or camp.config["apollo"].get("liste_comptes") or "").strip()
    if not nom_liste:
        raise SystemExit("Nom de la liste de comptes absent : renseignez [apollo] liste_comptes dans campagne.toml "
                         "(liste créée par creer_comptes.py ou importée dans Apollo).")
    cibles = json.loads(f_cibles.read_text(encoding="utf-8"))
    src = camp.fichier("prospection-signaux.csv")
    fiches = {r["id"]: r for r in lire_csv(src)} if src.exists() else {}
    web = defaultdict(list)  # résultats de chercher_web.py, s'il a tourné
    f_web = camp.apollo / "trouves-web.json"
    if f_web.exists():
        for w in json.loads(f_web.read_text(encoding="utf-8")):
            web[w["id"]].append(w)
    if args.entreprises:
        mots = [m.strip().lower() for m in args.entreprises.split(",") if m.strip()]
        cibles = [e for e in cibles if any(m in e["nom"].lower() for m in mots)]
        if not cibles:
            raise SystemExit(f"--entreprises : aucune entreprise de cibles.json ne contient {mots}.")

    from apollo_api import Apollo, nom_pays_apollo
    api = Apollo(camp.apollo / "cache")
    liste = api.liste(nom_liste, "accounts")
    comptes, page = [], 1
    while True:
        d = api.comptes([liste["id"]], page=page)
        comptes += d.get("accounts") or []
        if page >= ((d.get("pagination") or {}).get("total_pages") or 1):
            break
        page += 1
    if not comptes:
        raise SystemExit(f"La liste de comptes « {nom_liste} » est vide dans Apollo. La remplir d'abord : "
                         "creer_comptes.py --go, ou import de apollo/comptes-a-importer.csv dans Apollo sous ce nom ; "
                         "juste après, attendre quelques secondes (Apollo met la liste à jour en différé) et relancer.")
    (camp.apollo / "comptes-apollo.json").write_text(json.dumps(comptes, ensure_ascii=False, indent=1), encoding="utf-8")
    lien = rapprocher_comptes(cibles, comptes, charger_manuels(camp.apollo / "comptes-manuels.csv"))
    groupes = defaultdict(list)
    couv = []
    for e in cibles:
        if e["id"] in lien:
            groupes[lien[e["id"]]["id"]].append(e)
        else:
            print(f"  ! sans compte Apollo : {e['nom']}")
            couv.append({"tier": e["tier"], "entreprise": e["nom"], "entreprise_id": e["id"], "compte_apollo": "",
                         "recherche": "aucun compte dans la liste", "personnes_apollo": 0, "cibles": len(e["cibles"]),
                         "trouvees": 0, "nommees": f"0/{sum(c['type'] == 'personne' for c in e['cibles'])}",
                         "non_trouvees": ""})
    par_id = {c["id"]: c for c in comptes}
    rech = Recherche(api, P, nom_pays_apollo)
    regle = regle_web(camp.config)
    lignes = []
    for i, (cid, es) in enumerate(groupes.items(), 1):
        l, c = traiter(rech, par_id[cid], es, fiches, web, regle)
        lignes += l
        couv += c
        if i % 20 == 0:
            print(f"  {i}/{len(groupes)} comptes traités ({api.appels} appels API)")
    lignes.sort(key=lambda r: (ORDRE_TIER.get(r["tier"], 9), r["entreprise"], r["ordre"] != ORDRE_ENTREE,
                               r["garder"] != "oui"))
    couv.sort(key=lambda r: (ORDRE_TIER.get(r["tier"], 9), r["entreprise"]))
    suffixe = "-test" if args.entreprises else ""
    ecrire_csv(camp.apollo / f"contacts-a-valider{suffixe}.csv", COLONNES_REVUE, lignes)
    ecrire_csv(camp.apollo / f"couverture{suffixe}.csv", COLONNES_COUVERTURE, couv)
    gardes = [r for r in lignes if r["garder"] == "oui"]
    n_nom_ok, n_nom = (sum(int(r["nommees"].split("/")[i]) for r in couv) for i in (0, 1))
    print(f"{len(groupes)} comptes, {len(couv)} entreprises, {api.appels} appels API (0 crédit)")
    print(f"personnes nommées trouvées : {n_nom_ok}/{n_nom}")
    print(f"entreprises sans personne dans Apollo : {sum(1 for r in couv if not r['personnes_apollo'])}")
    print(f"lignes proposées : {len(lignes)} dont garder=oui : {len(gardes)} (avec email dispo : "
          f"{sum(r['email_dispo'] == 'oui' for r in gardes)}) -> enrichissement ≈ {len(gardes)} crédits max")
    print(f"-> {camp.apollo / f'contacts-a-valider{suffixe}.csv'} (colonne garder à relire) ; quota : {api.quota}")


if __name__ == "__main__":
    main()
