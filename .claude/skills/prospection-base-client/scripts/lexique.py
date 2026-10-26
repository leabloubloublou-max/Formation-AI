"""Lexique de détection des signaux dans du texte libre (posts LinkedIn, actualités, pages web).

FR / DE / EN (+ quelques IT). Chaque règle = (famille, sous_type, regex). Les détections sont des
CANDIDATS : bruités par nature (homonymes, « new CEO » d'un partenaire...). Les signaux forts sont
ensuite confirmés par les agents de recherche puis contre-vérifiés.

Familles :
  direction   nouveau dirigeant, départ, succession / transmission
  financement levée de fonds, augmentation de capital, subvention / programme public
  ma          rachat, acquisition, fusion, cession
  croissance  nouveau site / usine / extension, recrutement
  projet      certification, lancement produit, ERP / projet numérique
  tech        IA, industrie 4.0 / IoT, digitalisation, automatisation / robotique, innovation / R&D
  negatif     faillite, liquidation, restructuration, licenciements

À adapter selon la campagne (en gardant les noms de famille et de sous-type, lus par scorer.py et
dossiers.py) : les programmes publics (aide_publique : Suisse et Union européenne), les certifications
(industrie, dispositifs médicaux, horlogerie) et surtout la famille tech, qui mesure l'adoption des
technologies proches de l'offre (score tech du scorer).
"""
from __future__ import annotations

import re

W = r"[A-Za-zÀ-ÖØ-öø-ÿ]"          # lettre (pour des bornes de mots robustes aux accents)
NB = rf"(?<!{W})"                  # pas de lettre avant
NA = rf"(?!{W})"                   # pas de lettre après

ROLES_TOP = (r"CEO|Chief Executive Officer|directeur général|directrice générale|DG|administrateur délégué|"
             r"managing director|general manager|Geschäftsführer(?:in)?|Vorsitzende[rn]? der Geschäftsleitung|"
             r"Leiter(?:in)? der Geschäftsleitung|Geschäftsleiter(?:in)?|président(?:e)? de la direction|"
             r"direttore generale|amministratore delegato|country manager|site manager|directeur de site|"
             r"Standortleiter(?:in)?|président(?:e)?|Präsident(?:in)?|Verwaltungsratspräsident(?:in)?|"
             r"chairman|chairwoman|chair of the board|président(?:e)? du conseil")
ROLES_EXEC = (r"COO|CFO|CTO|CIO|CDO|CMO|CSO|CPO|Chief [A-Z][a-z]+ Officer|directeur (?:technique|des opérations|"
              r"financier|industriel|de production|commercial|R&D|qualité|informatique|du numérique|de l.innovation)|"
              r"directrice (?:technique|des opérations|financière|industrielle|de production|commerciale|R&D|qualité|"
              r"informatique)|head of (?:IT|digital|operations|engineering|R&D|quality|production|innovation|data)|"
              r"Leiter(?:in)? (?:IT|Informatik|Digitalisierung|Produktion|Qualität|Entwicklung|Technik|Operations)|"
              r"responsable (?:informatique|IT|qualité|de production|digital|du numérique|innovation)")

