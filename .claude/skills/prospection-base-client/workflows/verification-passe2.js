export const meta = {
  name: 'verification-passe2',
  description: "Étape 4, passe 2 : reprend les cas restés ouverts (identification des entités ambiguës ou non identifiées, complétion des sites et pages LinkedIn manquants), puis contre-vérifie chaque URL corrigée ou trouvée",
  whenToUse: "Après scripts/verif_passe2.py (en général après la passe 1 et verif_appliquer.py). Multi-agents : accord explicite de l'utilisateur avant de lancer",
  phases: [
    { title: 'Résolution', detail: "cas ambigus, à revoir ou non identifiés : registre du commerce, recherche web, preuve de la source" },
    { title: 'Complétion', detail: "entreprises identifiées à qui il manque le site ou la page LinkedIn" },
    { title: 'Contre-vérification', detail: 'agents sceptiques sur chaque URL corrigée ou trouvée, lot par lot' },
  ],
}

// args : le contenu de <campagne>/donnees/verification/args-passe2.json, écrit par scripts/verif_passe2.py
//   racine      chemin absolu du projet
//   campagne    dossier de la campagne, absolu ou relatif à racine
//   batches     lots [{id, mode: 'resolve' | 'complete', n, file, cles?, alias?}] ; file absolu ou relatif à la campagne
//   cible       description de la cible (le profil attendu des entreprises de la liste)
//   contexte    (facultatif) qui prospecte et pour vendre quoi
//   registres   (facultatif) registres du commerce consultables, par pays
//   python      (facultatif) défaut <racine>/.venv/bin/python
//   skill       (facultatif) défaut <racine>/.claude/skills/prospection-base-client
//   appels, appels_max (facultatifs, défaut 5 et 10) : appels d'outil par entité
//   paquet      (facultatif, défaut 30) : propositions au plus par agent de contre-vérification
// Les agents ne modifient aucun fichier : leurs retours restent dans le journal du run, que lit
// scripts/verif_appliquer.py (avec le journal de la passe 1 en premier).
const A = typeof args === 'string' ? JSON.parse(args) : args
const absolu = p => /^(\/|[A-Za-z]:[\\/]|\\\\)/.test(p)
const joindre = (base, p) => absolu(p) ? p : `${base.replace(/[\\/]+$/, '')}/${p}`
if (!A || typeof A !== 'object') {
  throw new Error("args attendus : le contenu de <campagne>/donnees/verification/args-passe2.json (scripts/verif_passe2.py)")
}
const manque = ['racine', 'campagne', 'cible'].filter(k => typeof A[k] !== 'string' || !A[k].trim())
if (manque.length || !Array.isArray(A.batches) || !A.batches.length) {
  throw new Error(`args attendus : {racine, campagne, cible, batches: [...]} ; manquant : ${[...manque, ...(Array.isArray(A.batches) && A.batches.length ? [] : ['batches'])].join(', ')}. Les écrire avec scripts/verif_passe2.py (fichier <campagne>/donnees/verification/args-passe2.json).`)
}
if (!absolu(A.racine)) throw new Error(`args.racine doit être un chemin absolu (reçu : ${A.racine})`)
const invalides = A.batches.filter(b => !b || !b.id || !b.file || !['resolve', 'complete'].includes(b.mode))
if (invalides.length) {
  throw new Error(`lots invalides (id, file et mode resolve ou complete attendus ; un manifeste de passe 1 va dans workflows/verification.js) : ${JSON.stringify(invalides.slice(0, 3))}`)
}

const RACINE = A.racine.replace(/[\\/]+$/, '')
const CAMPAGNE = joindre(RACINE, A.campagne)
const PY = A.python || `${RACINE}/.venv/bin/python`
const SKILL = A.skill || `${RACINE}/.claude/skills/prospection-base-client`
const TOOL = `"${PY}" "${SKILL}/scripts/outils_web.py"`
const APPELS = A.appels || 5
const APPELS_MAX = A.appels_max || 10
const PAQUET = A.paquet || 30
const REGISTRES = A.registres || "le registre du commerce du pays de l'entreprise"
const fichier = b => joindre(CAMPAGNE, b.file)
const STATUTS = ['confirmé', 'corrigé', 'trouvé', 'introuvable', 'ambigu', 'particulier']

