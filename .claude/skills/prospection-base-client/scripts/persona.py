"""Familles de rôles du persona : qui contacter dans chaque entreprise (étape 1 : persona_cible ; étape 6 : Apollo).

Une famille (direction, qualite, it, production, technique, service, ventes, finance, achats, projet) réunit :
- mots : déclencheurs pour lire le texte persona_cible (« responsable qualité », « l'IT », « SAV »...) ;
- titres : motif des intitulés de poste Apollo (français, anglais, allemand, italien) ; exclure : faux amis ;
- titres_api : intitulés envoyés à la recherche Apollo (person_titles[]) quand le vivier de l'entreprise ne suffit pas ;
- libelle : nom lisible (fichiers de revue) ; requete : mot-clé de la recherche web, par langue.
La section [persona] de campagne.toml choisit la famille d'entrée (entree) et les relais ; [persona.titres] ajoute des
intitulés à une famille fournie, ou crée une famille (par exemple maintenance = ["responsable maintenance", ...]).
Un intitulé de [persona.titres] est lu avec tolérance : chaque mot de 4 lettres ou plus vaut pour ses formes longues
(féminin, pluriel : « Leiter » reconnaît « Leiterin ») et jusqu'à deux mots de liaison (de, la, of, der, della...)
peuvent s'intercaler (« responsable maintenance » reconnaît « responsable de la maintenance »).

Le module lit aussi les intitulés (séniorité, poste junior), les mots utiles d'un nom d'entreprise et la colonne
dirigeants : outils partagés par extraire_personas.py, chercher_contacts.py, chercher_web.py et enrichir_et_creer.py.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------- familles fournies

FAMILLES: dict[str, dict] = {
    "direction": {
        "libelle": "direction",
        "mots": r"\b(ceo|directeur g[ée]n[ée]ral|direction g[ée]n[ée]rale|general manager|managing director|administrateur d[ée]l[ée]gu[ée]|patron|fondateur|g[ée]rante?s?|dirigeante?s?|gesch[äa]ftsf[üu]hrer\w*|inhaber\w*|amministratore delegato|direttore generale)\b|\bla direction\b(?!\s+(des|de|du|technique|commerciale|financi|industri|informatique|qualit|op))",
        "titres": r"\b(ceo|chief executive|managing director|general manager|directeur general|directrice generale|geschaftsfuhr\w*|geschaeftsfuehr\w*|gerant\w*|(?<!product )(?<!solution )(?<!process )(?<!service )(?<!data )(?<!system )(?<!platform )owner|inhaber\w*|co-?founder|founder|fondat\w*|grunder\w*|administrat\w* delegue\w*|delegierte\w*|amministratore delegato|direttore generale|(?<!vice )(?<!vice-)presid\w*|(?<!vice )(?<!vice-)prasident\w*|verwaltungsratsprasident\w*|chairman|managing partner|unternehmensleit\w*)\b|^(directeur|directrice|director|direktor|direttore)$",
        "titres_api": ["CEO", "Managing Director", "General Manager", "Directeur général", "Geschäftsführer", "Owner",
                       "Founder"],
        "requete": {"fr": "directeur", "de": "Geschäftsführer", "en": "CEO", "it": "amministratore delegato"},
    },
    "qualite": {
        "libelle": "qualité",
        "mots": r"qualit|\bqms\b|compliance|r[ée]glementaire|regulatory|\bqa\b|certification",
        "titres": r"quality|qualite|qualitat|qualitaet|\bqualita\b|\bqm\b|\bqms\b|\bqa\b|\bqc\b|\bra\b|regulatory|reglementaire|compliance|\biso\b",
        "titres_api": ["Quality Manager", "Head of Quality", "Responsable qualité", "Leiter Qualität",
                       "Regulatory Affairs", "QA Manager"],
        "requete": {"fr": "qualité", "de": "Qualität", "en": "quality", "it": "qualità"},
    },
    "it": {
        "libelle": "IT",
        "mots": r"\bit\b|informati|\bdsi\b|\bcio\b|syst[èe]mes? d'information|h[ée]bergement",
        "titres": r"\bit\b|\bict\b|\bikt\b|informati|information technology|information systems|\bcio\b|\bdsi\b|system\w* admin|sysadmin|network (engineer|admin\w*|security|specialist)|infrastructure|\berp\b|cyber",
        "titres_api": ["IT Manager", "Head of IT", "CIO", "Responsable informatique", "Leiter IT",
                       "System Administrator"],
        "requete": {"fr": "informatique", "de": "Informatik", "en": "IT manager", "it": "informatica"},
    },
    "production": {
        "libelle": "production / planification",
        "mots": r"production|ordonnancement|planification|op[ée]rations|\bcoo\b|m[ée]thodes|industrialisation|logistique|\batelier\b|\busine\b|\bavor\b|arbeitsvorbereitung",
        "titres": r"production|produktion|produzion|fertigung|manufactur|fabrication|operations|operationnel|\bcoo\b|chief operating|plant manager|site manager|standortleit|directeur de site|responsable de site|operational (director|manager|head)|directeur operationnel|werkleit|\busine\b|atelier|ordonnancement|planification|planning|planner|planificat|scheduler|disponent|\bavor\b|arbeitsvorbereitung|methodes|industrialis|industrial engineer|logisti|supply chain|betriebsleit|montage|assembly|\blean\b",
        "exclure": r"(sales|marketing|revenue|finance) operations|financial planning",
        "titres_api": ["Production Manager", "Head of Production", "Responsable production", "Leiter Produktion",
                       "Operations Manager", "COO", "Planning Manager"],
        "requete": {"fr": "production", "de": "Produktion", "en": "production", "it": "produzione"},
    },
    "technique": {
        "libelle": "technique / R&D",
        "mots": r"bureau d'[ée]tudes|engineering|ing[ée]nierie|r&d|recherche|d[ée]veloppement|\bcto\b|technique",
        "titres": r"r&d|r ?& ?d|\br\+d\b|research|recherche|development|developpement|entwicklung|forschung|\bf&e\b|engineering|ingenierie|bureau d.etudes|bureau technique|\bcto\b|chief technology|technical|technique|technik|technisch|technolog|konstruktion|hardware|electroni|elektroni|innovation|engineer|ingenieur|ingegner",
        "exclure": r"business development|developpement commercial|business developer|sales engineer|technico-commercial|technical sales|\bsales\b|commercial|\bvente|verkauf|vertrieb|account",
        "titres_api": ["CTO", "R&D Manager", "Head of R&D", "Engineering Manager", "Directeur technique",
                       "Leiter Entwicklung", "Technical Director"],
        "requete": {"fr": "R&D", "de": "Entwicklung", "en": "engineering", "it": "R&D"},
    },
    "service": {
        "libelle": "SAV / service",
        "mots": r"\bsav\b|support|service apr[èe]s|service client|service technique|maintenance",
        "titres": r"\bsav\b|after[- ]?sales|apres[- ]vente|customer service|service client|kundendienst|kundenservice|maintenance|instandhaltung|manutenzion|assistenza|field service|customer care|\brepair|\breparation|helpdesk|support (technique|client|engineer|manager|specialist|technician|technicien|lead|team)|(customer|technical|product|application|field) support|service (manager|technician|technicien|engineer|ingenieur|director|directeur|lead|coordinator|leiter\w*)|head of service|serviceleit\w*|servicetechnik\w*|service-techniker|service technique|technicien de service|(support|after) ?& ?service|service ?& ?support",
        "exclure": r"service client.*commercial|customer service representative",
        "titres_api": ["After Sales Manager", "Service Manager", "Customer Service Manager", "Responsable SAV",
                       "Leiter Kundendienst", "Support Manager"],
        "requete": {"fr": "SAV", "de": "Kundendienst", "en": "service", "it": "assistenza"},
    },
    "ventes": {
        "libelle": "ventes / offres",
        "mots": r"vente|commercial|chiffrage|devis|avant-vente|bid|offres|business development|key account",
        "titres": r"sales|\bvente|commercial|verkauf|vertrieb|business development|key account|\bkam\b|account manager|account executive|area manager|export|chiffrage|devis|estimat|offres|angebot|kalkulation|vendite",
        "titres_api": ["Sales Director", "Head of Sales", "Directeur commercial", "Verkaufsleiter", "Sales Manager",
                       "Key Account Manager"],
        "requete": {"fr": "commercial", "de": "Verkauf", "en": "sales", "it": "vendite"},
    },
    "finance": {
        "libelle": "finance",
        "mots": r"finance|\bcfo\b|comptab|administrati|controlling",
        "titres": r"\bcfo\b|chief financial|financ|finanz|comptab|accounting|accountant|buchhalt|controller|controlling|treasur|\bdaf\b|administrati",
        "titres_api": ["CFO", "Finance Director", "Head of Finance", "Directeur financier", "Leiter Finanzen",
                       "Controller"],
        "requete": {"fr": "finance", "de": "Finanzen", "en": "finance", "it": "finanza"},
    },
    "achats": {
        "libelle": "achats",
        "mots": r"achat|approvisionnement|procurement|supply chain",
        "titres": r"purchas|procurement|achat|acheteu|einkauf|beschaffung|buyer|approvisionnement|sourcing|supply chain|acquisti",
        "titres_api": ["Purchasing Manager", "Head of Purchasing", "Procurement Manager", "Responsable achats",
                       "Leiter Einkauf", "Buyer"],
        "requete": {"fr": "achats", "de": "Einkauf", "en": "purchasing", "it": "acquisti"},
    },
    "projet": {
        "libelle": "projet ERP / digital",
        "mots": r"\berp\b|chef de projet|business analyst|digital",
        "titres": r"\berp\b|business analyst|digitali[sz]|digital transformation|transformation digitale|chief digital|head of digital|process manager|prozessmanag|\bpmo\b|business process|business system|amelioration continue|continuous improvement|operational excellence|excellence operationnelle|(it|si|digital|process|system\w*) project manager|chef de projet (erp|it|si|informatique|digital)|projektleit\w* (erp|it|informatik)",
        "titres_api": ["ERP Manager", "ERP Project Manager", "Project Manager", "Chef de projet", "Projektleiter",
                       "Business Analyst"],
        # « ERP » comme l'original : un intitulé trouvé par ce mot passe le motif titres (« chef de projet » seul non)
        "requete": {"fr": "ERP", "de": "ERP", "en": "ERP", "it": "ERP"},
    },
}

# ---------------------------------------------------------------- lecture des intitulés

JUNIOR = r"\b(assistant\w*|assistent\w*|intern|internship|stagiaire|stage|apprenti\w*|apprentice|lernende\w*|praktikant\w*|student|etudiant\w*|trainee|junior|werkstudent\w*|alternan\w*|auszubildende\w*)\b"
SENIORITE = [
    (5, r"\b(ceo|c[a-z]o|chief|(?<!product )(?<!solution )(?<!process )(?<!service )(?<!data )(?<!system )(?<!platform )owner|co-?founder|founder|fondat\w*|inhaber\w*|grunder\w*|managing director|general manager|directeur general|directrice generale|geschaftsfuhr\w*|geschaeftsfuehr\w*|gerant\w*|presid\w*|prasident\w*|administrat\w* delegue\w*|delegierte\w*|amministratore delegato|direttore generale|managing partner)\b"),
    (4, r"\b(director|directeur|directrice|direktor|direttore|head|vp|vice|leiter\w*|leitung|chef|cheffe|responsable|responsabile|bereichsleit\w*|abteilungsleit\w*)\b"),
    (3, r"\b(manager|lead|verantwortlich\w*|coordinat\w*|koordinat\w*|supervis\w*|superviseur)\b"),
    (2, r"\b(senior|specialist|spezialist\w*|specialiste|engineer|ingenieur\w*|ingegnere|expert\w*|analyst|planner|planificat\w*|buyer|acheteu\w*|controller|technicien\w*|technician|administrat\w*|qualiticien\w*)\b"),
]
# mots qui ne distinguent pas une entreprise d'une autre (formes juridiques, pays, mots courants des raisons sociales)
MOTS_VIDES = {"sa", "ag", "gmbh", "sarl", "srl", "spa", "ltd", "inc", "co", "kg", "the", "de", "la", "le", "et", "und",
              "group", "groupe", "holding", "suisse", "schweiz", "switzerland", "swiss", "international", "s", "a", "l",
              "r", "electronic", "electronics", "elektronik", "electronique", "systems", "system", "technology",
              "technologies", "solutions", "services", "industrie", "industries", "industry", "engineering", "medical",
              "precision", "components", "member", "france", "italia", "deutschland", "germany", "europe", "company",
              "aujourd", "hui", "sagl", "sas", "llc", "corp", "corporation"}


def norm_ascii(s: str) -> str:
    """Minuscules sans accents, ponctuation gardée (lecture de persona_cible)."""
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()


def norm_texte(s: str) -> str:
    """Minuscules sans accents ni ponctuation (sauf & + /), espaces simples (intitulés et noms Apollo)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&+/ ]", " ", norm_ascii(s))).strip()


