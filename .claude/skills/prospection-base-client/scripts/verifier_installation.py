"""Contrôle de l'installation du skill et, avec --campagne, d'un dossier de campagne. Sans réseau.

Installation :
- Python 3.11 ou plus, lancé depuis le .venv du projet ;
- paquets de requirements.txt importables, aux versions demandées : requests, beautifulsoup4 (bs4), lxml, ddgs,
  openpyxl ;
- fichiers du skill : répertoire des localités suisses (donnees/localites-suisse.csv, © swisstopo), configuration
  d'exemple, workflows, consignes ; fichiers générés (__pycache__, .DS_Store) signalés, à laisser hors du zip ;
- clé Apollo présente (variable APOLLO_API_KEY ou fichier .env, voir commun.cle_apollo), JAMAIS affichée ; .env
  ignoré par git ; pas de .env dans le dossier du skill (il partirait avec le zip).
Campagne (--campagne <dossier>) :
- dossier présent, hors du dossier du skill, inscriptible ;
- campagne.toml lisible ; sections et clés connues ; types (liste, nombre, vrai ou faux) ; clés à remplir ;
  valeurs d'exemple de config/campagne.exemple.toml encore présentes (« Exemple SA », « Prénom Nom »...) ;
  [cible] et [persona] lus par icp.py et persona.py, comme le feront les scripts ;
- fichiers facultatifs : persona.md, exclure.csv, corrections.csv, apollo/comptes-manuels.csv, arbitrages.csv,
  noms-ambigus.csv ;
- où en est la campagne, d'après les fichiers présents.
Affiche une ligne par contrôle (✓ bon, ✗ à corriger, ! à revoir, sans bloquer) puis la prochaine action.
Code de sortie : 0 sans ✗, 1 sinon. Ne crée ni ne modifie aucun fichier (un fichier temporaire teste l'écriture).

Usage (depuis la racine du projet, celle qui contient .venv et .env) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py [--campagne campagnes/<nom>]
"""
from __future__ import annotations

import argparse
import importlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

ICI = Path(__file__).resolve().parent
SKILL = ICI.parent

# paquet pip -> module importé (versions demandées : requirements.txt)
PAQUETS = [("requests", "requests"), ("beautifulsoup4", "bs4"), ("lxml", "lxml"), ("ddgs", "ddgs"),
           ("openpyxl", "openpyxl")]
WORKFLOWS = ["decouverte-entreprises.js", "verification.js", "verification-passe2.js", "signaux-recherche.js"]
CONSIGNES = ["cartes-appel.md", "fichier-appel-redaction.md", "fichier-appel-sources.md", "phrases-signal.md"]
GENERES = ("__pycache__", ".DS_Store")   # jamais à livrer avec le skill (le bytecode porte le chemin de la machine)
TIRETS = ("\u2014", "\u2013")   # cadratin et demi-cadratin : jamais dans un texte dit ou écrit à un prospect

# Clés à remplir et étape qui en a besoin la première. Avant l'étape 6, une clé vide est à corriger ; à partir de
# l'étape 6, elle est seulement signalée (à remplir avant cette étape).
A_REMPLIR = [
    ("offre", "societe", 2), ("offre", "description", 2), ("cible", "description", 2),
    ("apollo", "liste_comptes", 6), ("apollo", "liste_contacts", 6),
    ("offre", "argument_cle", 9), ("offre", "appelant", 9), ("offre", "presentation_appelant", 9),
    ("offre", "question_ouverte", 9), ("offre", "cta", 9),
]
# Clés d'exemple qui peuvent rester telles quelles dans une vraie campagne (le nom n'est signalé que s'il diffère
# du nom du dossier).
EXEMPLE_PERMIS = {("campagne", "nom"), ("cible", "pays")}


# ---------------------------------------------------------------- affichage

def _marques() -> tuple[str, str, str, str]:
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✓✗→".encode(enc)
        return "✓", "✗", "!", "→"
    except (UnicodeEncodeError, LookupError):
        return "OK", "XX", "!!", "->"


OK, KO, AV, FL = _marques()


