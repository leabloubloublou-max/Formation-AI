"""Qualification ICP d'une entreprise (zone, taille, secteur, état) à partir de toutes les sources.

La cible vient de la section [cible] de campagne.toml (config/campagne.exemple.toml) :
  - zone : regions_prioritaires note 3 (codes de canton pour la Suisse ; vide = tout le pays), reste de
    cible.pays note 2, pays_voisins note 1, pays inconnu 1, tout autre pays 0 (exclusion « hors zone »).
    Sans cible.pays, la zone n'est pas un critère (note 3 pour tous).
    Suisse : quand les régions prioritaires couvrent tous les cantons d'une langue (GE, VD, NE, JU, FR et VS pour
    le français), les localités de cette langue des autres cantons comptent aussi (Jura bernois francophone) ;
    on peut aussi écrire « romande », « alémanique » ou « italienne » (les cantons de cette langue, plus ses
    localités des autres cantons).
  - taille : de taille_min à taille_max note 3, jusqu'à 2,5 fois taille_max note 2, petites (jusqu'à taille_min)
    et jusqu'à taille_limite note 1, au-delà 0 (exclusion « grand groupe »), inconnue 1,5.
  - secteur : règles [[cible.secteurs]] d'abord ({nom, note 0-3, motifs, exclure}), puis le profil fourni
    (profil_secteurs = « industrie » : règles SECTEURS ci-dessous ; « aucun » : pas de règle) ; secteur inconnu 2.
Notes 0-3 par axe ; fit = somme (0-9). Les motifs d'exclusion classent « hors cible » quoi qu'il arrive.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from commun import LANGUES_PAYS, charger_localites, code_pays, region as region_localite
from entites import drapeaux_exclure
from signaux_commun import config, domain, langue_principale, norm

CANTONS = {"AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE", "NW", "OW", "SG", "SH",
           "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH"}
REGION_CANTON = {
    "neuchâtel": "NE", "neuchatel": "NE", "vaud": "VD", "genève": "GE", "geneve": "GE", "geneva": "GE", "jura": "JU",
    "fribourg": "FR", "freiburg": "FR", "valais": "VS", "wallis": "VS", "berne": "BE", "bern": "BE", "zurich": "ZH",
    "zürich": "ZH", "zug": "ZG", "zoug": "ZG", "luzern": "LU", "lucerne": "LU", "basel": "BS", "bâle": "BS",
    "basel-stadt": "BS", "bâle-ville": "BS", "aargau": "AG", "argovie": "AG", "solothurn": "SO", "soleure": "SO",
    "st. gallen": "SG", "saint-gall": "SG", "ticino": "TI", "tessin": "TI", "thurgau": "TG", "thurgovie": "TG",
    "schwyz": "SZ", "graubünden": "GR", "grisons": "GR", "obwalden": "OW", "obwald": "OW", "nidwalden": "NW",
    "nidwald": "NW", "schaffhausen": "SH", "schaffhouse": "SH", "glarus": "GL", "glaris": "GL", "uri": "UR",
    "appenzell": "AR", "appenzell ausserrhoden": "AR", "appenzell innerrhoden": "AI", "basel-landschaft": "BL",
    "bâle-campagne": "BL",
}
REGION_CANTON_N = {norm(k): v for k, v in REGION_CANTON.items()}
LANGUE_REGION = {"romande": "fr", "suisse romande": "fr", "alemanique": "de", "suisse alemanique": "de",
                 "italienne": "it", "suisse italienne": "it"}
LANGUE_LOCALITE = {"romande": "fr", "alémanique": "de", "italienne": "it", "plurilingue": "multiple"}
NOTE_INCONNU = 2       # secteur inconnu ou sans règle

# ---------------------------------------------------------------- profil de secteurs « industrie »

SECTEURS = [  # (catégorie, note, regex) : premier match gagnant, testé dans cet ordre
    ("institution", 0, r"haute école|université|university|\bEPFL\b|\bHES\b|HEIG|centre de recherche|research (?:center|institute)|"
                       r"forschungsinstitut|école polytechnique|enseignement supérieur|higher education"),
    ("services non industriels", 0,
     r"transport(?:s|eur)? (?:routier|international|et logistique|de marchandises)|\btransports?\b(?= ?(?:sa|ag|\||,|$))|"
     r"\blogistique\b(?! industrielle)|\blogistics\b|logistik|services publics|utilities|services aux collectivités|"
     r"services pour les énergies|fourniture d.(?:énergie|électricité|eau|gaz)|distribution d.énergie|gestionnaire de réseau|"
     r"spedition|messagerie|express (?:delivery|courier)|fret|douane|transitaire|"
     r"nettoyage(?! (?:électronique|de précision|industriel|par ultrasons|des circuits))|reinigung(?!s(?:anlagen|technik|maschinen))|intérim|"
     r"placement (?:fixe|de personnel)|recrutement|staffing|personaldienst|travail temporaire|télécom|telecommunication|"
     r"fournisseur d.accès|téléphonie|emplois\b|agence de placement|fiduciaire|révision des comptes|audit financier|"
     r"conseil fiscal|treuhand|steuerberatung|garage|automobiles? (?:vw|audi)|concession automobile|paysag|menuiserie|"
     r"serrurerie|quincaillerie|caisse de compensation|compagnie d.assurances?|banque\b|agence immobilière|gérance immobilière|"
     r"restaura|hôtel|souvenir|\bcommune\b|\bville du\b|administration publique|services industriels|"
     r"distribution d.(?:électricité|eau|gaz)|multi-?fluides|énergie et (?:eau|multimédia)|palexpo|centre d.exposition|"
     r"événementiel|hygiène et|vêtements de travail|fournitures de bureau|office supplies|matériel de bureau|grossiste pharma|"
     r"leasing|location de (?:vêtements|véhicules|voitures|tapis)|private equity|holding / private|société d.investissement|"
     r"imprimerie|courrier|transport et|Transport routier|Services de nettoyage|Services financiers|Assurances|Immobilier|"
     r"Hôtellerie|Administration publique|Services d.installations|Ressources humaines|Comptabilité"),
    ("distribution", 1,
     r"distribut|négoce|grossiste|broker|courtier|reseller|revendeur|marketplace|boutique en ligne|e-?shop|sourcing|"
     r"handel|vertrieb|surstock|excess inventory|obsolète|apporteur de solutions|commerce de gros|wholesale|"
     r"vente en gros|import-export"),
    ("services techniques", 1, r"formation|certification ISO|inspection|calibration|étalonnage|conseil en|consulting|"
                               r"cabinet|laboratoire d.essais"),
    ("fabricant", 3,
     r"fabric|fabricant|manufactur|production|produit|usinage|décolletage|microtechni|horlog|watch|montre|médic|medical|"
     r"medtech|dentaire|dental|chirurg|surgery|instrument|machine|robot|automation|automatisation|mécatroni|électroni|"
     r"electronic|capteur|sensor|moteur|motor|entraînement|antrieb|laser|optique|optic|PVD|galvan|traitement de surface|"
     r"câbl|kabel|cable|connect|bobin|inductance|transformat|batter|circuits? imprimés?|PCB|EMS|sous-traitance|"
     r"mécanique|precision|précision|tôlerie|découpe|jet d.eau|injection|plastique|caoutchouc|gummi|joints|ressorts|"
     r"outillage|outils|métrologie|mesure|measurement|test|simulat|solaire|solar|onduleur|convertisseur|alimentation|"
     r"drone|vélo|biotech|bio-?impression|bioprint|ingénierie tissulaire|générateur|ventilat|écran|display|LCD|"
     r"semi-?conducteur|semiconductor|soudage|welding|brasage|plasma|palettes|emballage|enclosure|boîtier|clavier|HMI|"
     r"scie|diamant|fil|gaz de laboratoire|matériaux|composants? (?:mécaniques|électroniques)? ?sur mesure|"
     r"bureau d.études|engineering|ingénierie|développement (?:électronique|produit|de systèmes)|prototyp|"
     r"machines? d.assemblage|chronométrage|timing|synchronisation|oscillat|horloges|contrôle d.accès|"
     r"suivi en temps réel|monitoring|cartographie|aéronautique|aerospace|défense|spatial|ferroviaire|railway"),
    ("logiciel / IT", 1, r"logiciel|software|développement d.applications|software house|services IT|informatique|"
                         r"SaaS|web|digital agency|freelance|PDM|ERP"),
]
# rattrape un fabricant classé en distribution ou en services
FABRICANT_FORT = re.compile(r"fabric|fabricant|manufactur|production|usinage|décolletage|développe|conception|"
                            r"bureau d.études|sous-traitance|EMS", re.I)
# catégories rendues par les agents de recherche (workflow, puis recherche.json) et leur note
CAT_NOTE = {"fabricant": 3, "sous-traitant": 3, "distribution": 1, "logiciel": 1, "services": 0, "institution": 0, "autre": 2}

PROFILS = {
    "industrie": {"regles": SECTEURS, "categories": CAT_NOTE,
                  "fort": (FABRICANT_FORT, {"distribution", "services techniques", "services non industriels"},
                           ("fabricant", 3))},
    "aucun": {"regles": [], "categories": {}, "fort": None},
}

# ---------------------------------------------------------------- configuration de la cible

_cache: dict = {}


def _nombre(c: dict, cle: str) -> float:
    try:
        return float(c.get(cle))
    except (TypeError, ValueError):
        raise SystemExit(f"campagne.toml, [cible] {cle} : nombre attendu (lu : {c.get(cle)!r}).")


def _localites() -> dict:
    if "localites" not in _cache:
        _cache["localites"] = charger_localites()
    return _cache["localites"]


def _langues_cantons() -> tuple[dict, dict]:
    """(canton -> langue majoritaire, canton -> langues présentes) d'après le répertoire des localités."""
    if "langues" not in _cache:
        par = defaultdict(Counter)
        for canton, langue in _localites().values():
            if canton and langue in ("fr", "de", "it"):
                par[canton][langue] += 1
        _cache["langues"] = ({c: n.most_common(1)[0][0] for c, n in par.items()}, {c: set(n) for c, n in par.items()})
    return _cache["langues"]