def jetons(s: str) -> set[str]:
    """Mots utiles d'un nom d'entreprise ou d'un texte (plus de 2 lettres, hors MOTS_VIDES)."""
    return {t for t in norm_texte(s).split() if len(t) > 2 and t not in MOTS_VIDES}


def seniorite(titre: str) -> int:
    """5 dirigeant, 4 directeur ou responsable, 3 manager, 2 spécialiste, 1 autre, 0 junior."""
    t = norm_texte(titre)
    if re.search(JUNIOR, t):
        return 0
    if re.search(r"\bvice[- ]?presid|\bvp\b", t):
        return 4
    for w, pat in SENIORITE:
        if re.search(pat, t):
            return w
    return 1


def dirigeants(txt: str) -> list[tuple[str, str]]:
    """Colonne dirigeants : « Prénom Nom (rôle) ; Nom, Prénom (rôle) [date] » -> [(nom, rôle)] dans l'ordre ;
    les anciens (« ancien », « ex- », « former », « ehemalig ») sont ignorés."""
    out, parts, prof, cur = [], [], 0, ""
    for ch in txt or "":  # « ; » hors parenthèses seulement
        prof += (ch == "(") - (ch == ")")
        if ch == ";" and prof <= 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    for part in parts + [cur]:
        nom = re.split(r"[(\[]", part)[0].strip(" .,:")
        m = re.search(r"\((.*)\)", part)
        if "," in nom:
            fam, pre = nom.split(",", 1)
            nom = f"{pre.strip()} {fam.strip()}"
        role = m.group(1) if m else ""
        if re.match(r"\s*(ancien|ex-|former|ehemalig)", role, re.I):
            continue
        if 2 <= len(nom.split()) <= 5 and not re.search(r"\d", nom) and nom[:1].isupper():
            out.append((nom, role))
    return out


