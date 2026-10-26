"""Étape 5 : registre du commerce suisse (Zefix) + publications FOSC/SHAB de chaque entreprise suisse.

Facultatif : seulement si signaux.registre_suisse = true dans campagne.toml, et seulement pour les entreprises
suisses (pays CH, page LinkedIn en Suisse ou site en .ch) ou de pays inconnu (correspondance quasi exacte exigée).
Hors de Suisse, on saute ce script : les scripts suivants lisent zefix.json avec {} par défaut.

Source officielle et datée, la plus fiable pour :
  - changement de direction : personnes inscrites / radiées / modifiées (directeur général, gérant,
    Geschäftsführer, président du CA, administrateur délégué...) ;
  - augmentation de capital (proxy d'une levée de fonds), marge de fluctuation du capital (Kapitalband) ;
  - fusion, reprise de patrimoine, absorption (hasTakenOver / wasTakenOverBy) ;
  - changement de raison sociale, de siège, de but ; dissolution, liquidation, faillite, radiation.

API publique utilisée par l'interface zefix.ch (sans authentification) :
  POST https://www.zefix.ch/ZefixREST/api/v1/firm/search.json   {"name": ..., "languageKey": "fr"}
  GET  https://www.zefix.ch/ZefixREST/api/v1/firm/<ehraid>.json  (fiche + toutes les publications FOSC)

Correspondance : un candidat radié depuis plus de 8 ans (--radiees-ans, à la date de référence de la campagne) est
un ancien homonyme et n'est pas retenu, sauf si la liste marque déjà l'entreprise comme fermée.

Entrées : donnees/signaux/entites.json (entites.py) ; linkedin.json s'il existe (pays et nom de la page).
Sortie : donnees/signaux/zefix.json (par entreprise : correspondance, fiche, événements FOSC parsés, signaux sur
max(36, signaux.fenetre_mois) mois). Cache repris : une relance ne traite que les nouvelles entreprises.
Ordre conseillé : un passage avant collect_linkedin.py, un second avec --refresh après (le pays et le nom LinkedIn
débloquent des filiales suisses).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> \\
      [--refresh] [--workers 4] [--radiees-ans 8]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import argument_campagne
from signaux_commun import (Store, clean_text, config, domain, donnees, fenetre_mois, langue_principale,
                            load_entities, load_json, months_ago, name_tokens, norm, ouvrir, polite_sleep, session,
                            short_name, to_date)

API = "https://www.zefix.ch/ZefixREST/api/v1"
STATUS_BONUS = {"EXISTIEREND": 0.06, "IN_AUFLOESUNG": 0.0, "GELOESCHT": -0.12}

# ---------------------------------------------------------------- parsing des publications FOSC

SECTION = re.compile(
    r"(?P<h>Nouvelles? personnes? inscrites?|Personnes? inscrites? modifiées?|Personnes? radiées?|"
    r"Inscription ou modification de personnes?|Personnes? nouvellement inscrites?|"
    r"Eingetragene Personen neu oder mutierend|Ausgeschiedene Personen und erloschene Unterschriften|"
    r"Neu eingetragene Personen|Eingetragene Personen|Persone dimissionarie e firme cancellate|"
    r"Nuove persone iscritte o modifiche|Persone iscritte|Persone dimissionarie)\s*:", re.I)
SECTION_END = re.compile(
    r"\.\s+(?=(?:Statuts|Statuten|Capital|Aktienkapital|Stammkapital|Siège|Sitz|But|Zweck|Domicile|Domizil|"
    r"Nouvelle adresse|Neue Adresse|Communication|Mitteilungen|Fusion|Raison|Firma|Publikation|Organe|Liberierung|"
    r"Libération|Apport|Sacheinlage|Selon|Gemäss|Gemäß|Sede|Scopo|Capitale|Nuov|Persone|Personne|Nouvelle|"
    r"Eingetragene|Ausgeschiedene|Inscription|Marge|Kapitalband|Les|Die|Der|Das|La|Le)\b)")
ACTION = {"nouvelle": "entree", "nouvelles": "entree", "nouvellement": "entree", "eingetragene personen neu": "entree_ou_modif",
          "neu eingetragene": "entree", "nuove": "entree_ou_modif", "inscrite modifiée": "modification",
          "inscrites modifiées": "modification", "radiée": "sortie", "radiées": "sortie", "ausgeschiedene": "sortie",
          "dimissionarie": "sortie", "inscription ou modification": "entree_ou_modif", "persone iscritte": "entree"}

ROLE_LEVELS = [  # (niveau, regex) : ordre = priorité
    ("revision", r"organe de révision|Revisionsstelle|ufficio di revisione|organo di revisione"),
    ("top", r"directeur général|directrice générale|président(?:e)? de la direction|CEO|chief executive|"
            r"administrat(?:eur|rice) délégu[ée]e?|Delegierte[rn]? des Verwaltungsrates|Delegierte[rn]?\b|"
            r"Vorsitzende[rn]? der Geschäftsleitung|Vorsitzende[rn]? der Geschäftsführung|Geschäftsführer(?:in)?|"
            r"associ[ée]e? gérant(?:e)?|gérant(?:e)?|direttore generale|amministratore delegato|gerente|"
            r"administrat(?:eur|rice) unique|einzige[sr]? Mitglied|amministratore unico|Präsident(?:in)? der Geschäftsleitung|"
            r"\bdélégu[ée]e?\b|\bdelegat[oa]\b"),
    ("president", r"président(?:e)?|Präsident(?:in)?|presidente"),
    ("direction", r"directeur|directrice|Direktor(?:in)?|Mitglied der Geschäftsleitung|membre de la direction|"
                  r"direttore|direttrice|Geschäftsleitung|Vizedirektor(?:in)?|sous-directeur|sous-directrice"),
    ("conseil", r"administrat(?:eur|rice)s?|Mitglied(?:er)? des Verwaltungsrates|Mitglied(?:er)?\b|membres?\b|membr[oi]\b|vice-président"),
    ("signature", r"fondé(?:e)? de pouvoir|procuration|Prokurist(?:in)?|Prokura|procuratore|signature|Unterschrift|firma"),
]
ROLE_RX = [(lvl, re.compile(rx, re.I)) for lvl, rx in ROLE_LEVELS]
LEVEL_RANK = {"top": 5, "president": 4, "direction": 3, "conseil": 2, "signature": 1, "revision": 0, "": 0}

CAPITAL = re.compile(
    r"(?:Capital-actions|Capital social|Capital-participation|Aktienkapital|Stammkapital|Partizipationskapital|"
    r"Capitale azionario|Capitale sociale)\s+(?:nouveau|neu|nuovo)\s*:\s*(?P<cur>CHF|EUR|USD)\s*(?P<new>[\d'’.,]+)"
    r"(?:.{0,60}?\[(?:précédemment|bisher|finora)\s*:\s*(?:CHF|EUR|USD)\s*(?P<old>[\d'’.,]+)\])?", re.I)
KAPITALBAND = re.compile(r"marge de fluctuation du capital|Kapitalband|margine di variazione del capitale|"
                         r"capital(?:-actions)? conditionnel|bedingte[sn]? (?:Aktien)?kapital", re.I)
PATTERNS = {
    "fusion": re.compile(r"\bfusion\b|Fusion\b|reprise des actifs et passifs|Übernahme der Aktiven und Passiven|"
                         r"Vermögensübertragung|transfert de patrimoine|scission|Spaltung|scissione|absorption|"
                         r"übernimmt die Aktiven|reprend les actifs", re.I),
    "raison_sociale": re.compile(r"Raison (?:sociale|de commerce) nouvelle|Nouvelle raison|Firma neu|Neue Firma|"
                                 r"Ancienne raison|Ditta nuova|Nuova ditta", re.I),
    "siege": re.compile(r"Siège nouveau|Nouveau siège|Sitz neu|Neuer Sitz|Sede nuova", re.I),
    "but": re.compile(r"But nouveau|Nouveau but|Zweck neu|Neuer Zweck|Scopo nuovo", re.I),
    "dissolution": re.compile(r"(?:société|Gesellschaft|società)[^.;]{0,30}(?:est dissoute|ist aufgelöst|wird aufgelöst|è sciolta)|"
                              r"\ben liquidation\b|\bin Liquidation\b|in liquidazione", re.I),
    "faillite": re.compile(r"\bfaillite\b|Konkurs(?!amt)|fallimento", re.I),
    "sursis": re.compile(r"sursis concordataire|Nachlassstundung|concordato", re.I),
    "faillite_annulee": re.compile(r"annulé le jugement de faillite|révoqué la faillite|Konkurs(?:eröffnung)?[^.]{0,40}"
                                   r"(?:aufgehoben|widerrufen)|revoca(?:to)? (?:del|il) fallimento", re.I),
    "radiation": re.compile(r"(?:La|la) (?:société|succursale|raison individuelle|fondation|coopérative|association) "
                            r"(?:est|a été) radiée|est radiée d'office|"
                            r"Die (?:Gesellschaft|Firma|Zweigniederlassung|Stiftung|Genossenschaft) (?:wird|ist|wurde)[^.]{0,40}gelöscht|"
                            r"(?:La|la) società (?:è|viene) cancellata", re.I),
}


def amount(s: str) -> float | None:
    s = (s or "").replace("'", "").replace("’", "").replace(" ", "")
    if s.count(",") and s.count("."):
        s = s.replace(",", "")
    s = s.replace(",", ".")
    try:
        return float(s.rstrip("."))
    except ValueError:
        return None


def role_level(txt: str) -> tuple[str, str]:
    for lvl, rx in ROLE_RX:
        m = rx.search(txt)
        if m:
            return lvl, m.group(0)
    return "", ""


ORIGIN = re.compile(r"^(?:von |de |d'|d’|des |du |da |di |in |à |a |aus |originaire|ressortissant|citoyen|cittadin|"
                    r".*Staatsangehörig|.*ressortissant|suisse$|français|française|allemand|italien|autrichien|"
                    r"néerlandais|belge|britannique|américain|canadien|espagnol|portugais|chinois)", re.I)


def person(name: str, role_txt: str, action: str, old: str = "", texte: str = "") -> dict:
    lvl, role = role_level(role_txt)
    old_lvl, old_role = role_level(old) if old else ("", "")
    if action == "entree_ou_modif":
        action = "modification" if old else "entree"
    return {"action": action, "nom": clean_name(name), "niveau": lvl, "role": role, "ancien_niveau": old_lvl,
            "ancien_role": old_role, "texte": (texte or f"{name}, {role_txt}")[:300]}


def clean_name(n: str) -> str:
    n = re.sub(r"^(?:Les pouvoirs de|Die Unterschrift von|La firma di|M\.|Mme|Herr|Frau)\s+", "", n.strip(" ,.;:"))
    return n[:80]


def parse_person(entry: str, action: str, lang: str) -> dict | None:
    """Une entrée de rubrique structurée : FR « Nom Prénom, de X, à Y, rôle, signature » ;
    DE / IT « Nom, Prénom, von X, in Y, rôle, signature [bisher: ...] »."""
    entry = entry.strip(" .;")
    if not entry or len(entry) < 4:
        return None
    old = ""
    m = re.search(r"\[(?:bisher|précédemment|finora)\s*:\s*([^\]]*)\]", entry, re.I)
    if m:
        old, entry = m.group(1), (entry[: m.start()] + entry[m.end():])
    new_part = entry
    m2 = re.search(r",?\s*désormais\s+(.*)$", entry, re.I)
    if m2:
        old, new_part = entry[: m2.start()], m2.group(1)
        entry = entry[: m2.start()]
    segs = [x.strip() for x in entry.split(",")]
    if lang != "fr" and len(segs) > 1 and not ORIGIN.match(segs[1]) and not role_level(segs[1])[0]:
        name = f"{segs[0]}, {segs[1]}"
    else:
        name = segs[0]
    texte = entry[:300] if not m2 else f"{entry[:200]} -> {new_part[:120]}"
    return person(name, new_part, action, old, texte)


# Format narratif (NE, VD, JU, GE, TI, certains cantons alémaniques) : « X n'est plus directeur ; ses pouvoirs
# sont radiés. Y, de Z, à W, est administrateur unique avec signature individuelle. » Analyse phrase par phrase.
U = "A-ZÀ-ÝÄÖÜ"
NOM = (rf"(?P<nom>[{U}][\w'’\-]+(?:,\s+[{U}][\w'’\-.]+(?:\s+[{U}][\w'’\-.]+)*"     # DE : « Müller, Hans »
       rf"|(?:\s+(?:[{U}][\w'’\-.]+|de|von|van|da|di|del|le|la|du|dos)){{1,5}}))")
NOM_RX = re.compile(NOM)
HEADER = re.compile(r"^.*?\((?:FOSC|SHAB|FUSC|SOGC)[^)]*\)\.\s*")
SENT_SPLIT = re.compile(rf"(?<=[.;])\s+(?=[{U}])")
SORTIE_VERB = re.compile(r"\b(?:n'est plus|n’est plus|ne sont plus|ne sont|ist nicht mehr|sind nicht mehr|non è più|"
                         r"non sono più|ont démissionné|a démissionné|est décédée?|ist ausgeschieden|sind ausgeschieden|"
                         r"ist zurückgetreten)\b", re.I)
POUVOIRS_RADIES = re.compile(r"(?:Les pouvoirs de|La signature de|Die Unterschrift von|Die Unterschriften von|La firma di)\s+(.+?)\s+"
                             r"(?:sont|est|ist|sind|è)\s+(?:radiée?s?|erloschen|cancellata)", re.I)
ENTREE_VERB = re.compile(r",?\s+(?:est|sont|devient|deviennent|ist|sind|wird|werden|è|sono|diventa)\s+"
                         r"(?:désormais\s+|maintenant\s+|neu\s+|nun\s+|nunmehr\s+|jetzt\s+|ora\s+)?"
                         r"(?:nommée?s?\s+|désignée?s?\s+|élue?s?\s+|gewählt\s+(?:als|zum|zur)\s+|ernannt\s+(?:als|zum|zur)\s+)?", re.I)
SIGN_CONF = re.compile(r"(?:Signature|Procuration|Kollektivunterschrift|Einzelunterschrift|Kollektivprokura|Prokura|"
                       r"Firma|Procura)[^;.]{0,40}?(?:conférée?s?|erteilt|conferita)\s+(?:à|an|a)\s+(.+)$", re.I)


def names_in(txt: str) -> list[str]:
    """Noms de personnes d'une énumération « A, jusqu'ici président, et B »."""
    out = []
    for part in re.split(r"\s+(?:et|und|e|ainsi que)\s+|;\s*", txt):
        m = NOM_RX.match(part.strip(" ,"))
        if m and not role_level(m.group("nom"))[0]:
            out.append((m.group("nom"), part))
    return out


def parse_narrative(txt: str) -> list[dict]:
    out = []
    for sent in SENT_SPLIT.split(HEADER.sub("", txt, count=1)):
        sent = sent.strip()
        m = POUVOIRS_RADIES.search(sent)
        if m:
            for nom, part in names_in(m.group(1)):
                out.append(person(nom, "signature", "sortie", texte=sent))
            continue
        m = SORTIE_VERB.search(sent)
        if m:
            pre, post = sent[: m.start()], sent[m.end():]
            for nom, part in names_in(pre):
                own = role_level(part[len(nom):])[0]        # « A, jusqu'ici président, ... »
                out.append(person(nom, part[len(nom):] if own else post, "sortie", texte=sent))
            continue
        m = SIGN_CONF.search(sent)
        if m:
            for nom, part in names_in(m.group(1)):
                out.append(person(nom, "signature", "entree", texte=sent))
            continue
        m = ENTREE_VERB.search(sent)
        if m:
            pre, post = sent[: m.start()], sent[m.end():]
            nm = NOM_RX.match(pre)
            if nm and role_level(post)[0]:
                act = "modification" if re.search(r"désormais|nunmehr", m.group(0), re.I) else "entree"
                out.append(person(nm.group("nom"), post, act, texte=sent))
    return out


BIFFE = re.compile(r"\[(?:biffé|gestrichen|cancellato|radié)\s*:[^\]]*\]", re.I)
CONTRAT = re.compile(r"(?:contrat(?: de fusion| de transfert)?|projet de (?:fusion|scission)|Vertrag|Fusionsvertrag|"
                     r"Vermögensübertragungsvertrag|Spaltungsvertrag|contratto(?: di fusione)?)\s+(?:du|vom|del)\s+"
                     r"(\d{1,2})\.(\d{1,2})\.(\d{4})", re.I)


def historical_restatement(txt: str, pub_date: str) -> bool:
    """Fusion / transfert déjà ancien republié (traduction, changement de canton) : contrat de > 12 mois."""
    d = to_date(pub_date)
    for m in CONTRAT.finditer(txt):
        try:
            c = datetime(int(m[3]), int(m[2]), int(m[1])).date()
        except ValueError:
            continue
        if d and (d - c).days > 365:
            return True
    return False


def parse_message(msg: str, pub_date: str = "") -> dict:
    txt = BIFFE.sub(" ", clean_text(msg))    # passages biffés = ancien texte remplacé, pas un événement
    persons = []
    heads = list(SECTION.finditer(txt))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(txt)
        body = txt[h.end(): end]
        cut = SECTION_END.search(body)
        if cut:
            body = body[: cut.start()]
        hl = h.group("h").lower()
        action = next((v for k, v in ACTION.items() if k in hl), "entree")
        lang = "fr" if re.search(r"personne|inscri|radi", hl) else ("it" if re.search(r"persone", hl) else "de")
        for entry in re.split(r";\s*", body):
            p = parse_person(entry, action, lang)
            if p:
                persons.append(p)
    if not heads:
        persons = parse_narrative(txt)
    out = {"texte": txt, "personnes": persons}
    cap = CAPITAL.search(txt)
    if cap:
        new, old = amount(cap.group("new")), amount(cap.group("old") or "")
        out["capital"] = {"devise": cap.group("cur"), "nouveau": new, "ancien": old,
                          "variation": (new - old) if (new is not None and old is not None) else None}
    if KAPITALBAND.search(txt):
        out["kapitalband"] = True
    for k, rx in PATTERNS.items():
        if rx.search(txt):
            out[k] = True
    if out.get("fusion") and historical_restatement(txt, pub_date):
        out["fusion"] = False
        out["fusion_historique"] = True
    return out


def events_from(firm: dict) -> list[dict]:
    evs = []
    for p in firm.get("shabPub") or []:
        try:
            mtypes = [m.get("key") for m in ast.literal_eval(p.get("mutationTypes") or "[]")]
        except (ValueError, SyntaxError):
            mtypes = []
        ev = {"date": p.get("shabDate"), "shab_id": p.get("shabId"), "canton": p.get("registryOfficeCanton"),
              "mutations": mtypes, **parse_message(p.get("message") or "", p.get("shabDate") or "")}
        evs.append(ev)
    evs.sort(key=lambda e: e["date"] or "", reverse=True)
    return evs


def langue() -> str:
    """Langue des libellés Zefix et des liens de preuve : celle de l'appelant si Zefix la connaît, sinon fr."""
    lg = langue_principale()
    return lg if lg in ("fr", "de", "it", "en") else "fr"


