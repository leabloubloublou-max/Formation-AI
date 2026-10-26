"""Étape 9 : un script d'appel complet par contact, dans l'ordre d'appel (aucun appel réseau, 0 crédit).

Structure, celle d'un script d'appel qui a fait ses preuves : demande de permission (« 30 secondes ou je tombe
mal ? »), présentation en une phrase si on la demande, raison de l'appel en deux mots, une question ouverte puis
silence, un seul CTA avec deux créneaux. Le tronc commun est construit depuis la section [offre] de campagne.toml
(appelant, societe, presentation_appelant, description, argument_cle, preuves, question_ouverte, cta, ne_jamais_dire) :
aucune preuve ni aucun client écrit dans le code. Les parties propres à chaque contact (pourquoi vous, relance,
routage, objection probable, preuve à citer, à savoir) viennent des cartes rédigées par des agents
(consignes/cartes-appel.md).

Entrées, dans le dossier de campagne : appels/ordre-appel.csv (ordre_appel.py, --ordre pour un autre fichier) et les
cartes : appels/cartes-appel.json et/ou appels/cartes/*.json (un fichier par lot d'agent), ou --cartes.
Sorties : appels/scripts-appel.md (tronc commun puis une fiche par contact, dans l'ordre d'appel ; un résultat noté
entre parenthèses à la fin du titre d'une fiche est conservé à la génération suivante) et appels/scripts-appel.csv
(priorite, contact_id, nom, entreprise, script en texte brut, a_savoir) ; avec --maj-ordre, deux colonnes
script_appel et a_savoir_appel ajoutées au fichier d'ordre d'appel (à refaire après chaque ordre_appel.py).
Contrôles : champs de carte manquants, tirets cadratin et demi-cadratin, signal négatif ou phrase de
offre.ne_jamais_dire dans ce qui se dit, lieu d'un autre pays annoncé (« en Suisse » à une entreprise française),
preuve inconnue, nom corrigé par rapport à Apollo.

Ce module sert aussi à fichier_appel.py (lieux selon le pays, cartes, motifs interdits).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/scripts_appel.py --campagne campagnes/<nom>
      [--ordre <csv>] [--cartes <json ou dossier>] [--maj-ordre]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import Campagne, argument_campagne, ecrire_csv, lire_csv, norm
from ordre_appel import cle_contact, lire_json

# ---------------------------------------------------------------- pays et lieux (partagé avec fichier_appel.py)

NOMS_PAYS = {"CH": "Suisse", "FR": "France", "DE": "Allemagne", "IT": "Italie", "AT": "Autriche",
             "LI": "Liechtenstein", "BE": "Belgique", "LU": "Luxembourg", "MC": "Monaco", "NL": "Pays-Bas",
             "ES": "Espagne", "PT": "Portugal", "GB": "Royaume-Uni", "IE": "Irlande", "US": "États-Unis",
             "CA": "Canada"}
# mentions d'un lieu par pays (formes de base : pluriels et féminins reconnus)
LIEUX = {"CH": ["en Suisse", "suisse", "romand", "Romandie", "alémanique", "helvétique"],
         "FR": ["en France", "hexagonal"], "DE": ["en Allemagne"], "IT": ["en Italie"], "AT": ["en Autriche"],
         "LI": ["au Liechtenstein"], "BE": ["en Belgique"], "LU": ["au Luxembourg"], "NL": ["aux Pays-Bas"],
         "ES": ["en Espagne"], "PT": ["au Portugal"], "GB": ["au Royaume-Uni"], "IE": ["en Irlande"],
         "US": ["aux États-Unis"], "CA": ["au Canada"]}
_RX_LIEUX = {k: re.compile(r"\b(?:" + "|".join(re.escape(w) + r"(?:e|s|es)?" for w in v) + r")\b", re.I)
             for k, v in LIEUX.items()}


def textes_offre(config: dict) -> list[str]:
    o = config["offre"]
    return [o.get(k) or "" for k in ("presentation_appelant", "description", "argument_cle", "question_ouverte", "cta")] \
        + [p.get("phrase", "") for p in o.get("preuves") or [] if isinstance(p, dict)]


def pays_surveilles(config: dict) -> set[str]:
    """Pays dont un texte ne doit parler qu'à une entreprise de ce pays : ceux que l'offre cite (« hébergé en
    Suisse », « industriels romands ») et les pays visés par la campagne."""
    cites = {k for k, rx in _RX_LIEUX.items() for t in textes_offre(config) if rx.search(t)}
    return cites | {p.upper() for p in config["cible"].get("pays") or []}


def lieux_hors_pays(texte: str, code: str, surveilles: set[str]) -> list[str]:
    """Mentions d'un autre pays que celui de l'entreprise (code ISO) : à ne pas dire. Pays inconnu : rien."""
    if not code:
        return []
    vus = [m.group(0) for k in sorted(surveilles - {code}) if k in _RX_LIEUX for m in _RX_LIEUX[k].finditer(texte or "")]
    return list(dict.fromkeys(vus))


def lieux_a_eviter(code: str, config: dict) -> list[str]:
    """Pour une entreprise du pays « code » : les mentions de lieu de l'offre à ne pas reprendre."""
    if not code:
        return []
    return list(dict.fromkeys(x for t in textes_offre(config) for x in lieux_hors_pays(t, code, pays_surveilles(config))))