# ---------------------------------------------------------------- persona d'une campagne

# mots de liaison qui peuvent s'intercaler dans un intitulé de la configuration (deux au plus)
LIAISONS = ["de", "du", "des", "d", "la", "le", "les", "l", "en", "of", "the", "for", "der", "die", "das", "fur", "im",
            "di", "del", "della", "dello", "dei", "degli", "delle"]
_SEP = r"[^a-z0-9&+/]+"   # séparateur de mots (minuscules seulement : le motif passe par norm_ascii)


def _motif_intitule(intitule: str, normer) -> str:
    """« responsable maintenance » -> responsable\\w* puis jusqu'à deux mots de liaison puis maintenance\\w* ; un mot de
    moins de 4 lettres (IT, CIO) reste exact."""
    mots = re.findall(r"[a-z0-9&+/]+", normer(intitule))
    utiles = [m for m in mots if m not in LIAISONS] or mots
    liaison = rf"(?:{_SEP}(?:{'|'.join(LIAISONS)})){{0,2}}{_SEP}"
    return liaison.join(re.escape(m) + (r"\w*" if len(m) >= 4 else "") for m in utiles)


def _alternative(intitules: list[str], normer) -> str:
    """Motif « un des intitulés » (mots entiers, variantes tolérées), sur le texte normalisé de la même façon."""
    vus = [m for m in (_motif_intitule(t, normer) for t in intitules) if m]
    return r"\b(?:" + "|".join(sorted(set(vus), key=len, reverse=True)) + r")\b" if vus else ""


