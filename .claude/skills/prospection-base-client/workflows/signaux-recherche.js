export const meta = {
  name: 'signaux-recherche',
  description: "Étape 5 : recherche web des signaux de prospection (direction, financement, rachat, projets, adoption tech) par lot de dossiers, puis contre-vérification adverse des signaux forts",
  whenToUse: "Après scripts/dossiers.py, pour dater et sourcer les signaux des entreprises du périmètre avant scorer.py. Multi-agents : accord explicite de l'utilisateur avant de lancer",
  phases: [
    { title: 'Recherche', detail: "un agent par lot d'environ 15 entreprises : ICP, signaux datés et sourcés, adoption tech, personnes à contacter" },
    { title: 'Contre-vérification', detail: 'un sceptique par lot : tente de réfuter chaque signal fort' },
  ],
}

// args : le contenu de <campagne>/donnees/signaux/lots/args-recherche.json, écrit par scripts/dossiers.py
//   racine            chemin absolu du projet (obligatoire)
//   campagne          dossier de la campagne, absolu ou relatif à racine (obligatoire)
//   lots              [{id, file, n}] ; file absolu, ou relatif au dossier de la campagne (obligatoire)
//   date_reference    AAAA-MM-JJ : « aujourd'hui » pour les agents, base des fenêtres (obligatoire)
//   fenetre_mois      ancienneté maximale d'un signal, en mois (obligatoire)
//   offre             qui prospecte et pour vendre quoi (obligatoire)
//   cible             description de la cible, l'ICP (obligatoire)
//   categories        noms des catégories de secteur actives, parmi lesquelles l'agent choisit (obligatoire)
//   concurrents       (facultatif) qui vend la même chose que nous
//   exclusions        (facultatif) ce qui sort de la cible : texte ou liste de textes
//   zone, taille      (facultatifs) zone et effectif de la cible, en clair
//   persona           (facultatif) {entree, relais: []} : par qui entrer, vers qui router ensuite
//   cas_usage         (facultatif) cas d'usage de l'offre : pistes pour l'angle
//   registre_suisse   (facultatif, défaut true) : proposer l'outil du registre du commerce suisse
//   registres         (facultatif) registres du commerce consultables, par pays (texte)
//   domaines_registre (facultatif) domaines de registres officiels en plus de DOMAINES_REGISTRE
//   langue            (facultatif, défaut français) langue des textes rendus par les agents
//   python, skill     (facultatifs) défauts <racine>/.venv/bin/python et <racine>/.claude/skills/prospection-base-client
// Les agents ne modifient aucun fichier : leurs retours restent dans le journal du run, que lit
// scripts/apply_recherche.py (contrat : lot_id, entreprises, verdicts, id, index ; index -1 = adoption_tech).
const USAGE = "args attendus : le contenu de <campagne>/donnees/signaux/lots/args-recherche.json (scripts/dossiers.py) : {racine, campagne, lots: [{id, file, n}], date_reference, fenetre_mois, offre, cible, categories: [...], concurrents?, exclusions?, zone?, taille?, persona?, cas_usage?, registre_suisse?, registres?, domaines_registre?, langue?, python?, skill?}"
const A = typeof args === 'string' ? (() => { try { return JSON.parse(args) } catch (e) { return null } })() : args
if (!A || typeof A !== 'object' || Array.isArray(A)) throw new Error(USAGE)