const ENTITE = {
  type: 'object',
  properties: {
    key: { type: 'string' },
    nom_officiel: { type: 'string' },
    pays: { type: 'string' },
    ville: { type: 'string' },
    activite: { type: 'string' },
    site: { type: 'string' },
    site_statut: { type: 'string', enum: STATUTS },
    linkedin: { type: 'string' },
    linkedin_statut: { type: 'string', enum: STATUTS },
    motif_exclusion: { type: 'string', enum: ['', 'particulier', 'administration', 'fermée', 'non identifiée'] },
    preuve: { type: 'string' },
    note: { type: 'string' },
  },
  required: ['key', 'nom_officiel', 'pays', 'site', 'site_statut', 'linkedin', 'linkedin_statut', 'preuve'],
}
const LOT = {
  type: 'object',
  properties: { batch_id: { type: 'string' }, entites: { type: 'array', items: ENTITE } },
  required: ['batch_id', 'entites'],
}
const VERDICTS = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          key: { type: 'string' },
          champ: { type: 'string', enum: ['site', 'linkedin'] },
          valeur: { type: 'string' },
          verdict: { type: 'string', enum: ['confirmé', 'réfuté', 'incertain'] },
          raison: { type: 'string' },
        },
        required: ['key', 'champ', 'valeur', 'verdict', 'raison'],
      },
    },
  },
  required: ['verdicts'],
}

const CONTEXTE = `Contexte : une campagne de prospection B2B.${A.contexte ? ` Qui prospecte : ${A.contexte}.` : ''}
Les entreprises de la liste sont censées correspondre à cette cible : ${A.cible}
Leur site web et leur page LinkedIn entreprise ont été cherchés puis vérifiés (passe 1 : recherche par agents et contre-vérification). Il reste des cas que la passe 1 n'a pas su régler, ou qu'elle n'a pas traités.

Lire les données d'une entité (fichier JSON du lot) :
- key : la clé, à recopier telle quelle ; c'est aussi le nom donné par la source (nom : le nom de la source quand il diffère) ; alias : autres clés de la même entreprise ;
- pays, ville, secteur, activite, taille : données de la source ;
- source et preuve : d'où vient l'entreprise (URL et extrait), ce qu'elle fait selon la source. C'est le meilleur indice pour départager des homonymes ;
- passe1 : l'état après la passe 1 (nom officiel, pays, site, page LinkedIn, statuts, site_verif et linkedin_verif = verdict détaillé de la passe 1, preuve_verification, note avec les candidats écartés et les raisons du contre-vérificateur). Sans passe 1, passe1 contient les valeurs de la liste (statut « trouvé » = donné par la source, sans vérification).
Le piège principal : un homonyme dans un autre pays ou un autre métier.`

const OUTILS = `Outils :
- WebSearch et WebFetch (moteur différent de la passe 1 : à utiliser en priorité ; charge-les avec ToolSearch, requête "select:WebSearch,WebFetch").
- Outils DuckDuckGo, à lancer avec Bash, une commande par appel :
  ${TOOL} search "<requête>" [--region CH]   -> 8 résultats : titre | url | extrait
  ${TOOL} linkedin "<nom>" [--region CH]     -> pages linkedin.com/company trouvées, avec extrait
  ${TOOL} peek <url>                         -> statut HTTP, url finale, titre, liens LinkedIn présents sur la page, indices pays et adresse
  --region (facultatif) : code pays de l'entreprise (CH, FR, DE...).
- Registres du commerce (${REGISTRES}) : la raison sociale exacte, l'adresse, l'état (active, renommée, radiée, en liquidation). Jamais comme site web.
Seul ce que tes outils affichent compte comme vu : si une sortie trop longue est enregistrée dans un fichier, relis ce fichier avec Read.`

const REGLES = `Règles :
1. Site web = URL racine officielle de l'entreprise (https://domaine), vue dans un résultat de recherche ou une page que tu as lue. Jamais un annuaire, un registre, une marketplace, un site d'emploi, un réseau social, linktr.ee ou un article de presse.
2. LinkedIn = page entreprise au format https://www.linkedin.com/company/<slug> (normalise ch., fr., de. en www.). Préfère la page de l'entité elle-même (page du pays de l'entité si elle existe), sinon la page du groupe (dis-le en note). Jamais la page d'une filiale d'un pays tiers sans rapport avec l'entreprise. Contrôle nom, secteur et siège.
3. N'invente ni ne reconstruis aucune URL : chaque site ou page LinkedIn que tu rends doit être apparu dans une sortie d'outil de cette session. Un contrôle automatique écarte toute URL absente de tes sorties d'outils.
4. Avant de valider, essaie de réfuter toi-même (homonyme ? autre pays ? autre métier ?). S'il reste un doute sérieux : statut « ambigu », champ vide, candidats en note.
5. Statuts : « confirmé » (la valeur de passe1 est juste), « corrigé » (valeur de passe1 fausse, remplacée), « trouvé » (rien en passe1, trouvé maintenant), « introuvable » (rien de fiable : champ vide), « ambigu » (champ vide), « particulier » (personne physique ou entreprise individuelle sans présence web).
6. nom_officiel : la raison sociale exacte si tu l'as vue. pays : code ISO à 2 lettres. ville : ville du siège, si tu l'as vue. activite : 8 mots maximum. preuve : 40 mots maximum, ce que tu as vu (registre, titre de page, adresse, extrait LinkedIn). note : groupe d'appartenance, renommage ou reprise (avec la source), candidats écartés, doute. motif_exclusion, vide sauf : « particulier », « administration » (service public), « fermée » (radiée, en liquidation ou en faillite, source dans preuve), « non identifiée » (impossible de savoir de quelle entreprise il s'agit).
7. Si une entité a un champ alias, rends AUSSI une entrée identique pour chaque alias (même contenu, key = l'alias).
8. Ne modifie aucun fichier et n'en crée aucun. Réponds en français. Compte environ ${APPELS} appels d'outil par entité, ${APPELS_MAX} au maximum.`

