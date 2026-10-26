export const meta = {
  name: 'verification',
  description: "Étape 4, passe 1 : vérifie l'identité, le site et la page LinkedIn des entreprises de la liste (lots profonds et contrôles légers), puis contre-vérifie chaque URL corrigée ou trouvée",
  whenToUse: "Après scripts/verif_preparer.py, quand la liste doit servir à prospecter. Multi-agents : accord explicite de l'utilisateur avant de lancer",
  phases: [
    { title: 'Recherche', detail: 'un agent par lot : vérification profonde des entreprises douteuses, contrôle léger des solides' },
    { title: 'Contre-vérification', detail: 'agents sceptiques sur chaque URL corrigée ou nouvellement trouvée, lot par lot' },
  ],
}

// args : le contenu de <campagne>/donnees/verification/args-passe1.json, écrit par scripts/verif_preparer.py
//   racine      chemin absolu du projet
//   campagne    dossier de la campagne, absolu ou relatif à racine
//   batches     lots [{id, mode: 'deep' | 'light', n, file}] ; file absolu ou relatif au dossier de la campagne
//   cible       description de la cible (le profil attendu des entreprises de la liste)
//   contexte    (facultatif) qui prospecte et pour vendre quoi
//   registres   (facultatif) registres du commerce consultables, par pays
//   python      (facultatif) défaut <racine>/.venv/bin/python
//   skill       (facultatif) défaut <racine>/.claude/skills/prospection-base-client
//   appels, appels_max (facultatifs, défaut 3 et 6) : appels d'outil par entreprise en lot profond
//   paquet      (facultatif, défaut 40) : propositions au plus par agent de contre-vérification
// Les agents ne modifient aucun fichier : leurs retours restent dans le journal du run, que lit
// scripts/verif_appliquer.py.
const A = typeof args === 'string' ? JSON.parse(args) : args
const absolu = p => /^(\/|[A-Za-z]:[\\/]|\\\\)/.test(p)
const joindre = (base, p) => absolu(p) ? p : `${base.replace(/[\\/]+$/, '')}/${p}`
if (!A || typeof A !== 'object') {
  throw new Error("args attendus : le contenu de <campagne>/donnees/verification/args-passe1.json (scripts/verif_preparer.py)")
}
const manque = ['racine', 'campagne', 'cible'].filter(k => typeof A[k] !== 'string' || !A[k].trim())
if (manque.length || !Array.isArray(A.batches) || !A.batches.length) {
  throw new Error(`args attendus : {racine, campagne, cible, batches: [...]} ; manquant : ${[...manque, ...(Array.isArray(A.batches) && A.batches.length ? [] : ['batches'])].join(', ')}. Les écrire avec scripts/verif_preparer.py (fichier <campagne>/donnees/verification/args-passe1.json).`)
}
if (!absolu(A.racine)) throw new Error(`args.racine doit être un chemin absolu (reçu : ${A.racine})`)
const invalides = A.batches.filter(b => !b || !b.id || !b.file || !['deep', 'light'].includes(b.mode))
if (invalides.length) {
  throw new Error(`lots invalides (id, file et mode deep ou light attendus ; un manifeste de passe 2 va dans workflows/verification-passe2.js) : ${JSON.stringify(invalides.slice(0, 3))}`)
}

const RACINE = A.racine.replace(/[\\/]+$/, '')
const CAMPAGNE = joindre(RACINE, A.campagne)
const PY = A.python || `${RACINE}/.venv/bin/python`
const SKILL = A.skill || `${RACINE}/.claude/skills/prospection-base-client`
const TOOL = `"${PY}" "${SKILL}/scripts/outils_web.py"`
const APPELS = A.appels || 3
const APPELS_MAX = A.appels_max || 6
const PAQUET = A.paquet || 40
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
  properties: {
    batch_id: { type: 'string' },
    entites: { type: 'array', items: ENTITE },
    confirmes: { type: 'array', items: { type: 'string' } },
  },
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
Leur site web et leur page LinkedIn entreprise ont été trouvés automatiquement (donnés par la source de la liste, par des agents de découverte web ou par une recherche DuckDuckGo). Ta mission : vérifier et corriger ces résultats.