class Rapport:
    """Lignes de contrôle, affichées au fil de l'eau, et première action à faire."""

    def __init__(self):
        self.ko, self.av = [], []

    @staticmethod
    def section(titre: str) -> None:
        print(f"\n{titre}")

    @staticmethod
    def bon(texte: str) -> None:
        print(f"  {OK} {texte}")

    def erreur(self, texte: str, action: str = "") -> None:
        print(f"  {KO} {texte}")
        if action:
            print(f"      {FL} {action}")
        self.ko.append(action or texte)

    def alerte(self, texte: str, action: str = "") -> None:
        print(f"  {AV} {texte}")
        if action:
            print(f"      {FL} {action}")
        self.av.append(action or texte)

    @staticmethod
    def info(texte: str) -> None:
        print(f"    {texte}")


def pl(n: int, mot: str) -> str:
    """« 1 site », « 2 sites »."""
    return f"{n} {mot}" + ("s" if n > 1 and not mot.endswith(("s", "x")) else "")


def rel(p: Path) -> str:
    """Chemin lisible, à recopier dans une commande : relatif au dossier courant quand c'est possible, entre
    guillemets s'il contient une espace."""
    try:
        s = str(p.resolve().relative_to(Path.cwd().resolve())) or "."
    except ValueError:
        s = str(p)
    return f'"{s}"' if " " in s else s


# ---------------------------------------------------------------- installation

def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4]) or (0,)