class Persona:
    """Familles fournies, complétées par [persona.titres], et choix d'entrée et de relais de [persona]."""

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("persona") or {}
        self.familles = {k: dict(v, titres_api=list(v["titres_api"]), requete=dict(v["requete"]))
                         for k, v in FAMILLES.items()}
        self.perso: set[str] = set()   # familles créées par la configuration : prioritaires à la lecture du texte
        for fam, intitules in (cfg.get("titres") or {}).items():
            fam = str(fam).strip().lower()
            intitules = [intitules] if isinstance(intitules, str) else [str(t) for t in intitules or []]
            mots, titres = _alternative(intitules, norm_ascii), _alternative(intitules, norm_texte)
            if fam in self.familles:   # intitulés en plus pour une famille fournie
                f = self.familles[fam]
                f["titres_api"] += [t for t in intitules if t not in f["titres_api"]]
                if mots:
                    f["mots"] = f"(?:{f['mots']})|{mots}"
                if titres:
                    f["titres"] = f"(?:{f['titres']})|{titres}"
                continue
            nom = fam.replace("_", " ")
            cle = _alternative([nom], norm_ascii)
            self.familles[fam] = {
                "libelle": nom, "mots": "|".join(x for x in (mots, cle) if x),
                "titres": titres or _alternative([nom], norm_texte), "titres_api": intitules,
                "requete": {lg: nom for lg in ("fr", "de", "en", "it")}}
            self.perso.add(fam)
        entree = cfg.get("entree") or "direction"
        entree = entree if isinstance(entree, str) else (list(entree) or ["direction"])[0]
        self.entree = entree.strip().lower()
        relais = cfg.get("relais") or []
        self.relais = [r.strip().lower() for r in ([relais] if isinstance(relais, str) else relais) if r.strip()]
        inconnues = [f for f in [self.entree, *self.relais] if f not in self.familles]
        if inconnues:
            raise SystemExit(
                f"campagne.toml, [persona] : famille inconnue {', '.join(inconnues)}. Familles fournies : "
                f"{', '.join(FAMILLES)}. Pour une autre famille, ajoutez ses intitulés dans [persona.titres], "
                f"par exemple {inconnues[0]} = [\"intitulé en français\", \"intitulé en anglais\"].")
        self._mots = {k: re.compile(norm_ascii(v["mots"])) for k, v in self.familles.items()}
        self._titres = {k: re.compile(v["titres"]) for k, v in self.familles.items()}
        self._exclure = {k: re.compile(v["exclure"]) for k, v in self.familles.items() if v.get("exclure")}

    def familles_texte(self, texte: str) -> list[str]:
        """Familles citées dans un bout de persona_cible (une famille de la configuration l'emporte)."""
        t = norm_ascii(texte)
        brut = (t.strip(" .:()") or "").replace(" ", "_")
        if brut in self.familles:      # le texte est déjà un nom de famille (cibles structurées)
            return [brut]
        trouvees = [f for f, pat in self._mots.items() if pat.search(t)]
        perso = [f for f in trouvees if f in self.perso]
        return perso or trouvees

    def familles_titre(self, titre: str) -> set[str]:
        """Familles d'un intitulé de poste Apollo ou LinkedIn."""
        t = norm_texte(titre)
        return {f for f, pat in self._titres.items()
                if pat.search(t) and not (f in self._exclure and self._exclure[f].search(t))}

    def libelle(self, famille: str) -> str:
        return self.familles.get(famille, {}).get("libelle", famille)

    def famille_de_libelle(self, libelle: str) -> str | None:
        return next((k for k, v in self.familles.items() if v["libelle"] == libelle), None)

    def titres_api(self, famille: str) -> list[str]:
        return self.familles.get(famille, {}).get("titres_api", [])

    def requete(self, famille: str, langue: str) -> str:
        r = self.familles.get(famille, {}).get("requete", {})
        return r.get(langue) or r.get("en") or self.libelle(famille)