function resolvePrompt(b) {
  return `${CONTEXTE}

Ton lot : ${b.id}, ${b.n || 'plusieurs'} entités dans le fichier ${fichier(b)} (lis-le avec Read). Ce sont des cas que la passe 1 n'a pas su trancher (ambigu, incertain, réfuté, non contre-vérifié, non vérifié) ou pas su identifier. Le champ passe1 (preuve, note) te donne les pistes et les candidats déjà écartés : ne refais pas le même chemin, change d'angle.

Méthode, dans cet ordre :
1. Registre du commerce d'abord : cherche le nom de la source et ses variantes (avec et sans forme juridique, ancien nom) pour la raison sociale exacte, l'adresse, l'activité déclarée et l'état (active, renommée, radiée).
2. Recherche web avec WebSearch, puis lecture des pages (WebFetch ou peek). Repars de la preuve de la source : elle dit où l'entreprise a été vue et ce qu'elle fait.
3. Tranche : tes seuls arbitres pour départager des homonymes sont le registre et la preuve de la source. Un candidat n'est retenu que si le nom, le pays et l'activité collent avec eux. Sinon « ambigu », avec les candidats en note ; ne force rien.

${OUTILS}

${REGLES}

Rends une entrée dans entites pour CHAQUE entité du lot (et ses alias), avec batch_id = "${b.id}".`
}

function completePrompt(b) {
  return `${CONTEXTE}

Ton lot : ${b.id}, ${b.n || 'plusieurs'} entreprises dans le fichier ${fichier(b)} (lis-le avec Read). Elles sont identifiées (nom officiel, pays, activité dans passe1 ou dans les données de la source), mais il leur manque le site web, la page LinkedIn, ou les deux. Cherche ce qui manque avec un autre angle que la passe 1 :
- WebSearch avec le nom officiel exact, la ville, la marque ;
- pour LinkedIn : WebSearch "<nom officiel> LinkedIn", l'outil linkedin, et la lecture (peek ou WebFetch) des pages contact, à propos ou mentions légales du site officiel, où le lien est souvent caché ;
- pour un site : la fiche du registre ou une fiche d'entreprise peut citer le domaine officiel.
Une petite entreprise sans page LinkedIn ou sans site, c'est un résultat valable : statut « introuvable ». Ne force rien. Ne remets pas en cause ce que la passe 1 a confirmé, sauf erreur manifeste (dis-le en note). Si passe1 a déjà le site et la page LinkedIn, c'est une autre ligne de la même entreprise (un alias) qui en manquait : contrôle-les et, s'ils sont justes, statut « confirmé ».

${OUTILS}

${REGLES}

Rends une entrée dans entites pour CHAQUE entreprise du lot (et ses alias), avec batch_id = "${b.id}".`
}

function verifyPrompt(chunk) {
  return `${CONTEXTE}

D'autres agents ont proposé les URL ci-dessous (site web ou page LinkedIn corrigés ou nouvellement trouvés). Ton rôle : les contre-vérifier en sceptique. Chaque proposition est fausse jusqu'à preuve du contraire.

Pour chaque proposition :
1. L'URL existe et appartient bien à l'entreprise : peek ou WebFetch pour un site ; pour LinkedIn, l'outil linkedin, une recherche du slug, ou un lien depuis le site officiel doit faire apparaître ce slug avec un extrait cohérent.
2. C'est la même entité que celle de la liste : nom, pays et activité cohérents avec la source, sa preuve et le registre. Le contexte (source, preuve, passe 1) est dans le fichier du lot indiqué (champ file), à la clé key.
3. Ce n'est ni un homonyme, ni la page d'une filiale d'un pays tiers, ni un annuaire.
Verdict : « confirmé » seulement si tu as vu toi-même la preuve ; « réfuté » si c'est faux (dis pourquoi et, si tu l'as vue, quelle est la bonne URL) ; « incertain » sinon. Au moins un appel d'outil par proposition, sauf si la même URL revient pour la même entreprise. Un contrôle automatique ramène à « incertain » tout « confirmé » dont l'URL n'apparaît pas dans tes sorties d'outils.

${OUTILS}

Propositions (JSON) :
${JSON.stringify(chunk)}

Rends un verdict par proposition, en recopiant key, champ et valeur. Ne modifie aucun fichier. Réponds en français.`
}