def _preparer(c: dict) -> dict:
    """Lit et vérifie la section [cible] une fois par campagne."""
    pays = {code_pays(str(p)) or str(p).upper() for p in c.get("pays") or []} - {""}
    voisins = {code_pays(str(p)) or str(p).upper() for p in c.get("pays_voisins") or []} - {""} - pays
    cantons, regions, langues = set(), set(), set()
    for r in c.get("regions_prioritaires") or []:
        r = str(r).strip()
        if norm(r) in LANGUE_REGION:
            langues.add(LANGUE_REGION[norm(r)])
        elif r.upper() in CANTONS:
            cantons.add(r.upper())
        elif norm(r) in REGION_CANTON_N:
            cantons.add(REGION_CANTON_N[norm(r)])
        elif norm(r):
            regions.add(norm(r))
    if cantons or langues:
        majoritaire = _langues_cantons()[0]
        # langues dont tous les cantons sont prioritaires (ex. français : GE, VD, NE, JU, FR, VS)
        for lg in ("fr", "de", "it"):
            siens = {k for k, v in majoritaire.items() if v == lg}
            if cantons and siens and siens <= cantons:
                langues.add(lg)
        # « romande » vaut aussi les cantons de langue française, comme si on les avait listés : un canton connu
        # (liste, registre, région LinkedIn) sans localité reconnue reste prioritaire
        cantons |= {k for k, v in majoritaire.items() if v in langues}
    tmin, tmax, tlim = _nombre(c, "taille_min"), _nombre(c, "taille_max"), _nombre(c, "taille_limite")
    if not 0 <= tmin < tmax <= tlim:
        raise SystemExit(f"campagne.toml, [cible] : il faut 0 <= taille_min < taille_max <= taille_limite "
                         f"(lu : {tmin:g}, {tmax:g}, {tlim:g}).")
    profil = str(c.get("profil_secteurs") or "industrie").strip().lower()
    if profil not in PROFILS:
        raise SystemExit(f"campagne.toml, [cible] profil_secteurs = {profil!r} : valeurs possibles "
                         f"{', '.join(PROFILS)}.")
    regles, categories = [], {}
    for i, s in enumerate(c.get("secteurs") or [], 1):
        nom = str(s.get("nom") or "").strip()
        motifs = s.get("motifs") or []
        if isinstance(motifs, str):
            motifs = [motifs]
        try:
            note = float(s.get("note"))
        except (TypeError, ValueError):
            note = -1
        if not nom or not motifs or not 0 <= note <= 3:
            raise SystemExit(f"campagne.toml, [[cible.secteurs]] n° {i} : il faut nom, note (0 à 3) et motifs "
                             f"(liste d'expressions), lu : {s}.")
        note = int(note) if note == int(note) else note
        try:
            rx = re.compile("|".join(f"(?:{m})" for m in motifs), re.I)
        except re.error as err:
            raise SystemExit(f"campagne.toml, [[cible.secteurs]] « {nom} » : motif invalide ({err}).")
        regles.append((nom, note, rx, bool(s.get("exclure")), False))
        categories.setdefault(nom, {"note": note, "exclure": bool(s.get("exclure"))})
    p = PROFILS[profil]
    for cat, note, rx in p["regles"]:
        regles.append((cat, note, re.compile(rx, re.I), note == 0, True))
    for cat, note in p["categories"].items():
        categories.setdefault(cat, {"note": note, "exclure": note == 0})
    categories.setdefault("autre", {"note": NOTE_INCONNU, "exclure": False})
    return {"pays": pays, "voisins": voisins, "cantons": cantons, "regions": regions, "langues": langues,
            "prioritaire": bool(cantons or regions or langues), "taille_min": tmin, "taille_max": tmax,
            "taille_limite": tlim, "regles": regles, "fort": p["fort"], "categories": categories}