def fenetre_registre() -> int:
    """Fenêtre des signaux du registre : 36 mois, ou signaux.fenetre_mois s'il est plus long."""
    return max(36, fenetre_mois())


def signals_from(firm: dict, evs: list[dict], window_months: int | None = None) -> list[dict]:
    """Signaux datés (FOSC) sur la fenêtre, prêts pour le scorer."""
    window_months = window_months or fenetre_registre()
    sig = []
    url = f"https://www.zefix.ch/{langue()}/search/entity/list/firm/{firm.get('ehraid')}"
    for ev in evs:
        d = to_date(ev["date"])
        if not d or months_ago(d) > window_months:
            continue
        base = {"date": ev["date"], "source": "fosc", "url": url}
        for p in ev["personnes"]:
            lvl, old = p["niveau"], p["ancien_niveau"]
            if lvl == "revision":
                continue
            if p["action"] == "entree" and LEVEL_RANK[lvl] >= 3:
                sous = "nouveau_dirigeant" if lvl in ("top", "president") else "nouveau_cadre"
                sig.append({**base, "famille": "direction", "sous_type": sous, "niveau": lvl,
                            "resume": f"Inscription : {p['nom']} ({p['role']})", "extrait": p["texte"]})
            elif p["action"] == "modification" and LEVEL_RANK[lvl] > LEVEL_RANK[old] and LEVEL_RANK[lvl] >= 3:
                sous = "nouveau_dirigeant" if lvl in ("top", "president") else "nouveau_cadre"
                sig.append({**base, "famille": "direction", "sous_type": sous, "niveau": lvl,
                            "resume": f"Promotion : {p['nom']} ({p['ancien_role'] or '?'} -> {p['role']})",
                            "extrait": p["texte"]})
            elif p["action"] == "sortie" and LEVEL_RANK[lvl] >= 3:
                sig.append({**base, "famille": "direction", "sous_type": "depart_dirigeant", "niveau": lvl,
                            "resume": f"Radiation : {p['nom']} ({p['role']})", "extrait": p["texte"]})
            elif p["action"] in ("entree", "sortie") and lvl == "conseil":
                sig.append({**base, "famille": "direction", "sous_type": "conseil", "niveau": lvl,
                            "resume": f"{'Entrée' if p['action'] == 'entree' else 'Sortie'} CA : {p['nom']}",
                            "extrait": p["texte"]})
        cap = ev.get("capital")
        if cap and cap.get("variation") and cap["variation"] > 0:
            sig.append({**base, "famille": "financement", "sous_type": "augmentation_capital",
                        "resume": f"Capital {cap['devise']} {cap['ancien']:,.0f} -> {cap['nouveau']:,.0f} "
                                  f"(+{cap['variation']:,.0f})".replace(",", "'"), "extrait": ev["texte"][:300]})
        elif cap and cap.get("variation") is not None and cap["variation"] < 0:
            sig.append({**base, "famille": "negatif", "sous_type": "reduction_capital",
                        "resume": f"Réduction de capital {cap['devise']} {cap['ancien']:,.0f} -> {cap['nouveau']:,.0f}"
                        .replace(",", "'"), "extrait": ev["texte"][:300]})
        if ev.get("kapitalband"):
            sig.append({**base, "famille": "financement", "sous_type": "kapitalband",
                        "resume": "Marge de fluctuation / capital conditionnel (préparation de financement)",
                        "extrait": ev["texte"][:300]})
        if ev.get("fusion"):
            sig.append({**base, "famille": "ma", "sous_type": "fusion_reprise",
                        "resume": "Fusion / reprise de patrimoine inscrite", "extrait": ev["texte"][:300]})
        if ev.get("raison_sociale"):
            sig.append({**base, "famille": "projet", "sous_type": "changement_nom",
                        "resume": "Nouvelle raison sociale", "extrait": ev["texte"][:300]})
        if ev.get("siege"):
            sig.append({**base, "famille": "croissance", "sous_type": "nouveau_siege",
                        "resume": "Transfert de siège", "extrait": ev["texte"][:300]})
        if ev.get("but"):
            sig.append({**base, "famille": "projet", "sous_type": "changement_but",
                        "resume": "But social modifié", "extrait": ev["texte"][:300]})
        if ev.get("faillite_annulee"):
            sig.append({**base, "famille": "negatif", "sous_type": "faillite_annulee",
                        "resume": "Faillite prononcée puis annulée par le tribunal", "extrait": ev["texte"][:300]})
        elif ev.get("faillite") and not ev.get("fusion"):
            sig.append({**base, "famille": "negatif", "sous_type": "faillite",
                        "resume": "Faillite (registre)", "extrait": ev["texte"][:300]})
        elif ev.get("sursis"):
            sig.append({**base, "famille": "negatif", "sous_type": "sursis_concordataire",
                        "resume": "Sursis concordataire / Nachlassstundung (procédure de restructuration de dettes)",
                        "extrait": ev["texte"][:300]})
        elif (ev.get("dissolution") or ev.get("radiation")) and not ev.get("fusion"):
            sig.append({**base, "famille": "negatif", "sous_type": "dissolution",
                        "resume": "Dissolution / liquidation / radiation", "extrait": ev["texte"][:300]})
    for t in firm.get("hasTakenOver") or []:
        if t.get("shabDate") and months_ago(to_date(t["shabDate"])) <= window_months:
            sig.append({"date": t["shabDate"], "source": "fosc", "url": url, "famille": "ma",
                        "sous_type": "absorbe", "resume": f"A absorbé {t.get('name')}", "extrait": ""})
    for t in firm.get("wasTakenOverBy") or []:
        sig.append({"date": t.get("shabDate") or "", "source": "fosc", "url": url, "famille": "ma",
                    "sous_type": "absorbee_par", "resume": f"Absorbée par {t.get('name')}", "extrait": ""})
    return sig