Lire les données d'une entreprise (fichier JSON du lot) :
- key : la clé, à recopier telle quelle ; c'est aussi le nom donné par la source, qui peut être abrégé, sans forme juridique ou mal orthographié (nom : le nom de la source quand il diffère de la clé) ;
- pays, ville, secteur, activite, taille : données de la source, à confirmer ;
- site et linkedin : valeurs actuelles. site_statut « trouvé » = donné par la source, sans vérification ; site_confiance « haute » = indice fort (preuve lue sur le site lui-même, ou mot du nom dans le domaine), « basse » ou « à vérifier » = douteux ; linkedin_source « site web » = lien lu sur le site officiel (fiable si le site est le bon) ;
- source et preuve : d'où vient l'entreprise (URL et extrait). C'est le meilleur indice pour départager des homonymes ;
- categorie : solide, probable, faible ou non recherché (la raison de son mode de contrôle) ; a_revoir et note : remarques des étapes précédentes.
Le piège principal : un homonyme dans un autre pays ou un autre métier.`

const OUTILS = `Outils (DuckDuckGo, sorties courtes, à lancer avec Bash, une commande par appel) :
- ${TOOL} search "<requête>" [--region CH]   -> 8 résultats : titre | url | extrait
- ${TOOL} linkedin "<nom>" [--region CH]     -> pages linkedin.com/company trouvées, avec extrait (secteur, siège, abonnés)
- ${TOOL} peek <url>                         -> statut HTTP, url finale, titre, description, liens LinkedIn présents sur la page, indices pays et adresse, pages contact ou mentions légales
--region (facultatif) : code pays de l'entreprise (CH, FR, DE...) pour des résultats de ce pays.
Si DuckDuckGo ne répond pas, utilise WebSearch ou WebFetch (charge-les avec ToolSearch, requête "select:WebSearch,WebFetch").
Registres du commerce (${REGISTRES}) : utiles pour la raison sociale exacte, l'adresse, un changement de nom ou une radiation. Jamais comme site web.
Seul ce que tes outils affichent compte comme vu : si une sortie trop longue est enregistrée dans un fichier, relis ce fichier avec Read.
Compte environ ${APPELS} appels d'outil par entreprise, ${APPELS_MAX} au maximum.`

const REGLES = `Règles :
1. Site web = URL racine officielle de l'entreprise (https://domaine), vue dans un résultat de recherche ou une page que tu as lue. Jamais un annuaire, un registre, une marketplace, un site d'emploi, un réseau social, linktr.ee ou un article de presse. Pour un groupe international : le site du groupe, ou celui du pays de l'entité.
2. LinkedIn = page entreprise au format https://www.linkedin.com/company/<slug> (normalise ch., fr., de. en www.). Préfère la page de l'entité elle-même (page du pays de l'entité si elle existe), sinon la page du groupe (dis-le en note). Jamais la page d'une filiale d'un pays tiers sans rapport avec l'entreprise (par exemple « Exemple France » pour Exemple SA, entité suisse). Contrôle nom, secteur et siège dans l'extrait.
3. N'invente ni ne reconstruis aucune URL : chaque site ou page LinkedIn que tu rends doit être apparu dans une sortie d'outil de cette session. Un contrôle automatique écarte toute URL absente de tes sorties d'outils.
4. Avant de valider une correction, essaie de la réfuter toi-même (homonyme ? autre pays ? autre métier ?). S'il reste un doute sérieux : statut « ambigu », champ vide, candidats dans note.
5. Statuts : « confirmé » (la valeur actuelle est juste), « corrigé » (valeur actuelle fausse ou imparfaite, remplacée), « trouvé » (rien avant, trouvé maintenant), « introuvable » (rien de fiable : champ vide, y compris si la valeur actuelle est fausse), « ambigu » (champ vide), « particulier » (personne physique ou entreprise individuelle sans présence web identifiable).
6. key : recopie exactement la clé du lot. nom_officiel : la raison sociale exacte si tu l'as vue, sinon le nom usuel. pays : code ISO à 2 lettres. ville : ville du siège, si tu l'as vue. activite : 8 mots maximum. preuve : 40 mots maximum, ce que tu as vu (titre de page, adresse, extrait LinkedIn, registre). note : groupe d'appartenance, candidats écartés, doute.
7. Si l'entreprise appartient à un groupe (maison mère, actionnaire majoritaire), a été renommée, absorbée ou reprise, dis-le dans note avec la source. motif_exclusion, vide sauf : « particulier », « administration » (service public), « fermée » (radiée, en liquidation ou en faillite, source dans preuve), « non identifiée » (impossible de savoir de quelle entreprise il s'agit).
8. Ne modifie aucun fichier et n'en crée aucun. Réponds en français.`

function deepPrompt(b) {
  return `${CONTEXTE}

Ton lot : ${b.id}, ${b.n || 'plusieurs'} entreprises dans le fichier ${fichier(b)} (lis-le avec Read). Elles sont à vérifier en profondeur, les plus incertaines en premier : pour chaque entreprise, identifie l'entité réelle, puis confirme, corrige ou trouve son site web et sa page LinkedIn.

${OUTILS}

${REGLES}

Rends une entrée dans entites pour CHAQUE entreprise du lot (${b.n || 'toutes'}), avec batch_id = "${b.id}".`
}

