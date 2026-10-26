"""Étape 2, découverte web : consolide les trouvailles du workflow workflows/decouverte-entreprises.js en une liste
d'entreprises au contrat (entreprises.csv), avec une version lisible de tout ce qui a été trouvé.

Entrées :
- un ou plusieurs journaux du workflow (journal.jsonl, ou le dossier du run qui le contient) : retours structurés
  des agents (modalite, segment, entreprises). Les transcripts des agents (agent-<id>.jsonl, dans le dossier du
  journal) servent au contrôle anti-invention : un site, une page LinkedIn, une URL de preuve ou de signal qu'un
  agent n'a pas vus dans les résultats de ses outils sont écartés (une sortie volumineuse, dont le transcript ne
  garde qu'un aperçu, est lue dans son fichier complet). Garder le journal dans son dossier de run :
  copié seul, il ne peut plus être contrôlé (le script le signale) ;
- --deja <liste.csv> (répétable) : nos listes existantes, pour marquer les entreprises déjà connues ;
- --exclure <csv> (répétable ; défaut <campagne>/exclure.csv s'il existe) : nos clients et partenaires actuels,
  retirés de la liste ;
- --linkedin <csv> (défaut <campagne>/entreprises-linkedin.csv s'il existe) : sortie de linkedin_site.py, qui lit
  les sites, pour compléter les pages LinkedIn que les agents n'ont pas vues (colonnes nom, linkedin_company).
Pour --deja et --exclure, colonnes de nom et de site devinées (nom, entreprise, company, name... ; site, website,
domaine...).
Sorties, dans le dossier de la campagne :
- donnees/decouverte-mentions.json : toutes les mentions, avec les notes du contrôle ;
- entreprises-toutes.csv : une ligne par entreprise, dédoublonnée par nom puis par domaine, preuves fusionnées,
  statut (cible, hors cible et motif, aucune preuve vue, exclue, déjà connue) : le fichier à relire ;
- entreprises.csv : les entreprises retenues, au contrat (commun.COLONNES_ENTREPRISES, puis signaux). Les hors
  cible et les entreprises sans preuve vue n'y entrent pas, sauf avec --garder-hors-cible ou --garder-non-vues ;
  nos clients et partenaires jamais.
--ajouter garde les deux fichiers existants et n'y ajoute que les entreprises nouvelles (même nom normalisé ou même
domaine = déjà présente) : pour combiner une découverte web et une liste importée (importer_liste.py). Une entreprise
déjà écartée dans entreprises-toutes.csv et retenue cette fois y est marquée « ajoutée par » ; une entreprise déjà
exclue comme client ou partenaire actuel le reste. Sans --ajouter, un ancien apollo/contacts-importes.csv (d'une
liste précédente) est renommé en contacts-importes.precedent.csv.
Sans LLM ni réseau. Un résultat d'agent rejoué depuis le cache (reprise de workflow) n'est compté qu'une fois.

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/consolider_decouverte.py \\
      --campagne campagnes/<nom> <journal.jsonl ou dossier du run> [...] [--deja <liste.csv>]... [--exclure <csv>]...
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

from commun import (COLONNES_ENTREPRISES, Campagne, argument_campagne, charger_localites, charger_noms, code_pays,
                    domaine, ecrire_csv, linkedin_company, lire_csv, norm, region, site_propre, slug_linkedin)

# fichier lisible : tout ce qui a été trouvé
COLONNES_TOUTES = ["nom", "autres_noms", "pays", "ville", "canton", "region", "site", "linkedin", "linkedin_source",
                   "secteur", "activite", "taille", "signaux", "n_sources", "sources", "segments", "types_preuve",
                   "preuve_1_url", "preuve_1_extrait", "preuves_autres", "preuve_sur_le_site", "controle",
                   "deja_connue", "exclure", "statut"]
# entreprises.csv : le contrat, puis les signaux croisés par les agents
COLONNES_LISTE = COLONNES_ENTREPRISES + ["signaux"]


# ---------------------------------------------------------------- contrôle anti-invention

def texte(contenu) -> str:
    if isinstance(contenu, str):
        return contenu
    if isinstance(contenu, list):
        return " ".join(texte(c.get("text", "") if isinstance(c, dict) else c) for c in contenu)
    return ""


SORTIE_PERSISTEE = re.compile(r"Full output saved to: ([^\n<]+)")


def sortie_complete(chemin: str, dossier_run: Path) -> str:
    """Texte complet d'une sortie d'outil volumineuse, dont le transcript ne garde qu'un aperçu (« Full output saved
    to: <chemin> ») ; cherchée aussi, par son nom, dans tool-results/ du run et des dossiers parents (session)."""
    p = Path(chemin.strip())
    for c in (p, dossier_run / "tool-results" / p.name, *(d / "tool-results" / p.name for d in dossier_run.parents[:3])):
        if c.is_file():
            return c.read_text(encoding="utf-8", errors="ignore")
    return ""


def corpus_agents(dossier_run: Path) -> dict:
    """agentId -> tout ce que ses outils lui ont renvoyé, en minuscules : le seul « vu » qui compte (sorties
    volumineuses comprises, lues dans leur fichier complet)."""
    vus = {}
    for f in dossier_run.glob("agent-*.jsonl"):
        morceaux = []
        for ligne in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                m = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            msg = m.get("message") or {}
            contenu = msg.get("content") if isinstance(msg, dict) else None
            for c in contenu if isinstance(contenu, list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    t = texte(c.get("content"))
                    morceaux.append(t)
                    morceaux += [sortie_complete(p, dossier_run) for p in SORTIE_PERSISTEE.findall(t)]
        corpus = " ".join(morceaux).lower()
        vus[f.stem[len("agent-"):]] = corpus + " " + unquote(corpus)
    return vus


def url_vue(url: str, corpus: str) -> bool:
    u = re.sub(r"^https?://(www\.)?", "", (url or "").strip().lower()).rstrip("/")
    return bool(u) and (u in corpus or unquote(u) in corpus or domaine(url) in corpus)


def controler(m: dict, corpus: str | None) -> list[str]:
    """Vide ce que l'agent n'a pas vu ; marque une preuve non vue. Rien à faire sans transcript."""
    if corpus is None:
        return []
    notes = []
    if m.get("site") and domaine(m["site"]) not in corpus:
        notes.append(f"site écarté, non vu par l'agent ({m['site']})")
        m["site"] = ""
    if m.get("linkedin"):
        s = slug_linkedin(m["linkedin"])
        if not s or (s not in corpus and unquote(s) not in corpus):
            notes.append(f"LinkedIn écarté, non vu par l'agent ({m['linkedin']})")
            m["linkedin"] = ""
    if m.get("url_preuve") and not url_vue(m["url_preuve"], corpus):
        notes.append(f"preuve non vue par l'agent ({m['url_preuve']})")
        m["preuve_non_vue"] = True
    if m.get("signal") and m.get("url_signal") and not url_vue(m["url_signal"], corpus):
        notes.append("signal écarté, source non vue par l'agent")
        m["signal"], m["url_signal"] = "", ""
    return notes


# ---------------------------------------------------------------- lecture

def journal(chemin: str) -> Path:
    """journal.jsonl, ou le dossier du run qui le contient."""
    p = Path(chemin).expanduser()
    if p.is_dir():
        p = p / "journal.jsonl"
    if not p.is_file():
        raise SystemExit(f"Journal introuvable : {p} (dossier du run : find ~/.claude/projects -type d "
                         "-path '*workflows*' -name '<runId>')")
    return p


def resultats(journaux: list[Path], stats: Counter):
    """(résultat d'agent, corpus de cet agent ou None) ; un résultat rejoué depuis le cache n'est rendu qu'une fois."""
    vus = set()
    for j in journaux:
        corpus = corpus_agents(j.parent)
        if not corpus:
            print(f"! aucun transcript d'agent à côté de {j} : contrôle anti-invention impossible pour ce journal")
        for ligne in j.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(ligne)
            except json.JSONDecodeError:
                continue
            r = d.get("result")
            if d.get("type") == "result" and isinstance(r, dict) and "entreprises" in r:
                sig = json.dumps(r, sort_keys=True, ensure_ascii=False)[:3000]
                if sig in vus:
                    continue
                vus.add(sig)
                c = corpus.get(d.get("agentId", ""))
                stats["résultats contrôlés" if c is not None else "résultats non contrôlés (transcript absent)"] += 1
                yield r, c


def charger_linkedin(chemin: Path | None) -> dict:
    """nom normalisé -> page LinkedIn lue sur le site (sortie de linkedin_site.py)."""
    li = {}
    if chemin:
        for r in lire_csv(chemin):
            if linkedin_company(r.get("linkedin_company", "")):
                li[norm(r.get("nom", ""))] = linkedin_company(r["linkedin_company"])
    return li


MOTIF_CLIENT = "client ou partenaire actuel"


def fusionner(chemin: Path, nouvelles: list[dict], colonnes: list[str],
              reprendre: bool = False) -> tuple[list[dict], list[str], int, int]:
    """--ajouter : lignes existantes de chemin, puis les nouvelles qui n'y sont pas (même nom normalisé ou même
    domaine). Avec reprendre (entreprises-toutes.csv) : une ligne existante écartée (exclure rempli) que retrouve une
    nouvelle ligne retenue entre dans entreprises.csv ; son exclure est vidé et son statut complété
    (« ; ajoutée par <_origine> »), pour garder la règle « exclure vide = dans entreprises.csv ».
    Rend (lignes, colonnes, nombre de nouvelles déjà présentes, lignes reprises)."""
    if not chemin.exists():
        return nouvelles, colonnes, 0, 0
    anciennes = lire_csv(chemin)
    par_nom, par_dom = {}, {}
    for i, r in enumerate(anciennes):
        par_nom.setdefault(norm(r.get("nom", "")), i)
        par_dom.setdefault(domaine(r.get("site", "")), i)
    par_nom.pop("", None)
    par_dom.pop("", None)
    ajout, reprises = [], 0
    for l in nouvelles:
        i = par_nom.get(norm(l["nom"]))
        if i is None and l.get("site"):
            i = par_dom.get(domaine(l["site"]))
        if i is None:
            ajout.append(l)
        elif reprendre and l.get("_retenue") and anciennes[i].get("exclure"):
            r = anciennes[i]
            r["exclure"] = ""
            r["statut"] = f"{r.get('statut', '')} ; ajoutée par {l.get('_origine', 'un nouvel ajout')}".lstrip(" ;")
            reprises += 1
    cols = list(dict.fromkeys([*(anciennes[0].keys() if anciennes else []), *colonnes]))
    if colonnes[:len(COLONNES_ENTREPRISES)] == COLONNES_ENTREPRISES:     # entreprises.csv : le contrat d'abord
        cols = COLONNES_ENTREPRISES + [c for c in cols if c not in COLONNES_ENTREPRISES]
    return anciennes + ajout, cols, len(nouvelles) - len(ajout), reprises


def clients_deja_exclus(chemin: Path) -> tuple[set, set]:
    """--ajouter : noms normalisés et domaines déjà exclus comme clients ou partenaires actuels dans
    entreprises-toutes.csv. Ils le restent, même si la liste d'exclusion de ce passage ne les contient pas."""
    noms, doms = set(), set()
    if chemin.exists():
        for r in lire_csv(chemin):
            if r.get("exclure") == MOTIF_CLIENT:
                noms.add(norm(r.get("nom", "")))
                doms.add(domaine(r.get("site", "")))
    return noms - {""}, doms - {""}


def verifier_fichiers(fichiers: list[str]) -> None:
    """Arrêt avec un message clair si un fichier passé en option n'existe pas."""
    introuvables = [f for f in fichiers if f and not Path(f).is_file()]
    if introuvables:
        raise SystemExit("Introuvable : " + ", ".join(introuvables))


def avertir_listes_suivantes(camp: Campagne) -> None:
    """Les listes des étapes 3 et 4 datent d'avant cette liste : l'étape 5 lit pourtant la plus avancée."""
    suivantes = [n for n in ("entreprises-enrichi.csv", "entreprises-verifie.csv") if camp.fichier(n).exists()]
    if suivantes:
        print(f"! {' et '.join(suivantes)} {'datent' if len(suivantes) > 1 else 'date'} de la liste précédente, et "
              "l'étape 5 lit la liste la plus avancée : relancer l'étape 3 (puis 4) pour tenir compte de cette liste")


def ecarter_contacts_importes(camp: Campagne) -> None:
    """Sans --ajouter : entreprises.csv est remplacée, l'ancien apollo/contacts-importes.csv ne lui correspond plus
    (ordre_appel.py et plan_sequence.py le lisent en repli) : il est renommé en contacts-importes.precedent.csv."""
    ancien = camp.dossier / "apollo" / "contacts-importes.csv"
    if ancien.exists():
        precedent = ancien.with_name("contacts-importes.precedent.csv")
        ancien.replace(precedent)
        print(f"! {ancien.name} venait d'une liste précédente : renommé en {precedent.name} "
              "(option --ajouter pour combiner les listes)")


# ---------------------------------------------------------------- consolidation

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Consolide les journaux du workflow de découverte en entreprises-toutes.csv et entreprises.csv.")
    argument_campagne(ap)
    ap.add_argument("journaux", nargs="+", help="journal.jsonl du workflow, ou le dossier du run qui le contient")
    ap.add_argument("--deja", action="append", default=[], help="liste existante à reconnaître (CSV), répétable")
    ap.add_argument("--exclure", action="append", default=None,
                    help="nos clients et partenaires actuels (CSV), répétable ; défaut <campagne>/exclure.csv s'il existe")
    ap.add_argument("--linkedin", help="sortie de linkedin_site.py (colonnes nom, linkedin_company) ; "
                                       "défaut <campagne>/entreprises-linkedin.csv s'il existe")
    ap.add_argument("--garder-hors-cible", action="store_true", help="garder dans entreprises.csv les hors cible")
    ap.add_argument("--garder-non-vues", action="store_true", help="garder dans entreprises.csv les entreprises sans preuve vue")
    ap.add_argument("--ajouter", action="store_true", help="ajouter aux fichiers existants au lieu de les remplacer")
    a = ap.parse_args()
    verifier_fichiers([*(a.exclure or []), *a.deja, a.linkedin or ""])

    camp = Campagne(a.campagne, config_obligatoire=False)
    journaux = [journal(j) for j in a.journaux]
    if a.exclure is None:
        a.exclure = [str(camp.fichier("exclure.csv"))] if camp.fichier("exclure.csv").exists() else []
    if a.linkedin is None and camp.fichier("entreprises-linkedin.csv").exists():
        a.linkedin = str(camp.fichier("entreprises-linkedin.csv"))
    for f in a.exclure + ([a.linkedin] if a.linkedin else []):
        print(f"lu : {f}")
    loc = charger_localites()
    deja_noms, deja_doms = charger_noms(a.deja)
    excl_noms, excl_doms = charger_noms(a.exclure)
    if a.ajouter:
        avant_noms, avant_doms = clients_deja_exclus(camp.fichier("entreprises-toutes.csv"))
        excl_noms, excl_doms = excl_noms | avant_noms, excl_doms | avant_doms
        if avant_noms:
            print(f"lu : {camp.fichier('entreprises-toutes.csv')} ({len(avant_noms)} clients ou partenaires "
                  "déjà exclus, qui le restent)")
    li_sites = charger_linkedin(Path(a.linkedin) if a.linkedin else None)

    stats = Counter()
    mentions = []
    for r, corpus in resultats(journaux, stats):
        for e in r.get("entreprises") or []:
            m = {**e, "modalite": r.get("modalite", ""), "segment": e.get("segment") or r.get("segment", "")}
            m["controle"] = controler(m, corpus)
            for n in m["controle"]:
                stats[n.split(",")[0].split(" (")[0]] += 1
            mentions.append(m)
    (camp.donnees / "decouverte-mentions.json").write_text(json.dumps(mentions, ensure_ascii=False, indent=0),
                                                           encoding="utf-8")

    E, par_dom = {}, {}
    for m in mentions:
        k, d = norm(m.get("nom")), domaine(m.get("site", ""))
        if not k:
            continue
        if d and d in par_dom:
            k = par_dom[d]
        e = E.setdefault(k, {"noms": Counter(), "pays": Counter(), "villes": Counter(), "sites": Counter(),
                             "linkedin": Counter(), "secteurs": [], "activites": [], "tailles": [], "signaux": [],
                             "hors_cible": Counter(), "sources": set(), "segments": set(), "types": set(),
                             "preuves": [], "controle": [], "n_vues": 0})
        if d and d not in par_dom:
            par_dom[d] = k
        e["noms"][m["nom"].strip()] += 1
        if (m.get("pays") or "").strip():
            e["pays"][code_pays(m["pays"]) or m["pays"].strip().upper()] += 1
        if m.get("ville"):
            e["villes"][m["ville"].strip()] += 1
        if d:
            e["sites"][d] += 1
        if linkedin_company(m.get("linkedin", "")):
            e["linkedin"][linkedin_company(m["linkedin"])] += 1
        for champ, dst in (("secteur", "secteurs"), ("activite", "activites"), ("taille", "tailles")):
            if m.get(champ) and m[champ].strip() not in e[dst]:
                e[dst].append(m[champ].strip())
        if m.get("signal"):
            e["signaux"].append(m["signal"].strip() + (f" ({m['url_signal']})" if m.get("url_signal") else ""))
        if (m.get("hors_cible") or "").strip():
            e["hors_cible"][m["hors_cible"].strip()] += 1
        e["sources"].add(m["modalite"])
        if m.get("segment"):
            e["segments"].add(m["segment"])
        e["types"].add(m.get("type_source", ""))
        e["controle"] += m["controle"]
        if m.get("url_preuve") and not m.get("preuve_non_vue"):
            e["n_vues"] += 1
            if len(e["preuves"]) < 4 and m["url_preuve"] not in [p[0] for p in e["preuves"]]:
                e["preuves"].append((m["url_preuve"], (m.get("extrait") or "").strip()[:240]))

    lignes = []
    for k, e in E.items():
        nom = e["noms"].most_common(1)[0][0]
        pays = e["pays"].most_common(1)[0][0] if e["pays"] else ""
        ville = e["villes"].most_common(1)[0][0] if e["villes"] else ""
        site = site_propre(e["sites"].most_common(1)[0][0]) if e["sites"] else ""
        linkedin = e["linkedin"].most_common(1)[0][0] if e["linkedin"] else li_sites.get(norm(nom), "")
        canton, reg = region(ville, pays, loc)
        deja = (k in deja_noms) or (domaine(site) in deja_doms if site else False)
        exclue = (k in excl_noms) or (domaine(site) in excl_doms if site else False)
        # hors cible : seulement si la majorité des mentions le dit (un agent isolé ne suffit pas)
        hc_motif, hc_n = e["hors_cible"].most_common(1)[0] if e["hors_cible"] else ("", 0)
        hors_cible = hc_n * 2 > sum(e["noms"].values())
        non_vue = e["n_vues"] == 0
        sur_site = bool(site) and any(domaine(u).endswith(domaine(site)) for u, _ in e["preuves"])
        statut = ("exclue (client ou partenaire actuel)" if exclue else "aucune preuve vue (à vérifier)" if non_vue
                  else f"hors cible ({hc_motif})" if hors_cible else "cible")
        statut += " ; déjà dans nos listes" if deja else ""
        stats[statut.split(" ;")[0].split(" (")[0]] += 1
        stats["déjà dans nos listes"] += deja
        retenue = not exclue and (a.garder_hors_cible or not hors_cible) and (a.garder_non_vues or not non_vue)
        lignes.append({
            "nom": nom, "autres_noms": " | ".join(n for n in e["noms"] if n != nom)[:200],
            "pays": pays, "ville": ville, "canton": canton, "region": reg, "site": site, "linkedin": linkedin,
            "linkedin_source": "agent" if e["linkedin"] else ("site web" if linkedin else ""),
            "secteur": " | ".join(e["secteurs"])[:200], "activite": e["activites"][0] if e["activites"] else "",
            "taille": " | ".join(e["tailles"])[:200], "signaux": " || ".join(dict.fromkeys(e["signaux"]))[:600],
            "n_sources": len(e["sources"]), "sources": " | ".join(sorted(e["sources"])),
            "segments": " | ".join(sorted(e["segments"])), "types_preuve": " | ".join(sorted(t for t in e["types"] if t)),
            "preuve_1_url": e["preuves"][0][0] if e["preuves"] else "",
            "preuve_1_extrait": e["preuves"][0][1] if e["preuves"] else "",
            "preuves_autres": " || ".join(u for u, _ in e["preuves"][1:]),
            "preuve_sur_le_site": "oui" if sur_site else "non",
            "controle": " ; ".join(dict.fromkeys(e["controle"]))[:500],
            "deja_connue": "oui" if deja else "",
            # vide = l'entreprise est dans entreprises.csv ; sinon la raison
            "exclure": "" if retenue else (MOTIF_CLIENT if exclue else "aucune preuve vue" if non_vue
                                           else f"hors cible ({hc_motif})"),
            "statut": statut,
            "_ecartee": hors_cible or non_vue or exclue, "_non_vue": non_vue, "_retenue": retenue,
            "_origine": f"découverte web ({' | '.join(sorted(e['sources']))})",
        })
    # cible d'abord, puis le plus de sources, puis le nom
    lignes.sort(key=lambda l: (l["_ecartee"], -l["n_sources"], norm(l["nom"])))

    # --- entreprises.csv : le contrat des étapes suivantes
    retenues = [l for l in lignes if l["_retenue"]]
    liste = []
    for l in retenues:
        liste.append({
            "nom": l["nom"], "pays": l["pays"], "ville": l["ville"], "canton": l["canton"], "region": l["region"],
            "site": l["site"], "site_statut": "trouvé" if l["site"] else "",
            "site_confiance": ("haute" if l["preuve_sur_le_site"] == "oui" else "à vérifier") if l["site"] else "",
            "linkedin": l["linkedin"], "linkedin_statut": "trouvé" if l["linkedin"] else "",
            "linkedin_source": l["linkedin_source"], "linkedin_confiance": "à vérifier" if l["linkedin"] else "",
            "secteur": l["secteur"], "activite": l["activite"] or l["secteur"], "taille": l["taille"],
            "source": f"découverte web ({l['sources']})",
            "preuve": f"{l['preuve_1_url']} : « {l['preuve_1_extrait']} »" if l["preuve_1_url"] else "",
            "a_revoir": "non" if l["site"] and not l["_non_vue"] else "oui",
            "exclure": "", "deja_connue": l["deja_connue"],
            "note": l["statut"] if l["_ecartee"] else "", "signaux": l["signaux"],
        })
    toutes, cols_toutes, cols_liste = lignes, COLONNES_TOUTES, COLONNES_LISTE
    n_deja_toutes = n_deja_liste = n_reprises = 0
    if a.ajouter:
        toutes, cols_toutes, n_deja_toutes, n_reprises = fusionner(
            camp.fichier("entreprises-toutes.csv"), lignes, COLONNES_TOUTES, reprendre=True)
        liste, cols_liste, n_deja_liste, _ = fusionner(camp.fichier("entreprises.csv"), liste, COLONNES_LISTE)
    else:
        ecarter_contacts_importes(camp)
    avertir_listes_suivantes(camp)
    ecrire_csv(camp.fichier("entreprises-toutes.csv"), cols_toutes, toutes)
    ecrire_csv(camp.fichier("entreprises.csv"), cols_liste, liste)

    print(f"{len(mentions)} mentions, {len(lignes)} entreprises uniques : {stats['cible']} dans la cible, "
          f"{stats['hors cible']} hors cible, {stats['aucune preuve vue']} sans preuve vue, "
          f"{stats['exclue']} exclues (clients ou partenaires), {stats['déjà dans nos listes']} déjà dans nos listes")
    print("contrôle anti-invention : " + ", ".join(f"{k} {v}" for k, v in stats.items()
                                                    if k.startswith(("résultats", "site", "LinkedIn", "preuve", "signal"))))
    print(f"retenues : {len(retenues)} ; sans site : {sum(1 for l in retenues if not l['site'])} ; "
          f"sans LinkedIn : {sum(1 for l in retenues if not l['linkedin'])}")
    if a.ajouter:
        print(f"--ajouter : entreprises.csv + {len(retenues) - n_deja_liste} (déjà présentes : {n_deja_liste}) ; "
              f"entreprises-toutes.csv + {len(lignes) - n_deja_toutes}, dont écartées avant et retenues cette fois : "
              f"{n_reprises}")
    print(f"-> {camp.fichier('entreprises-toutes.csv')} (à relire)")
    print(f"-> {camp.fichier('entreprises.csv')} ({len(liste)} entreprises au contrat)")


if __name__ == "__main__":
    main()