# ---------------------------------------------------------------- correspondance entité <-> registre

def search(name: str) -> list[dict]:
    for attempt in range(3):
        try:
            r = session().post(f"{API}/firm/search.json", json={"name": name, "languageKey": langue(), "maxEntries": 30, "deletedFirms": True},
                               headers={"Accept": "application/json"}, timeout=20)
            if r.status_code == 404:
                return []
            if r.ok:
                return r.json().get("list") or []
        except Exception:  # noqa: BLE001
            pass
        polite_sleep(1.5 * (attempt + 1), 3 * (attempt + 1))
    return []


STATUS_WORDS = {"en", "liquidation", "in", "liquidazione", "radiee", "aufloesung", "i", "l", "d"}
GENERIC = {"schweiz", "suisse", "switzerland", "svizzera", "swiss", "international", "electronic", "electronics",
           "systems", "system", "technologies", "technology", "ch", "europe", "und", "et", "and", "holzwerk",
           "materiel", "industriel", "industrie", "solutions", "manufacturing", "engineering", "precision"}
HOLDING = re.compile(r"\b(?:holding|group|groupe|gruppe|fondation|stiftung|prévoyance|vorsorge|pensionskasse|"
                     r"personalf(?:ü|ue)rsorge|wohlfahrtsfonds|immobili)", re.I)