# ---------------------------------------------------------------- interdits (partagé avec fichier_appel.py)

# signal négatif : il sert à l'appelant, jamais au prospect
NEGATIFS = [r"faillite", r"licenci", r"restructur", r"liquidation", r"cyberattaque", r"cyber", r"attaque", r"sursis",
            r"rançon", r"proc[ée]dure (collective|de faillite|concordataire)", r"concordat", r"insolvab"]
TIRETS = [r"\u2014", r"\u2013"]


def motifs_interdits(config: dict) -> list[str]:
    """Tirets, signaux négatifs et phrases exactes de offre.ne_jamais_dire (un « sujet » sert de consigne aux agents)."""
    return TIRETS + NEGATIFS + [re.escape(x.strip()) for x in config["offre"].get("ne_jamais_dire") or [] if x.strip()]


def interdits_trouves(texte: str, motifs: list[str]) -> list[str]:
    return [m.group(0) for motif in motifs for m in [re.search(motif, texte or "", re.I)] if m]


# ---------------------------------------------------------------- cartes (partagé avec fichier_appel.py)

CHAMPS_CARTE = ("pourquoi_vous", "relance", "routage")


def charger_cartes(camp: Campagne, chemin: str | None = None) -> dict:
    """contact_id -> carte, depuis appels/cartes-appel.json et appels/cartes/*.json (ou --cartes : fichier ou dossier).
    contact_id est la clé du contact dans l'ordre d'appel : id Apollo, ou id local « local-... » ; une carte sans
    contact_id est ignorée."""
    if chemin:
        p = Path(chemin)
        fichiers = sorted(p.glob("*.json")) if p.is_dir() else [p]
        if not p.exists():
            raise SystemExit(f"Cartes introuvables : {p}")
    else:
        fichiers = [camp.dossier / "appels" / "cartes-appel.json"] + sorted((camp.dossier / "appels" / "cartes").glob("*.json"))
    cartes = {}
    for f in fichiers:
        d = lire_json(f, None)
        if d is None:
            continue
        for c in (d.values() if isinstance(d, dict) else d):
            cle = (c.get("contact_id") or c.get("apollo_contact_id") or "").strip() if isinstance(c, dict) else ""
            if cle:
                cartes[cle] = c
    return cartes


# ---------------------------------------------------------------- tronc commun