const estTexte = v => typeof v === 'string' && v.trim() !== ''
const estAbsolu = p => /^(\/|[A-Za-z]:[\\/]|\\\\)/.test(p)
const listeTextes = v => Array.isArray(v) && v.every(x => typeof x === 'string')
const erreurs = []
if (!estTexte(A.racine) || !estAbsolu(A.racine)) erreurs.push('racine : chemin absolu du projet')
if (!estTexte(A.campagne)) erreurs.push('campagne : dossier de la campagne (absolu, ou relatif à racine)')
if (!Array.isArray(A.lots) || !A.lots.length || !A.lots.every(l => l && estTexte(l.id) && estTexte(l.file))) erreurs.push('lots : liste non vide de {id, file, n}')
if (!estTexte(A.date_reference) || !/^\d{4}-\d{2}-\d{2}$/.test(A.date_reference)) erreurs.push('date_reference : date AAAA-MM-JJ')
if (!Number.isInteger(A.fenetre_mois) || A.fenetre_mois < 1) erreurs.push('fenetre_mois : entier, 1 ou plus')
if (!estTexte(A.offre)) erreurs.push('offre : qui prospecte et pour vendre quoi')
if (!estTexte(A.cible)) erreurs.push('cible : description de la cible (ICP)')
if (!listeTextes(A.categories) || !A.categories.some(estTexte)) erreurs.push('categories : liste non vide des catégories de secteur')
if (A.concurrents !== undefined && typeof A.concurrents !== 'string') erreurs.push('concurrents : texte')
if (A.exclusions !== undefined && typeof A.exclusions !== 'string' && !listeTextes(A.exclusions)) erreurs.push('exclusions : texte ou liste de textes')
if (A.persona !== undefined && (typeof A.persona !== 'object' || A.persona === null || Array.isArray(A.persona))) erreurs.push('persona : {entree, relais: []}')
if (A.cas_usage !== undefined && !listeTextes(A.cas_usage)) erreurs.push('cas_usage : liste de textes')
if (A.domaines_registre !== undefined && !listeTextes(A.domaines_registre)) erreurs.push('domaines_registre : liste de domaines')
for (const k of ['zone', 'taille', 'registres', 'langue', 'python', 'skill']) {
  if (A[k] !== undefined && typeof A[k] !== 'string') erreurs.push(`${k} : texte`)
}
if (erreurs.length) throw new Error(`args invalides :\n- ${erreurs.join('\n- ')}\n${USAGE}`)

const sansBarre = p => p.replace(/[\\/]+$/, '')
const ROOT = sansBarre(A.racine)
const resoudre = (base, p) => (estAbsolu(p) ? sansBarre(p) : `${base}/${sansBarre(p).replace(/^\.\//, '')}`)
const CAMPAGNE = resoudre(ROOT, A.campagne)
const PY = A.python ? resoudre(ROOT, A.python) : `${ROOT}/.venv/bin/python`
const SKILL = A.skill ? resoudre(ROOT, A.skill) : `${ROOT}/.claude/skills/prospection-base-client`
const SIG = `"${PY}" "${SKILL}/scripts/outils_signaux.py"`
const WEB = `"${PY}" "${SKILL}/scripts/outils_web.py"`
const LOTS = A.lots.map(l => ({ id: l.id, n: l.n || 0, file: resoudre(CAMPAGNE, l.file) }))
const DATE = A.date_reference
const FENETRE = A.fenetre_mois
const LANGUE = estTexte(A.langue) ? A.langue : 'français'
const CATS = [...new Set([...A.categories.filter(estTexte), 'autre'])]
const EXCLUSIONS = (Array.isArray(A.exclusions) ? A.exclusions : [A.exclusions || '']).filter(estTexte)
const PERSONA = A.persona || {}
const ENTREE = estTexte(PERSONA.entree) ? PERSONA.entree : 'la direction (le décideur)'
const RELAIS = listeTextes(PERSONA.relais) ? PERSONA.relais.filter(estTexte) : []
const CAS = (A.cas_usage || []).filter(estTexte)
const REGISTRE_SUISSE = A.registre_suisse !== false
const REGISTRES = estTexte(A.registres) ? A.registres : "le registre du commerce du pays de l'entreprise"
const SOUS_TYPES = ['nouveau_dirigeant', 'depart_dirigeant', 'nouveau_cadre', 'succession', 'conseil', 'levee',
  'augmentation_capital', 'aide_publique', 'rachat', 'fusion_reprise', 'nouveau_site', 'recrutement', 'erp_numerique',
  'certification', 'lancement_produit', 'difficultes', 'dissolution']
