export const meta = {
  name: 'decouverte-entreprises',
  description: "Étape 2 : recense sur le web les entreprises d'une cible, un agent par segment et par source transverse, avec une preuve publique pour chacune, puis comble les angles morts",
  whenToUse: "Constituer une liste d'entreprises à prospecter quand on ne part pas d'une liste existante (export Apollo ou autre)",
  phases: [
    { title: 'Balayage', detail: 'un agent par segment (secteur x zone) et par source transverse' },
    { title: 'Angles morts', detail: 'critique de couverture puis recherches complémentaires' },
  ],
}

// args (objet JSON) :
//   racine           chemin absolu du projet (obligatoire)
//   campagne         dossier de la campagne, absolu ou relatif à racine (obligatoire)
//   python           (facultatif) interpréteur ; défaut <racine>/.venv/bin/python
//   skill            (facultatif) dossier du skill ; défaut <racine>/.claude/skills/prospection-base-client
//   icp              description de la cible : secteurs, zone, taille (obligatoire)
//   exclusions       (facultatif) ce qui n'est pas dans la cible : texte ou liste de textes
//   contexte         qui prospecte et pour vendre quoi, en deux phrases (obligatoire)
//   segments         liste de segments « secteur, zone » : un agent chacun (obligatoire)
//   sources          (facultatif) sources transverses [{id, titre, consigne}] : un agent chacune ; défaut : SOURCES
//   max_complements  (facultatif, défaut 6 ; 0 = ni critique ni compléments)
//   cible_par_agent  (facultatif, défaut 40) : volume visé par agent
// Le script n'écrit aucun fichier : consolider_decouverte.py lit ensuite le journal du run (voir « suite »).
const USAGE = "args attendus : {racine, campagne, icp, contexte, segments: [...], exclusions?, sources?: [{id, titre, consigne}], python?, skill?, max_complements?, cible_par_agent?}"
const A = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return null } })() : args
if (!A || typeof A !== 'object' || Array.isArray(A)) throw new Error(USAGE)

const estTexte = v => typeof v === 'string' && v.trim() !== ''
const estAbsolu = p => /^(\/|[A-Za-z]:[\\/])/.test(p)
const estEntier = (v, min) => Number.isInteger(v) && v >= min
const erreurs = []
if (!estTexte(A.racine) || !estAbsolu(A.racine)) erreurs.push('racine : chemin absolu du projet')
if (!estTexte(A.campagne)) erreurs.push('campagne : dossier de la campagne (absolu, ou relatif à racine)')
if (!estTexte(A.icp)) erreurs.push('icp : description de la cible (secteurs, zone, taille)')
if (!estTexte(A.contexte)) erreurs.push('contexte : qui prospecte et pour vendre quoi, en deux phrases')
if (!Array.isArray(A.segments) || !A.segments.length || !A.segments.every(estTexte)) erreurs.push('segments : liste non vide de textes « secteur, zone »')
if (A.exclusions !== undefined && !estTexte(A.exclusions) && !(Array.isArray(A.exclusions) && A.exclusions.every(estTexte))) erreurs.push('exclusions : texte ou liste de textes')
if (A.sources !== undefined && !(Array.isArray(A.sources) && A.sources.every(s => s && estTexte(s.id) && estTexte(s.titre) && estTexte(s.consigne)))) erreurs.push('sources : liste de {id, titre, consigne}')
if (A.python !== undefined && !estTexte(A.python)) erreurs.push('python : chemin de l\'interpréteur')
if (A.skill !== undefined && !estTexte(A.skill)) erreurs.push('skill : chemin du dossier du skill')
if (A.max_complements !== undefined && !estEntier(A.max_complements, 0)) erreurs.push('max_complements : entier, 0 ou plus')
if (A.cible_par_agent !== undefined && !estEntier(A.cible_par_agent, 1)) erreurs.push('cible_par_agent : entier, 1 ou plus')
if (erreurs.length) throw new Error(`args invalides :\n- ${erreurs.join('\n- ')}\n${USAGE}`)