def phrase(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if not s or s[-1] in ".?!»…" else s + "."


def de(societe: str) -> str:
    return f"d'{societe}" if re.match(r"[aeiouyhàâéèêëîïôûAEIOUYHÀÂÉÈÊËÎÏÔÛ]", societe or "") else f"de {societe}"


def minuscule_initiale(s: str) -> str:
    """« Nous éditons ... » -> « nous éditons ... » après deux-points (seulement un pronom en tête)."""
    return s[0].lower() + s[1:] if re.match(r"(Nous|On|Notre|Nos)\b", s or "") else s


class Offre:
    """Les textes de la section [offre], avec un repère visible quand une clé manque."""

    def __init__(self, config: dict):
        o = config["offre"]
        self.manquants = [k for k in ("appelant", "societe", "presentation_appelant", "question_ouverte", "cta")
                          if not (o.get(k) or "").strip()]
        if not (o.get("description") or o.get("argument_cle") or "").strip():
            self.manquants.append("description ou argument_cle")
        val = lambda k: (o.get(k) or "").strip() or f"[À COMPLÉTER : offre.{k}]"
        self.appelant, self.societe = val("appelant"), val("societe")
        self.presentation, self.question, self.cta = val("presentation_appelant"), val("question_ouverte"), val("cta")
        self.description, self.argument = (o.get("description") or "").strip(), (o.get("argument_cle") or "").strip()
        self.lien_agenda = (o.get("lien_agenda") or "").strip()
        self.preuves = [p for p in o.get("preuves") or [] if isinstance(p, dict) and (p.get("phrase") or "").strip()]
        self.ne_jamais_dire = [x for x in o.get("ne_jamais_dire") or [] if x.strip()]

    def qui(self) -> str:
        return phrase(f"{self.societe}, {self.presentation}")

    def raison(self) -> str:
        pitch = " ".join(phrase(x) for x in (self.description, self.argument) if x)
        return f"En deux mots : {minuscule_initiale(pitch)}" if pitch else "[À COMPLÉTER : offre.description]"

    def preuve(self, carte: dict) -> tuple[dict | None, str]:
        """(preuve à citer, alerte) : le cas nommé dans la carte ; sans clé « preuve », la seule preuve s'il n'y en a
        qu'une ; « aucune » ou vide : pas de preuve."""
        if "preuve" not in carte:
            return (self.preuves[0] if len(self.preuves) == 1 else None), ""
        cas = norm(str(carte.get("preuve") or ""))
        if not cas or cas == "aucune":
            return None, ""
        p = next((p for p in self.preuves if norm(p.get("cas", "")) == cas), None)
        return p, "" if p else f"preuve « {carte.get('preuve')} » absente de offre.preuves"

    def vocal(self) -> str:
        accroche = (phrase(self.preuves[0]["phrase"]) + " Je pense que ça peut vous parler.") if self.preuves \
            else phrase(self.argument or self.description)
        return (f"Bonjour Monsieur X, {self.appelant}, {de(self.societe)}. {accroche} Je vous rappelle [jour], ou vous "
                "pouvez me joindre au [numéro]. Bonne journée.")


def tronc(o: Offre) -> str:
    preuves = "\n".join(f"- **{p.get('cas') or 'preuve'}** : « {phrase(p['phrase'])} »" for p in o.preuves) \
        or "- aucune preuve dans offre.preuves : ne citer aucun client ni aucun chiffre."
    jamais = "".join(f"\n- {x}" for x in ["un signal négatif (procédure, incident, licenciements...)",
                                          "un chiffre absent des preuves",
                                          "le nom d'une source interne (« Apollo », « notre base »)"] + o.ne_jamais_dire)
    agenda = f" (lien d'agenda : {o.lien_agenda})" if o.lien_agenda else ""
    return f"""## Le déroulé commun

1. **Ouverture**, puis on attend la réponse :
> « Bonjour Monsieur X, {o.appelant}, {de(o.societe)}. Auriez-vous 30 secondes à m'accorder ou je tombe mal ? »

Attendre. S'il dit non, demander quand rappeler et raccrocher.

2. **S'il demande « vous êtes qui ? » ou « vous faites quoi ? »** :
> « {o.qui()} »

Une phrase, puis pivot immédiat.

3. **Raison de l'appel**, puis la **preuve** de la fiche (s'il y en a une) et la phrase **Pourquoi vous** :
> « {o.raison()} »

4. **Question ouverte** :
> « {o.question} »

Silence. On attend. C'est le point le plus dur du script. Si la réponse est courte : la **relance** de la fiche.

5. **CTA unique** (deux créneaux précis de l'agenda) :
> « {o.cta} »

**Message vocal** (20 secondes) :
> « {o.vocal()} »

## Les preuves (une seule par appel, celle qui correspond au cas ; aucun autre chiffre)

{preuves}

## Si ça bloque

- **Le dirigeant renvoie vers quelqu'un** : la phrase **Si ça bloque** de la fiche ; noter le nom, demander à être
  transféré ou l'email, et rappeler en citant le dirigeant (« Monsieur X m'a conseillé de vous appeler »).
- **« Envoyez-moi une documentation »** ou **« un mail »** -> « Avec plaisir. Pour viser juste : qu'est-ce qui vous
  serait le plus utile ? », puis reproposer le rendez-vous (et l'envoyer par email{agenda}).
- **« Pas de budget »** -> « Quand se décident vos budgets, et qui y participe ? »
- **« On a déjà un prestataire »** -> « Bon signe. Qu'est-ce qui marche bien avec lui ? »
- **« Ce n'est pas moi »** -> « Qui serait la bonne personne ? Je peux dire que je viens de votre part ? »
- **« Rappelez plus tard »** -> proposer deux créneaux précis pour rappeler.
- **« C'est combien ? »** -> « Ça dépend du cas, on commence petit. C'est justement l'objet du rendez-vous. »
  (ne jamais annoncer de prix)

## Jamais au téléphone
{jamais}

La rubrique « À savoir » de chaque fiche est pour l'appelant seulement.
"""


def salutation(c: dict, r: dict) -> str:
    nom = c.get("nom_a_utiliser") or f"{r.get('prenom', '')} {r.get('nom', '')}".strip()
    if not c.get("civilite"):
        return f"Bonjour {nom}"
    famille = nom.split(" ", 1)[1] if " von " in f" {nom} " else nom.split()[-1]   # particule des noms germaniques
    return f"Bonjour {c['civilite']} {famille}"


def script_complet(c: dict, r: dict, o: Offre, preuve: dict | None, lieux: list[str]) -> str:
    """Le script à lire pour ce contact, déroulé commun compris (texte brut, une rubrique par ligne)."""
    raison = " ".join(x for x in (o.raison(), phrase(preuve["phrase"]) if preuve else "", phrase(c.get("pourquoi_vous", ""))) if x)
    lignes = [f"OUVERTURE : {salutation(c, r)}, {o.appelant}, {de(o.societe)}. Auriez-vous 30 secondes à m'accorder "
              "ou je tombe mal ?",
              "(Attendre. S'il dit non, demander quand rappeler et raccrocher.)",
              f"S'IL DEMANDE QUI VOUS ÊTES : {o.qui()} (Une phrase, puis pivot immédiat.)",
              f"RAISON DE L'APPEL : {raison}",
              f"QUESTION OUVERTE : {o.question}",
              "(Silence. On attend. C'est le point le plus dur du script.)",
              f"RELANCE SI RÉPONSE COURTE : {c.get('relance') or 'À COMPLÉTER'}",
              f"CTA : {o.cta}",
              f"SI ÇA BLOQUE : {c.get('routage') or 'À COMPLÉTER'}"]
    if c.get("objection_probable"):
        lignes.append(f"OBJECTION PROBABLE : {c['objection_probable']}")
    if lieux:
        lignes.insert(0, f"(ATTENTION : ne pas dire {', '.join(f'« {x} »' for x in lieux)} à cette entreprise, "
                         "d'un autre pays ; reformuler sans lieu.)")
    return "\n".join(lignes)


def resultats_notes(md: Path) -> dict:
    """Titres de fiches d'un .md déjà généré, par contact_id (pour garder un résultat noté entre parenthèses)."""
    titres, courant = {}, None
    if md.exists():
        for l in md.read_text(encoding="utf-8").splitlines():
            m = re.match(r"### \d+\. (.*)$", l)
            if m:
                courant = m[1].strip()
                continue
            m = re.search(r"· id (\S+)\s*$", l)
            if m and courant:
                titres[m[1]] = courant
                courant = None
    return titres


# ---------------------------------------------------------------- programme

def main() -> None:
    ap = argparse.ArgumentParser(description="Un script d'appel par contact, dans l'ordre d'appel (étape 9).")
    argument_campagne(ap)
    ap.add_argument("--ordre", help="CSV d'ordre d'appel (défaut : appels/ordre-appel.csv)")
    ap.add_argument("--cartes", help="cartes : fichier JSON ou dossier de JSON (défaut : appels/cartes-appel.json et appels/cartes/)")
    ap.add_argument("--maj-ordre", action="store_true",
                    help="ajouter aussi script_appel et a_savoir_appel au fichier d'ordre d'appel (non par défaut)")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    chemin_ordre = Path(a.ordre) if a.ordre else camp.appels / "ordre-appel.csv"
    if not chemin_ordre.exists():
        raise SystemExit(f"{chemin_ordre} absent : lancer d'abord ordre_appel.py (étape 8).")
    o = Offre(camp.config)
    cartes = charger_cartes(camp, a.cartes)
    if not cartes:
        raise SystemExit("Aucune carte d'appel : faire écrire appels/cartes-appel.json (ou appels/cartes/L*.json) par des "
                         "agents qui suivent consignes/cartes-appel.md, à partir des briefs de fichier_appel.py.")
    contacts = lire_csv(chemin_ordre)
    for r in contacts:
        r["_cle"] = cle_contact(r)               # id Apollo, ou id local d'un contact absent d'Apollo
    lignes = sorted((r for r in contacts if r["_cle"] in cartes),
                    key=lambda r: int(r["priorite"]) if (r.get("priorite") or "").isdigit() else 99999)
    if not lignes:
        raise SystemExit(f"Aucune carte ne correspond à un contact de {chemin_ordre.name} (clé contact_id).")
    orphelines = set(cartes) - {r["_cle"] for r in contacts}
    motifs = motifs_interdits(camp.config)
    surveilles = pays_surveilles(camp.config)
    md_path, csv_path = camp.appels / "scripts-appel.md", camp.appels / "scripts-appel.csv"
    anciens = resultats_notes(md_path)

    alertes = [f"configuration : offre.{k} vide" for k in o.manquants]
    a_adapter, a_adapter_n = {}, {}          # pays -> mentions de lieu du tronc à ne pas dire, nombre de contacts
    md = [f"# Scripts d'appel · {camp.nom} · {len(lignes)} contacts", "",
          f"Ordre d'appel : celui de `{chemin_ordre.name}` (refus avec réponse en fin de liste, langue de l'appelant, "
          "téléphone connu, tier). Noter le résultat de chaque appel entre parenthèses à la fin du titre de la fiche : il "
          "est gardé à la génération suivante.", "", tronc(o), "## Les fiches, dans l'ordre d'appel", ""]
    plats = []
    for r in lignes:
        c = cartes[r["_cle"]]
        qui = f"{r.get('priorite')} {r.get('prenom', '')} {r.get('nom', '')}".strip()
        for k in CHAMPS_CARTE:
            if not (c.get(k) or "").strip():
                alertes.append(f"{qui} : « {k} » manquant dans la carte")
        preuve, alerte = o.preuve(c)
        if alerte:
            alertes.append(f"{qui} : {alerte}")
        code = (r.get("pays_entreprise") or "").upper()
        dit = [o.qui(), o.raison(), o.question, o.cta, preuve["phrase"] if preuve else ""]
        lieux = lieux_hors_pays(" ".join(dit), code, surveilles)
        for k in CHAMPS_CARTE + ("objection_probable",):
            for x in interdits_trouves(c.get(k) or "", motifs):
                alertes.append(f"{qui} {k} : « {x} »")
            for x in lieux_hors_pays(c.get(k) or "", code, surveilles):
                alertes.append(f"{qui} {k} : « {x} » pour une entreprise hors de ce pays ({code})")
        if lieux:
            a_adapter.setdefault(code, set()).update(lieux)
            a_adapter_n[code] = a_adapter_n.get(code, 0) + 1
        nom = c.get("nom_a_utiliser") or f"{r.get('prenom', '')} {r.get('nom', '')}".strip()
        if nom.replace(" ", "").lower() != f"{r.get('prenom', '')}{r.get('nom', '')}".replace(" ", "").lower():
            alertes.append(f"{qui} nom corrigé : Apollo « {r.get('prenom', '')} {r.get('nom', '')} » -> « {nom} »")
        civ = f"{c['civilite']} " if c.get("civilite") else ""
        titre = f"{civ}{nom} · {r.get('titre') or 'poste inconnu'} · {r.get('entreprise', '')}"
        ancien = anciens.get(r["_cle"], "")
        suite = ancien[len(titre):].strip() if ancien.startswith(titre) else ""
        tel = f"{r['telephone']} ({r.get('type_telephone') or '?'})" if r.get("telephone") else "pas de numéro"
        a_savoir = " ".join(f"{str(x).rstrip('.')}." for x in c.get("a_savoir") or [] if str(x).strip())
        md += [f"### {r.get('priorite')}. {titre}" + (f" {suite}" if suite else ""), "",
               f"Tél. : {tel} · tier {r.get('tier', '?')} · langue : {r.get('langue') or '?'}"
               + (f" · déjà contacté : {r['deja_contacte']}" if r.get("deja_contacte") else "") + f" · id {r['_cle']}", ""]
        if preuve:
            md.append(f"- **Preuve à citer** ({preuve.get('cas') or 'preuve'}) : « {phrase(preuve['phrase'])} »")
        md += [f"- **Pourquoi vous** (fin de la raison de l'appel) : « {c.get('pourquoi_vous') or 'À COMPLÉTER'} »",
               f"- **Relance** (si la réponse est courte) : « {c.get('relance') or 'À COMPLÉTER'} »",
               f"- **Si ça bloque :** « {c.get('routage') or 'À COMPLÉTER'} »"]
        if c.get("objection_probable"):
            md.append(f"- **Objection probable :** {c['objection_probable']}")
        if c.get("exemple_pour_eux"):
            md.append(f"- **Exemple pour eux** (si la conversation s'ouvre) : {c['exemple_pour_eux']}")
        if lieux:
            md.append(f"- **Lieu :** entreprise hors de ce pays : ne pas dire {', '.join(f'« {x} »' for x in lieux)}.")
        md += [f"- **À savoir (ne pas lire) :** {a_savoir or 'rien'}", ""]
        plats.append({"priorite": r.get("priorite"), "contact_id": r["_cle"], "nom": nom,
                      "entreprise": r.get("entreprise", ""), "script": script_complet(c, r, o, preuve, lieux),
                      "a_savoir": a_savoir})
    md_path.write_text("\n".join(md), encoding="utf-8")
    ecrire_csv(csv_path, ["priorite", "contact_id", "nom", "entreprise", "script", "a_savoir"], plats)
    print(f"{len(plats)} scripts (sur {len(contacts)} contacts de {chemin_ordre.name}) -> {md_path}\n-> {csv_path}")
    if a.maj_ordre:
        par_id = {p["contact_id"]: p for p in plats}
        champs = [k for k in contacts[0] if k not in ("script_appel", "a_savoir_appel", "_cle")] + ["script_appel", "a_savoir_appel"]
        for x in contacts:
            p = par_id.get(x["_cle"])
            x["script_appel"], x["a_savoir_appel"] = (p["script"], p["a_savoir"]) if p else ("", "")
            if p and not (x.get("contact_id") or "").strip():
                x["contact_id"] = x["_cle"]        # id local gardé : un nom corrigé ne le change plus
        ecrire_csv(chemin_ordre, champs, contacts)
        print(f"-> colonnes script_appel et a_savoir_appel dans {chemin_ordre}")
    for code, lieux in sorted(a_adapter.items()):
        alertes.append(f"{a_adapter_n[code]} contact(s) d'entreprises de {code} : tronc commun à adapter au téléphone "
                       f"({', '.join(sorted(lieux))}), signalé dans leur fiche")
    if orphelines:
        alertes.append(f"{len(orphelines)} carte(s) sans contact dans {chemin_ordre.name} : {', '.join(sorted(orphelines)[:5])}")
    print(f"{len(alertes)} alerte(s)" + "".join(f"\n  ! {x}" for x in alertes))


if __name__ == "__main__":
    main()