// registres officiels : leurs faits bruts (capital, fusion, liquidation) ne sont pas contre-vérifiés ; une URL de
// registre que l'agent n'a pas vue est déclassée par scripts/apply_recherche.py (même liste de domaines)
const DOMAINES_REGISTRE = ['zefix.ch', 'zefix.admin.ch', 'shab.ch', 'amtsblattportal.ch', 'handelsregister.de',
  'unternehmensregister.de', 'bodacc.fr', 'infogreffe.fr', 'annuaire-entreprises.data.gouv.fr', 'registroimprese.it',
  'kbopub.economie.fgov.be', 'lbr.lu', 'oera.li', 'kvk.nl', 'company-information.service.gov.uk',
  ...(A.domaines_registre || [])].map(d => d.toLowerCase().replace(/^www\./, ''))

// date ISO moins n mois (jour ramené à la fin du mois si besoin), sans horloge : le run reste reproductible
function moinsMois(iso, n) {
  const [y, m, d] = iso.split('-').map(Number)
  const total = y * 12 + (m - 1) - n
  const yy = Math.floor(total / 12)
  const mm = total - yy * 12 + 1
  const bissextile = yy % 4 === 0 && (yy % 100 !== 0 || yy % 400 === 0)
  const fin = [31, bissextile ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mm - 1]
  return `${yy}-${String(mm).padStart(2, '0')}-${String(Math.min(d, fin)).padStart(2, '0')}`
}
const DEBUT = moinsMois(DATE, FENETRE)
const DEBUT_STRUCT = moinsMois(DATE, FENETRE + 12)

function hote(url) {
  const m = /^[a-z]+:\/\/([^/?#\s]+)/i.exec((url || '').trim())
  return m ? m[1].toLowerCase().replace(/^www\./, '') : ''
}
const estRegistre = url => { const h = hote(url); return !!h && DOMAINES_REGISTRE.some(d => h === d || h.endsWith(`.${d}`)) }

const PERSONNE = {
  type: 'object',
  properties: { nom: { type: 'string' }, role: { type: 'string' } },
  required: ['nom', 'role'],
}
const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    lot_id: { type: 'string' },
    entreprises: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          nom_verifie: { type: 'string' },
          activite: { type: 'string' },
          categorie: { type: 'string', enum: CATS },
          effectif_estime: { type: 'string' },
          groupe_parent: { type: 'string' },
          dans_icp: { type: 'boolean' },
          raison_hors_icp: { type: 'string' },
          signaux: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                famille: { type: 'string', enum: ['direction', 'financement', 'ma', 'croissance', 'projet', 'negatif'] },
                sous_type: { type: 'string', enum: SOUS_TYPES },
                date: { type: 'string' },
                resume: { type: 'string' },
                source_url: { type: 'string' },
                confiance: { type: 'string', enum: ['haute', 'moyenne', 'faible'] },
              },
              required: ['famille', 'sous_type', 'date', 'resume', 'source_url', 'confiance'],
            },
          },
          adoption_tech: {
            type: 'object',
            properties: {
              niveau: { type: 'string', enum: ['fort', 'moyen', 'faible', 'inconnu'] },
              preuves: { type: 'array', items: { type: 'string' } },
              concurrent: { type: 'boolean' },
            },
            required: ['niveau', 'preuves', 'concurrent'],
          },
          dirigeants: {
            type: 'array',
            items: {
              type: 'object',
              properties: { nom: { type: 'string' }, role: { type: 'string' }, depuis: { type: 'string' } },
              required: ['nom', 'role'],
            },
          },
          pourquoi_maintenant: { type: 'string' },
          angle: { type: 'string' },
          persona_cible: { type: 'string' },
          cibles: {
            type: 'object',
            properties: {
              entree: { type: 'array', items: PERSONNE },
              relais: { type: 'array', items: PERSONNE },
            },
            required: ['entree', 'relais'],
          },
          sources: { type: 'array', items: { type: 'string' } },
        },
        required: ['id', 'nom_verifie', 'activite', 'categorie', 'effectif_estime', 'dans_icp', 'signaux', 'adoption_tech',
          'dirigeants', 'pourquoi_maintenant', 'angle', 'persona_cible', 'cibles'],
      },
    },
  },
  required: ['lot_id', 'entreprises'],
}

