"""Étape 4 : applique les retours des workflows de vérification et écrit entreprises-verifie.csv.

Entrées :
- un ou plusieurs journaux de run (journal.jsonl, ou le dossier du run qui le contient), dans l'ordre des passes :
  passe 1 (workflows/verification.js) puis passe 2 (workflows/verification-passe2.js). Les retours structurés des
  agents y sont cherchés partout, même stockés en chaîne JSON : lots {batch_id, entites, confirmes} et {verdicts}.
  Lignes « failed » ignorées ; un lot rendu deux fois (reprise) : le dernier compte ; les journaux s'appliquent dans
  l'ordre, le dernier l'emporte pour une même entité ;
- la liste de départ (entreprises-enrichi.csv, sinon entreprises.csv), toujours relue : le résultat ne dépend que de
  la liste, des journaux et des arbitrages, on peut relancer autant de fois qu'on veut ;
- les manifestes de donnees/verification/ (verif_preparer.py, verif_passe2.py) : alias de la passe 2, et entités
  confiées à un lot qui n'a rien rendu ;
- facultatif : <campagne>/arbitrages.csv (ou --arbitrages), décisions prises à la main, appliquées en dernier.

Règles, pour chaque champ (site, linkedin) d'une entité rendue :
- « confirmé » : valeur actuelle gardée ; dans un lot léger (clé dans confirmes, ou entité rendue avec un champ
  « confirmé »), jugé sans outil : « confirmé (contrôle léger) » ;
- alias de la passe 2 (manifeste) : la valeur actuelle d'un alias est celle de sa clé principale avant le lot (celle
  que l'agent a vue dans passe1) ; les verdicts d'une clé principale et de ses alias sont cherchés sous la clé
  principale, puis sous les alias ; un alias que l'agent n'a pas rendu reçoit l'entrée de sa clé principale ;
- « corrigé » ou « trouvé » sans valeur : « introuvable » ; avec une valeur, selon la contre-vérification :
  « réfuté » -> champ vidé, raison en note ; « incertain » -> valeur gardée, à revoir ; pas de verdict pour cette
  valeur -> « non contre-vérifié », valeur gardée, à revoir ;
- « introuvable », « ambigu », « particulier » : champ vidé, l'ancienne valeur va en note ;
- contrôle anti-invention, quand les transcripts des agents (agent-<id>.jsonl) sont à côté du journal : une URL
  corrigée ou trouvée absente des sorties d'outils de l'agent (une sortie volumineuse est lue dans son fichier
  complet, « Full output saved to ») est écartée (« écarté (non vu) », à revoir) ; un verdict
  « confirmé » dont l'URL n'apparaît pas dans les sorties du contre-vérificateur devient « incertain » ;
- entité confiée à un lot qui ne l'a pas rendue : « non vérifié », valeurs gardées, à revoir ; entité jamais confiée à
  un lot (exclue, ou laissée de côté par --max) : ligne recopiée telle quelle.
Le statut détaillé va dans site_verif et linkedin_verif ; les colonnes du contrat en sont déduites : site_statut
« confirmé », « corrigé » (valeur de la ligne changée par la vérification) ou « introuvable » ; site_confiance
« haute » (vérifié) ou « à vérifier » (incertain, non contre-vérifié) ; après un contrôle léger, « haute » pour une
valeur sûre au sens de verif_preparer.py (site de confiance haute, LinkedIn lu sur le site) sur toutes les lignes de
l'entité, inchangée sinon. a_revoir = oui si un statut détaillé vaut ambigu,
réfuté, incertain, non vérifié, non contre-vérifié ou écarté (non vu), sinon non. exclure reçoit le motif rendu par
l'agent (particulier, administration, fermée, non identifiée). nom_officiel vient de l'agent ; pays, ville et
activite ne sont complétés que s'ils sont vides (un pays différent est signalé en note) ; canton et région suivent
la ville pour la Suisse. La preuve de la source reste dans preuve ; celle de l'agent va dans preuve_verification.

arbitrages.csv (facultatif, colonnes nom, champ, valeur, statut, note ; une ligne par décision, nom = la clé de
l'entité) :
- champ site ou linkedin : valeur = la bonne URL, vide pour garder la valeur actuelle, « aucun » pour vider le
  champ ; statut = statut détaillé à poser (« corrigé », « page du groupe », « introuvable », « ambigu »...) ;
- champ nom_officiel, pays, ville, activite, exclure, a_revoir ou note : valeur posée telle quelle (« aucun » =
  vide ; note : ajoutée).

Sortie : entreprises-verifie.csv (commun.COLONNES_ENTREPRISES, autres colonnes de la liste, puis verification,
site_verif, linkedin_verif, preuve_verification) ; la version précédente est copiée dans
donnees/verification/entreprises-verifie.precedent.csv. Sans LLM ni réseau.

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom>
      <journal passe 1> [<journal passe 2> ...] [--arbitrages <csv>] [--sans-controle]
Dossier d'un run de workflow : find ~/.claude/projects -type d -path '*workflows*' -name '<runId>'
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import (COLONNES_ENTREPRISES, Campagne, argument_campagne, charger_localites, code_pays, domaine,
                    ecrire_csv, linkedin_company, lire_csv, norm, region, site_propre, slug_linkedin)
from verif_preparer import MANIFESTES, NON_IDENTIFIE, cle, entites_de, linkedin_sur, liste_de_base, site_sur

A_REVOIR = {"ambigu", "réfuté", "incertain", "non vérifié", "non contre-vérifié", "écarté (non vu)"}
VIDES = {"introuvable", "ambigu", "particulier"}
MOTIFS = {"particulier", "administration", "fermée", "non identifiée"}
AUCUN = {"aucun", "aucune", "-", "vide"}
MODES = {"deep": "profonde", "light": "légère", "resolve": "résolution", "complete": "complétion"}
COLONNES_VERIF = ["verification", "site_verif", "linkedin_verif", "preuve_verification"]
# colonnes qu'une vérification peut changer (les autres colonnes de la liste sont recopiées)
GEREES = ["nom_officiel", "pays", "ville", "canton", "region", "activite", "site", "site_statut", "site_confiance",
          "linkedin", "linkedin_statut", "linkedin_source", "linkedin_confiance", "a_revoir", "exclure",
          *COLONNES_VERIF]
CHAMPS_ARBITRAGE = {"site", "linkedin", "nom_officiel", "pays", "ville", "activite", "exclure", "a_revoir", "note"}


def court(s, n: int = 300) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "..."


# ---------------------------------------------------------------- URL

def cle_url(champ: str, url: str) -> str:
    """Ce qui identifie une URL : le domaine d'un site, le slug d'une page LinkedIn."""
    if champ == "site":
        return domaine(url)
    return slug_linkedin(url) or re.sub(r"^https?://(www\.)?", "", (url or "").strip().lower()).rstrip("/")


def propre(champ: str, url: str) -> str:
    if champ == "site":
        return site_propre(url)
    return linkedin_company(url) or url.strip()


def vu(champ: str, url: str, corpus: str) -> bool:
    k = cle_url(champ, url)
    return bool(k) and (k in corpus or unquote(k) in corpus)


# ---------------------------------------------------------------- journaux

def chercher(obj, out: dict) -> None:
    """Cherche récursivement les retours d'agents (lots et verdicts), y compris dans une chaîne JSON."""
    if isinstance(obj, dict):
        if "batch_id" in obj and "entites" in obj:
            out["lots"].append(obj)
            return
        if isinstance(obj.get("verdicts"), list):
            out["verdicts"].extend(v for v in obj["verdicts"] if isinstance(v, dict))
            return
        for v in obj.values():
            chercher(v, out)
    elif isinstance(obj, list):
        for v in obj:
            chercher(v, out)
    elif isinstance(obj, str) and obj.lstrip().startswith("{") and ('"entites"' in obj or '"verdicts"' in obj):
        try:
            chercher(json.loads(obj), out)
        except json.JSONDecodeError:
            pass


