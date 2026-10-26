"""Étape 5 : intègre les résultats du workflow de recherche (workflows/signaux-recherche.js) dans recherche.json.

Lit un ou plusieurs journaux de run (journal.jsonl, ou le dossier du run qui le contient) et y cherche partout, même
stockés en chaîne JSON, les retours des agents : {lot_id, entreprises} (recherche) et {lot_id, verdicts}
(contre-vérification). Chaque verdict est rattaché à son signal par (id, index) ; l'index -1 désigne adoption_tech :
  - « réfuté »    -> signal marqué réfuté (ignoré par le scorer) ;
  - « confirmé »  -> confiance « vérifié » au scorer ;
  - « incertain » -> confiance « agent » (poids réduit) ; date_corrigee appliquée si fournie (date_origine gardée).
Adoption tech « fort » : confirmé = fort ; incertain = moyen ; réfuté = faible.
Un journal donné après un autre remplace ses résultats pour les mêmes lots : passer TOUS les journaux de la campagne,
dans l'ordre chronologique.

Contrôle anti-invention (--sans-controle pour le couper) : la source_url de chaque signal doit apparaître TELLE QUELLE
(pas comme simple préfixe d'une autre page) dans ce que les outils de l'agent de recherche lui ont renvoyé (sorties
volumineuses comprises, lues dans leur fichier complet), dans les URL qu'il a ouvertes ou dans les éléments de son lot
(fiche du registre, posts, actualités, pages relevées ; les adresses du site et de la page LinkedIn de l'entreprise ne
sont pas des sources à elles seules). Il faut pour cela les transcripts des agents (agent-<id>.jsonl) à côté du
journal. Cas particuliers :
  - registre du commerce (DOMAINES_REGISTRE) : l'URL exacte, ou l'identifiant de la fiche (zefix : ehraid) vu ;
  - « domaine vu » : seul le domaine apparaît, dans les sorties d'outils ; accepté avec une confiance plafonnée à
    « moyenne », sauf pour un domaine du lot (site de l'entreprise, presse déjà relevée) ou un hôte générique
    (linkedin.com, registres, réseaux sociaux, moteurs) : l'URL exacte y est exigée ;
  - source_url vide : « source absente » (contrôlé même sans transcripts).
Un signal « source non vue » ou « source absente » passe en confiance « faible » (le scorer le compte comme une
détection automatique), sauf si le contre-vérificateur l'a confirmé en ayant lui-même vu la source. Un « confirmé »
dont la source n'apparaît pas dans les sorties du contre-vérificateur devient « incertain ».
Les tirets cadratins et demi-cadratins des agents sont remplacés (règle de rédaction des textes destinés aux prospects).

Sortie : <campagne>/donnees/signaux/recherche.json, {id: {id, lot, nom_verifie, activite, categorie, effectif_estime,
groupe_parent, dans_icp, raison_hors_icp, signaux[{famille, sous_type, date, resume, source_url, confiance, verdict,
raison_verdict, date_origine, controle, confiance_origine}], adoption_tech{niveau, preuves[], concurrent, verdict,
raison_verdict}, dirigeants[{nom, role, depuis}], pourquoi_maintenant, angle, persona_cible, cibles{entree[{nom, role}],
relais[{nom, role}]}, sources[]}} ; fusionné avec le fichier existant (les autres entreprises sont gardées).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/apply_recherche.py --campagne campagnes/<nom>
      <journal.jsonl ou dossier du run> [<journal 2> ...] [--sans-controle]
Dossier d'un run de workflow : find ~/.claude/projects -type d -path '*workflows*' -name '<runId>'
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

CADRATIN, DEMI_CADRATIN = "\u2014", "\u2013"
# registres du commerce officiels (même liste que DOMAINES_REGISTRE dans workflows/signaux-recherche.js, complétée par
# domaines_registre de args-recherche.json) et hôtes génériques : une page vue sur ces sites n'en garantit aucune
# autre, seule l'URL exacte compte (ou, pour un registre, l'identifiant de la fiche)
DOMAINES_REGISTRE = {"zefix.ch", "zefix.admin.ch", "shab.ch", "amtsblattportal.ch", "handelsregister.de",
                     "unternehmensregister.de", "bodacc.fr", "infogreffe.fr", "annuaire-entreprises.data.gouv.fr",
                     "registroimprese.it", "kbopub.economie.fgov.be", "lbr.lu", "oera.li", "kvk.nl",
                     "company-information.service.gov.uk"}
HOTES_GENERIQUES = {"linkedin.com", "xing.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
                    "youtube.com", "google.com", "bing.com", "duckduckgo.com", "wikipedia.org", "moneyhouse.ch"}
# lecture d'un lot par un agent (Read, ou cat dans Bash) : remplacée par texte_lot()
LECTURE_LOT = re.compile(r"[\\/]lots[\\/](L\d+)\.json\b", re.I)
# adresses d'identité d'un dossier : connues avant la recherche, ce ne sont pas des sources à elles seules
IDENTITE_LOT = ("site_web", "linkedin")


def find(obj, out: dict, agent: str) -> None:
    """Cherche récursivement les retours d'agents (recherche, verdicts), y compris dans une chaîne JSON."""
    if isinstance(obj, dict):
        if "lot_id" in obj and "entreprises" in obj:
            out["recherche"].append((agent, obj))
            return
        if "lot_id" in obj and "verdicts" in obj:
            out["verifs"].append((agent, obj))
            return
        for v in obj.values():
            find(v, out, agent)
    elif isinstance(obj, list):
        for v in obj:
            find(v, out, agent)
    elif isinstance(obj, str) and obj.lstrip().startswith("{") and ('"entreprises"' in obj or '"verdicts"' in obj):
        try:
            find(json.loads(obj), out, agent)
        except json.JSONDecodeError:
            pass