const VERIF_SCHEMA = {
  type: 'object',
  properties: {
    lot_id: { type: 'string' },
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          index: { type: 'integer' },
          verdict: { type: 'string', enum: ['confirmé', 'réfuté', 'incertain'] },
          raison: { type: 'string' },
          date_corrigee: { type: 'string' },
        },
        required: ['id', 'index', 'verdict', 'raison'],
      },
    },
  },
  required: ['lot_id', 'verdicts'],
}

const HORS_ICP = [
  `grand groupe, au-delà de la taille limite${estTexte(A.taille) ? ' (voir Taille)' : ''}`,
  'simple filiale commerciale d\'un grand groupe sans production ni décision locale',
  ...EXCLUSIONS,
  'fermée ou en liquidation',
  `hors zone${estTexte(A.zone) ? ' (voir Zone)' : ''}`,
]
// rôles d'un « nouveau cadre clé » : rôles techniques usuels, puis relais du persona (sans doublon)
const ROLES_CLES = [...new Map(['IT', 'numérique', 'qualité', 'opérations', 'technique', ...RELAIS]
  .map(r => [r.toLowerCase(), r])).values()]

const OUTILS = [
  '- Recherche web : WebSearch et WebFetch (charge-les avec ToolSearch, requête "select:WebSearch,WebFetch"). C\'est l\'outil principal.',
  REGISTRE_SUISSE ? `- Registre du commerce suisse (officiel, entreprises suisses seulement) : ${SIG} zefix "<nom>"   -> fiche, url à citer, absorptions, publications récentes` : '',
  `- Registres du commerce consultables (par la recherche web) : ${REGISTRES}.`,
  `- Actualités datées (DuckDuckGo) : ${SIG} news "<requête>" [--region CH]`,
  `- Secours DuckDuckGo : ${WEB} search "<requête>" [--region CH]   et   ${WEB} peek <url>`,
  "- N'ouvre pas linkedin.com avec les outils locaux (une collecte LinkedIn peut tourner depuis la même adresse IP) ; les extraits LinkedIn vus par la recherche web suffisent.",
  'Seul ce que tes outils affichent compte comme vu : si une sortie trop longue est enregistrée dans un fichier, relis ce fichier avec Read.',
].filter(Boolean).join('\n')

const CONTEXTE = `Contexte : une campagne de prospection B2B.
Qui prospecte, et pour vendre quoi : ${A.offre}
Cible (ICP) : ${A.cible}${estTexte(A.zone) ? `\nZone : ${A.zone}` : ''}${estTexte(A.taille) ? `\nTaille : ${A.taille}` : ''}${EXCLUSIONS.length ? `\nHors cible : ${EXCLUSIONS.join(' ; ')}` : ''}
Date de référence (aujourd'hui) : ${DATE}.`

