"""Étape 5 : signaux consolidés -> scores -> tiers de prospection A / B / C / D / Hors cible.

Principe (des signaux qui font monter une entreprise dans les tiers) :
  1. tier de base = fit ICP (zone + taille + secteur, 0-9, icp.py et section [cible] de campagne.toml) :
     bon fit = B, fit moyen = C, fit faible = D ;
  2. les signaux font MONTER d'un ou deux crans (le A = bon fit ET signal) :
       - « moment » (timing, -10..10) : changement de direction, levée / augmentation de capital, rachat / fusion,
         nouveau site, projet ERP / numérique... pondéré par la fiabilité (registre > vérifié > agent > auto)
         et la récence (≤ 12 mois x1, 12-24 x0,65, 24-36 x0,3) ;
       - « adoption tech / early adopter » (0-10) : maturité du site (stack), mentions IA / industrie 4.0,
         activité LinkedIn, recrutement tech, appréciation de l'agent ;
  3. les signaux négatifs (difficultés, liquidation) font descendre ou excluent ;
  4. une entreprise qui vend ce que nous vendons (concurrent, d'après la recherche par agents) plafonne en B.
Score de tri = 2 x fit + moment + 0,8 x tech. Poids et seuils : constantes ci-dessous.

Entrées (<campagne>/donnees/signaux/) : entites.json, zefix.json, linkedin.json, site.json, news.json (facultatifs),
recherche.json (apply_recherche.py, facultatif), historique/*.json (instantané précédent, pour la veille).
Sorties :
  - <campagne>/prospection-signaux.csv : une ligne par entreprise, triée par tier puis score ;
  - <campagne>/rapport-signaux.md : tiers, fiches du tier A, tableau du tier B, nouveaux signaux, alertes,
    concurrents, pages LinkedIn corrigées, méthode ;
  - donnees/signaux/signaux.json : {id: [signaux datés, avec confiance, source et poids]} ;
  - donnees/signaux/historique/<date de référence>.json : instantané des signaux pesants (mode veille).
Déterministe, sans réseau : relançable à tout moment (après une correction du lexique, de l'ICP ou de la recherche).

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/scorer.py --campagne campagnes/<nom>
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

# ---------------------------------------------------------------- poids des signaux « moment »
# (famille, sous_type) -> {fiabilité: poids à ≤ 12 mois}
W = {
    ("direction", "nouveau_dirigeant"): {"registre": 6, "vérifié": 6, "agent": 4.5, "auto": 2},
    ("direction", "nouveau_cadre"): {"registre": 2.5, "vérifié": 3, "agent": 2.5, "auto": 1},
    ("direction", "depart_dirigeant"): {"registre": 3, "vérifié": 3, "agent": 2.5, "auto": 1},
    ("direction", "succession"): {"registre": 4, "vérifié": 5, "agent": 4, "auto": 1.5},
    ("direction", "conseil"): {"registre": 1, "vérifié": 1, "agent": 1, "auto": 0.25},
    ("financement", "levee"): {"registre": 5, "vérifié": 6, "agent": 4.5, "auto": 1.5},
    ("financement", "augmentation_capital"): {"registre": 4, "vérifié": 4, "agent": 3, "auto": 1},
    ("financement", "kapitalband"): {"registre": 1.5, "vérifié": 1.5, "agent": 1, "auto": 0.5},
    ("financement", "aide_publique"): {"registre": 2.5, "vérifié": 2.5, "agent": 2, "auto": 0.75},
    ("ma", "rachat"): {"registre": 5, "vérifié": 5, "agent": 4, "auto": 1.5},
    ("ma", "fusion_reprise"): {"registre": 4, "vérifié": 4, "agent": 3.5, "auto": 1.5},
    ("ma", "absorbe"): {"registre": 3, "vérifié": 3, "agent": 3, "auto": 1},
    ("croissance", "nouveau_site"): {"registre": 1.5, "vérifié": 3, "agent": 2.5, "auto": 1},
    ("croissance", "nouveau_siege"): {"registre": 1.5, "vérifié": 1.5, "agent": 1.5, "auto": 0.5},
    ("croissance", "recrutement"): {"registre": 1, "vérifié": 1.5, "agent": 1.5, "auto": 0.5},
    ("projet", "erp_numerique"): {"registre": 3, "vérifié": 4, "agent": 3.5, "auto": 0.75},
    ("projet", "certification"): {"registre": 1, "vérifié": 1, "agent": 1, "auto": 0.5},
    ("projet", "lancement_produit"): {"registre": 0.5, "vérifié": 1, "agent": 1, "auto": 0.25},
    ("projet", "changement_nom"): {"registre": 1, "vérifié": 1, "agent": 1, "auto": 0.25},
    ("projet", "changement_but"): {"registre": 0.5, "vérifié": 0.5, "agent": 0.5, "auto": 0},
    ("negatif", "difficultes"): {"registre": -6, "vérifié": -6, "agent": -4, "auto": -0.5},
    ("negatif", "dissolution"): {"registre": -10, "vérifié": -10, "agent": -6, "auto": -1},
    ("negatif", "faillite"): {"registre": -10, "vérifié": -10, "agent": -7, "auto": -1},
    ("negatif", "sursis_concordataire"): {"registre": -7, "vérifié": -7, "agent": -5, "auto": -1},
    ("negatif", "faillite_annulee"): {"registre": -2, "vérifié": -2, "agent": -2, "auto": 0},
    ("negatif", "reduction_capital"): {"registre": -1, "vérifié": -1, "agent": -1, "auto": 0},
}
GRAVES = {"faillite", "sursis_concordataire", "dissolution", "difficultes"}
# l'agent a établi que la fiche du registre est celle d'un homonyme : le registre est alors ignoré
REGISTRE_HOMONYME = re.compile(r"(?:registre|zefix)[^.]{0,140}homonyme|homonyme[^.]{0,80}registre", re.I)
# niveau de la personne inscrite au registre (collect_zefix.py) -> coefficient d'un signal de direction
NIVEAU_REGISTRE = {"top": 1.0, "president": 0.5, "direction": 1.0, "conseil": 1.0, "signature": 0.3, "": 0.8}
FAMILLE_LABEL = {"direction": "Direction", "financement": "Financement", "ma": "Rachat / fusion",
                 "croissance": "Croissance", "projet": "Projet", "negatif": "Négatif", "tech": "Tech"}
# nouveau cadre clé (IT, numérique, qualité, opérations...) : +1 au signal vérifié ou d'agent ; les familles relais du
# persona de la campagne ([persona] relais) comptent aussi
ROLES_CLES = re.compile(r"\b(?:CIO|CDO|CTO|IT|informati|digital|numérique|data|innovation|qualité|quality|QMS|"
                        r"opérations|operations|COO|production|industriel)", re.I)
SEUIL_MOMENT, SEUIL_TECH = 4, 6
BONUS_CAPITAL = re.compile(r"\+\s?(\d[\d']{6,})")    # augmentation de capital d'au moins un million (registre)
TIERS = ["A", "B", "C", "D"]
MOIS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
COLONNES = ["rang", "tier", "fenetre_opportunite", "score", "tier_fit", "monte_de", "fit_icp", "timing", "tech",
            "nom", "pays", "canton", "secteur", "taille", "activite", "pourquoi_maintenant", "signaux_direction",
            "signaux_financement", "signaux_rachat_fusion", "signaux_croissance_projets", "signaux_tech",
            "signaux_negatifs", "dirigeants", "persona_cible", "angle", "site", "linkedin", "linkedin_corrige",
            "registre", "motifs_exclusion", "recherche_agent", "sources", "id"]

_persona = {}


def decay(d, confiance: str) -> float:
    from signaux_commun import months_ago
    if d is None:
        return 0.3 if confiance in ("vérifié", "agent") else 0.0
    m = months_ago(d)
    if m is None or m < -3:
        return 0.0
    if m <= 12:
        return 1.0
    if m <= 24:
        return 0.65
    if m <= 36:
        return 0.3
    return 0.0


# ---------------------------------------------------------------- consolidation des signaux

def person_of(resume: str) -> str:
    m = re.match(r"^(?:Inscription|Radiation|Promotion|Entrée CA|Sortie CA) : (.+?)(?: \(|$)", resume or "")
    return m.group(1).strip().lower() if m else ""


def flip_flops_removed(sigs: list[dict]) -> list[dict]:
    """Même personne radiée puis réinscrite (ou l'inverse) à < 6 mois : changement de signature, pas de dirigeant."""
    from signaux_commun import to_date
    events = {}
    for s in sigs:
        if s["famille"] == "direction":
            events.setdefault(person_of(s["resume"]), []).append(s)
    drop = set()
    for name, evs in events.items():
        if not name:
            continue
        ins = [x for x in evs if x["sous_type"] in ("nouveau_dirigeant", "nouveau_cadre")]
        out = [x for x in evs if x["sous_type"] == "depart_dirigeant"]
        for a in ins:
            for b in out:
                da, db = to_date(a["date"]), to_date(b["date"])
                if da and db and abs((da - db).days) <= 183:
                    drop.update({id(a), id(b)})
    return [s for s in sigs if id(s) not in drop]


def collect_signals(e: dict, z: dict, li: dict, site: dict, news: dict, rech: dict) -> list[dict]:
    import auto
    from signaux_commun import clip, to_date
    sig = []
    # l'agent a vu les événements du registre : son interprétation (rôle réel, rachat...) remplace l'événement brut
    # de même famille daté à ± 25 jours, pour ne pas compter deux fois le même fait
    agent_dates = [(s.get("famille"), to_date(s.get("date"))) for s in (rech or {}).get("signaux", [])
                   if not (s.get("verdict") or "").lower().startswith("réfut")]
    if z.get("statut") == "ok":
        for s in flip_flops_removed(z.get("signaux", [])):
            d = to_date(s.get("date"))
            if d and any(f == s["famille"] and ad and abs((ad - d).days) <= 25 for f, ad in agent_dates):
                continue
            sig.append({**s, "confiance": "registre", "source": "registre du commerce"})
    if not rech:   # entreprise recherchée par un agent : ses signaux remplacent les détections automatiques
        if li.get("statut") == "ok":
            for s in auto.linkedin(li):
                if s["famille"] != "tech":
                    sig.append({**s, "confiance": "auto", "source": "post LinkedIn",
                                "resume": "post : « " + clip(re.sub(r"\s+", " ", s.get("texte", "")), 120) + " »"})
        for s in auto.news(news):
            if s["famille"] != "tech":
                sig.append({**s, "confiance": "auto", "source": "actualité web", "resume": s.get("titre") or clip(s["extrait"], 160)})
    for s in (rech or {}).get("signaux", []):
        v = (s.get("verdict") or "").lower()
        if v.startswith("réfut") or v.startswith("refut"):
            continue
        conf = "vérifié" if v.startswith("confirm") else "agent"
        if conf == "agent" and s.get("confiance") == "faible":
            conf = "auto"
        # contrôle anti-invention d'apply_recherche.py : source jamais vue par l'agent, ou pas de source
        note = " (contre-vérifiée)" if conf == "vérifié" else \
            {"source non vue": ", source non vue", "source absente": ", sans source"}.get(s.get("controle") or "", "")
        sig.append({"famille": s.get("famille", ""), "sous_type": s.get("sous_type", ""), "date": s.get("date", ""),
                    "resume": s.get("resume", ""), "url": s.get("source_url", ""), "confiance": conf,
                    "source": "recherche agent" + note, "niveau": s.get("niveau", "")})
    return sig


def role_cle(resume: str) -> bool:
    """Nouveau cadre dans un rôle clé : ROLES_CLES, ou une famille relais du persona de la campagne."""
    if ROLES_CLES.search(resume or ""):
        return True
    P = _persona.get("P")
    if P is None or not P.relais:
        return False
    return bool((set(P.familles_texte(resume)) | P.familles_titre(resume)) & set(P.relais))


def weight(s: dict) -> float:
    from signaux_commun import to_date
    w = W.get((s["famille"], s["sous_type"]))
    if not w:
        return 0.0
    base = w.get(s["confiance"], 0)
    if s["confiance"] == "registre" and s["famille"] == "direction":
        base *= NIVEAU_REGISTRE.get(s.get("niveau", ""), 0.8)
    if s["famille"] == "direction" and s["sous_type"] == "nouveau_cadre" and s["confiance"] in ("vérifié", "agent") \
            and role_cle(s.get("resume", "")):
        base += 1
    if s["sous_type"] == "augmentation_capital" and BONUS_CAPITAL.search(s.get("resume", "")):
        base += 1                                      # au moins un million levé
    return base * decay(to_date(s.get("date")), s["confiance"])


def timing_score(sig: list[dict]) -> tuple[float, list[dict]]:
    best = {}
    conseil = 0.0
    neg = 0.0
    for s in sig:
        s["poids"] = round(weight(s), 2)
        if s["poids"] == 0:
            continue
        key = (s["famille"], s["sous_type"])
        if s["famille"] == "negatif":
            neg = min(neg, s["poids"]) if s["confiance"] != "auto" else neg + s["poids"]
            continue
        if key == ("direction", "conseil"):
            conseil += s["poids"]
            continue
        if key not in best or s["poids"] > best[key]["poids"]:
            best[key] = s
    pos = sum(s["poids"] for s in best.values()) + min(conseil, 2)
    total = max(-10.0, min(10.0, min(pos, 10) + max(neg, -10)))
    top = sorted(best.values(), key=lambda s: -s["poids"])
    return round(total, 1), top


def tech_score(site: dict, li: dict, rech: dict) -> tuple[float, list[str], bool]:
    from signaux_commun import clip, months_ago, to_date
    preuves, web, cont, act, hire = [], 0.0, 0.0, 0.0, 0.0
    if site.get("statut") == "ok":
        cats = set(site.get("stack_categories", []))
        stack = site.get("stack", [])
        if cats & {"cms_moderne", "framework"}:
            web += 0.75
        if "marketing" in cats:
            web += 0.75
        if "analytics" in cats:
            web += 0.25
        if "chat_ia" in cats:
            web += 1.0
        elif "chat" in cats:
            web += 0.5
        if cats & {"portail", "ecommerce"}:
            web += 0.5
        if len(site.get("langues", [])) >= 3:
            web += 0.25
        d = to_date(site.get("derniere_date"))
        if d and months_ago(d) <= 6:
            web += 0.25
        web = min(web, 3)
        notable = [x for x in stack if x not in ("Google Analytics 4", "Google Tag Manager", "Cloudflare", "AWS CloudFront")
                   and not x.startswith(("Cookie", "OneTrust", "Usercentrics", "Borlabs", "Complianz", "iubenda", "Didomi", "Axeptio"))]
        if notable:
            preuves.append("site : " + ", ".join(notable[:6]))
        jobs = (site.get("carrieres") or {}).get("postes_tech") or []
        if jobs:
            hire = 1.5 if len(jobs) >= 3 else 1.0
            preuves.append("recrute : " + " ; ".join(clip(j, 60) for j in jobs[:2]))
    counts = Counter()
    counts.update(site.get("tech") or {})
    counts.update(li.get("tech_posts") or {})
    if counts.get("ia", 0) >= 1:
        cont += 2 if counts["ia"] >= 3 else 1.5
        preuves.append(f"IA mentionnée ({counts['ia']}x site/posts)")
    if counts.get("industrie40", 0) >= 1:
        cont += 0.75
        preuves.append("industrie 4.0 / IoT")
    if counts.get("digital", 0) >= 2:
        cont += 0.5
    if counts.get("automatisation", 0) >= 3:
        cont += 0.5
    if counts.get("innovation", 0) >= 3:
        cont += 0.25
    cont = min(cont, 3)
    if li.get("statut") == "ok":
        p90 = li.get("posts_90j") or 0
        act = 1.5 if p90 >= 6 else 1.0 if p90 >= 3 else 0.5 if p90 >= 1 else 0
        if p90:
            preuves.append(f"LinkedIn actif ({p90} posts / 90 j)")
    agent = 0.0
    concurrent = False
    at = (rech or {}).get("adoption_tech") or {}
    if at:
        agent = {"fort": 3, "moyen": 1.5}.get(at.get("niveau"), 0)
        concurrent = bool(at.get("concurrent"))
        preuves = [clip(p, 120) for p in (at.get("preuves") or [])[:3]] + preuves
    return round(min(10, web + cont + act + hire + agent), 1), preuves, concurrent


def tier_of(fit: float, timing: float, tech: float, motifs: list[str], concurrent: bool) -> tuple[str, str, int]:
    """Tier de base par le fit (bon fit = B), puis les signaux font monter : A = bon fit ET signal."""
    if motifs:
        return "Hors cible", "Hors cible", 0
    base = 1 if fit >= 7.5 else 2 if fit >= 6 else 3
    strong_t, strong_x = timing >= SEUIL_MOMENT, tech >= SEUIL_TECH
    boost = 2 if (strong_t and strong_x) or timing >= 7 else 1 if (strong_t or strong_x) else 0
    if timing < 0:
        boost -= 1
    final = max(0, min(3, base - boost))
    if fit < 6:
        final = max(final, 1)          # le fit reste la porte d'entrée : pas de A sous 6/9
    if concurrent:
        final = max(final, 1)          # vend ce que nous vendons : concurrent ou partenaire, pas un prospect prioritaire
    return TIERS[final], TIERS[base], base - final


# ---------------------------------------------------------------- textes

def mois(d: str) -> str:
    from signaux_commun import to_date
    dd = to_date(d)
    return f"{MOIS_FR[dd.month - 1]} {dd.year}" if dd else "date inconnue"


def phrase(s: dict) -> str:
    """Signal lisible : « Nouveau dirigeant au registre : Prénom Nom (directeur général), oct. 2025 »."""
    from signaux_commun import clip
    r = s.get("resume") or s.get("terme", "")
    if s.get("confiance") == "registre" and s["famille"] == "direction":
        nom = person_of(r) and re.match(r"^\w[\w ]* : (.+?)(?: \(|$)", r).group(1)
        role = (re.search(r"\(([^)]*)\)\s*$", r) or [None, ""])[1]
        role = role.split("->")[-1].strip() if "->" in role else role
        r = {"nouveau_dirigeant": f"Nouveau dirigeant au registre : {nom} ({role})",
             "nouveau_cadre": f"Nouveau directeur au registre : {nom} ({role})",
             "depart_dirigeant": f"Départ de {nom} ({role}) au registre",
             "conseil": f"Conseil d'administration : {r.split(' : ')[0].replace('CA', '').strip().lower()} de {nom}",
             }.get(s["sous_type"], r)
    return f"{clip(r, 140)}, {mois(s.get('date'))}"


def fmt_sig(s: dict) -> str:
    return f"{phrase(s)} ({s.get('source')})"


def pourquoi(top: list[dict], tech_preuves: list[str], rech: dict) -> str:
    if (rech or {}).get("pourquoi_maintenant"):
        return rech["pourquoi_maintenant"]
    parts = [phrase(s) for s in top[:2] if s["poids"] >= 1.5]
    if tech_preuves:
        parts.append("Tech : " + "; ".join(tech_preuves[:2]))
    return " | ".join(parts)


def dirigeants(z: dict, rech: dict) -> str:
    if (rech or {}).get("dirigeants"):
        return "; ".join(f"{d.get('nom')} ({d.get('role', '')}{', depuis ' + d['depuis'] if d.get('depuis') else ''})"
                         for d in rech["dirigeants"][:4])
    out = []
    for s in z.get("signaux", []):
        if s["famille"] == "direction" and s["sous_type"] == "nouveau_dirigeant":
            out.append(f"{s['resume'].split(':', 1)[-1].strip()} [{s['date']}]")
    return "; ".join(out[:3])


def persona_cible(rech: dict) -> str:
    """Texte de l'agent, sinon rédigé depuis les cibles structurées : « Entrée : Prénom Nom (rôle) ; relais : rôle »."""
    if (rech or {}).get("persona_cible"):
        return rech["persona_cible"]
    c = (rech or {}).get("cibles") or {}

    def fmt(x: dict) -> str:
        nom, role = (x.get("nom") or "").strip(), (x.get("role") or "").strip()
        return f"{nom} ({role})" if nom and role else nom or role

    entree = ", ".join(t for t in (fmt(x) for x in c.get("entree") or [] if isinstance(x, dict)) if t)
    relais = ", ".join(t for t in (fmt(x) for x in c.get("relais") or [] if isinstance(x, dict)) if t)
    return " ; ".join(p for p in (f"Entrée : {entree}" if entree else "", f"relais : {relais}" if relais else "") if p)


# ---------------------------------------------------------------- veille

def sig_key(eid: str, s: dict) -> str:
    return f"{eid}|{s['famille']}|{s['sous_type']}|{s.get('date', '')}|{norm_txt(s.get('resume', ''))[:60]}"


def norm_txt(t: str) -> str:
    return re.sub(r"\W+", " ", (t or "").lower()).strip()


def veille(rows: list[dict], all_sig: dict) -> list[dict]:
    """Instantané daté des signaux pesants ; renvoie ceux absents de l'instantané précédent (mode veille)."""
    from signaux_commun import aujourdhui, donnees, load_json, save_json
    hist = donnees() / "historique"
    hist.mkdir(parents=True, exist_ok=True)
    jour = aujourdhui().isoformat()
    tiers = {r["id"]: r for r in rows}
    cur = {sig_key(eid, s): {"id": eid, **{k: s.get(k, "") for k in ("famille", "sous_type", "date", "resume", "source", "url")}}
           for eid, sigs in all_sig.items() for s in sigs
           if (s.get("poids") or 0) >= 1.5 and tiers[eid]["tier"] != "Hors cible"}
    prev_files = sorted(f for f in hist.glob("*.json") if f.stem < jour)
    save_json(hist / f"{jour}.json", cur)
    if not prev_files:
        return []
    prev = load_json(prev_files[-1], {}) or {}
    new = [dict(v, nom=tiers[v["id"]]["nom"], tier=tiers[v["id"]]["tier"], depuis=prev_files[-1].stem)
           for k, v in cur.items() if k not in prev]
    return sorted(new, key=lambda x: (x["tier"], x["nom"]))


# ---------------------------------------------------------------- rapport

def md_cell(s: str, n: int = 220) -> str:
    from signaux_commun import clip
    return clip(str(s or ""), n).replace("|", "/").replace("\n", " ")


def _n(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def methode_fit() -> str:
    """Barème du fit, écrit depuis la section [cible] de la campagne (icp.cible())."""
    from icp import cible
    from signaux_commun import config
    c = cible()
    if not c["pays"]:
        zone = "zone (pas de zone imposée : 3 pour tous)"
    else:
        prio = [str(r) for r in config()["cible"].get("regions_prioritaires") or []]
        if c["cantons"]:   # langue déduite des cantons listés (localités de cette langue hors de ces cantons)
            prio += [f"localités de langue {l}" for l in sorted(c["langues"])]
        zone = "zone (" + (f"régions prioritaires {', '.join(prio)} : 3 ; reste de {', '.join(sorted(c['pays']))} : 2"
                           if c["prioritaire"] else f"{', '.join(sorted(c['pays']))} : 3")
        zone += (f" ; pays voisins {', '.join(sorted(c['voisins']))} et pays inconnu : 1" if c["voisins"]
                 else " ; pays inconnu : 1") + " ; autre pays : hors cible)"
    tmin, tmax, tlim = c["taille_min"], c["taille_max"], c["taille_limite"]
    deux = min(2.5 * tmax, tlim)
    taille = (f"taille ({_n(tmin + 1)} à {_n(tmax)} : 3 ; {_n(tmax + 1)} à {_n(deux)} : 2 ; {_n(tmin)} ou moins"
              + (f" et {_n(deux + 1)} à {_n(tlim)}" if deux < tlim else "") + f" : 1 ; plus de {_n(tlim)} : hors cible ; "
              "inconnue : 1,5)")
    regles = []
    for nom, note, _, exclue, du_profil in c["regles"]:
        if not du_profil:
            regles.append(f"{nom} {'hors cible' if exclue else _n(note)}")
    deja = {nom for nom, _, _, _, du_profil in c["regles"] if not du_profil}
    cats = [f"{k} {'hors cible' if v['exclure'] else _n(v['note'])}" for k, v in c["categories"].items() if k not in deja]
    secteur = "secteur (" + (f"règles de la campagne : {', '.join(regles)} ; " if regles else "") \
        + f"catégories : {', '.join(cats)} ; inconnu : 2)"
    return f"{zone}, {taille}, {secteur}"


def report(camp, rows, zf, lk, st, nw, rc, nouveaux=None) -> None:
    from signaux_commun import aujourdhui, clip
    t = Counter(r["tier"] for r in rows)
    zok = sum(1 for v in zf.values() if v.get("statut") == "ok")
    lok = sum(1 for v in lk.values() if v.get("statut") == "ok")
    sok = sum(1 for v in st.values() if v.get("statut") == "ok")
    L = [f"# Prospection {camp.nom} : tiers et signaux\n",
         f"_Généré le {aujourdhui().isoformat()} (date de référence) par `scripts/scorer.py` à partir de la liste de la "
         f"campagne ({len(rows)} entreprises après dédoublonnage)._\n",
         "## Résultat\n",
         "| Tier | Entreprises | Lecture |", "|---|---|---|",
         f"| **A** | {t['A']} | à contacter en priorité : bon fit ICP **et** au moins un signal (moment ou tech) |",
         f"| **B** | {t['B']} | à travailler : bon fit sans signal, ou fit moyen avec signal |",
         f"| **C** | {t['C']} | fit moyen sans signal : nurturing |",
         f"| **D** | {t['D']} | fit faible (zone, taille ou secteur limites) : opportuniste |",
         f"| Hors cible | {t['Hors cible']} | exclues de la liste, grands groupes, hors zone, secteur hors cible, radiées... |",
         "",
         f"- Fenêtre d'opportunité (signal fort récent, tiers A/B) : **{sum(1 for r in rows if r['fenetre_opportunite'])}**",
         f"- Entreprises montées d'au moins un tier grâce aux signaux : **{sum(1 for r in rows if r['monte_de'])}**",
         f"- Couverture : registre {zok} entreprises, LinkedIn {lok} pages, sites {sok}, actualités {len(nw)}, "
         f"recherche agents {len(rc)}.\n"]
    sel = [r for r in rows if r["tier"] == "A"]
    L += [f"## Tier A ({len(sel)}) : à contacter maintenant\n",
          "« fenêtre » = fenêtre d'opportunité (signal fort récent) ; ↑ = tiers gagnés grâce aux signaux.\n"]
    for r in sel:
        flag = " · fenêtre" if r["fenetre_opportunite"] else ""
        up = f" (↑{r['monte_de']} depuis {r['tier_fit']})" if r["monte_de"] else ""
        L.append(f"### {r['rang']}. {r['nom']}{flag}")
        L.append(f"_{r['pays']} {r['canton']} · {r['secteur']} · {r['taille']} · fit {r['fit_icp']} / moment "
                 f"{r['timing']} / tech {r['tech']}{up}_\n")
        L.append(f"- **Pourquoi maintenant** : {r['pourquoi_maintenant'] or '-'}")
        for lab, col in (("Direction", "signaux_direction"), ("Financement", "signaux_financement"),
                         ("Rachat / fusion", "signaux_rachat_fusion"), ("Croissance / projets", "signaux_croissance_projets"),
                         ("Tech", "signaux_tech"), ("Négatif", "signaux_negatifs")):
            if r[col]:
                L.append(f"- **{lab}** : {clip(r[col], 420)}")
        if r["dirigeants"]:
            L.append(f"- **Dirigeants** : {r['dirigeants']}")
        if r["angle"] or r["persona_cible"]:
            L.append(f"- **Angle** : {r['angle'] or '-'} · **Persona** : {r['persona_cible'] or '-'}")
        L.append("")
    sel = [r for r in rows if r["tier"] == "B"]
    L += [f"## Tier B ({len(sel)}) : à travailler\n",
          "| # | Entreprise | Pays | Fit | Moment | Tech | Pourquoi maintenant |", "|---|---|---|---|---|---|---|"]
    for r in sel:
        flag = " · fenêtre" if r["fenetre_opportunite"] else ""
        up = f" ↑{r['monte_de']}" if r["monte_de"] else ""
        L.append(f"| {r['rang']} | **{md_cell(r['nom'], 50)}**{flag}{up} | {r['pays']} {r['canton']} | {r['fit_icp']} | "
                 f"{r['timing']} | {r['tech']} | {md_cell(r['pourquoi_maintenant'])} |")
    L.append("")
    if nouveaux:
        L += [f"## Nouveaux signaux depuis le {nouveaux[0]['depuis']} ({len(nouveaux)})\n",
              "| Tier | Entreprise | Signal | Source |", "|---|---|---|---|"]
        for n in nouveaux:
            L.append(f"| {n['tier']} | {md_cell(n['nom'], 45)} | {md_cell(phrase(n), 160)} | {n['source']} |")
        L.append("")
    neg = [r for r in rows if "radiée" in r["motifs_exclusion"] or r["_neg_fiable"]]
    if neg:
        L += ["## Alertes : entreprises radiées, en liquidation ou en difficulté\n",
              "| Entreprise | Pays | Détail |", "|---|---|---|"]
        for r in neg:
            L.append(f"| {md_cell(r['nom'], 50)} | {r['pays']} | {md_cell(r['motifs_exclusion'] or r['signaux_negatifs'], 200)} |")
        L.append("")
    # entreprises qui vendent ce que nous vendons, ou intégrateurs : concurrents ou partenaires, pas des prospects
    autres = [r for r in rows if re.search(r"concurren|partenaire potentiel|piste partenaire|intégrateur|"
                                           r"vend(?:ent)? (?:lui-même |elle-même |déjà )?(?:la même|le même|ce que nous)",
                                           r["motifs_exclusion"], re.I) or r.get("_concurrent")]
    if autres:
        L += ["## À noter : concurrents ou partenaires potentiels\n",
              "Repérés par la recherche : ils vendent ce que nous vendons ou intègrent des solutions proches, donc pas "
              "des prospects classiques.\n"]
        for r in autres:
            raison = r["motifs_exclusion"].split("selon recherche : ")[-1] if "selon recherche" in r["motifs_exclusion"] \
                else "vend ce que nous vendons (plafonné en B)"
            L.append(f"- **{r['nom']}** ({r['pays'] or 'pays inconnu'}, tier {r['tier']}) : {clip(raison, 220)}")
        L.append("")
    corr = [r for r in rows if r["linkedin_corrige"]]
    if corr:
        L += [f"## Pages LinkedIn corrigées ({len(corr)})\n",
              "L'URL de la liste ne répondait pas ; nouvelle page validée par le site web ou le nom.\n"]
        L += [f"- {r['nom']} : {r['linkedin']}" for r in corr]
        L.append("")
    L += ["## Méthode\n",
          f"**Tier de base = fit ICP** (0-9) : {methode_fit()}. Fit ≥ 7,5 : B ; ≥ 6 : C ; sinon D.\n",
          f"**Les signaux font monter** : +1 tier si « moment » ≥ {SEUIL_MOMENT} ou « tech » ≥ {SEUIL_TECH} ; +2 si les "
          "deux (ou moment ≥ 7). Moment négatif : -1 tier. Le A exige un fit ≥ 6. Les entreprises qui vendent ce que "
          "nous vendons (concurrents) plafonnent en B.\n",
          "**Moment** (-10 à 10) : poids selon la nature × fiabilité (registre > contre-vérifié > agent > détection auto) "
          "× récence (≤ 12 mois ×1 ; 12-24 ×0,65 ; 24-36 ×0,3). Ex. nouveau directeur général au registre = 6, "
          "levée vérifiée = 6, rachat = 5, augmentation de capital = 4 (+1 si au moins un million), projet ERP = 4.\n",
          "**Tech / early adopter** (0-10) : maturité du site (CMS moderne, marketing automation, chat / assistant IA, "
          "portail client), mentions IA / industrie 4.0 (site + posts), activité LinkedIn, recrutement tech, "
          "appréciation de l'agent (fort / moyen).\n",
          "**Sources** : registre du commerce (quand la campagne l'interroge : nominations, radiations, capital, "
          "fusions, liquidations), page LinkedIn publique (taille, secteur, posts datés), site web (stack, pages "
          "actualités et carrières, sitemap), actualités DuckDuckGo, puis agents de recherche et contre-vérification "
          "adverse.\n",
          "Relancer : voir README.md du skill, étape 5.\n"]
    camp.fichier("rapport-signaux.md").write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- main

def main() -> None:
    from commun import argument_campagne
    ap = argparse.ArgumentParser(description="Étape 5 : scores et tiers A, B, C, D (prospection-signaux.csv, "
                                             "rapport-signaux.md, donnees/signaux/signaux.json).")
    argument_campagne(ap)
    a = ap.parse_args()

    from commun import ecrire_csv
    from icp import adjust_with_agent, qualify
    from persona import Persona
    from signaux_commun import donnees, load_entities, load_json, ouvrir, save_json
    camp = ouvrir(a.campagne)
    _persona["P"] = Persona(camp.config)
    data = donnees()
    ents = load_entities()
    zf, lk, st, nw = (load_json(data / f"{n}.json", {}) or {} for n in ("zefix", "linkedin", "site", "news"))
    rc = load_json(data / "recherche.json", {}) or {}
    rows, all_sig = [], {}
    for e in ents:
        z, li, site, news, rech = zf.get(e["id"], {}), lk.get(e["id"], {}), st.get(e["id"], {}), nw.get(e["id"], {}), rc.get(e["id"], {})
        if rech and REGISTRE_HOMONYME.search(" ".join([rech.get("pourquoi_maintenant", ""), rech.get("raison_hors_icp", ""),
                                                        rech.get("activite", ""), rech.get("nom_verifie", "")])):
            z = {}                                     # l'agent a établi que la fiche du registre est un homonyme
        q = adjust_with_agent(qualify(e, z, li, site), rech)
        sig = collect_signals(e, z, li if li.get("statut") == "ok" else {}, site, news, rech)
        timing, top = timing_score(sig)
        tech, tpreuves, concurrent = tech_score(site if site.get("statut") == "ok" else {},
                                                li if li.get("statut") == "ok" else {}, rech)
        tier, tier_fit, gain = tier_of(q["fit"], timing, tech, q["motifs_exclusion"], concurrent)
        score = round(2 * q["fit"] + max(timing, -10) + 0.8 * tech, 1)
        by_fam = {}
        for s in sorted(sig, key=lambda s: -(s.get("poids") or 0)):
            if (s.get("poids") or 0) != 0:
                by_fam.setdefault(s["famille"], []).append(s)
        all_sig[e["id"]] = sorted(sig, key=lambda s: s.get("date") or "", reverse=True)
        li_url = (li.get("url") if li.get("statut") == "ok" else "") or e.get("linkedin", "")
        rows.append({
            "tier": tier, "fenetre_opportunite": "oui" if (tier in ("A", "B") and timing >= 5) else "",
            "score": score, "tier_fit": tier_fit, "monte_de": gain if gain > 0 else "",
            "fit_icp": q["fit"], "timing": timing, "tech": tech,
            "nom": e["nom"], "id": e["id"],
            "pays": q["pays"], "canton": q["canton"], "secteur": (rech.get("categorie") or q["secteur"]),
            "taille": (rech.get("effectif_estime") or q["taille"]), "activite": rech.get("activite") or e.get("activite", ""),
            "site": e.get("site", ""), "linkedin": li_url,
            "linkedin_corrige": "oui" if li.get("correction") else "",
            "pourquoi_maintenant": pourquoi(top, tpreuves, rech),
            "signaux_direction": " | ".join(fmt_sig(s) for s in by_fam.get("direction", [])[:3]),
            "signaux_financement": " | ".join(fmt_sig(s) for s in by_fam.get("financement", [])[:2]),
            "signaux_rachat_fusion": " | ".join(fmt_sig(s) for s in by_fam.get("ma", [])[:2]),
            "signaux_croissance_projets": " | ".join(fmt_sig(s) for s in (by_fam.get("croissance", []) + by_fam.get("projet", []))[:3]),
            "signaux_tech": " | ".join(tpreuves[:5]),
            "signaux_negatifs": " | ".join(fmt_sig(s) for s in by_fam.get("negatif", [])[:2]),
            "_concurrent": concurrent,
            "_neg_fiable": any(s["confiance"] != "auto" and s["sous_type"] in GRAVES for s in by_fam.get("negatif", [])),
            "dirigeants": dirigeants(z if z.get("statut") == "ok" else {}, rech),
            "persona_cible": persona_cible(rech), "angle": rech.get("angle", ""),
            "motifs_exclusion": " ; ".join(q["motifs_exclusion"]),
            "recherche_agent": "oui" if rech else "",
            "sources": " | ".join(dict.fromkeys(s["url"] for s in (top[:4] + by_fam.get("negatif", [])[:1]) if s.get("url"))),
            "registre": f"{z.get('nom')} ({z.get('uid')}, {z.get('etat')})" if z.get("statut") == "ok" else "",
        })
    order = {"A": 0, "B": 1, "C": 2, "D": 3, "Hors cible": 4}
    rows.sort(key=lambda r: (order[r["tier"]], -r["score"]))
    for i, r in enumerate(rows, 1):
        r["rang"] = i
    out = camp.fichier("prospection-signaux.csv")
    ecrire_csv(out, COLONNES, rows)
    save_json(data / "signaux.json", all_sig)
    nouveaux = veille(rows, all_sig)
    report(camp, rows, zf, lk, st, nw, rc, nouveaux)
    t = Counter(r["tier"] for r in rows)
    print(f"{out.name} : {len(rows)} entreprises | A {t['A']} | B {t['B']} | C {t['C']} | D {t['D']} | hors cible {t['Hors cible']} | "
          f"fenêtre d'opportunité {sum(1 for r in rows if r['fenetre_opportunite'])} | montées grâce aux signaux "
          f"{sum(1 for r in rows if r['monte_de'])}")
    if nouveaux:
        print(f"veille : {len(nouveaux)} nouveaux signaux depuis le {nouveaux[0]['depuis']}")
    print(f"-> {out}, {camp.fichier('rapport-signaux.md')}, {data / 'signaux.json'}")


if __name__ == "__main__":
    main()