def score(ref: str, cand: dict, dom_label: str = "") -> float:
    """Proximité entre un nom de référence de l'entité et un candidat Zefix."""
    a = set(name_tokens(ref)) - STATUS_WORDS
    b = set(name_tokens(cand.get("name", ""))) - STATUS_WORDS
    if not a or not b:
        return 0.0
    ct = norm(cand.get("name", "")).split()          # domaine = suite contiguë de mots du nom (frontières de mots)
    dom_ok = len(dom_label) >= 4 and any("".join(ct[i:j]) == dom_label for i in range(len(ct)) for j in range(i + 1, len(ct) + 1))
    if a == b:
        s = 1.0
    elif a <= b:
        extra = b - a
        s = 0.85 - 0.05 * len(extra)
        if not dom_ok and not extra <= GENERIC:
            s -= 0.2
    elif b <= a:
        s = 0.8 - 0.05 * (len(a) - len(b))
    else:
        s = len(a & b) / len(a | b)
    if dom_ok:
        s += 0.06
    elif all(len(t) <= 3 for t in a) and norm(ref) != norm(cand.get("name", "")):
        s -= 0.3                                      # acronyme (ABC, EMS...) : homonymes trop fréquents
    if norm(ref) == norm(cand.get("name", "")):
        s += 0.05
    if HOLDING.search(cand.get("name", "")) and not HOLDING.search(ref):
        s -= 0.08
    s += 0.01 * len(a & b)                            # départage : correspondance plus riche
    return s + STATUS_BONUS.get(cand.get("status"), 0)