function propositions(lot, b) {
  const out = []
  for (const e of lot.entites || []) {
    for (const champ of ['site', 'linkedin']) {
      const st = e[`${champ}_statut`]
      if ((st === 'corrigé' || st === 'trouvé') && e[champ]) {
        out.push({ file: fichier(b), key: e.key, champ, valeur: e[champ], nom_officiel: e.nom_officiel, pays: e.pays, activite: e.activite || '', preuve: e.preuve })
      }
    }
  }
  // les alias gardent chacun leur proposition : le verdict est rattaché à la clé (même URL revue sans nouvel appel)
  return out
}

function paquets(items, n) {
  const out = []
  for (let i = 0; i < items.length; i += n) out.push(items.slice(i, i + n))
  return out
}

// Chaque lot passe à sa contre-vérification dès qu'il est rendu, sans attendre les autres
const res = await pipeline(A.batches,
  (item, orig) => {
    const b = orig || item
    const resolution = b.mode === 'resolve'
    return agent(resolution ? resolvePrompt(b) : completePrompt(b), {
      label: `${b.id} ${resolution ? 'résolution' : 'complétion'} (${b.n || '?'})`,
      phase: resolution ? 'Résolution' : 'Complétion',
      schema: LOT,
      effort: 'medium',
    })
  },
  async (lot, b) => {
    if (!lot) return { lot: null, props: [], verifs: [] }
    const props = propositions(lot, b)
    const ps = paquets(props, PAQUET)
    const verifs = await parallel(ps.map((c, i) => () =>
      agent(verifyPrompt(c), {
        label: `${b.id} contre-vérif ${i + 1}/${ps.length} (${c.length})`,
        phase: 'Contre-vérification',
        schema: VERDICTS,
        effort: 'medium',
      })))
    const sans = ps.filter((c, i) => !verifs[i]).reduce((n, c) => n + c.length, 0)
    return { lot, props, verifs: verifs.filter(Boolean), sans }
  })

const rendus = A.batches.map((b, i) => ({ b, r: res[i] }))
const echecs = rendus.filter(x => !x.r || !x.r.lot).map(x => x.b.id)
if (echecs.length) log(`Lots sans résultat (à relancer par reprise, sinon « non vérifié ») : ${echecs.join(', ')}`)
const ok = rendus.filter(x => x.r && x.r.lot).map(x => x.r)
const entites = ok.flatMap(r => r.lot.entites || [])
const verdicts = ok.flatMap(r => r.verifs.flatMap(v => v.verdicts || []))
const propositionsTotal = ok.reduce((n, r) => n + r.props.length, 0)
const sansContreVerif = ok.reduce((n, r) => n + (r.sans || 0), 0)
if (sansContreVerif) log(`${sansContreVerif} propositions sans contre-vérification (agent en échec) : « non contre-vérifié » à l'application`)
log(`Passe 2 : ${ok.length}/${A.batches.length} lots, ${propositionsTotal} URL corrigées ou trouvées, ${verdicts.length} verdicts`)
const compter = (arr, f) => arr.reduce((m, x) => { const k = f(x); m[k] = (m[k] || 0) + 1; return m }, {})
return {
  lots_ok: ok.map(r => r.lot.batch_id),
  lots_ko: echecs,
  entites_rendues: entites.length,
  statuts_site: compter(entites, e => e.site_statut),
  statuts_linkedin: compter(entites, e => e.linkedin_statut),
  propositions: propositionsTotal,
  verdicts: compter(verdicts, v => v.verdict),
  sans_contre_verif: sansContreVerif,
  non_confirmes: verdicts.filter(v => v.verdict !== 'confirmé'),
  suite: `Appliquer les deux passes, dans l'ordre : "${PY}" "${SKILL}/scripts/verif_appliquer.py" --campagne "${CAMPAGNE}" <run de la passe 1> <run de cette passe 2>`,
}