def cible() -> dict:
    """Section [cible] préparée (pays, régions, tailles, règles de secteur) de la campagne ouverte."""
    cfg = config()
    if _cache.get("cfg") is not cfg:
        _cache["cfg"], _cache["cible"] = cfg, _preparer(cfg["cible"])
    return _cache["cible"]


def categories() -> dict[str, dict]:
    """Catégories de secteur actives {nom: {note, exclure}} : règles de la campagne d'abord, puis celles du profil
    (catégories demandées aux agents de recherche et lues par adjust_with_agent), « autre » en dernier."""
    return cible()["categories"]


# ---------------------------------------------------------------- zone

def _localite(ville: str) -> tuple[str, str]:
    """(canton, langue) d'une localité suisse : fr, de, it, multiple ; vides si inconnue."""
    canton, reg = region_localite(ville or "", "CH", _localites())
    return canton, LANGUE_LOCALITE.get(reg, "")


def langue_suisse(villes: list[str], canton: str = "") -> str:
    """Langue (fr, de, it) d'une entreprise suisse : celle de la première localité connue (siège, ville) ; pour une
    localité plurilingue (Biel/Bienne), celle de l'appelant (appels.langues) si elle est parlée dans son canton ;
    sinon la langue majoritaire du canton ; vide si inconnue."""
    for ville in villes:
        ct, lg = _localite(ville) if ville else ("", "")
        if lg in ("fr", "de", "it"):
            return lg
        if ct:
            if lg == "multiple" and langue_principale() in _langues_cantons()[1].get(ct, set()):
                return langue_principale()
            canton = canton or ct
            break
    return _langues_cantons()[0].get(canton, "")


