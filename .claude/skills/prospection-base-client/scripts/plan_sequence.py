"""Étape 8 : plan de séquence, une ligne par contact (aucun appel réseau, 0 crédit).

Règles de la chaîne enseignée en formation, appliquées de façon simple et déterministe :
- vagues : les comptes de score A d'abord, puis B (base-abc.csv, dans l'ordre du rang), 10 à 20 comptes par semaine
  (--comptes-semaine, 15 par défaut) ; les comptes C (retirés) restent hors plan ;
- une seule voix par entreprise : d'abord le contact d'entrée (s'il y en a plusieurs : email vérifié d'abord, puis la
  séniorité la plus haute), puis les relais un par un, chacun seulement après la séquence de la voix précédente (quatre
  semaines plus tard), sans réponse, ou plus tôt si le dirigeant renvoie vers lui ; les autres contacts d'entrée
  viennent en dernier. Une entreprise sans contact d'entrée commence par son premier relais ;
- canal : email si statut_email vaut verified ; sinon appel si un numéro est connu (appels/ordre-appel.csv ou colonnes
  de téléphone des contacts), sinon LinkedIn si le profil est connu, sinon appel (numéro à trouver) ;
- cadence : J1 email 1 (le signal et la proposition d'échange), J4 appel, J8 email 2 dans le même fil, J15 email 3
  (un autre angle), J22 email 4 de clôture courtoise ; sans email vérifié, les emails deviennent des appels ou des
  messages LinkedIn aux mêmes jours. Tout s'arrête à la première réponse, même un « non merci ».
Un contact qui a répondu et décliné (a_eviter dans appels/ordre-appel.csv) reste dans le fichier, sans canal.

Entrées, dans le dossier de campagne : base-abc.csv (score, rang, signal et date, source, première phrase), les
contacts (--contacts, sinon apollo/contacts-crees.csv, sinon apollo/contacts-importes.csv), et s'ils existent
appels/ordre-appel.csv et appels/ordre-appel-relais.csv (téléphone, historique, à éviter), rattachés par la clé du
contact (id Apollo, ou id local d'un contact importé absent d'Apollo, voir ordre_appel.cle_contact).
Sortie : appels/plan-sequence.csv. Les dates partent du lundi qui suit la date de référence de la campagne
(--debut pour en choisir une autre).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/plan_sequence.py --campagne campagnes/<nom>
      [--comptes-semaine 15] [--scores A,B] [--debut AAAA-MM-JJ] [--contacts <csv>]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import ORDRE_ENTREE, Campagne, argument_campagne, ecrire_csv, lire_csv
from ordre_appel import Index, charger_contacts, cle_contact, historique

SENIORITE = ["owner", "founder", "c_suite", "partner", "vp", "head", "director", "manager", "senior", "entry", "intern"]
JOURS = (0, 3, 7, 14, 21)                     # J1, J4, J8, J15, J22
ECART_VOIX = 28                                # une séquence de 22 jours, puis la voix suivante
ETAPES = {
    "email": "J1 email 1 ; J4 appel ; J8 email 2 (même fil) ; J15 email 3 ; J22 email 4 (clôture)",
    "appel": "J1 appel ; J4 appel ; J8 appel ; J15 appel ; J22 dernier appel (clôture)",
    "LinkedIn": "J1 invitation LinkedIn (note de moins de 200 caractères) ; J4 appel au standard ; J8 message LinkedIn ; "
                "J15 message LinkedIn ; J22 message de clôture",
}
COLONNES = ["vague", "j1", "j4", "j8", "j15", "j22", "etapes", "score_abc", "rang", "tier", "entreprise",
            "entreprise_id", "voix", "ordre", "condition", "prenom", "nom", "titre", "email", "statut_email",
            "telephone", "linkedin", "canal", "signal", "source", "phrase_signal", "pourquoi_maintenant",
            "deja_contacte", "remarque", "contact_id"]


def lundi_suivant(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


def rang_contact(c: dict, i: int) -> tuple:
    s = (c.get("seniorite") or "").lower()
    return (c.get("statut_email") != "verified", SENIORITE.index(s) if s in SENIORITE else len(SENIORITE), i)


def canal(c: dict, tel: str) -> tuple[str, str]:
    if c.get("statut_email") == "verified":
        return "email", ""
    if tel:
        return "appel", ""
    if c.get("linkedin"):
        return "LinkedIn", ""
    return "appel", "numéro à trouver (standard de l'entreprise)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan de séquence, une ligne par contact (étape 8, aucun appel réseau).")
    argument_campagne(ap)
    ap.add_argument("--comptes-semaine", type=int, default=15, help="comptes par vague (10 à 20 ; défaut 15)")
    ap.add_argument("--scores", default="A,B", help="scores A/B/C inclus dans les vagues, dans l'ordre (défaut A,B)")
    ap.add_argument("--debut", help="date du J1 de la première vague, AAAA-MM-JJ (défaut : lundi suivant la date de référence)")
    ap.add_argument("--contacts", help="CSV de contacts (défaut : apollo/contacts-crees.csv, sinon contacts-importes.csv)")
    a = ap.parse_args()
    if a.comptes_semaine < 1:
        raise SystemExit("--comptes-semaine doit valoir au moins 1.")

    camp = Campagne(a.campagne)
    base_csv = camp.fichier("base-abc.csv")
    if not base_csv.exists():
        raise SystemExit(f"{base_csv} absent : lancer d'abord reinjecter_apollo.py (aperçu, sans --go), étape 7.")
    base = Index(lire_csv(base_csv))
    contacts, source = charger_contacts(camp, a.contacts)
    appels = {}                                # clé du contact (id Apollo ou id local) -> ligne de l'ordre d'appel
    for nom in ("ordre-appel.csv", "ordre-appel-relais.csv"):
        if (camp.dossier / "appels" / nom).exists():
            appels.update({cle_contact(r): r for r in lire_csv(camp.dossier / "appels" / nom)})
    scores = [s.strip().upper() for s in a.scores.split(",") if s.strip()]
    try:
        debut = date.fromisoformat(a.debut) if a.debut else lundi_suivant(camp.date_reference())
    except ValueError:
        raise SystemExit(f"--debut : date invalide « {a.debut} » (format AAAA-MM-JJ).")

    # contacts par compte de base-abc.csv
    par_compte, orphelins = defaultdict(list), []
    for i, c in enumerate(contacts):
        b = base.de(c)
        (par_compte[b["id"]].append((i, c)) if b.get("id") else orphelins.append(c))
    comptes = sorted((b for b in base.lignes if b.get("id") in par_compte and b.get("score_abc") in scores),
                     key=lambda b: (scores.index(b["score_abc"]), int(b["rang"]) if (b.get("rang") or "").isdigit() else 9999))
    vague_de = {b["id"]: k // a.comptes_semaine + 1 for k, b in enumerate(comptes)}

    lignes = []

    def ligne(c: dict, b: dict, **kw) -> dict:
        ap_ = appels.get(cle_contact(c), {})
        tel = ap_.get("telephone") or c.get("mobile") or c.get("telephone_direct") or c.get("telephone_standard") or ""
        return {"score_abc": b.get("score_abc", ""), "rang": b.get("rang", ""), "tier": b.get("tier") or c.get("tier", ""),
                "entreprise": b.get("nom") or c["entreprise"], "entreprise_id": b.get("id") or c["entreprise_id"],
                "ordre": c["ordre"], "prenom": c["prenom"], "nom": c["nom"], "titre": c["titre"], "email": c["email"],
                "statut_email": c["statut_email"], "telephone": tel, "linkedin": c["linkedin"],
                "signal": b.get("signal_et_date", ""), "source": b.get("source_signal", ""),
                "phrase_signal": b.get("phrase_signal", ""), "pourquoi_maintenant": b.get("pourquoi_maintenant", ""),
                "deja_contacte": ap_.get("deja_contacte") or historique({}, c), "contact_id": c["contact_id"],
                "_a_eviter": ap_.get("a_eviter", ""),
                **kw}

    for b in comptes:
        groupe = par_compte[b["id"]]
        entrees = sorted([(i, c) for i, c in groupe if c["ordre"] == ORDRE_ENTREE], key=lambda x: rang_contact(x[1], x[0]))
        relais = sorted([(i, c) for i, c in groupe if c["ordre"] != ORDRE_ENTREE], key=lambda x: rang_contact(x[1], x[0]))
        voix = (entrees[:1] + relais + entrees[1:]) if entrees else relais
        n = 0
        for i, c in voix:
            l = ligne(c, b, vague=vague_de[b["id"]])
            if l["_a_eviter"]:
                l.update(canal="aucun", etapes="ne pas contacter", remarque=f"à éviter : {l['_a_eviter']}")
                lignes.append(l)
                continue
            n += 1
            j1 = debut + timedelta(days=7 * (l["vague"] - 1) + ECART_VOIX * (n - 1))
            k, rem = canal(c, l["telephone"])
            if n == 1 and c["ordre"] != ORDRE_ENTREE and entrees:
                cond = "dès la vague, à valider : le contact d'entrée a décliné"
            elif n == 1:
                cond = "dès la vague" + ("" if c["ordre"] == ORDRE_ENTREE else " (pas de contact d'entrée : on commence par le relais)")
            elif c["ordre"] == ORDRE_ENTREE:
                cond = "autre contact d'entrée : seulement si personne n'a répondu"
            else:
                cond = "après la séquence de la voix précédente, sans réponse, ou plus tôt si le dirigeant renvoie vers lui"
            if not c["contact_id"]:
                rem = "; ".join(x for x in (rem, "pas d'id Apollo : contact non créé, à inscrire à la main") if x)
            if c["ordre"] == ORDRE_ENTREE and n == 1 and not b.get("phrase_signal") and b.get("score_abc") == "A":
                rem = "; ".join(x for x in (rem, "première phrase à rédiger (consignes/phrases-signal.md)") if x)
            l.update(voix=n, condition=cond, canal=k, etapes=ETAPES[k], remarque=rem,
                     **{f"j{j + 1}": (j1 + timedelta(days=j)).isoformat() for j in JOURS})
            lignes.append(l)

    # hors plan : comptes d'un autre score, contacts sans compte dans base-abc.csv
    for b in base.lignes:
        if b.get("id") in par_compte and b.get("score_abc") not in scores:
            for i, c in par_compte[b["id"]]:
                lignes.append(ligne(c, b, vague="hors plan", canal="aucun", etapes="",
                                    remarque=f"compte {b.get('score_abc') or '?'} ({b.get('raison_abc') or 'hors des scores retenus'})"))
    for c in orphelins:
        lignes.append(ligne(c, {}, vague="hors plan", canal="aucun", etapes="",
                            remarque="entreprise absente de base-abc.csv (entreprise_id, nom ou site à vérifier)"))
    dest = camp.appels / "plan-sequence.csv"
    ecrire_csv(dest, COLONNES, lignes)

    planifies = [l for l in lignes if isinstance(l.get("vague"), int) and l.get("voix")]
    n_vagues = max(vague_de.values(), default=0)
    print(f"{len(lignes)} contacts (source : {source.name}) -> {dest}")
    print(f"{len(comptes)} comptes en {n_vagues} vague(s) de {a.comptes_semaine} au plus, J1 de la première : {debut.isoformat()}")
    if not 10 <= a.comptes_semaine <= 20:
        print("! la formation conseille 10 à 20 comptes par semaine")
    for v in range(1, n_vagues + 1):
        ids = [k for k, x in vague_de.items() if x == v]
        print(f"  vague {v} : {len(ids)} comptes, scores {dict(Counter(base.par_id[k].get('score_abc') for k in ids))}")
    print("voix 1 par canal :", Counter(l["canal"] for l in planifies if l["voix"] == 1).most_common(),
          "| voix suivantes :", sum(1 for l in planifies if l["voix"] > 1),
          "| à éviter :", sum(1 for l in lignes if l.get("canal") == "aucun" and l.get("vague") != "hors plan"),
          "| hors plan :", sum(1 for l in lignes if l.get("vague") == "hors plan"))
    sans_contact = [b for b in base.lignes if b.get("score_abc") in scores and b.get("id") not in par_compte]
    if sans_contact:
        print(f"! {len(sans_contact)} compte(s) {'/'.join(scores)} sans aucun contact (étape 6) : "
              + ", ".join(b.get("nom", "?") for b in sans_contact[:8]) + (" ..." if len(sans_contact) > 8 else ""))
    a_rediger = sum(1 for l in planifies if "première phrase" in l.get("remarque", ""))
    if a_rediger:
        print(f"! {a_rediger} compte(s) A sans première phrase : consignes/phrases-signal.md, puis reinjecter_apollo.py --phrases")


if __name__ == "__main__":
    main()