const sansBarre = p => p.replace(/[\\/]+$/, '')
const ROOT = sansBarre(A.racine)
const resoudre = p => (estAbsolu(p) ? sansBarre(p) : `${ROOT}/${sansBarre(p).replace(/^\.\//, '')}`)
const CAMPAGNE = resoudre(A.campagne)
const NOM = CAMPAGNE.split(/[\\/]/).pop()
const PY = A.python ? resoudre(A.python) : `${ROOT}/.venv/bin/python`
const SKILL = A.skill ? resoudre(A.skill) : `${ROOT}/.claude/skills/prospection-base-client`
const TOOL = `"${PY}" "${SKILL}/scripts/outils_web.py"`
const MAX_COMPLEMENTS = A.max_complements === undefined ? 6 : A.max_complements
const CIBLE = A.cible_par_agent || 40
const EXCLUSIONS = Array.isArray(A.exclusions) ? A.exclusions.join(' ; ') : (A.exclusions || '')
const TYPES = ["site de l'entreprise", 'registre du commerce', 'annuaire ou association', "liste d'exposants",
  'parc ou cluster', "offre d'emploi", 'presse / article', 'LinkedIn', 'autre']

// Schéma rendu par chaque agent de recensement : c'est ce que lit consolider_decouverte.py (ne pas le changer seul)
const ENTREPRISE = {
  type: 'object',
  properties: {
    nom: { type: 'string' },
    ville: { type: 'string' },
    pays: { type: 'string' },
    site: { type: 'string' },
    linkedin: { type: 'string' },
    secteur: { type: 'string' },
    activite: { type: 'string' },
    taille: { type: 'string' },
    type_source: { type: 'string', enum: TYPES },
    url_preuve: { type: 'string' },
    extrait: { type: 'string' },
    signal: { type: 'string' },
    url_signal: { type: 'string' },
    hors_cible: { type: 'string' },
  },
  required: ['nom', 'pays', 'type_source', 'url_preuve', 'extrait'],
}
const TROUVAILLES = {
  type: 'object',
  properties: {
    modalite: { type: 'string' },
    segment: { type: 'string' },
    requetes: { type: 'array', items: { type: 'string' } },
    entreprises: { type: 'array', items: ENTREPRISE },
  },
  required: ['modalite', 'entreprises'],
}
const CRITIQUE = {
  type: 'object',
  properties: {
    constat: { type: 'string' },
    taches: {
      type: 'array',
      items: {
        type: 'object',
        properties: { titre: { type: 'string' }, consigne: { type: 'string' } },
        required: ['titre', 'consigne'],
      },
    },
  },
  required: ['taches'],
}

// Sources transverses par défaut : chacune couvre tous les segments à la fois
const SOURCES = [
  { id: 'salons', titre: "Listes d'exposants des salons du secteur", consigne: "Source : les listes d'exposants des salons professionnels du secteur et de la zone (éditions récentes et à venir). Trouve les salons pertinents, ouvre leurs listes d'exposants (pages, PDF, plans de halle) et recense les exposants qui sont dans la cible, pas ceux que la cible ou les exclusions écartent." },
  { id: 'associations', titre: 'Annuaires des associations, chambres et clusters', consigne: "Source : les annuaires de membres des associations professionnelles, des chambres de commerce et d'industrie, des parcs technologiques et des clusters régionaux de la zone. Parcours les listes de membres (souvent par région ou par métier) et recense les entreprises de la cible." },
  { id: 'emplois', titre: "Offres d'emploi de la zone", consigne: "Source : les offres d'emploi publiées dans la zone pour les métiers typiques des entreprises de la cible (déduis-les de la cible : métiers de production, techniques ou de service propres au secteur). L'employeur doit être nommé : une offre d'un cabinet de recrutement pour un client anonyme ne compte pas. Une entreprise qui recrute est aussi un signal : note-le dans signal." },
]

const PREUVE = `Règles :
1. Chaque entreprise a une preuve vue dans cette session : une URL (url_preuve) et un extrait littéral de 30 mots au plus (extrait) qui montre qu'elle existe et ce qu'elle fait. Une page de l'entreprise elle-même est la meilleure preuve.
2. Renseigne : le nom tel qu'écrit dans la source, la ville, le pays (code ISO à 2 lettres), le site officiel seulement si tu l'as vu (jamais deviné à partir du nom), la page LinkedIn de l'entreprise seulement si tu l'as vue, le secteur (6 mots au plus), l'activité (une phrase), la taille si elle est publiée (« 51-200 sur LinkedIn », « 80 collaborateurs »), et un signal récent s'il te passe sous les yeux (date AAAA-MM et fait : rachat, nouveau dirigeant, nouveau site ou nouvelle usine, recrutement, nouveau produit), avec son URL.
3. Une entreprise qui n'est pas dans la cible (trop grande, hors zone, ${EXCLUSIONS ? 'dans les exclusions, ' : ''}concurrent qui vend ce que nous vendons...) : note-la quand même si tu l'as rencontrée, avec le motif dans hors_cible ; sinon laisse hors_cible vide. Ne cherche pas les hors cible.
4. N'invente rien : pas de nom deviné, pas d'URL reconstruite, pas de taille estimée.
5. Vise le volume utile, environ ${CIBLE} entreprises de la cible : continue tant que tes requêtes rapportent des entreprises nouvelles, change d'angle quand elles s'épuisent. Liste les requêtes lancées dans requetes. Réponds en français.`