def variants(name: str) -> list[str]:
    base = short_name(name)
    flat = re.sub(r"[-\u2013+&/.,']", " ", base)
    toks = [t for t in flat.split() if norm(t) not in LEGAL_WORDS]
    out = [name.strip(), base, flat, " ".join(toks[:2])]
    longest = max(toks, key=len) if toks else ""
    if len(longest) >= 5:
        out.append(longest)
    return out


LEGAL_WORDS = {"sa", "ag", "gmbh", "sarl", "sàrl", "ltd", "co", "kg", "se", "inc"}


def references(e: dict, li: dict | None) -> list[str]:
    refs = [re.sub(r"\s*\(.*?\)\s*|\s*\(.*$", " ", e["nom"]).strip(), e["nom"], e["nom_court"], short_name(e["nom"])]
    for inner in re.findall(r"\(([^)]+)\)", e["nom"]):
        inner = re.sub(r"^(?:ex-|anciennement |aujourd.hui |groupe )", "", inner.strip(), flags=re.I)
        for part in inner.split(","):
            if re.search(r"\b(?:AG|SA|GmbH|Sàrl|Ltd)\b", part) or "ex-" in e["nom"] or "aujourd" in e["nom"]:
                refs.append(short_name(part))
    if li and li.get("nom"):
        refs.append(short_name(li["nom"]))
    for autre in e.get("autres_noms") or []:      # autres noms de la liste (nom usuel, ancien nom officiel)
        refs.append(re.sub(r"\s*\(.*?\)\s*|\s*\(.*$", " ", autre).strip())
    out = []
    for r in refs:
        if len(norm(r)) >= 3 and norm(r) not in {norm(x) for x in out} and not re.search(r"non identifi|inconnu", r, re.I):
            out.append(r.strip())
    return out