def lire_journal(chemin: Path) -> dict:
    out = {"recherche": [], "verifs": []}
    for ligne in chemin.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        agent = str(d.get("agentId", "")) if isinstance(d, dict) else ""
        find(d.get("result", d) if isinstance(d, dict) else d, out, agent)
    return out


def sans_tirets(obj):
    """Règle de rédaction : jamais de tiret cadratin ni demi-cadratin dans des textes réutilisables auprès des prospects."""
    if isinstance(obj, str):
        for t in (CADRATIN, DEMI_CADRATIN):
            obj = obj.replace(f" {t} ", ", ").replace(t, "-")
        return obj
    if isinstance(obj, list):
        return [sans_tirets(x) for x in obj]
    if isinstance(obj, dict):
        return {k: sans_tirets(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------- contrôle anti-invention

def texte(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(texte(c.get("text") or c.get("content") or "") if isinstance(c, dict) else str(c)
                        for c in contenu)
    return ""


def minuscules(s: str) -> str:
    s = s.lower()
    return s + " " + unquote(s)


SORTIE_PERSISTEE = re.compile(r"Full output saved to: ([^\n<]+)")


def sortie_complete(chemin: str, dossier: Path) -> str:
    """Texte complet d'une sortie d'outil volumineuse, dont le transcript ne garde qu'un aperçu (« Full output saved
    to: <chemin> ») ; cherchée aussi, par son nom, dans tool-results/ du run et des dossiers parents (session).
    Même règle que consolider_decouverte.py et verif_appliquer.py."""
    p = Path(chemin.strip())
    for c in (p, dossier / "tool-results" / p.name, *(d / "tool-results" / p.name for d in dossier.parents[:3])):
        if c.is_file():
            return c.read_text(encoding="utf-8", errors="ignore")
    return ""


def corpus_agents(dossier: Path, lots_lus: dict | None = None) -> dict:
    """agentId -> ce que ses outils lui ont renvoyé (sorties volumineuses comprises) et les URL qu'il a ouvertes, en
    minuscules : le seul « vu ». La lecture brute d'un lot n'est pas gardée : main() ajoute le lot sans ses adresses
    d'identité (texte_lot). lots_lus, s'il est donné, reçoit agentId -> identifiants des lots que l'agent a lus."""
    vus = {}
    for f in dossier.glob("agent-*.jsonl"):
        morceaux, lus, appels_lot = [], set(), set()
        for ligne in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                m = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            msg = m.get("message") if isinstance(m, dict) else None
            contenu = msg.get("content") if isinstance(msg, dict) else None
            for c in contenu if isinstance(contenu, list) else []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_result":
                    if c.get("tool_use_id") not in appels_lot:
                        t = texte(c.get("content"))
                        morceaux.append(t)
                        morceaux += [sortie_complete(p, dossier) for p in SORTIE_PERSISTEE.findall(t)]
                elif c.get("type") == "tool_use" and isinstance(c.get("input"), dict):
                    lot = LECTURE_LOT.search(" ".join(str(c["input"].get(k, "")) for k in ("file_path", "command")))
                    if lot:
                        lus.add(lot[1].upper())
                        appels_lot.add(c.get("id"))
                        continue
                    # URL ouverte (WebFetch) ou commande lancée (outils_web.py peek <url>)
                    morceaux += [str(c["input"].get(k, "")) for k in ("url", "command")]
        vus[f.stem[len("agent-"):]] = minuscules(" ".join(morceaux))
        if lots_lus is not None:
            lots_lus[f.stem[len("agent-"):]] = lus
    return vus


def texte_lot(f: Path) -> tuple[str, set]:
    """(texte du lot en minuscules sans les adresses d'identité des dossiers, domaines de toutes ses URL)."""
    if not f.is_file():
        return "", set()
    brut = f.read_text(encoding="utf-8", errors="ignore")
    domaines = {domaine(u) for u in re.findall(r"https?://[^\s\"'<>()\]]+", brut)} - {""}
    try:
        lot = json.loads(brut)
    except json.JSONDecodeError:
        return minuscules(brut), domaines
    for d in lot if isinstance(lot, list) else []:
        if isinstance(d, dict):
            for k in IDENTITE_LOT:
                d.pop(k, None)
            if isinstance(d.get("site"), dict):
                d["site"].pop("url", None)
    return minuscules(json.dumps(lot, ensure_ascii=False)), domaines


def cle_url(url: str) -> str:
    """URL sans protocole, www, ancre ni barre finale ; fr.linkedin.com et www.linkedin.com confondus."""
    u = re.sub(r"^https?://(www\.)?", "", (url or "").strip().lower()).split("#")[0]
    return re.sub(r"^[a-z]{2}\.linkedin\.com\b", "linkedin.com", u).rstrip("/")


def domaine(url: str) -> str:
    return cle_url(url).split("/")[0].split("?")[0]


def sur(d: str, hotes) -> bool:
    """Le domaine d est l'un des hôtes, ou l'un de leurs sous-domaines."""
    return any(d == h or d.endswith("." + h) for h in hotes)


def cite(fragment: str, corpus: str, fin: str) -> bool:
    """Le fragment figure dans le corpus comme un tout : pas collé à la fin d'un autre nom ni d'une adresse e-mail,
    et suivi de « fin »."""
    return bool(re.search(r"(?<![a-z0-9@-])" + re.escape(fragment) + fin, corpus))


# fin d'une URL dans un texte : rien, espace, guillemet, parenthèse, séparateur, paramètres ou point final
FIN_URL = r"/?(?=$|[\s\"'<>()\[\]{}|,;\\?#&*`]|\.(?:\s|$))"


def vue(url: str, corpus: str, domaines_lot=frozenset(), registres=DOMAINES_REGISTRE) -> str:
    """« url vue », « domaine vu », « source non vue » ou « source absente » dans un corpus (sorties d'outils, lot)."""
    k = cle_url(url)
    if not k:
        return "source absente"
    if any(cite(x, corpus, FIN_URL) for x in {k, unquote(k)}):
        return "url vue"
    d = domaine(url)
    if sur(d, registres):
        # même fiche sous une autre forme (langue, nom dans l'URL) : son numéro vu, celui de la fiche zefix (ehraid,
        # affiché aussi par outils_signaux.py zefix) ou un numéro d'au moins 6 chiffres (SIREN...) ; un numéro court
        # ne compte que dans son contexte (firm/, ehraid)
        ids = re.findall(r"/firm/(\d+)", k) or re.findall(r"(?<!\d)\d{6,}(?!\d)", k)
        if not ids:
            return "source non vue"
        avant = r"(?<!\d)" if len(ids[-1]) >= 5 else r"(?:/firm/|ehraid\W{0,3})"
        return "url vue" if re.search(avant + ids[-1] + r"(?!\d)", corpus) else "source non vue"
    if d and not sur(d, HOTES_GENERIQUES) and not sur(d, domaines_lot) and cite(d, corpus, r"(?![a-z0-9-])"):
        return "domaine vu"
    return "source non vue"


# ---------------------------------------------------------------- normalisation au contrat

def normaliser(e: dict, lot_id: str) -> dict:
    """Entreprise rendue par un agent -> schéma de recherche.json (clés manquantes ajoutées, types corrigés)."""
    at = e.get("adoption_tech") if isinstance(e.get("adoption_tech"), dict) else {}
    cibles = e.get("cibles") if isinstance(e.get("cibles"), dict) else {}

    def personnes(lst):
        return [{"nom": (x.get("nom") or "").strip(), "role": (x.get("role") or "").strip()} if isinstance(x, dict)
                else {"nom": "", "role": str(x).strip()} for x in lst or []]

    out = {
        "id": e.get("id", ""), "lot": lot_id, "nom_verifie": e.get("nom_verifie", ""), "activite": e.get("activite", ""),
        "categorie": e.get("categorie", ""), "effectif_estime": e.get("effectif_estime", ""),
        "groupe_parent": e.get("groupe_parent", ""), "dans_icp": e.get("dans_icp", True),
        "raison_hors_icp": e.get("raison_hors_icp", ""),
        "signaux": [s for s in e.get("signaux") or [] if isinstance(s, dict)],
        "adoption_tech": {**at, "niveau": at.get("niveau", "inconnu"), "preuves": list(at.get("preuves") or []),
                          "concurrent": bool(at.get("concurrent"))},
        "dirigeants": [d for d in e.get("dirigeants") or [] if isinstance(d, dict)],
        "pourquoi_maintenant": e.get("pourquoi_maintenant", ""), "angle": e.get("angle", ""),
        "persona_cible": e.get("persona_cible", ""),
        "cibles": {"entree": personnes(cibles.get("entree")), "relais": personnes(cibles.get("relais"))},
        "sources": [str(x) for x in e.get("sources") or []],
    }
    for k, v in e.items():     # champs en plus rendus par l'agent : gardés
        out.setdefault(k, v)
    return out


def main() -> None:
    from commun import argument_campagne
    ap = argparse.ArgumentParser(description="Étape 5 : intègre les journaux du workflow de recherche de signaux "
                                             "dans donnees/signaux/recherche.json.")
    argument_campagne(ap)
    ap.add_argument("journaux", nargs="+", help="journal.jsonl (ou dossier du run), dans l'ordre chronologique")
    ap.add_argument("--sans-controle", action="store_true",
                    help="ne pas faire le contrôle anti-invention (sources vues dans les transcripts des agents, "
                         "source vide)")
    a = ap.parse_args()

    from signaux_commun import donnees, load_json, ouvrir, save_json
    ouvrir(a.campagne)
    data = donnees()
    chemins = []
    for j in a.journaux:
        p = Path(j).expanduser()
        p = p / "journal.jsonl" if p.is_dir() else p
        if not p.is_file():
            raise SystemExit(f"Journal introuvable : {p}")
        chemins.append(p)

    # lot -> (retour, (corpus, lots lus) de l'agent ou None) ; un journal plus récent remplace le même lot
    lots, verifs = {}, {}
    for p in chemins:
        out = lire_journal(p)
        lus = {}
        corpus = {} if a.sans_controle else corpus_agents(p.parent, lus)
        if not a.sans_controle and not corpus and out["recherche"]:
            print(f"! aucun transcript d'agent à côté de {p} : contrôle anti-invention impossible pour ce journal")
        vu = lambda agent: (corpus[agent], lus.get(agent, set())) if agent in corpus else None
        for agent, r in out["recherche"]:
            lots[r["lot_id"]] = (r, vu(agent))
        for agent, v in out["verifs"]:
            verifs[v["lot_id"]] = (v, vu(agent))
        print(f"{p.parent.name} : recherche {sorted(r['lot_id'] for _, r in out['recherche'])}, "
              f"vérifs {sorted(v['lot_id'] for _, v in out['verifs'])}")
    if not lots:
        raise SystemExit("Aucun retour de recherche dans ces journaux : rien n'est écrit (mauvais fichier, ou run sans "
                         "résultat). Le journal est le journal.jsonl du dossier du run de workflow.")

    manifeste = {m["id"]: m for m in load_json(data / "lots" / "manifest.json", []) or [] if isinstance(m, dict)}
    args_rech = load_json(data / "lots" / "args-recherche.json", {}) or {}
    registres = DOMAINES_REGISTRE | {str(d).lower().removeprefix("www.") for d in
                                     (args_rech.get("domaines_registre") or [] if isinstance(args_rech, dict) else [])}
    connus = {e["id"] for e in load_json(data / "entites.json", []) or []}
    rech = load_json(data / "recherche.json", {}) or {}
    stats, inconnus = Counter(), []
    for lot_id, (r, vu_r) in sorted(lots.items()):
        v_lot, vu_v = verifs.get(lot_id) or ({}, None)
        vmap = {(v.get("id"), v.get("index")): v for v in v_lot.get("verdicts", []) if isinstance(v, dict)}
        # le lot compte comme vu (fiche du registre, posts, actualités), sans les adresses d'identité des dossiers ;
        # ses domaines exigent l'URL exacte
        txt_lot, domaines_lot = texte_lot(Path((manifeste.get(lot_id) or {}).get("file")
                                               or data / "lots" / f"{lot_id}.json"))
        corpus_r = None if vu_r is None else vu_r[0] + " " + txt_lot
        corpus_v = None if vu_v is None else vu_v[0] + (" " + txt_lot if lot_id.upper() in vu_v[1] else "")
        for e in r.get("entreprises", []):
            if not isinstance(e, dict) or not e.get("id"):
                continue
            e = normaliser(e, lot_id)
            for i, s in enumerate(e["signaux"]):
                url = str(s.get("source_url") or "").strip()
                v = vmap.get((e["id"], i))
                if v and v.get("verdict") == "confirmé" and corpus_v is not None and url \
                        and vue(url, corpus_v, domaines_lot, registres) == "source non vue":
                    v = dict(v, verdict="incertain",
                             raison=(v.get("raison") or "") + " (source non vue par le contre-vérificateur)")
                    stats["confirmé ramené à incertain (source non vue)"] += 1
                if v:
                    s["verdict"] = v["verdict"]
                    s["raison_verdict"] = v.get("raison", "")
                    if v.get("date_corrigee"):
                        s["date_origine"], s["date"] = s.get("date", ""), v["date_corrigee"]
                    stats[f"signal {v['verdict']}"] += 1
                else:
                    stats["signal sans contre-vérification"] += 1
                if a.sans_controle:
                    continue
                # sans transcript, seule l'absence de source se contrôle
                controle = vue(url, corpus_r, domaines_lot, registres) if corpus_r is not None or not url \
                    else ""
                if not controle:
                    continue
                s["controle"] = controle
                if s.get("verdict") == "confirmé":
                    continue
                if controle in ("source non vue", "source absente"):
                    s["confiance_origine"], s["confiance"] = s.get("confiance", ""), "faible"
                    stats[f"signal {controle} (confiance faible)"] += 1
                elif controle == "domaine vu" and s.get("confiance") not in ("moyenne", "faible"):
                    s["confiance_origine"], s["confiance"] = s.get("confiance", ""), "moyenne"
                    stats["signal domaine vu seulement (confiance moyenne)"] += 1
            at = e["adoption_tech"]
            v = vmap.get((e["id"], -1))
            if v and at.get("niveau") == "fort":
                at["verdict"] = v["verdict"]
                at["raison_verdict"] = v.get("raison", "")
                if v["verdict"] == "incertain":
                    at["niveau"] = "moyen"
                elif v["verdict"] == "réfuté":
                    at["niveau"] = "faible"
                stats[f"tech fort {v['verdict']}"] += 1
            if connus and e["id"] not in connus:
                inconnus.append(e["id"])
            rech[e["id"]] = sans_tirets(e)
            stats["entreprises"] += 1
    save_json(data / "recherche.json", rech)
    print(dict(stats))
    if inconnus:
        print(f"! {len(inconnus)} id absents de entites.json (ignorés par le scorer) : {', '.join(inconnus[:10])}")
    print(f"{data / 'recherche.json'} : {len(rech)} entreprises")


if __name__ == "__main__":
    main()