function researchPrompt(lot) {
  return `Tu es agent de recherche pour cette campagne.
${CONTEXTE}
Lot ${lot.id} : ${lot.n || 'plusieurs'} entreprises.

FICHIER À LIRE EN PREMIER (outil Read) : ${lot.file}
C'est une liste JSON de dossiers pré-collectés par entreprise :
- "site_web", "linkedin", "ville" : identité donnée par la liste ; "icp_pre" : pré-qualification automatique (pays, canton, secteur, taille, fit sur 9) ; "activite_liste" : activité donnée par la liste.
- "registre" (si présent) : registre du commerce et événements publiés depuis 36 mois au moins (OFFICIEL et fiable sur les faits : inscriptions, radiations, capital, fusions, liquidations ; à toi d'interpréter le rôle réel). "url" : la fiche, à citer comme source.
- "linkedin_profil" / "linkedin_posts" : page LinkedIn publique (taille, secteur, derniers posts datés). Peut manquer.
- "site" : stack technique du site, langues, page carrières (postes tech), signaux datés.
- "actualites" / "signaux_web_candidats" / "signaux_linkedin_candidats" : détections AUTOMATIQUES par mots-clés, bruitées (homonymes, profils génériques). À confirmer ou écarter.

OBJECTIF : pour CHAQUE entreprise, établir les signaux qui justifient de la contacter maintenant, avec date et source, son degré d'adoption technologique (early adopter ou pas) et les personnes à contacter.

1. Identité et ICP : activité réelle (1 phrase factuelle), categorie (une de : ${CATS.join(', ')} ; « autre » si aucune ne convient), effectif estimé avec sa source (page LinkedIn « 51-200 employés », site, presse), groupe parent éventuel. dans_icp = false si l'entreprise sort de la cible : ${HORS_ICP.join(' ; ')}. raison_hors_icp : la raison en une phrase ("" sinon).
2. Signaux datés de ${DEBUT} à ${DATE} (signale aussi un événement structurant de ${DEBUT_STRUCT} à ${DEBUT} : il sera pondéré moins) :
   - direction : nouveau CEO / directeur général / gérant / administrateur délégué / nouveau propriétaire (nouveau_dirigeant), départ (depart_dirigeant), transmission familiale ou reprise par le management (succession), nouveau cadre clé : ${ROLES_CLES.join(', ')} (nouveau_cadre), changement de président du conseil d'administration (conseil). Avec le registre : dis si le nouveau « directeur » est bien le patron (presse, page équipe, post LinkedIn) ; sinon nouveau_cadre.
   - financement : levée de fonds avec montant et investisseurs (levee), augmentation de capital (augmentation_capital), aide publique : programme public d'innovation, subvention nationale, régionale ou européenne (aide_publique).
   - ma : rachat par un groupe ou un fonds, acquisition d'une autre société (rachat), fusion ou reprise (fusion_reprise).
   - croissance : nouveau site, usine ou extension (nouveau_site), vague de recrutement (recrutement).
   - projet : projet ERP, MES ou numérique (erp_numerique), certification récente (certification), lancement d'un produit majeur (lancement_produit).
   - negatif : faillite, liquidation, sursis, licenciements, restructuration, difficultés financières (difficultes, dissolution).
   Pour chaque signal : date (AAAA-MM-JJ ou AAAA-MM), résumé en ${LANGUE} (1 phrase factuelle), source_url d'une page que tu as RÉELLEMENT consultée et qui le dit (registre : le champ url du dossier, ou l'url affichée par l'outil du registre), confiance « haute » (officiel, presse, site de l'entreprise), « moyenne » ou « faible ». Écarte les candidats automatiques faux (homonyme, page générique, date hors fenêtre) : ne les recopie pas.
3. adoption_tech : « fort » = preuve concrète d'early adopter (IA, vision, IoT, jumeau numérique, robotique dans les produits OU l'exploitation, projet industrie 4.0, transformation numérique récente, outils modernes : configurateur, portail client, marketing automation, recrutement data / logiciel / automation, programmes d'innovation). « moyen » = maturité numérique correcte sans plus. « faible » = traditionnel. preuves : 1 à 3 faits concrets avec leur source. concurrent = true si l'entreprise vend elle-même ce que nous vendons (voir l'offre${estTexte(A.concurrents) ? ` ; à repérer : ${A.concurrents}` : ''}) : concurrent ou partenaire, pas un prospect.
4. dirigeants : noms et rôles (et « depuis » si connu), d'après le registre, LinkedIn ou le site.
5. pourquoi_maintenant : 1 à 2 phrases factuelles en ${LANGUE}, la raison de contacter maintenant ("" si aucun signal). angle : 1 hypothèse de cas d'usage de notre offre adaptée à leur métier${CAS.length ? ` (pistes : ${CAS.join(', ')})` : ''}, au conditionnel, sans chiffre ni promesse.
6. Qui contacter : on entre par : ${ENTREE}${RELAIS.length ? ` ; puis on route vers : ${RELAIS.join(', ')}` : ''}. cibles.entree : la ou les personnes d'entrée, [{nom, role}] ; cibles.relais : les relais, dans l'ordre de préférence. nom = « Prénom Nom » seulement si tu l'as vu dans une source, sinon nom vide et le rôle en clair. persona_cible : la même chose en une ligne, au format « Entrée : Prénom Nom (rôle) ; relais : rôle, rôle ».

OUTILS (à lancer avec Bash, une commande par appel) :
${OUTILS}
Budget : 3 à 6 recherches par entreprise, davantage pour les fits élevés (icp_pre.fit au moins 7,5) ; arrête quand le tableau est clair. Ne modifie aucun fichier et n'en crée aucun.

RÈGLES : rien d'inventé ; pas de signal sans date ni source consultée ; « inconnu » plutôt qu'une supposition. Un contrôle automatique cherche chaque source_url, telle quelle, dans tes sorties d'outils et dans les éléments de ton lot (fiche du registre, posts, actualités) : cite l'URL exacte de la page qui dit le fait, jamais une URL reconstruite ni la seule adresse du site ou de la page LinkedIn de l'entreprise. Un signal sans source_url, ou dont la page n'y apparaît pas, est déclassé. Textes en ${LANGUE} ; jamais de tiret cadratin ni demi-cadratin (caractères U+2014 et U+2013). Couvre les ${lot.n || ''} entreprises du fichier, avec leur "id" exact, et renvoie lot_id = "${lot.id}".`
}