def canton_of(z: dict, li: dict, e: dict | None = None) -> str:
    """Canton suisse : registre, sinon liste, sinon région LinkedIn, sinon localité (siège, ville)."""
    z, li, e = z or {}, li or {}, e or {}
    if z.get("statut") in ("ok", "ambigu") and z.get("canton"):
        return z["canton"]
    if (e.get("canton") or "").strip().upper() in CANTONS:
        return e["canton"].strip().upper()
    reg = norm(li.get("region", ""))
    if reg.upper() in CANTONS:
        return reg.upper()
    if reg in REGION_CANTON_N:
        return REGION_CANTON_N[reg]
    for ville in (z.get("siege"), e.get("ville"), li.get("ville")):
        canton = _localite(ville)[0] if ville else ""
        if canton:
            return canton
    return ""


def _pays_du_domaine(site: str, c: dict) -> str:
    """Pays d'après le domaine national du site (.ch -> CH), pour les pays connus seulement."""
    d = domain(site or "")
    tld = d.rsplit(".", 1)[-1] if "." in d else ""
    code = {"uk": "GB"}.get(tld, tld.upper())
    return code if len(code) == 2 and code in (set(LANGUES_PAYS) | c["pays"] | c["voisins"]) else ""


def _prioritaire(pays: str, canton: str, e: dict, z: dict, li: dict, c: dict) -> bool:
    if pays == "CH":
        if canton in c["cantons"]:
            return True
        if c["langues"]:
            # localité d'une langue prioritaire hors des cantons listés (Jura bernois francophone, Bienne)
            for ville in (z.get("siege"), e.get("ville"), li.get("ville")):
                ct, lg = _localite(ville) if ville else ("", "")
                if not ct:
                    continue
                return lg in c["langues"] or (lg == "multiple" and bool(c["langues"] & _langues_cantons()[1].get(ct, set())))
    noms = {norm(x) for x in (e.get("canton"), e.get("region"), li.get("region"), canton) if x}
    return bool(noms & c["regions"])