def queries_for(e: dict, li: dict | None) -> list[str]:
    out = []
    for r in references(e, li):
        for q in variants(r):
            q = q.strip()
            if len(norm(q)) >= 3 and norm(q) not in {norm(x) for x in out}:
                out.append(q)
    return out[:8]


def is_swiss_candidate(e: dict, li: dict | None) -> tuple[bool, bool]:
    """(à chercher, exige une correspondance forte)."""
    if set(e.get("flags") or []) & {"exclure", "particulier", "administration"}:
        return False, False
    pays_li = (li or {}).get("pays", "")
    if e["pays"] == "CH" or pays_li == "CH" or domain(e.get("site", "")).endswith(".ch"):
        return True, False
    if e["pays"]:
        return False, False
    # pays inconnu : souvent une filiale suisse dont la page LinkedIn est celle du groupe étranger -> registre
    # interrogé, mais correspondance quasi exacte exigée
    return True, True


RADIEE_ANS = 8       # homonyme radié depuis plus longtemps : écarté (--radiees-ans)


def resolve(e: dict, li: dict | None, radiees_ans: float = RADIEE_ANS) -> dict:
    go, strict = is_swiss_candidate(e, li)
    if not go:
        return {"statut": "hors_suisse_ou_exclu"}
    refs = references(e, li)
    dom_label = norm(domain(e.get("site", "")).split(".")[-2] if e.get("site") and "." in domain(e["site"]) else "").replace(" ", "")
    ferme = "fermee_ou_liquidation" in (e.get("flags") or [])
    cands = {}
    for q in queries_for(e, li):
        for c in search(q):
            # cohérence : une entreprise trouvée aujourd'hui (web, Apollo, liste) n'a pas été radiée il y a plus de
            # radiees_ans ans (date de référence de la campagne) ; un tel candidat est un ancien homonyme
            dd = to_date(c.get("deleteDate") or "")
            if dd and not ferme and radiees_ans and (months_ago(dd) or 0) > 12 * radiees_ans:
                continue
            sc, ref = max((score(r, c, dom_label), r) for r in refs)
            if c["ehraid"] not in cands or sc > cands[c["ehraid"]][0]:
                cands[c["ehraid"]] = (sc, c, ref)
        polite_sleep(0.3, 0.8)
    if not cands:
        return {"statut": "introuvable"}
    ranked = sorted(cands.values(), key=lambda x: -x[0])
    best_s, best, q = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else 0
    seuil = 0.92 if strict else 0.72
    if best.get("status") != "EXISTIEREND" and "fermee_ou_liquidation" not in e["flags"]:
        seuil = max(seuil, 0.9)                         # radiée / en liquidation : correspondance quasi exacte exigée
    top = [{"nom": c["name"], "ehraid": c["ehraid"], "siege": c["legalSeat"], "statut": c["status"],
            "score": round(s, 2)} for s, c, _ in ranked[:5]]
    if best_s < seuil:
        return {"statut": "non_concluant", "candidats": top}
    if strict:  # pays inconnu, site hors .ch : mêmes mots exactement (« Exemple GmbH » ≠ « Exemple Bau GmbH »)
        bt = set(name_tokens(best["name"])) - STATUS_WORDS
        if not any(set(name_tokens(r)) - STATUS_WORDS == bt for r in refs):
            return {"statut": "non_concluant", "candidats": top}
    ambigu = second >= best_s - 0.025 and ranked[1][1]["name"].lower() != best["name"].lower()
    r = session().get(f"{API}/firm/{best['ehraid']}.json", timeout=25)
    if not r.ok:
        return {"statut": f"fiche_http_{r.status_code}", "candidats": top}
    firm = r.json()
    evs = events_from(firm)
    return {
        "statut": "ambigu" if ambigu else "ok",
        "score": round(best_s, 2), "requete": q, "candidats": top if ambigu else top[:2],
        "nom": firm.get("name"), "uid": firm.get("uidFormatted"), "ehraid": firm.get("ehraid"),
        "siege": firm.get("legalSeat"), "canton": next((x["canton"] for x in evs if x.get("canton")), ""),
        "forme": firm.get("legalFormId"), "etat": firm.get("status"), "radiation": firm.get("deleteDate"),
        "but": (firm.get("purpose") or "")[:600],
        "adresse": firm.get("address") or {},
        "anciens_noms": firm.get("oldNames"),
        "a_absorbe": [x.get("name") for x in firm.get("hasTakenOver") or []],
        "absorbee_par": [x.get("name") for x in firm.get("wasTakenOverBy") or []],
        "revision": [x.get("name") for x in firm.get("auditFirms") or []],
        "extrait_cantonal": firm.get("cantonalExcerptWeb"),
        "premiere_publication": evs[-1]["date"] if evs else "",
        "n_publications": len(evs),
        "evenements": [{k: v for k, v in ev.items() if k != "texte"} | {"texte": ev["texte"][:700]}
                       for ev in evs[:40]],
        "signaux": signals_from(firm, evs),
        "collecte": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Registre du commerce suisse (Zefix) des entreprises de la campagne.")
    argument_campagne(ap)
    ap.add_argument("--refresh", action="store_true", help="refait toutes les entreprises (sinon : seulement les nouvelles)")
    ap.add_argument("--workers", type=int, default=4, help="requêtes en parallèle (défaut 4)")
    ap.add_argument("--radiees-ans", type=float, default=RADIEE_ANS, metavar="N",
                    help=f"écarte les homonymes radiés depuis plus de N ans (défaut {RADIEE_ANS} ; 0 = aucun filtre)")
    a = ap.parse_args()
    ouvrir(a.campagne)
    if not config()["signaux"].get("registre_suisse", True):
        print("signaux.registre_suisse = false dans campagne.toml : registre suisse non interrogé.")
        return
    store = Store(donnees() / "zefix.json")
    lis = load_json(donnees() / "linkedin.json", {}) or {}
    ents = load_entities()
    todo = [e for e in ents if a.refresh or e["id"] not in store]
    print(f"{len(ents)} entités, {len(todo)} à traiter", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(resolve, e, lis.get(e["id"]), a.radiees_ans): e for e in todo}
        for i, f in enumerate(as_completed(futs), 1):
            e = futs[f]
            try:
                rec = f.result()
            except Exception as err:  # noqa: BLE001
                rec = {"statut": f"erreur : {err.__class__.__name__}: {str(err)[:120]}"}
            store.put(e["id"], rec, flush_every=5)
            if rec["statut"] not in ("hors_suisse_ou_exclu",):
                extra = f"{rec.get('nom', '')} ({rec.get('siege', '')}) {len(rec.get('signaux', []))} signaux" \
                    if rec.get("nom") else str(rec.get("candidats", ""))[:120]
                print(f"[{i}/{len(todo)}] {e['id']} -> {rec['statut']} {extra}", flush=True)
    store.flush()
    from collections import Counter
    print(Counter(v["statut"] for v in store.data.values()))


if __name__ == "__main__":
    main()