RULES: list[tuple] = [
    # ---------------------------------------------------------------- direction
    ("direction", "nouveau_dirigeant",
     rf"{NB}(?:nouve(?:au|l|lle)|nomm[ée]e?s?|nomination|désign[ée]e?|accueill(?:ons|ir|e)|bienvenue à|"
     rf"rejoint|arrivée de|prend(?:ra)? (?:la|ses) fonctions?)\b.{{0,70}}?\b(?:{ROLES_TOP}){NA}"),
    ("direction", "nouveau_dirigeant",
     rf"\b(?:{ROLES_TOP})\b.{{0,50}}?{NB}(?:nomm[ée]e?|désign[ée]e?|entre(?:ra)? en fonction|a été nommée?){NA}"),
    ("direction", "nouveau_dirigeant",
     rf"{NB}(?:prend|reprend|reprendra|prendra) (?:la direction|les rênes|la tête|la présidence){NA}"),
    ("direction", "nouveau_dirigeant",
     rf"{NB}(?:neue[rn]?|ernannt|übernimmt|übernehmen|begrüss?en|begrüßen|willkommen|Amtsantritt)\b.{{0,70}}?\b(?:{ROLES_TOP}){NA}"),
    ("direction", "nouveau_dirigeant",
     rf"{NB}(?:new|appoint(?:s|ed|ment of)?|names?|named|welcomes?|welcoming|joins?|joined|promot(?:ed|ion)|"
     rf"takes? over as|has been elected)\b.{{0,70}}?\b(?:{ROLES_TOP}){NA}"),
    ("direction", "nouveau_dirigeant", rf"{NB}(?:takes? the helm|at the helm|new leadership){NA}"),
    ("direction", "nouveau_cadre",
     rf"{NB}(?:nouve(?:au|l|lle)|nomm[ée]e?|neue[rn]?|new|appoint(?:s|ed)|welcomes?|joins?|rejoint)\b.{{0,60}}?\b(?:{ROLES_EXEC}){NA}"),
    ("direction", "succession",
     rf"{NB}(?:succède à|succession|passation|transmission (?:de l.entreprise|familiale|à la)|relève (?:familiale|générationnelle)|"
     rf"Nachfolge(?:r|rin|regelung)?|Führungswechsel|Wechsel an der Spitze|Generationenwechsel|Stabübergabe|"
     rf"succeeds|succession plan|steps? down|stepping down|départ à la retraite|prend sa retraite|in den Ruhestand|"
     rf"retires?|retirement of){NA}"),
    # ---------------------------------------------------------------- financement
    ("financement", "levee",
     rf"{NB}(?:lev[ée]e? de fonds|lève (?:[\d.,']+\s*)?(?:millions?|mio|M\b)|tour de (?:financement|table)|"
     rf"série [ABC]{NA}|pré-?seed|seed round|round de seed|capital-risque|"
     rf"Finanzierungsrunde|sammelt (?:[\d.,']+\s*)?(?:Millionen|Mio)|Seed-Runde|Wachstumsfinanzierung|Risikokapital|"
     rf"funding round|financing round|investment round|series [ABC]{NA}|raises? (?:(?:\$|€|CHF|USD|EUR)\s?)?[\d.,]+\s*(?:m|mn|million|bn|billion|mio){NA}|"
     rf"raised (?:(?:\$|€|CHF|USD|EUR)\s?)?[\d.,]+\s*(?:m|mn|million|mio)|secures? (?:(?:\$|€|CHF|USD|EUR)\s?[\d.,]+\s*\w+ (?:in )?)?(?:funding|investment|financing)|"
     rf"venture capital|growth equity|private placement){NA}"),
    ("financement", "augmentation_capital",
     rf"{NB}(?:augmentation (?:de|du) capital|Kapitalerhöhung|capital increase|aumento di capitale){NA}"),
    ("financement", "aide_publique",          # programmes publics suisses et européens : à compléter pour un autre pays
     rf"{NB}(?:Innosuisse|EIC Accelerator|Horizon Europe|Horizon 2020|subvention|Fördergelder|Förderprojekt|"
     rf"grant (?:from|of)|Venture Kick|Venture Leaders|FIT Digital|Fondation pour l.innovation technologique|"
     rf"prêt d.amorçage|Technologiefonds|fonds de technologie){NA}"),
    # ---------------------------------------------------------------- M&A
    ("ma", "rachat",
     rf"{NB}(?:rach[eè]te|rachat|rachet[ée]e?s?|acquiert|acquis par|reprise par|repris(?:e)? par|reprend la société|"
     rf"fusion(?:ne|né)?|fusionnent|rejoint le groupe|intègre le groupe|cède|cession de|nouvel actionnaire|"
     rf"übernimmt (?:die |den |das )?(?:Firma|Gesellschaft|Mehrheit|Aktienmehrheit|Unternehmen|[A-Z][\w&.-]+ (?:GmbH|AG|SA))|"
     rf"(?:wurde|wird|ist) (?:von|durch) [^.]{{0,60}}übernommen|Übernahme (?:der|des|von) [^.]{{0,40}}(?:GmbH|AG|SA|Gruppe|"
     rf"Unternehmen|Firma|Gesellschaft)|Akquisition|akquiriert|fusioniert|verkauft an|Verkauf an|gehört neu zu|"
     rf"neuer Eigentümer|neue Eigentümer|acquires?|acquired by|ha(?:s|ve) acquired|merger|merges? with|divests?|sold to|"
     rf"vend (?:l.entreprise|la société|sa filiale|son activité|ses activités)|vendue? à|a vendu|"
     rf"takeover|buy-?out|MBO|joins? the .{{0,30}}(?:group|family)){NA}"),
    # ---------------------------------------------------------------- croissance
    ("croissance", "nouveau_site",
     rf"{NB}(?:nouvelle usine|nouveau site|nouveaux locaux|nouveau bâtiment|nouvelle halle|nouveau siège|"
     rf"agrandissement|extension (?:de (?:notre|l.usine|nos)|du site)|inaugur(?:e|é|ation|ons)|déménag(?:e|ement)|"
     rf"neuer Standort|neues Werk|neues Gebäude|Neubau|Erweiterung|Spatenstich|Einweihung|Umzug|"
     rf"new (?:facility|plant|site|headquarters|building|factory|production hall|cleanroom)|groundbreaking|"
     rf"grand opening|expands? (?:its|our) (?:production|capacity|facility)){NA}"),
    ("croissance", "recrutement",
     rf"{NB}(?:nous recrutons|on recrute|rejoignez(?:-nous| notre équipe)|offres? d.emploi|poste à pourvoir|"
     rf"we.re hiring|we are hiring|join our team|wir suchen|Stellenangebot|offene Stellen|Verstärkung gesucht|"
     rf"#hiring|#recrutement|#jobs|#emploi|#stellenangebot){NA}"),
    # ---------------------------------------------------------------- projet
    ("projet", "certification",
     rf"{NB}(?:ISO\s?13485|ISO\s?9001|ISO\s?14001|ISO\s?27001|ISO\s?45001|EN\s?9100|AS\s?9100|IATF\s?16949|"
     rf"certifi(?:é|ée|cation|ed|ziert|zierung)){NA}"),
    ("projet", "certification", r"(?<![A-Za-z])(?:RJC|MDR|IVDR|FDA)(?![A-Za-z])", True),
    ("projet", "lancement_produit",
     rf"{NB}(?:lancement|lance (?:son|sa|ses|un|une)|nouveau produit|nouvelle gamme|launch(?:es|ed)?|"
     rf"new product|unveil(?:s|ed)?|neues Produkt|lanciert|Markteinführung|Produktneuheit){NA}"),
    ("projet", "erp_numerique",
     rf"{NB}(?:nouvel ERP|nouveau ERP|migration (?:ERP|SAP|vers)|S/4\s?HANA|SAP Business One|ProConcept|"
     rf"Microsoft Dynamics|Odoo|proALPHA|abas ERP|ERP-Einführung|ERP-Umstellung|ERP implementation|"
     rf"go-?live){NA}"),
    ("projet", "erp_numerique", r"(?<![A-Za-z])(?:ERP|MES|PLM|PDM|SAP|CRM)(?![A-Za-z])", True),
    # ---------------------------------------------------------------- tech (mots-clés liés à l'offre, à adapter)
    ("tech", "ia",
     rf"{NB}(?:intelligence artificielle|IA générative|künstliche[rn]? Intelligenz|artificial intelligence|"
     rf"machine learning|apprentissage automatique|deep learning|réseaux? de neurones|neural networks?|"
     rf"ChatGPT|Copilot|generative AI|GenAI|IA embarquée|edge AI|computer vision|"
     rf"#AI|#IA|#KI|#ArtificialIntelligence|#MachineLearning){NA}"),
    ("tech", "ia", r"(?<![A-Za-zÀ-ÿ])(?:IA|AI|KI|LLM|LLMs|GPT(?:-?\d)?)(?![A-Za-zÀ-ÿ])", True),
    ("tech", "industrie40",
     rf"{NB}(?:industrie 4\.0|industry 4\.0|smart factory|usine (?:intelligente|connectée|du futur)|"
     rf"internet des objets|internet of things|digital twin|jumeau numérique|digitaler Zwilling|"
     rf"maintenance prédictive|predictive maintenance|vorausschauende Wartung|#industry40|#industrie40){NA}"),
    ("tech", "industrie40", r"(?<![A-Za-z])(?:IoT|IIoT|MES)(?![A-Za-z])", True),
    ("tech", "digital",
     rf"{NB}(?:digitalisation|digitalization|Digitalisierung|transformation (?:digitale|numérique)|"
     rf"digital transformation|numérisation|dématérialisation|cloud|cybersécurité|cybersecurity|"
     rf"Cybersicherheit|data-driven|données en temps réel|real-time data){NA}"),
    ("tech", "automatisation",
     rf"{NB}(?:automatisation|automation|Automatisierung|robotique|robotics|Robotik|cobots?|robots?|"
     rf"vision industrielle|machine vision|Bildverarbeitung){NA}"),
    ("tech", "innovation",
     rf"{NB}(?:innovation|innovant|innovative|R&D|recherche et développement|Forschung und Entwicklung|"
     rf"brevets?|patents?|Patente?|spin-?off|start-?up|scale-?up|prix de l.innovation|innovation award|"
     rf"Swiss Technology Award|Innovationspreis|accélérateur|accelerator){NA}"),
    # ---------------------------------------------------------------- négatif
    ("negatif", "difficultes",
     rf"{NB}(?:faillite|Konkurs|insolvab|Insolvenz|insolvency|bankrupt(?:cy)?|en liquidation|in Liquidation|"
     rf"sursis concordataire|Nachlassstundung|licenciements?|licencie|Stellenabbau|Entlassungen?|layoffs?|"
     rf"restructuration|Restrukturierung|restructuring|Kurzarbeit|chômage partiel|cash crunch|going concern|"
     rf"ferme ses portes|fermeture (?:du site|de l.usine|définitive)|Schliessung|Schließung|plant closure|delisting){NA}"),
]