def zone(e: dict, z: dict, li: dict) -> tuple[int, str, str]:
    """(note 0-3, pays, canton)."""
    c, z, li = cible(), z or {}, li or {}
    pays = code_pays(e.get("pays", "")) or ("CH" if z.get("statut") == "ok" else "") or code_pays(li.get("pays", ""))
    if not pays:
        pays = _pays_du_domaine(e.get("site", ""), c)
    canton = canton_of(z, li, e) if pays == "CH" else ""
    if not c["pays"]:
        return 3, pays, canton
    if pays in c["pays"]:
        return (3 if not c["prioritaire"] or _prioritaire(pays, canton, e, z, li, c) else 2), pays, canton
    if pays in c["voisins"]:
        return 1, pays, ""
    return (0 if pays else 1), pays, ""


# ---------------------------------------------------------------- taille

def note_taille(top: float) -> float:
    """Note 0-3 d'un effectif (haut de la tranche) selon taille_min, taille_max et taille_limite."""
    c = cible()
    if top <= c["taille_min"]:
        return 1
    if top <= c["taille_max"]:
        return 3
    if top > c["taille_limite"]:
        return 0
    if top <= 2.5 * c["taille_max"]:
        return 2
    return 1


def _haut_de_tranche(txt: str) -> int | None:
    """« 51-200 employés » -> 200 ; « ~80 personnes » -> 80 ; « env. 1 200 » -> 1200 ; « 1,001-5,000 » -> 5000 ;
    None si illisible."""
    t = (txt or "").replace("\u202f", " ").replace("\xa0", " ").replace("'", "")
    t = re.sub(r"(?<=\d)[.,\u2019](?=\d{3}(?!\d))", "", t)     # séparateur de milliers : 1,200 / 10.001
    m = re.search(r"(\d[\d ]*)\s*(?:-|\u2013|à)\s*(\d[\d ]*)", t)
    if m:
        top = int(m.group(2).replace(" ", ""))
    else:
        m = re.search(r"(\d[\d ]{0,6})", t)
        if not m:
            return None
        top = int(m.group(1).replace(" ", ""))
    return top if top > 0 else None


def taille(li: dict, e: dict | None = None) -> tuple[float, str]:
    """(note 0-3, libellé). Tranche LinkedIn, sinon salariés présents sur LinkedIn, sinon taille de la liste."""
    li = li or {}
    mn, mx = li.get("taille_min"), li.get("taille_max")
    n = li.get("salaries_linkedin")
    if mn is None and n:
        mn = mx = n
    if mn is None:
        t = ((e or {}).get("taille") or "").strip()
        top = _haut_de_tranche(t)
        return (1.5, "inconnue") if top is None else (note_taille(top), f"{t} (liste)")
    lab = li.get("taille") or (f"~{n} sur LinkedIn" if n else f"{mn}-{mx if mx is not None else ''}")
    top = mx if mx is not None else mn * 10
    return note_taille(top), lab


def size_from_text(txt: str) -> float | None:
    """« 51-200 employés », « ~80 personnes », « env. 1 200 » -> note taille (None si illisible)."""
    top = _haut_de_tranche(txt)
    return None if top is None else note_taille(top)


# ---------------------------------------------------------------- secteur

PURPOSE_CUT = re.compile(r"\.\s+(?:La société peut|Die Gesellschaft kann|La società può|Elle peut|Sie kann|The company may)|"
                         r"\s+(?:La société peut|Die Gesellschaft kann|La società può)", re.I)


def purpose_core(but: str) -> str:
    """Première phrase du but social, sans les clauses-types (« activité mobilière ou immobilière »...)."""
    return PURPOSE_CUT.split(but or "", maxsplit=1)[0][:300]