const OUTILS = `Outils :
- WebSearch pour chercher et WebFetch pour lire une page, une liste ou un PDF (charge-les avec ToolSearch, requête "select:WebSearch,WebFetch").
- Outils DuckDuckGo à lancer avec Bash (autre moteur, utile en complément ; tronque les sorties longues avec head) :
  ${TOOL} search "<requête>"   -> 8 résultats : titre | url | extrait (ajoute --region CH, --region de-de... pour viser un pays)
  ${TOOL} peek <url>           -> titre, description, indices de pays et d'adresse d'une page
  ${TOOL} linkedin "<nom>"     -> pages LinkedIn company candidates`

const ENTETE = `Tu recenses des entreprises pour une campagne de prospection (campagne « ${NOM} »).
Contexte (qui prospecte, pour vendre quoi) : ${A.contexte}
Cible : ${A.icp}${EXCLUSIONS ? `\nExclusions (hors cible) : ${EXCLUSIONS}` : ''}`

function segmentPrompt(seg) {
  return `${ENTETE}

Ton segment attitré (modalite = "segment", segment = "${seg}") : ${seg}.
Trouve les entreprises de ce segment qui sont dans la cible, par toutes les sources utiles : sites d'entreprises, registre du commerce, annuaires et associations professionnelles, listes d'exposants de salons, parcs et clusters, offres d'emploi, presse régionale, pages LinkedIn d'entreprises. Commence par les annuaires et les listes : une seule page en donne souvent des dizaines.

${OUTILS}

${PREUVE}`
}

function sourcePrompt(s) {
  return `${ENTETE}

Les segments de la campagne : ${A.segments.join(' ; ')}.
Ta source attitrée (modalite = "${s.id}") : ${s.titre}.
${s.consigne}
Indique dans segment celui des segments qui correspond le mieux à chaque entreprise.

${OUTILS}

${PREUVE}`
}

// même normalisation que commun.norm (formes juridiques retirées) : compteurs alignés sur la consolidation
const LEGAL = new Set(['sa', 'ag', 'gmbh', 'sarl', 'sas', 'sasu', 'ltd', 'holding', 'co', 'kg', 'group', 'groupe', 'the',
  'et', 'und', 'and', 'cie', 'inc', 'sagl', 'spa', 'srl', 's', 'a', 'g', 'succursale', 'filiale'])