function lightPrompt(b) {
  return `${CONTEXTE}

Ton lot : ${b.id}, ${b.n || 'plusieurs'} entreprises dans le fichier ${fichier(b)} (lis-le avec Read). Elles sont à contrôler légèrement. Chacune porte sa catégorie (champ categorie) : « solide » = site de confiance haute et page LinkedIn sûre ; « probable », « faible » ou « non recherché » = moins sûre, à regarder de plus près. Pour chacune, juge sans outil si le nom, le domaine et le slug LinkedIn collent, et si le pays et l'activité sont plausibles pour la cible. Repère en particulier les homonymes (même nom, autre pays ou autre métier), les pages LinkedIn d'une filiale d'un pays tiers, et les sites de groupe alors que l'entité locale a le sien. N'utilise les outils que pour les cas suspects (attendu : 10 à 25 % du lot).

${OUTILS}

${REGLES}

Rends dans entites uniquement les entreprises dont au moins un champ change ou qui méritent une note (tous les champs remplis, statut « confirmé » pour un champ inchangé), et dans confirmes la liste des clés confirmées sans changement. Chaque clé du lot doit apparaître une fois, dans l'un ou l'autre. batch_id = "${b.id}".`
}

function verifyPrompt(chunk) {
  return `${CONTEXTE}

D'autres agents ont proposé les URL ci-dessous (site web ou page LinkedIn corrigés ou nouvellement trouvés). Ton rôle : les contre-vérifier en sceptique. Chaque proposition est fausse jusqu'à preuve du contraire.

Pour chaque proposition :
1. L'URL existe et appartient bien à l'entreprise : peek pour un site ; pour LinkedIn, linkedin "<nom>" ou search "<slug> linkedin" doit faire apparaître ce slug avec un extrait cohérent.
2. C'est la même entité que celle de la liste : nom, pays et activité cohérents avec la source et sa preuve. Le contexte (nom donné par la source, preuve, anciennes valeurs) est dans le fichier du lot indiqué (champ file), à la clé key.
3. Ce n'est ni un homonyme, ni la page d'une filiale d'un pays tiers, ni un annuaire.
Verdict : « confirmé » seulement si tu as vu toi-même la preuve ; « réfuté » si c'est faux (dis pourquoi et, si tu l'as vue, quelle est la bonne URL) ; « incertain » sinon. Au moins un appel d'outil par proposition, sauf si la même URL revient pour la même entreprise. Un contrôle automatique ramène à « incertain » tout « confirmé » dont l'URL n'apparaît pas dans tes sorties d'outils.

${OUTILS}

Propositions (JSON) :
${JSON.stringify(chunk)}

Rends un verdict par proposition, en recopiant key, champ et valeur. Ne modifie aucun fichier. Réponds en français.`
}

// URL corrigées ou trouvées d'un lot : ce que la contre-vérification doit examiner
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
    return agent(b.mode === 'deep' ? deepPrompt(b) : lightPrompt(b), {
      label: `${b.id} ${b.mode === 'deep' ? 'profond' : 'léger'} (${b.n || '?'})`,
      phase: 'Recherche',
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
log(`Recherche : ${ok.length}/${A.batches.length} lots, ${propositionsTotal} URL corrigées ou trouvées, ${verdicts.length} verdicts`)
const compter = (arr, f) => arr.reduce((m, x) => { const k = f(x); m[k] = (m[k] || 0) + 1; return m }, {})
return {
  lots_ok: ok.map(r => r.lot.batch_id),
  lots_ko: echecs,
  entites_rendues: entites.length,
  confirmes_leger: ok.reduce((n, r) => n + (r.lot.confirmes ? r.lot.confirmes.length : 0), 0),
  statuts_site: compter(entites, e => e.site_statut),
  statuts_linkedin: compter(entites, e => e.linkedin_statut),
  propositions: propositionsTotal,
  verdicts: compter(verdicts, v => v.verdict),
  sans_contre_verif: sansContreVerif,
  non_confirmes: verdicts.filter(v => v.verdict !== 'confirmé'),
  suite: `Appliquer : "${PY}" "${SKILL}/scripts/verif_appliquer.py" --campagne "${CAMPAGNE}" <dossier de ce run ou son journal.jsonl> ; puis, s'il reste des cas ouverts, scripts/verif_passe2.py et workflows/verification-passe2.js`,
}