def _secteur(e: dict, z: dict, li: dict, site: dict) -> tuple[float, str, bool]:
    """(note, catégorie, exclue) : sources prises dans l'ordre de fiabilité, la première qui parle gagne ;
    pour chaque source, règles de la campagne d'abord, puis celles du profil."""
    li, site, z = li or {}, site or {}, z or {}
    c = cible()
    sources = [e.get("activite", ""), li.get("secteur", ""), e.get("secteur", ""), purpose_core(z.get("but", "")),
               " ".join([li.get("specialites", ""), li.get("description", "")[:400]]), site.get("description", "")]
    sources = [x for x in sources if x and x.strip()]
    if not sources:
        return NOTE_INCONNU, "inconnu", False
    for source in sources:
        for cat, note, rx, exclue, du_profil in c["regles"]:
            if rx.search(source):
                fort = c["fort"]
                if du_profil and fort and cat in fort[1] and fort[0].search(source):
                    return fort[2][1], fort[2][0], False
                return note, cat, exclue
    return NOTE_INCONNU, "autre", False


def secteur(e: dict, z: dict, li: dict, site: dict) -> tuple[float, str]:
    """(note 0-3, catégorie)."""
    n, cat, _ = _secteur(e, z, li, site)
    return n, cat


# ---------------------------------------------------------------- qualification

def qualify(e: dict, z: dict | None, li: dict | None, site: dict | None) -> dict:
    z, li, site = z or {}, (li if (li or {}).get("statut") == "ok" else {}), (site if (site or {}).get("statut") == "ok" else {})
    zn, pays, canton = zone(e, z, li)
    tn, tl = taille(li, e)
    sn, sc, sx = _secteur(e, z, li, site)
    motifs = []
    exclure = (e.get("exclure") or "").strip()
    flags = set(e.get("flags", [])) | drapeaux_exclure(exclure)
    if exclure and not drapeaux_exclure(exclure):
        motifs.append(f"exclue : {exclure}")
    if "particulier" in flags:
        motifs.append("particulier / entreprise individuelle")
    if "administration" in flags:
        motifs.append("administration")
    if "non_identifie" in flags:
        motifs.append("entité non identifiée")
    etat = z.get("etat") if z.get("statut") == "ok" else ""
    if etat in ("GELOESCHT", "IN_AUFLOESUNG") or "fermee_ou_liquidation" in flags:
        motifs.append("radiée / en liquidation" + (f" ({z.get('radiation')})" if z.get("radiation") else ""))
    if zn == 0:
        motifs.append(f"hors zone ({pays})")
    if sx:
        motifs.append(f"secteur hors cible ({sc})")
    if tn == 0:
        motifs.append(f"grand groupe ({tl})")
    return {"pays": pays, "canton": canton, "note_zone": zn, "taille": tl, "note_taille": tn,
            "secteur": sc, "note_secteur": sn, "fit": round(zn + tn + sn, 1), "motifs_exclusion": motifs,
            "etat_registre": etat}


def adjust_with_agent(q: dict, rech: dict) -> dict:
    """La recherche agent (catégorie, effectif, verdict ICP) prime sur les heuristiques par mots-clés."""
    if not rech:
        return q
    q = dict(q, motifs_exclusion=list(q["motifs_exclusion"]))
    cats = categories()
    cat = (rech.get("categorie") or "").strip()
    cle = next((k for k in cats if k.lower() == cat.lower()), None) if cat else None
    if cle:
        q["secteur"], q["note_secteur"] = cle, cats[cle]["note"]
        if cats[cle]["exclure"] and not any(m.startswith("secteur") for m in q["motifs_exclusion"]):
            q["motifs_exclusion"].append(f"secteur hors cible ({cle})")
        elif not cats[cle]["exclure"]:
            q["motifs_exclusion"] = [m for m in q["motifs_exclusion"] if not m.startswith("secteur")]
    if q["taille"] == "inconnue" and rech.get("effectif_estime"):
        n = size_from_text(rech["effectif_estime"])
        if n is not None:
            q["taille"], q["note_taille"] = rech["effectif_estime"], n
            if n == 0:
                q["motifs_exclusion"].append(f"grand groupe ({rech['effectif_estime']})")
    if rech.get("dans_icp") is False:
        q["motifs_exclusion"].append("hors ICP selon recherche : " + (rech.get("raison_hors_icp") or "non précisé"))
    q["fit"] = round(q["note_zone"] + q["note_taille"] + q["note_secteur"], 1)
    return q