# 4e élément optionnel : True = regex sensible à la casse (acronymes : « MES » ≠ « mes », « MDR » ≠ « mdr »).
# « acquisition de données » n'est pas un rachat.
EXCLUDE = re.compile(r"acquisition (?:de|des) (?:données|signaux|signal|mesures|images)|data acquisition|"
                     r"Datenerfassung|Messdatenerfassung|acquisition system|système d.acquisition", re.I)
COMPILED = [(r[0], r[1], re.compile(r[2]) if len(r) > 3 and r[3] else re.compile(r[2], re.I)) for r in RULES]

# Signaux « forts » (moment de contact) vs « contexte » : repère pour la lecture, non utilisé par les scripts
FORTS = {("direction", "nouveau_dirigeant"), ("direction", "succession"), ("financement", "levee"),
         ("financement", "augmentation_capital"), ("ma", "rachat"), ("negatif", "difficultes")}


def detect(text: str, ctx: int = 110) -> list[dict]:
    """Toutes les règles qui matchent, avec un extrait autour du 1er match (une entrée par sous-type)."""
    out, seen = [], set()
    if not text:
        return out
    for fam, sub, rx in COMPILED:
        if (fam, sub) in seen:
            continue
        for m in rx.finditer(text):
            window = text[max(0, m.start() - ctx): m.end() + ctx]
            if fam == "ma" and EXCLUDE.search(window):
                continue
            seen.add((fam, sub))
            out.append({"famille": fam, "sous_type": sub, "terme": m.group(0)[:60],
                        "extrait": re.sub(r"\s+", " ", window).strip()})
            break
    return out


def tech_counts(text: str) -> dict[str, int]:
    """Nombre d'occurrences par sous-type tech (profil d'adoption technologique d'un texte)."""
    counts = {}
    for fam, sub, rx in COMPILED:
        if fam != "tech":
            continue
        n = sum(1 for _ in rx.finditer(text or ""))
        if n:
            counts[sub] = counts.get(sub, 0) + n
    return counts