// signaux forts à contre-vérifier : direction (patron), financement, rachat, négatif, projet numérique, tech « fort »
function claimsOf(res) {
  const claims = []
  for (const e of res.entreprises || []) {
    (e.signaux || []).forEach((s, i) => {
      const fort = (s.famille === 'direction' && ['nouveau_dirigeant', 'succession', 'depart_dirigeant'].includes(s.sous_type)) ||
        ['financement', 'ma', 'negatif'].includes(s.famille) || (s.famille === 'projet' && s.sous_type === 'erp_numerique')
      // faits bruts d'un registre officiel (capital, fusion, liquidation) : pas de contre-vérification ;
      // l'interprétation d'un changement de direction (qui est vraiment le patron ?) reste vérifiée
      if (estRegistre(s.source_url) && s.famille !== 'direction') return
      if (fort) claims.push({ id: e.id, nom: e.nom_verifie, index: i, famille: s.famille, sous_type: s.sous_type,
        date: s.date, resume: s.resume, source_url: s.source_url })
    })
    if (e.adoption_tech && e.adoption_tech.niveau === 'fort') {
      claims.push({ id: e.id, nom: e.nom_verifie, index: -1, famille: 'adoption_tech', sous_type: 'fort',
        date: '', resume: (e.adoption_tech.preuves || []).join(' ; '), source_url: (e.sources || []).slice(0, 3).join(' ') })
    }
  }
  return claims
}