function norm(s) {
  return (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').split(' ').filter(w => w && !LEGAL.has(w)).join(' ')
}

function uniques(results) {
  const by = new Map()
  for (const r of results) {
    for (const e of r.entreprises || []) {
      const k = norm(e.nom)
      if (!k) continue
      if (!by.has(k)) by.set(k, { nom: e.nom, pays: e.pays, secteur: e.secteur || '', hors: !!(e.hors_cible || '').trim(), sources: new Set() })
      by.get(k).sources.add(r.modalite + (r.segment ? ` / ${r.segment}` : ''))
    }
  }
  return by
}

// --- Phase 1 : un agent par segment et un par source transverse, tous en parallèle
phase('Balayage')
const SRC = A.sources || SOURCES
const taches1 = [
  ...A.segments.map(seg => ({ label: `Segment : ${seg}`, prompt: segmentPrompt(seg) })),
  ...SRC.map(s => ({ label: `Source : ${s.titre}`, prompt: sourcePrompt(s) })),
]
const round1Raw = await parallel(taches1.map(t => () =>
  agent(t.prompt, { label: t.label, phase: 'Balayage', schema: TROUVAILLES, effort: 'medium' })))
const echecs = taches1.filter((t, i) => !round1Raw[i]).map(t => t.label)
if (echecs.length) log(`Agents en échec (à relancer par reprise) : ${echecs.join(', ')}`)
const round1 = round1Raw.filter(Boolean)
const u1 = uniques(round1)
log(`Premier balayage : ${round1.reduce((n, r) => n + (r.entreprises || []).length, 0)} mentions, ${u1.size} entreprises uniques`)

// --- Phase 2 : critique de couverture, puis compléments (barrière voulue : la critique lit tout le bilan)
let critique = null
let complements = []
let round2 = []
if (MAX_COMPLEMENTS > 0) {
  phase('Angles morts')
  const parSegment = {}
  for (const e of u1.values()) {
    if (e.hors) continue
    for (const s of e.sources) {
      const seg = s.includes(' / ') ? s.split(' / ').slice(1).join(' / ') : s
      parSegment[seg] = (parSegment[seg] || 0) + 1
    }
  }
  const bilan = {
    cible: A.icp,
    exclusions: EXCLUSIONS,
    segments: A.segments,
    agents: round1.map(r => ({ modalite: r.modalite, segment: r.segment || '', n_entreprises: (r.entreprises || []).length, requetes: (r.requetes || []).slice(0, 25) })),
    agents_en_echec: echecs,
    entreprises_dans_la_cible_par_segment: parSegment,
    total_uniques: u1.size,
    echantillon: [...u1.values()].filter(e => !e.hors).slice(0, 150).map(e => `${e.nom} (${e.pays}, ${e.secteur})`),
  }
  critique = await agent(`Tu contrôles la couverture d'une recherche d'entreprises pour une campagne de prospection.
Contexte (qui prospecte, pour vendre quoi) : ${A.contexte}
Cible : ${A.icp}${EXCLUSIONS ? `\nExclusions (hors cible) : ${EXCLUSIONS}` : ''}

Bilan du premier balayage : agents lancés (un par segment et par source transverse), entreprises trouvées par agent, requêtes lancées, entreprises de la cible par segment et un échantillon.

${JSON.stringify(bilan)}

Repère les angles morts : segments sous-couverts, sources non exploitées (annuaires d'associations, chambres de commerce, listes d'exposants, parcs et clusters, registre du commerce, offres d'emploi, presse régionale), sous-secteurs ou communes manquants, langues non couvertes. Propose au plus ${MAX_COMPLEMENTS} tâches de recherche complémentaires, chacune avec un titre et une consigne précise (source, requêtes types, ce qu'il faut recenser), qui ont le plus de chances de rapporter des entreprises NOUVELLES de la cible. Écris aussi un constat de 3 phrases au plus. Réponds en français.`,
    { label: 'Critique de couverture', phase: 'Angles morts', schema: CRITIQUE, effort: 'high' })

  complements = critique ? critique.taches.slice(0, MAX_COMPLEMENTS) : []
  if (!critique) log('Critique de couverture en échec : pas de recherches complémentaires (relancer par reprise)')
  if (critique && critique.taches.length > MAX_COMPLEMENTS) {
    log(`${critique.taches.length - MAX_COMPLEMENTS} tâches complémentaires non lancées (plafond ${MAX_COMPLEMENTS}) : ${critique.taches.slice(MAX_COMPLEMENTS).map(t => t.titre).join(', ')}`)
  }
  round2 = (await parallel(complements.map((t, i) => () =>
    agent(sourcePrompt({ id: `complement-${i + 1}`, titre: t.titre, consigne: t.consigne }),
      { label: `Complément : ${t.titre}`, phase: 'Angles morts', schema: TROUVAILLES, effort: 'medium' })))).filter(Boolean)
} else {
  log('max_complements = 0 : ni critique de couverture ni recherches complémentaires')
}

const tout = [...round1, ...round2]
const u = uniques(tout)
const dansCible = [...u.values()].filter(e => !e.hors).length
return {
  campagne: CAMPAGNE,
  par_agent: tout.map(r => ({ modalite: r.modalite, segment: r.segment || '', entreprises: (r.entreprises || []).length })),
  agents_en_echec: echecs,
  mentions: tout.reduce((n, r) => n + (r.entreprises || []).length, 0),
  entreprises_uniques: u.size,
  dans_la_cible: dansCible,
  nouvelles_au_complement: u.size - u1.size,
  constat_critique: critique ? (critique.constat || '') : '',
  taches_complementaires: complements.map(t => t.titre),
  suite: `Consolider : "${PY}" "${SKILL}/scripts/consolider_decouverte.py" --campagne "${CAMPAGNE}" "<dossier du run>" (dossier du run, qui contient journal.jsonl et les transcripts agent-<id>.jsonl : find ~/.claude/projects -type d -path '*workflows*' -name '<runId>')`,
}