def comparer(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    return (a > b) - (a < b)


def exigences() -> dict[str, list[tuple[str, tuple[int, ...]]]]:
    """requirements.txt -> {paquet: [(opérateur, version)]}."""
    f = SKILL / "requirements.txt"
    out: dict[str, list] = {}
    if not f.exists():
        return out
    for ligne in f.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*(.*)", ligne)
        if not m:
            continue
        specs = []
        for s in m[2].split(","):
            sm = re.match(r"\s*(>=|<=|==|!=|<|>|~=)\s*([0-9][0-9.]*)", s)
            if sm:
                specs.append((sm[1], version_tuple(sm[2])))
        out[m[1].lower()] = specs
    return out


def respecte(version: str, specs: list) -> bool:
    v = version_tuple(version)
    for op, ref in specs:
        c = comparer(v, ref)
        ok = {">=": c >= 0, "<=": c <= 0, "==": c == 0, "!=": c != 0, "<": c < 0, ">": c > 0,
              "~=": c >= 0 and v[:max(1, len(ref) - 1)] == ref[:max(1, len(ref) - 1)]}[op]
        if not ok:
            return False
    return True


def texte_specs(specs: list) -> str:
    return ",".join(f"{op}{'.'.join(map(str, v))}" for op, v in specs)


def controler_python(r: Rapport) -> tuple[bool, bool]:
    """(Python assez récent, interpréteur du .venv du dossier courant)."""
    v = sys.version_info
    if v < (3, 11):
        r.erreur(f"Python {v.major}.{v.minor} ({sys.executable}) : 3.11 ou plus est requis",
                 "recréez le .venv avec Python 3.11 ou plus, puis réinstallez les paquets (README.md, « Installation »)")
        return False, False
    r.bon(f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")
    venv = Path.cwd() / ".venv"
    if venv.is_dir():
        if Path(sys.prefix).resolve() == venv.resolve():
            r.bon("interpréteur du .venv du projet")
            return True, True
        r.alerte(f"lancé avec {sys.executable}, pas avec celui de {rel(venv)}",
                 "lancez les scripts avec .venv/bin/python, depuis la racine du projet")
    else:
        r.alerte(f"aucun dossier .venv dans le dossier courant ({Path.cwd()})",
                 "lancez la commande depuis la racine du projet, ou créez le .venv (README.md, « Installation »)")
    return True, False


def controler_paquets(r: Rapport, du_venv: bool) -> None:
    from importlib import metadata
    specs = exigences()
    installer = f".venv/bin/pip install -r {rel(SKILL / 'requirements.txt')}"
    if not du_venv and (Path.cwd() / ".venv").is_dir():
        installer = "relancez avec .venv/bin/python (ce Python n'est pas celui du projet), sinon " + installer
    for paquet, module in PAQUETS:
        try:
            mod = importlib.import_module(module)
            if module == "ddgs":   # ce que commun.recherche_web utilise
                getattr(mod, "DDGS")
                getattr(importlib.import_module("ddgs.exceptions"), "DDGSException")
        except Exception as e:  # noqa: BLE001 (paquet absent ou cassé)
            r.erreur(f"{paquet} introuvable pour {sys.executable} ({type(e).__name__})", installer)
            continue
        try:
            version = metadata.version(paquet)
        except metadata.PackageNotFoundError:
            version = str(getattr(mod, "__version__", "") or "")
        attendu = specs.get(paquet, [])
        if version and attendu and not respecte(version, attendu):
            r.erreur(f"{paquet} {version} : version attendue {texte_specs(attendu)}", installer)
        else:
            r.bon(f"{paquet} {version or '(version inconnue)'}")


def controler_fichiers_skill(r: Rapport) -> None:
    loc = SKILL / "donnees" / "localites-suisse.csv"
    if not loc.exists():
        r.erreur(f"répertoire des localités suisses absent ({rel(loc)}) : canton et région resteraient vides",
                 "recopiez le dossier donnees/ du skill depuis le zip")
    else:
        with loc.open(encoding="utf-8-sig") as f:
            entete = f.readline()
            n = sum(1 for _ in f)
        if all(c in entete for c in ("Ortschaftsname", "Kantonskürzel", "Sprache")):
            r.bon(f"répertoire des localités suisses : {n} localités (© swisstopo)")
        else:
            r.erreur(f"{rel(loc)} : en-tête inattendu (Ortschaftsname, Kantonskürzel, Sprache attendus)",
                     "recopiez le dossier donnees/ du skill depuis le zip")
    manquent = [f"config/{n}" for n in ("campagne.exemple.toml",) if not (SKILL / "config" / n).exists()]
    manquent += [f"workflows/{n}" for n in WORKFLOWS if not (SKILL / "workflows" / n).exists()]
    manquent += [f"consignes/{n}" for n in CONSIGNES if not (SKILL / "consignes" / n).exists()]
    if manquent:
        r.erreur(f"fichiers du skill absents : {', '.join(manquent)}", "recopiez le dossier complet du skill")
    else:
        r.bon(f"fichiers du skill : configuration d'exemple, {len(WORKFLOWS)} workflows, {len(CONSIGNES)} consignes")
    # fichiers générés (bytecode Python, Finder) : sans effet ici, mais à laisser hors du zip si le skill est partagé
    generes = sorted({str(p.relative_to(SKILL)) for p in SKILL.rglob("*") if p.name in GENERES})
    if generes:
        r.info(f"fichiers générés dans le dossier du skill ({', '.join(generes[:4])}"
               f"{', ...' if len(generes) > 4 else ''}) : à laisser hors du zip si vous partagez le skill ; depuis "
               f"{rel(SKILL.parent)} : zip -r {SKILL.name}.zip {SKILL.name} -x '*/__pycache__/*' '*.DS_Store' "
               "'*/.env'")
    if SKILL.parent != Path.cwd().resolve() / ".claude" / "skills":
        r.info(f"skill installé hors du projet courant ({SKILL}) : adaptez le chemin des commandes, et passez "
               f"skill = {SKILL} dans les args du workflow de découverte (étape 2)")


def git_ignore(chemin: Path) -> bool | None:
    """True : ignoré par git ; False : suivi possible ; None : pas de dépôt git ou git absent."""
    try:
        p = subprocess.run(["git", "check-ignore", "-q", chemin.name], cwd=chemin.parent,
                           capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return {0: True, 1: False}.get(p.returncode)


def controler_cle(r: Rapport) -> None:
    from commun import a_une_cle_apollo
    env = Path.cwd() / ".env"
    if a_une_cle_apollo():
        source = "variable d'environnement APOLLO_API_KEY" if os.environ.get("APOLLO_API_KEY", "").strip() \
            else "fichier .env"
        r.bon(f"clé Apollo présente ({source} ; jamais affichée)")
    else:
        detail = (f" ({rel(env)} existe, mais APOLLO_API_KEY y est vide)" if env.exists() else "")
        r.alerte(f"clé Apollo absente{detail} : nécessaire à partir de l'étape 6 (recherche et écriture dans Apollo)",
                 f"cp {rel(SKILL / 'exemple.env')} .env, puis collez la clé après APOLLO_API_KEY= "
                 "(README.md, « Clé API Apollo »)")
    if env.exists() and git_ignore(env) is False:
        r.alerte(".env n'est pas ignoré par git : la clé pourrait partir dans un commit",
                 "ajoutez la ligne .env au fichier .gitignore du projet")
    if (SKILL / ".env").exists():
        r.alerte(f"un fichier .env est dans le dossier du skill ({rel(SKILL / '.env')}) : il partirait avec le zip",
                 "déplacez-le à la racine du projet")


# ---------------------------------------------------------------- campagne

def lignes_exemple() -> tuple[dict, set]:
    """Valeurs de config/campagne.exemple.toml et clés marquées « À COMPLÉTER »."""
    import tomllib
    f = SKILL / "config" / "campagne.exemple.toml"
    if not f.exists():
        return {}, set()
    with f.open("rb") as h:
        valeurs = tomllib.load(h)
    marquees, section = set(), ""
    for ligne in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[([A-Za-z0-9_.]+)\]", ligne)
        if m:
            section = m[1]
            continue
        m = re.match(r"\s*([A-Za-z0-9_]+)\s*=", ligne)
        if m and "À COMPLÉTER" in ligne:
            marquees.add((section, m[1]))
    return valeurs, marquees


def vide(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def controler_types(r: Rapport, brut: dict, cfg: dict) -> bool:
    """Sections et clés inconnues (fautes de frappe), types attendus. False si une erreur bloque la suite."""
    from commun import DEFAUTS
    bon = True
    inconnues = []
    for s, v in brut.items():
        if s not in DEFAUTS:
            inconnues.append(f"[{s}]")
        elif isinstance(v, dict):
            inconnues += [f"{s}.{k}" for k in v if k not in DEFAUTS[s]]
    if inconnues:
        r.alerte(f"clés inconnues, ignorées par les scripts : {', '.join(inconnues)}",
                 "vérifiez l'orthographe (modèle : config/campagne.exemple.toml)")
    for s, defauts in DEFAUTS.items():
        if not isinstance(cfg.get(s), dict):
            r.erreur(f"[{s}] doit être une section (lu : {cfg.get(s)!r})", "voir config/campagne.exemple.toml")
            bon = False
            continue
        for k, d in defauts.items():
            v = cfg[s].get(k)
            if isinstance(d, bool):
                ok = isinstance(v, bool)
                attendu = "true ou false, sans guillemets"
            elif isinstance(d, int):
                ok = isinstance(v, (int, float)) and not isinstance(v, bool)
                attendu = "un nombre, sans guillemets"
            elif isinstance(d, list):
                ok = isinstance(v, list) or ((s, k) == ("persona", "relais") and isinstance(v, str))
                attendu = 'une liste entre crochets, par exemple ["CH"]'
            elif isinstance(d, dict):
                ok = isinstance(v, dict)
                attendu = "une section"
            else:
                ok = isinstance(v, str) or ((s, k) == ("persona", "entree") and isinstance(v, list))
                attendu = "un texte entre guillemets"
            if not ok:
                r.erreur(f"{s}.{k} : {attendu} (lu : {v!r})", f"corrigez {s}.{k} dans campagne.toml")
                bon = False
    return bon


def controler_valeurs(r: Rapport, cfg: dict, dossier: Path) -> None:
    from datetime import date
    from commun import DEFAUTS, code_pays
    exemple, marquees = lignes_exemple()
    # valeurs d'exemple encore présentes
    restes, a_confirmer = [], []
    for s, k in sorted(marquees):
        if s in exemple and k in exemple[s] and cfg.get(s, {}).get(k) == exemple[s][k] and not vide(exemple[s][k]):
            if (s, k) == ("campagne", "nom"):
                if dossier.name != cfg[s][k]:
                    a_confirmer.append(f"{s}.{k}")
            elif (s, k) not in EXEMPLE_PERMIS:
                restes.append(f"{s}.{k}")
    if restes:
        r.erreur(f"valeurs d'exemple encore présentes : {', '.join(restes)}",
                 "remplacez chaque valeur marquée « À COMPLÉTER » dans campagne.toml (README.md, « Fichiers à compléter »)")
    if a_confirmer:
        r.alerte(f"nom d'exemple : {', '.join(a_confirmer)}", "donnez le nom de votre campagne (titres des rapports)")
    # les autres valeurs propres à l'exemple (ni vides, ni nombres, ni égales aux valeurs par défaut)
    autres = [f"{s}.{k}" for s, sec in exemple.items() if isinstance(sec, dict) for k, v in sec.items()
              if (s, k) not in marquees and not vide(v) and not isinstance(v, (bool, int, float))
              and v != DEFAUTS.get(s, {}).get(k) and cfg.get(s, {}).get(k) == v]
    if autres:
        r.alerte(f"identiques à l'exemple (logiciel de maintenance en Suisse romande) : {', '.join(autres)}",
                 "vérifiez qu'elles conviennent à votre campagne")

    # clés à remplir
    for s, k, etape in A_REMPLIR:
        if vide(cfg[s].get(k)):
            if etape < 6:
                r.erreur(f"{s}.{k} est vide (lue dès l'étape {etape})", f"remplissez {s}.{k} dans campagne.toml")
            else:
                r.alerte(f"{s}.{k} est vide", f"à remplir avant l'étape {etape}")

    # campagne
    d = str(cfg["campagne"].get("date_reference") or "").strip()
    if d:
        try:
            date.fromisoformat(d)
            r.bon(f"date de référence figée : {d}")
        except ValueError:
            r.erreur(f"campagne.date_reference = {d!r} : format AAAA-MM-JJ attendu", "corrigez-la, ou laissez \"\"")

    # offre
    o = cfg["offre"]
    preuves = o.get("preuves") or []
    mal = [p for p in preuves if not (isinstance(p, dict) and str(p.get("cas") or "").strip()
                                      and str(p.get("phrase") or "").strip())]
    if mal:
        r.erreur(f"offre.preuves : {pl(len(mal), 'preuve')} sans cas ou sans phrase",
                 'chaque preuve : { cas = "...", phrase = "..." }, un résultat réel, jamais inventé')
    elif not preuves:
        r.alerte("offre.preuves est vide : les scripts d'appel ne citeront ni client ni chiffre",
                 "ajoutez vos résultats clients réels, si vous en avez (avant l'étape 9)")
    textes = {f"offre.{k}": o.get(k) for k in ("description", "argument_cle", "presentation_appelant",
                                               "question_ouverte", "cta", "signature_email")}
    textes.update({f"offre.preuves[{i}]": p.get("phrase") for i, p in enumerate(preuves, 1) if isinstance(p, dict)})
    tirets = [k for k, v in textes.items() if isinstance(v, str) and any(t in v for t in TIRETS)]
    if tirets:
        r.erreur(f"tiret cadratin ou demi-cadratin dans {', '.join(tirets)} (textes dits aux prospects)",
                 "remplacez-le par une virgule, deux-points ou un point")

    # cible : lue comme les scripts la liront (icp.py)
    c = cfg["cible"]
    for cle in ("pays", "pays_voisins"):
        faux = [str(p) for p in (c.get(cle) or []) if not code_pays(str(p))]
        if faux:
            r.erreur(f"cible.{cle} : pays inconnus {', '.join(faux)}", 'codes ISO à deux lettres, par exemple ["CH", "FR"]')
    faux = [str(p) for p in (cfg["apollo"].get("pays_contacts") or []) if not code_pays(str(p))]
    if faux:
        r.erreur(f"apollo.pays_contacts : pays inconnus {', '.join(faux)}", "codes ISO à deux lettres")
    if not c.get("pays"):
        r.alerte("cible.pays est vide : la zone ne comptera pas dans le fit", 'par exemple pays = ["CH"]')
    try:
        import icp
        p = icp._preparer(c)
    except SystemExit as e:
        r.erreur(str(e), "corrigez la section [cible] de campagne.toml")
    except Exception as e:  # noqa: BLE001 (contrôle de confort : ne pas masquer le reste)
        r.alerte(f"[cible] non contrôlée ({type(e).__name__} : {e})")
    else:
        zone = ", ".join(sorted(p["pays"])) or "toute zone"
        prio = sorted(p["cantons"]) + sorted(p["regions"]) + [f"langue {x}" for x in sorted(p["langues"])]
        regles = len(c.get("secteurs") or [])
        r.bon(f"cible : {zone}" + (f", prioritaires {', '.join(prio)}" if prio else "")
              + f" ; taille {p['taille_min']:g} à {p['taille_max']:g} (au-delà de {p['taille_limite']:g} : exclue)"
              + f" ; secteurs : profil {str(c.get('profil_secteurs') or 'industrie').lower()}"
              + (f" + {pl(regles, 'règle')}" if regles else ""))
        if p["regions"] and p["pays"] == {"CH"}:
            r.alerte(f"cible.regions_prioritaires : {', '.join(sorted(p['regions']))} n'est ni un canton ni "
                     "« romande », « alémanique » ou « italienne »", "écrivez des codes de canton : GE, VD, NE...")

    # persona : lu comme les scripts le liront (persona.py)
    try:
        from persona import Persona
        P = Persona(cfg)
    except SystemExit as e:
        r.erreur(str(e), "corrigez la section [persona] de campagne.toml")
    except Exception as e:  # noqa: BLE001
        r.alerte(f"[persona] non contrôlé ({type(e).__name__} : {e})")
    else:
        ajoutees = sorted(P.perso)
        r.bon(f"persona : entrée {P.entree} ; relais {', '.join(P.relais) or 'aucun'}"
              + (f" ; familles ajoutées : {', '.join(ajoutees)}" if ajoutees else ""))

    # signaux, apollo, appels
    s = cfg["signaux"]
    if not (isinstance(s.get("fenetre_mois"), int) and not isinstance(s.get("fenetre_mois"), bool)
            and s["fenetre_mois"] >= 1):
        r.erreur(f"signaux.fenetre_mois = {s.get('fenetre_mois')!r} : nombre entier de mois, 1 ou plus",
                 "par exemple fenetre_mois = 24")
    if not s.get("logiciels"):
        r.alerte("signaux.logiciels est vide : pas de recherche des logiciels des prospects (étape 5, facultative)")
    if cfg["apollo"].get("mobiles") is True:
        r.alerte("apollo.mobiles = true : 8 crédits Apollo par numéro de mobile", "à confirmer avant l'étape 6")
    langues = cfg["appels"].get("langues") or []
    if not langues:
        r.alerte("appels.langues est vide : l'ordre d'appel ne tiendra pas compte de la langue", 'par exemple ["fr"]')
    elif any(not re.fullmatch(r"[a-z]{2}", str(x).strip().lower()) for x in langues):
        r.erreur(f"appels.langues = {langues!r} : codes de langue à deux lettres attendus", 'par exemple ["fr", "de"]')


def entete(chemin: Path) -> set[str]:
    """En-têtes d'un CSV, même sans ligne (virgule ou point-virgule)."""
    premiere = chemin.read_text(encoding="utf-8-sig").splitlines()[:1]
    if not premiere:
        return set()
    sep = ";" if premiere[0].count(";") > premiere[0].count(",") else ","
    return {x.strip().strip('"').lower() for x in premiere[0].split(sep)}


def controler_facultatifs(r: Rapport, dossier: Path) -> None:
    from commun import charger_noms, lire_csv
    persona = dossier / "persona.md"
    if persona.exists() and persona.read_text(encoding="utf-8", errors="ignore").strip():
        r.bon("persona.md présent")
    else:
        r.alerte("persona.md absent : le persona du décideur n'est pas encore validé",
                 "étape 1 : faites valider le persona avec Claude, puis enregistrez la réponse dans persona.md")
    exclure = dossier / "exclure.csv"
    if exclure.exists():
        try:
            noms, doms = charger_noms([str(exclure)])
        except Exception as e:  # noqa: BLE001
            r.erreur(f"exclure.csv illisible ({type(e).__name__} : {e})", "CSV en UTF-8, colonnes nom et site")
        else:
            if noms or doms:
                r.bon(f"exclure.csv : {pl(len(noms), 'nom')} et {pl(len(doms), 'site')} à retirer de la prospection")
            else:
                r.erreur("exclure.csv : aucune colonne nom ni site reconnue (ou fichier vide)", "colonnes nom, site")
    else:
        r.alerte("exclure.csv absent : aucun client ni partenaire actuel ne sera retiré",
                 "créez exclure.csv (colonnes nom, site) si vous avez des clients ou des partenaires")
    attendus = [  # fichier facultatif, colonnes obligatoires (une au moins par groupe), rôle
        (dossier / "corrections.csv", [{"nom"}, {"site", "linkedin"}], "corrections de site et de LinkedIn (étape 3)"),
        (dossier / "apollo" / "comptes-manuels.csv", [{"entreprise", "nom"}, {"compte_apollo", "compte"}],
         "rapprochements manuels avec les comptes Apollo (étape 6)"),
        (dossier / "arbitrages.csv", [{"nom"}, {"champ"}], "décisions manuelles de vérification (étape 4)"),
        (dossier / "noms-ambigus.csv", [{"nom"}], "noms à chercher avec la ville (étape 5)"),
    ]
    for f, groupes, role in attendus:
        if not f.exists():
            continue
        try:
            cols, n = entete(f), len(lire_csv(f))
        except Exception as e:  # noqa: BLE001
            r.erreur(f"{rel(f)} illisible ({type(e).__name__})", "CSV en UTF-8, virgule ou point-virgule")
            continue
        manque = [" ou ".join(sorted(g)) for g in groupes if not g & cols]
        if manque:
            r.erreur(f"{rel(f)} : colonne absente ({', '.join(manque)})", f"en-têtes attendus pour les {role}")
        else:
            r.bon(f"{rel(f)} : {pl(n, 'ligne')}, {role}")


def compter(chemin: Path) -> tuple[int, int]:
    """(lignes retenues, retenues sans site) d'une liste d'entreprises."""
    from commun import lire_csv
    lignes = [l for l in lire_csv(chemin) if not (l.get("exclure") or "").strip()]
    return len(lignes), sum(1 for l in lignes if not (l.get("site") or "").strip())


def avancement(r: Rapport, dossier: Path) -> str:
    """Fichiers présents et étape suivante."""
    f = lambda *p: dossier.joinpath(*p).exists()
    vus = []
    for nom in ("entreprises.csv", "entreprises-enrichi.csv", "entreprises-verifie.csv", "prospection-signaux.csv",
                "base-abc.csv", "apollo/contacts-importes.csv", "apollo/contacts-crees.csv", "apollo/reinjection.csv",
                "appels/ordre-appel.csv", "appels/plan-sequence.csv", "appels/scripts-appel.md",
                "appels/fichier-appel.csv"):
        if f(nom):
            vus.append(nom)
    r.info("fichiers de la chaîne : " + (", ".join(vus) if vus else "aucun pour l'instant"))
    if not f("persona.md"):
        return "étape 1 : cible et persona du décideur (persona.md, sections [cible] et [persona])"
    if not f("entreprises.csv"):
        return "étape 2 : trouver les entreprises (découverte web par agents, ou liste existante, export Apollo compris)"
    n, sans_site = compter(dossier / "entreprises.csv")
    r.info(f"entreprises.csv : {pl(n, 'entreprise')} {'retenue' if n < 2 else 'retenues'}, dont {sans_site} sans site")
    if not f("prospection-signaux.csv"):
        if not f("entreprises-enrichi.csv") and not f("entreprises-verifie.csv") and sans_site:
            return f"étape 3 : trouver le site et la page LinkedIn ({pl(sans_site, 'entreprise')} sans site)"
        if not f("entreprises-verifie.csv"):
            return "étape 4 (facultative, multi-agents) : vérifier la liste ; ou directement l'étape 5 (signaux)"
        return "étape 5 : signaux et priorisation (tiers A à D, score A, B, C)"
    if not (f("apollo/contacts-crees.csv") or f("apollo/contacts-importes.csv")):
        return "étape 6 : contacts Apollo (liste de comptes, recherche gratuite, puis enrichissement sur accord)"
    if not f("apollo/reinjection.csv"):
        return "étape 7 : score A, B, C et réinjection dans Apollo (aperçu d'abord)"
    if not (f("appels/ordre-appel.csv") and f("appels/plan-sequence.csv")):
        return "étape 8 : ordre d'appel et plan de séquence"
    if not (f("appels/scripts-appel.md") or f("appels/fichier-appel.csv")):
        return "étape 9 : scripts d'appel et fichier d'appel (rédaction sur demande)"
    return "chaîne complète : veille avant chaque vague (étape 5), puis étapes 7 à 9 de nouveau"


def controler_campagne(r: Rapport, arg: str) -> str | None:
    """Contrôles de la campagne ; rend l'étape suivante, ou None si la campagne n'est pas lisible."""
    import tomllib
    from commun import CONFIG_EXEMPLE, charger_config
    dossier = Path(arg).expanduser().resolve()
    r.section(f"Campagne ({rel(dossier)})")
    if not dossier.is_dir():
        r.erreur(f"dossier de campagne introuvable : {dossier}",
                 f"mkdir -p {arg} && cp {rel(CONFIG_EXEMPLE)} {arg}/campagne.toml, puis complétez campagne.toml")
        return None
    if dossier == SKILL or SKILL in dossier.parents:
        r.erreur("le dossier de campagne est dans le dossier du skill : il partirait avec le zip",
                 "placez-le à la racine du projet, par exemple campagnes/<nom>")
    try:
        with tempfile.NamedTemporaryFile(dir=dossier, prefix=".verification-", delete=True):
            pass
        r.bon("dossier présent et inscriptible")
    except OSError as e:
        r.erreur(f"dossier non inscriptible ({e.strerror})", "vérifiez les droits du dossier")
    fichier = dossier / "campagne.toml"
    if not fichier.exists():
        r.erreur("campagne.toml absent", f"cp {rel(CONFIG_EXEMPLE)} {arg}/campagne.toml, puis complétez-le")
        return None
    try:
        with fichier.open("rb") as h:
            brut = tomllib.load(h)
        cfg = charger_config(fichier)
    except (tomllib.TOMLDecodeError, SystemExit) as e:
        r.erreur(f"campagne.toml illisible : {e}", "corrigez la syntaxe : guillemets, crochets, virgules")
        return None
    r.bon(f"campagne.toml lisible (campagne « {cfg['campagne']['nom'] or dossier.name} »)")
    if controler_types(r, brut, cfg):
        controler_valeurs(r, cfg, dossier)
    controler_facultatifs(r, dossier)
    r.section("Avancement")
    return avancement(r, dossier)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Contrôle de l'installation du skill et d'une campagne (sans réseau ; la clé Apollo n'est "
                    "jamais affichée).")
    ap.add_argument("--campagne", help="dossier de la campagne à contrôler aussi (contient campagne.toml), "
                                       "par exemple campagnes/ma-campagne")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    r = Rapport()
    r.section(f"Installation du skill ({rel(SKILL)})")
    recent, du_venv = controler_python(r)
    if not recent:   # tomllib et commun.py exigent Python 3.11 : inutile d'aller plus loin
        print(f"\nProchaine action : {r.ko[0]}")
        sys.exit(1)
    controler_paquets(r, du_venv)
    controler_fichiers_skill(r)
    r.section("Clé API Apollo")
    controler_cle(r)
    etape = controler_campagne(r, a.campagne) if a.campagne else None

    print(f"\nBilan : {len(r.ko)} à corriger ({KO}), {len(r.av)} à revoir ({AV}).")
    if r.ko:
        print(f"Prochaine action : {r.ko[0]}")
        if len(r.ko) > 1:
            print(f"  puis les autres lignes {KO}, et relancez ce contrôle.")
    elif not a.campagne:
        print("Prochaine action : créez le dossier de la campagne et son campagne.toml (README.md, « Démarrer une "
              f"campagne »), puis relancez :\n  .venv/bin/python {rel(Path(__file__))} --campagne campagnes/<nom>")
    elif etape:
        print(f"Prochaine action : {etape}.")
        m = re.match(r"étape (\d)", etape)
        if m:
            print(f"  Dans Claude Code : « lance l'étape {m[1]} du skill prospection-base-client »")
    sys.exit(1 if r.ko else 0)


if __name__ == "__main__":
    main()