def lire_journal(chemin: Path) -> tuple[list, list]:
    """[(agentId, lot)], [(agentId, verdict)] dans l'ordre du journal ; seules les lignes de résultat comptent."""
    lots, verdicts = [], []
    for ligne in chemin.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            d = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict) or ("type" in d and d["type"] != "result"):
            continue
        out = {"lots": [], "verdicts": []}
        chercher(d.get("result", d), out)
        aid = str(d.get("agentId", ""))
        lots += [(aid, l) for l in out["lots"]]
        verdicts += [(aid, v) for v in out["verdicts"]]
    return lots, verdicts


def texte(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(texte(c.get("text") or c.get("content") or "") if isinstance(c, dict) else str(c)
                        for c in contenu)
    return ""


SORTIE_PERSISTEE = re.compile(r"Full output saved to: ([^\n<]+)")


def sortie_complete(chemin: str, dossier: Path) -> str:
    """Texte complet d'une sortie d'outil volumineuse, dont le transcript ne garde qu'un aperçu (« Full output saved
    to: <chemin> ») ; cherchée aussi, par son nom, dans tool-results/ du run et des dossiers parents (session)."""
    p = Path(chemin.strip())
    for c in (p, dossier / "tool-results" / p.name, *(d / "tool-results" / p.name for d in dossier.parents[:3])):
        if c.is_file():
            return c.read_text(encoding="utf-8", errors="ignore")
    return ""


def corpus_agents(dossier: Path) -> dict:
    """agentId -> tout ce que ses outils lui ont renvoyé, en minuscules : le seul « vu » qui compte (sorties
    volumineuses comprises, lues dans leur fichier complet)."""
    vus = {}
    for f in dossier.glob("agent-*.jsonl"):
        morceaux = []
        for ligne in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                m = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            msg = m.get("message") if isinstance(m, dict) else None
            contenu = msg.get("content") if isinstance(msg, dict) else None
            for c in contenu if isinstance(contenu, list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    t = texte(c.get("content"))
                    morceaux.append(t)
                    morceaux += [sortie_complete(p, dossier) for p in SORTIE_PERSISTEE.findall(t)]
        corpus = " ".join(morceaux).lower()
        vus[f.stem[len("agent-"):]] = corpus + " " + unquote(corpus)
    return vus


# ---------------------------------------------------------------- application

class Application:
    def __init__(self, base: list[dict], manifestes: dict):
        self.ents = entites_de(base)
        for e in self.ents.values():
            r = e["lignes"][0]
            e["etat"] = {c: (r.get(c) or "") for c in GEREES}
            # sûr sur toutes les lignes de la liste (verif_preparer.py classe l'entité par sa ligne la plus douteuse)
            e["surs_lignes"] = {"site": all(site_sur(l) for l in e["lignes"]),
                                "linkedin": all(linkedin_sur(l) for l in e["lignes"])}
            e["note_base"], e["note_verif"], e["notes_arb"], e["lots"] = r.get("note", ""), "", [], []
            e["touchee"] = e["rendue"] = False
        self.par_norm: dict[str, list] = {}
        for k, e in self.ents.items():
            self.par_norm.setdefault(norm(e["key"]), []).append(k)
        self.alias = {}       # lot -> {clé alias : clé principale}
        self.attendues = {}   # manifeste -> {clé : lot}
        for nom, m in manifestes.items():
            self.attendues[nom] = {}
            for b in m:
                al = {cle(a): cle(k) for a, k in (b.get("alias") or {}).items()}
                self.alias[b.get("id")] = al
                for k in [*(b.get("cles") or []), *al]:
                    self.attendues[nom][cle(k)] = b.get("id")
        self.verdicts: dict = {}
        self.stats = Counter()
        self.inconnues: list[str] = []
        self._loc = None

    def retrouver(self, key: str) -> str | None:
        k = cle(key)
        if k in self.ents:
            return k
        cands = self.par_norm.get(norm(key), [])
        return cands[0] if len(cands) == 1 else None

    # -- verdicts de contre-vérification
    def ajouter_verdicts(self, verdicts: list, corpus: dict | None) -> None:
        for aid, v in verdicts:
            champ = "site" if v.get("champ") in ("site", "website") else "linkedin" if v.get("champ") == "linkedin" else ""
            k = self.retrouver(v.get("key", ""))
            if not champ or k is None or v.get("verdict") not in ("confirmé", "réfuté", "incertain"):
                self.stats["verdicts illisibles ou clé inconnue"] += 1
                continue
            v = dict(v)
            c = corpus.get(aid) if corpus is not None else None
            if v["verdict"] == "confirmé" and c is not None and v.get("valeur") and not vu(champ, v["valeur"], c):
                v["verdict"] = "incertain"
                v["raison"] = "URL non vue par le contre-vérificateur ; " + str(v.get("raison") or "")
                self.stats["verdicts confirmés ramenés à incertain (URL non vue)"] += 1
            self.verdicts[(k, champ, cle_url(champ, v.get("valeur") or ""))] = v

    def verdict(self, cles: tuple, champ: str, val: str):
        """Premier verdict trouvé sous ces clés (clé principale, puis alias)."""
        for k in cles:
            v = self.verdicts.get((k, champ, cle_url(champ, val))) or self.verdicts.get((k, champ, ""))
            if v:
                return v
        return None

    # -- un champ
    def decider(self, cles: tuple, champ: str, actuel: str, val: str, st: str, corpus: str | None):
        """cles : clés sous lesquelles chercher les verdicts ; actuel : la valeur que l'agent a vue."""
        notes = []
        if st == "confirmé":
            if actuel:
                if val and cle_url(champ, val) != cle_url(champ, actuel):
                    notes.append(f"{champ} proposé sans statut corrigé, non retenu : {val}")
                return actuel, "confirmé", notes
            if not val:
                return "", "introuvable", notes
            st = "trouvé"
        if st in ("corrigé", "trouvé"):
            if not val:   # valeur retirée sans remplaçant
                if actuel:
                    notes.append(f"ancien {champ} retiré : {actuel}")
                return "", "introuvable", notes
            val = propre(champ, val)
            ancien = f" ; ancien : {actuel}" if actuel and cle_url(champ, actuel) != cle_url(champ, val) else ""
            if corpus is not None and not vu(champ, val, corpus):
                notes.append(f"{champ} écarté, non vu par l'agent ({val}){ancien}")
                self.stats[f"{champ} écarté (non vu par l'agent)"] += 1
                return "", "écarté (non vu)", notes
            v = self.verdict(cles, champ, val)
            if v is None:
                return val, "non contre-vérifié", notes
            if v["verdict"] == "réfuté":
                notes.append(f"{champ} réfuté ({val}) : {court(v.get('raison'))}{ancien}")
                return "", "réfuté", notes
            if v["verdict"] == "incertain":
                notes.append(f"{champ} incertain : {court(v.get('raison'))}")
                return val, "incertain", notes
            return val, st, notes
        if st in VIDES:
            if actuel:
                notes.append(f"ancien {champ} retiré ({st}) : {actuel}")
            return "", st, notes
        return actuel, "non vérifié", [f"{champ} : statut inconnu ({st or 'vide'})"]

    @staticmethod
    def poser(et: dict, champ: str, val: str, detail: str) -> None:
        """Valeur, statut détaillé, puis statut et confiance du contrat."""
        ancien = et[champ]
        et[champ], et[f"{champ}_verif"] = val, detail
        if detail == "non vérifié":
            return
        if detail == "confirmé (contrôle léger)":
            et[f"{champ}_statut"] = "confirmé"
        elif detail == "confirmé" and val:   # « corrigé » si la valeur remplace celle de la ligne (alias)
            et[f"{champ}_statut"] = "confirmé" if cle_url(champ, val) == cle_url(champ, ancien) else "corrigé"
            et[f"{champ}_confiance"] = "haute"
        elif val and detail in ("incertain", "non contre-vérifié"):
            et[f"{champ}_statut"], et[f"{champ}_confiance"] = "corrigé", "à vérifier"
        elif val:
            et[f"{champ}_statut"], et[f"{champ}_confiance"] = ("confirmé" if cle_url(champ, val) == cle_url(champ, ancien)
                                                                else "corrigé"), "haute"
        else:
            et[f"{champ}_statut"], et[f"{champ}_confiance"] = "introuvable", ""
        if champ == "linkedin":
            if not val:
                et["linkedin_source"] = ""
            elif cle_url(champ, val) != cle_url(champ, ancien):
                et["linkedin_source"] = "agent"

    def localites(self) -> dict:
        if self._loc is None:
            self._loc = charger_localites()
        return self._loc

    @staticmethod
    def surs(f: dict) -> dict:
        """Valeurs sûres au sens de verif_preparer.py, dans l'état actuel et sur toutes les lignes de la liste."""
        et = f["etat"]
        return {"site": site_sur(et) and f["surs_lignes"]["site"],
                "linkedin": linkedin_sur(et) and f["surs_lignes"]["linkedin"]}

    # -- une entité rendue par un agent
    def entite(self, k: str, e: dict, lot: str, mode: str, corpus: str | None, cles: tuple | None = None,
               actuels: dict | None = None) -> None:
        """cles : clés sous lesquelles chercher les verdicts (passe 2 : la clé principale, puis ses alias) ;
        actuels : site et LinkedIn de la clé principale avant ce lot, ceux que l'agent a vus (sinon : l'état de k)."""
        f = self.ents[k]
        et, notes = f["etat"], []
        surs = self.surs(f)   # avant tout changement : sert au contrôle léger
        nom_off = court(e.get("nom_officiel"), 200)
        motif = (e.get("motif_exclusion") or "").strip()
        if nom_off and NON_IDENTIFIE.search(nom_off):
            notes.append(f"nom officiel : {nom_off}")
            motif = motif or "non identifiée"
        elif nom_off:
            et["nom_officiel"] = nom_off
        p = code_pays(e.get("pays", ""))
        if p and not et["pays"]:
            et["pays"] = p
        elif p and et["pays"].upper() != p:
            notes.append(f"pays selon la vérification : {p}")
        ville = court(e.get("ville"), 80)
        if ville and not et["ville"]:
            et["ville"] = ville
            if et["pays"].upper() == "CH" and not et["canton"]:
                et["canton"], et["region"] = region(ville, "CH", self.localites())
        if e.get("activite") and not et["activite"]:
            et["activite"] = court(e["activite"], 200)
        statuts = []
        for champ in ("site", "linkedin"):
            val = str(e.get(champ) or (e.get("website") if champ == "site" else "") or "").strip()
            st = str(e.get(f"{champ}_statut") or (e.get("website_statut") if champ == "site" else "") or "").strip()
            statuts.append(st)
            actuel = actuels[champ] if actuels is not None else et[champ]
            nv, detail, n = self.decider(cles or (k,), champ, actuel, val, st, corpus)
            if et[champ] and actuel != et[champ] and cle_url(champ, nv) != cle_url(champ, et[champ]):
                n.append(f"ancien {champ} de cette ligne : {et[champ]}")   # alias qui avait sa propre valeur
            if mode == "light" and detail == "confirmé":   # jugé sans outil : comme une clé de confirmes
                detail = "confirmé (contrôle léger)"
            self.poser(et, champ, nv, detail)
            if detail == "confirmé (contrôle léger)" and surs[champ]:
                et[f"{champ}_confiance"] = "haute"
            notes += n
        if "particulier" in statuts and not motif:
            motif = "particulier"
        et["exclure"] = motif if motif in MOTIFS else ""
        if motif and motif not in MOTIFS:
            notes.append(f"motif d'exclusion proposé : {motif}")
        et["preuve_verification"] = court(e.get("preuve"), 400)
        f["note_verif"] = " | ".join(x for x in [court(e.get("note"), 400), *notes] if x)
        f["lots"].append(f"{MODES.get(mode, mode)} ({lot})")
        f["touchee"] = f["rendue"] = True

    def confirme(self, k: str, item, lot: str) -> None:
        f = self.ents[k]
        et = f["etat"]
        if isinstance(item, dict):   # forme enrichie {key, nom_officiel, pays, activite} acceptée
            for c in ("nom_officiel", "activite"):
                if item.get(c) and not et[c]:
                    et[c] = court(item[c], 200)
            if code_pays(item.get("pays", "")) and not et["pays"]:
                et["pays"] = code_pays(item["pays"])
        if not et["nom_officiel"]:
            et["nom_officiel"] = f["key"]
        surs = self.surs(f)   # solide : confiance haute
        for champ in ("site", "linkedin"):
            if et[champ]:
                self.poser(et, champ, et[champ], "confirmé (contrôle léger)")
                if surs[champ]:
                    et[f"{champ}_confiance"] = "haute"
        f["lots"].append(f"légère ({lot})")
        f["touchee"] = f["rendue"] = True

    # -- un journal
    def journal(self, chemin: Path, controle: bool) -> set:
        lots, verdicts = lire_journal(chemin)
        corpus = corpus_agents(chemin.parent) if controle else None
        if controle and not corpus:
            print(f"! aucun transcript d'agent à côté de {chemin} : contrôle anti-invention impossible pour ce journal")
            corpus = None
        self.ajouter_verdicts(verdicts, corpus)
        derniers = {}
        for aid, l in lots:   # un lot rendu deux fois (reprise) : le dernier gagne
            derniers[str(l.get("batch_id"))] = (aid, l)
        print(f"{chemin.parent.name}/{chemin.name} : lots {sorted(derniers)} ; verdicts {len(verdicts)} ; "
              f"contrôle anti-invention {'oui' if corpus is not None else 'non'}")
        for bid, (aid, l) in derniers.items():
            c = corpus.get(aid) if corpus is not None else None
            if corpus is not None and c is None:
                self.stats["lots sans transcript (non contrôlés)"] += 1
            mode = l.get("mode") or {"D": "deep", "L": "light", "R": "resolve", "C": "complete"}.get(bid[:1], "")
            alias = self.alias.get(bid, {})
            groupes = {}   # clé principale -> (principale, alias...) : clés de ses verdicts, dans cet ordre
            for a, p in alias.items():
                groupes[p] = (*groupes.get(p, (p,)), a)
            # site et LinkedIn des clés principales avant ce lot : ce que l'agent a vu (passe1), alias compris
            avant = {p: {ch: self.ents[p]["etat"][ch] for ch in ("site", "linkedin")} for p in groupes if p in self.ents}
            rendues = set()
            for e in l.get("entites") or []:
                if not isinstance(e, dict):
                    continue
                k = self.retrouver(str(e.get("key", "")))
                if k is None:
                    self.inconnues.append(f"{bid} : {e.get('key')}")
                    continue
                p = alias.get(k, k)
                self.entite(k, e, bid, mode, c, cles=groupes.get(p), actuels=avant.get(p))
                rendues.add(k)
                self.stats["entités rendues"] += 1
            for a, principale in alias.items():   # alias oublié par l'agent : même résultat que la clé principale
                if a not in rendues and principale in rendues and a in self.ents:
                    e = next(x for x in l["entites"] if isinstance(x, dict) and self.retrouver(str(x.get("key", ""))) == principale)
                    self.entite(a, e, bid, mode, c, cles=groupes[principale], actuels=avant.get(principale))
                    self.stats["alias complétés"] += 1
            for item in l.get("confirmes") or []:
                key = item.get("key", "") if isinstance(item, dict) else str(item)
                k = self.retrouver(key)
                if k is None:
                    self.inconnues.append(f"{bid} : {key}")
                elif k not in rendues:
                    self.confirme(k, item, bid)
                    self.stats["confirmées en contrôle léger"] += 1
        return set(derniers)

    # -- entités confiées à un lot sans retour
    def non_verifiees(self, lots_vus: set) -> None:
        for nom, att in self.attendues.items():
            if not set(att.values()) & lots_vus:   # manifeste préparé mais pas encore lancé
                continue
            for k, bid in att.items():
                f = self.ents.get(k)
                if f is None or f["rendue"]:
                    continue
                for champ in ("site", "linkedin"):
                    f["etat"][f"{champ}_verif"] = "non vérifié"
                f["lots"].append(f"non vérifiée ({bid})")
                f["touchee"] = True
                self.stats["confiées sans retour (non vérifié)"] += 1

    # -- arbitrages manuels
    def arbitrages(self, chemin: Path) -> list:
        forces = []
        for r in lire_csv(chemin):
            key = r.get("nom") or r.get("cle") or r.get("key") or ""
            champ = (r.get("champ") or "").strip().lower()
            k = self.retrouver(key)
            if k is None or champ not in CHAMPS_ARBITRAGE:
                print(f"! arbitrage ignoré (nom inconnu ou champ non prévu) : {key} / {champ}")
                continue
            f, valeur = self.ents[k], (r.get("valeur") or "").strip()
            et, vide = f["etat"], valeur.lower() in AUCUN
            if champ in ("site", "linkedin"):
                val = "" if vide else (valeur or et[champ])
                self.poser(et, champ, val, (r.get("statut") or "").strip() or "arbitrage")
            elif champ == "note":
                pass
            elif champ == "a_revoir":
                forces.append((k, "" if vide else valeur))
            else:
                et[champ] = "" if vide else (code_pays(valeur) or valeur if champ == "pays" else valeur)
            if (r.get("note") or "").strip() or champ == "note":
                f["notes_arb"].append(court(r.get("note") or valeur, 400))
            f["touchee"] = True
            self.stats["arbitrages appliqués"] += 1
        return forces

    def lignes(self, base: list[dict], forces: list) -> list[dict]:
        for f in self.ents.values():
            et = f["etat"]
            if f["touchee"] and (f["lots"] or et["site_verif"] or et["linkedin_verif"]):
                et["a_revoir"] = "oui" if {et["site_verif"], et["linkedin_verif"]} & A_REVOIR else "non"
                et["verification"] = " ; ".join(f["lots"])
        for k, v in forces:
            self.ents[k]["etat"]["a_revoir"] = v
        out = []
        for r in base:
            o = dict(r)
            f = self.ents.get(cle(r.get("nom") or ""))
            if f and f["touchee"]:
                o.update(f["etat"])
                o["note"] = " | ".join(dict.fromkeys(x for x in (f["note_base"], f["note_verif"], *f["notes_arb"]) if x))
            out.append(o)
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Étape 4 : applique les journaux des workflows de vérification et écrit "
                                             "entreprises-verifie.csv.")
    argument_campagne(ap)
    ap.add_argument("journaux", nargs="+", help="journal.jsonl (ou dossier du run), passe 1 puis passe 2")
    ap.add_argument("--arbitrages", help="décisions manuelles (CSV nom, champ, valeur, statut, note) ; "
                                         "défaut : <campagne>/arbitrages.csv s'il existe")
    ap.add_argument("--sans-controle", action="store_true",
                    help="ne pas faire le contrôle anti-invention sur les transcripts des agents")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    chemins = []
    for j in a.journaux:
        p = Path(j).expanduser()
        p = p / "journal.jsonl" if p.is_dir() else p
        if not p.is_file():
            raise SystemExit(f"Journal introuvable : {p}")
        chemins.append(p)
    arb = Path(a.arbitrages) if a.arbitrages else camp.fichier("arbitrages.csv")
    if a.arbitrages and not arb.exists():
        raise SystemExit(f"Fichier d'arbitrages introuvable : {arb}")
    source = liste_de_base(camp)
    base = lire_csv(source)
    if not base:
        raise SystemExit(f"{source} ne contient aucune ligne.")
    manifestes = {}
    for nom in MANIFESTES.values():
        m = camp.verification / nom
        if m.exists():
            manifestes[nom] = json.loads(m.read_text(encoding="utf-8"))

    app = Application(base, manifestes)
    lots_vus = set()
    for p in chemins:
        lots_vus |= app.journal(p, not a.sans_controle)
    if not lots_vus:
        raise SystemExit("Aucun retour de lot dans ces journaux : rien n'est écrit (mauvais fichier, ou run sans "
                         "résultat). Le journal est le journal.jsonl du dossier du run de workflow.")
    app.non_verifiees(lots_vus)
    forces = app.arbitrages(arb) if arb.exists() else []

    lignes = app.lignes(base, forces)
    colonnes = list(COLONNES_ENTREPRISES)
    colonnes += [c for c in base[0] if c and c not in colonnes and c not in COLONNES_VERIF] + COLONNES_VERIF
    sortie = camp.fichier("entreprises-verifie.csv")
    if sortie.exists():
        shutil.copyfile(sortie, camp.verification / "entreprises-verifie.precedent.csv")
    ecrire_csv(sortie, colonnes, lignes)

    st = app.stats
    for k in sorted(st):
        print(f"  {k} : {st[k]}")
    if app.inconnues:
        print(f"! {len(app.inconnues)} clés rendues absentes de la liste (ignorées) : " + " ; ".join(app.inconnues[:10]))
    verifiees = [l for l in lignes if l.get("verification")]
    for champ in ("site", "linkedin"):
        c = Counter(l[f"{champ}_verif"] for l in verifiees)
        print(f"{champ} : " + ", ".join(f"{k} {v}" for k, v in c.most_common()) +
              f" ; rempli {sum(1 for l in lignes if l.get(champ))}/{len(lignes)}")
    excl = Counter(l["exclure"] for l in verifiees if l.get("exclure"))
    if excl:
        print("exclues par la vérification : " + ", ".join(f"{k} {v}" for k, v in excl.most_common()))
    revoir = [l for l in verifiees if l.get("a_revoir") == "oui"]
    print(f"{len(verifiees)} lignes vérifiées sur {len(lignes)}, {len(revoir)} à revoir -> {sortie}")
    for l in revoir[:30]:
        print(f"  à revoir : {l['nom']} | site {l['site_verif'] or '-'} | linkedin {l['linkedin_verif'] or '-'}")
    if len(revoir) > 30:
        print(f"  ... et {len(revoir) - 30} autres (colonne a_revoir)")
    if revoir:
        print("Trancher : note de chaque ligne (raison du contre-vérificateur), puis arbitrages.csv ou passe 2 "
              "(verif_passe2.py).")


if __name__ == "__main__":
    main()