function verifPrompt(lot, claims) {
  return `Tu es contre-vérificateur ADVERSE pour cette campagne de prospection.
${CONTEXTE}
Un agent de recherche a produit les signaux ci-dessous (lot ${lot.id} ; dossiers des entreprises dans ${lot.file}).
Ton travail : essayer de RÉFUTER chacun. Un faux signal fait perdre du temps commercial ; mieux vaut « incertain » que « confirmé » à tort.

Pour chaque signal :
1. Ouvre la source (WebFetch, ou ${WEB} peek <url>).${REGISTRE_SUISSE ? ` Pour un signal issu du registre suisse : ${SIG} zefix "<nom>".` : ''}
2. Vérifie : (a) la source dit bien cela ; (b) c'est la MÊME entreprise (pas un homonyme, pas la maison mère étrangère, pas un client ou un partenaire cité) ; (c) la date est juste et dans la fenêtre (depuis ${DEBUT}, ou de ${DEBUT_STRUCT} à ${DEBUT} pour un événement structurant) ; (d) pour nouveau_dirigeant : le rôle est vraiment celui du patron (CEO, directeur général, gérant, administrateur délégué, nouveau propriétaire), pas un simple fondé de pouvoir ; (e) pour adoption_tech « fort » (index = -1) : les preuves sont concrètes et propres à l'entreprise (pas du marketing générique).
3. Si la source ne s'ouvre pas, cherche une seconde source (WebSearch, ou ${WEB} search "<requête>"). Toujours rien : « incertain ».
Verdicts : « confirmé » (preuve solide vue par toi), « réfuté » (faux, autre entité, ou date hors fenêtre), « incertain ». Donne une raison courte ; date_corrigee si la vraie date diffère. Un contrôle automatique ramène à « incertain » tout « confirmé » dont l'URL exacte n'apparaît pas dans tes sorties d'outils : ouvre la source elle-même.
Ne modifie aucun fichier. N'ouvre pas linkedin.com avec les outils locaux. Textes en ${LANGUE}, sans tiret cadratin ni demi-cadratin. Renvoie lot_id = "${lot.id}" et un verdict par signal, avec le même id et le même index.

SIGNAUX À VÉRIFIER (${claims.length}) :
${JSON.stringify(claims, null, 1)}`
}

// chaque lot passe à sa contre-vérification dès que sa recherche est rendue, sans attendre les autres
const results = await pipeline(
  LOTS,
  lot => agent(researchPrompt(lot), { label: `recherche:${lot.id}`, phase: 'Recherche', schema: RESEARCH_SCHEMA }),
  (res, lot) => {
    if (!res) return null
    const claims = claimsOf(res)
    log(`${lot.id} : ${(res.entreprises || []).length} entreprises, ${claims.length} signaux forts à contre-vérifier`)
    if (!claims.length) return { lot: lot.id, recherche: res, verifs: { lot_id: lot.id, verdicts: [] } }
    return agent(verifPrompt(lot, claims), { label: `verif:${lot.id}`, phase: 'Contre-vérification', schema: VERIF_SCHEMA })
      .then(v => ({ lot: lot.id, recherche: res, verifs: v || { lot_id: lot.id, verdicts: [] }, sans_verif: !v }))
  },
)
const ok = results.filter(Boolean)
const manquants = LOTS.filter(l => !ok.find(r => r.lot === l.id)).map(l => l.id)
if (manquants.length) log(`Lots sans résultat (à relancer par reprise) : ${manquants.join(', ')}`)
const sansVerif = ok.filter(r => r.sans_verif).map(r => r.lot)
if (sansVerif.length) log(`Contre-vérification en échec (signaux gardés avec la confiance « agent ») : ${sansVerif.join(', ')}`)
return {
  lots: ok.map(r => ({
    lot: r.lot,
    entreprises: (r.recherche.entreprises || []).length,
    signaux: (r.recherche.entreprises || []).reduce((n, e) => n + (e.signaux || []).length, 0),
    verdicts: (r.verifs.verdicts || []).length,
    refutes: (r.verifs.verdicts || []).filter(v => v.verdict === 'réfuté').length,
  })),
  manquants,
  sans_contre_verification: sansVerif,
  fenetre: { debut: DEBUT, structurant_depuis: DEBUT_STRUCT, reference: DATE },
  suite: `Intégrer : "${PY}" "${SKILL}/scripts/apply_recherche.py" --campagne "${CAMPAGNE}" <dossier de ce run ou son journal.jsonl> (avec les journaux des runs précédents de la campagne, dans l'ordre), puis "${PY}" "${SKILL}/scripts/scorer.py" --campagne "${CAMPAGNE}"`,
}
