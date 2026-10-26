# Prospection B2B avec Claude Code (skill `prospection-base-client`)

Ce dossier est un skill pour Claude Code. Il mène une campagne de prospection B2B de bout en bout : de la
définition de la cible jusqu'au fichier d'appel remis au commercial. Ce README s'adresse à la personne qui
l'installe. Les consignes de Claude sont dans `SKILL.md`.

## Ce que fait le skill

Neuf étapes. Chacune peut se lancer seule, dès que ses fichiers d'entrée existent.

| # | Étape | Ce que vous obtenez |
|---|---|---|
| 1 | Cible et persona | la cible (ICP) et le persona du décideur, validés avec vous |
| 2 | Trouver les entreprises | une liste d'entreprises de la cible : trouvée sur le web par des agents (avec une preuve publique pour chacune), ou tirée d'un export Apollo ou d'une autre liste |
| 3 | Site et LinkedIn | le site officiel et la page LinkedIn de chaque entreprise (pour une liste qui n'en a pas) |
| 4 | Vérification (facultative) | chaque site et chaque page LinkedIn vérifiés par des agents, puis contre-vérifiés |
| 5 | Signaux et priorités | des signaux datés et sourcés (registre du commerce, LinkedIn, site, actualités, recherche par agents), des tiers A à D et un score A, B, C |
| 6 | Contacts Apollo | les bonnes personnes de chaque entreprise, retrouvées dans Apollo, validées par vous, puis créées dans des listes Apollo |
| 7 | Réinjection dans Apollo | signal et date, source, première phrase et score dans des champs de contact Apollo |
| 8 | Séquence et ordre d'appel | l'ordre d'appel (langue, téléphone, priorité) et un plan de séquence sur trois semaines |
| 9 | Scripts et fichier d'appel | un script d'appel par contact et un fichier d'appel (Excel et CSV) pour le commercial |

Comment ça marche :

- Les **scripts Python** font le travail répétitif : recherche DuckDuckGo, lecture des sites, pages LinkedIn
  publiques, registre du commerce suisse, API Apollo. Ils gardent un cache : une relance ne refait (et ne
  refacture) rien.
- Les **agents** de Claude Code font les recherches qui demandent du jugement (outil Workflow). Un contrôle
  mécanique écarte toute URL qu'un agent n'a pas réellement vue.
- Tout est réglé dans un fichier `campagne.toml` (votre offre, votre cible, votre persona). Toutes les sorties
  vont dans un dossier de campagne, jamais dans le dossier du skill.
- Claude demande votre accord avant toute dépense (crédits Apollo, tokens des workflows) et avant toute écriture
  dans Apollo. Il ne rédige aucun message sans demande.

## Prérequis

- **Claude Code**. Les étapes à agents utilisent son outil Workflow et ses sous-agents.
- **Python 3.11 ou plus** (vérifiez avec `python3 --version`).
- Un accès internet : DuckDuckGo, sites des entreprises, LinkedIn public, registre du commerce suisse, Apollo.
- **Un compte Apollo avec accès à l'API**, seulement pour les étapes 6 et 7. L'accès à l'API dépend de votre
  offre Apollo.
- **Node.js n'est pas requis** : les fichiers `workflows/*.js` sont exécutés par Claude Code.
- Les commandes sont écrites pour macOS et Linux. Windows n'a pas été testé : utilisez `.venv\Scripts\python.exe`
  à la place de `.venv/bin/python`.

## Installation

1. **Copier le dossier du skill**, au choix :
   - dans votre projet (recommandé, les commandes de cette documentation supposent cet emplacement) :

     ```bash
     cd <votre projet>
     mkdir -p .claude/skills
     cp -R <dossier décompressé>/prospection-base-client .claude/skills/
     ```

   - ou pour tous vos projets : `~/.claude/skills/prospection-base-client/`.

2. **Créer l'environnement Python à la racine du projet** et installer les paquets :

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r .claude/skills/prospection-base-client/requirements.txt
   ```

   Si `python3` est plus ancien que 3.11, utilisez un Python plus récent (`python3.12 -m venv .venv`, par
   exemple). Paquets installés (`requirements.txt`) :

   | Paquet | Sert à |
   |---|---|
   | `requests` | API Apollo, sites web, registre suisse |
   | `beautifulsoup4`, `lxml` | lecture des pages web |
   | `ddgs` | recherche DuckDuckGo, sans clé |
   | `openpyxl` | fichier d'appel au format Excel |

3. **Contrôler l'installation** (sans réseau) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py
   ```

   Le script affiche une ligne par contrôle (✓ bon, ✗ à corriger, ! à revoir) et la prochaine action.

4. **Ouvrir une nouvelle session Claude Code dans le projet.** Le skill y est disponible : Claude le charge quand
   vous parlez de prospection, ou quand vous le nommez.

Lancez toujours les scripts avec `.venv/bin/python`, depuis la racine du projet. Selon votre système, `python3`
peut être un autre interpréteur, sans `ddgs`.

**Si le skill est ailleurs** (par exemple dans `~/.claude/skills/`) :

- dans toutes les commandes, remplacez `.claude/skills/prospection-base-client` par le vrai chemin
  (`~/.claude/skills/prospection-base-client`) ;
- créez quand même le `.venv` à la racine du projet ;
- dans les args du workflow de découverte (étape 2), passez `skill` (le chemin du skill) et `python` (si le
  `.venv` n'est pas à la racine). Les autres workflows reçoivent ces chemins des scripts qui préparent leurs args.

## Clé API Apollo

Seules les étapes 6 et 7 l'utilisent. Les étapes 1 à 5, 8 et 9 marchent sans clé.

1. **Créer la clé dans Apollo** : Settings > Integrations > API Keys, puis « Create new key ». Donnez un nom et
   une description, puis :
   - le plus simple : activez « Set as master key » (accès à tous les points d'accès) ;
   - sinon, cochez seulement les points d'accès du tableau ci-dessous. Un point d'accès manquant donne une
     erreur 403 : le script affiche alors le chemin refusé.
2. **Créer le fichier `.env` à la racine du projet**, à partir du modèle :

   ```bash
   cp .claude/skills/prospection-base-client/exemple.env .env
   ```

   puis collez la clé après le signe égal : `APOLLO_API_KEY=votre_cle`. Une variable d'environnement
   `APOLLO_API_KEY` marche aussi. Les scripts cherchent la clé dans cet ordre : variable d'environnement, `.env`
   du dossier courant ou d'un dossier parent, `.env` du dossier du skill (déconseillé : il partirait avec un zip).
3. **Ne partagez jamais ce fichier et ne le mettez jamais dans git.** Si le projet est un dépôt git, ajoutez la
   ligne `.env` au `.gitignore` du projet. `verifier_installation.py` fait le contrôle : il signale un `.env` que
   git n'ignore pas, et ne dit rien hors d'un dépôt git. Les scripts n'affichent jamais la clé :
   `verifier_installation.py` dit seulement si elle est présente.

Points d'accès utilisés, par script (les noms entre guillemets inversés dans la dernière colonne sont ceux de la
documentation Apollo ; pour les autres, cochez le point d'accès qui porte ce chemin) :

| Script | Quand | Points d'accès appelés | Nom du droit dans Apollo |
|---|---|---|---|
| `creer_comptes.py` | avec `--go` seulement | `POST /api/v1/accounts/bulk_create`, `POST /api/v1/labels/add_entity_ids_to_label_names` | |
| `chercher_contacts.py` | toujours (lecture, 0 crédit) | `GET /api/v1/labels`, `POST /api/v1/accounts/search`, `POST /api/v1/mixed_people/api_search` | `api/v1/labels/index`, `api/v1/mixed_people/api_search` |
| `enrichir_et_creer.py` | avec `--go` seulement | `POST /api/v1/people/bulk_match` (payant), `GET /api/v1/webhook_result/{id}` (mobiles seulement), `GET /api/v1/labels`, `POST /api/v1/labels`, `POST /api/v1/contacts/bulk_create`, `POST /api/v1/labels/add_entity_ids_to_label_names`, `POST /api/v1/contacts/search` | `api/v1/people/bulk_match`, `api/v1/labels/index`, `api/v1/contacts/bulk_create` |
| `exporter_listes.py` | toujours (lecture, 0 crédit) | `GET /api/v1/labels`, `POST /api/v1/contacts/search` | `api/v1/labels/index` |
| `reinjecter_apollo.py` | avec `--go` seulement | `GET /api/v1/typed_custom_fields`, `POST /api/v1/fields`, `POST /api/v1/contacts/bulk_update` | `api/v1/typed_custom_fields/index`, `api/v1/fields/create`, `api/v1/contacts/bulk_update` |

**Coûts en crédits Apollo :**

- recherche de personnes et de comptes : 0 crédit (la recherche ne donne ni email ni téléphone, et masque le nom
  de famille) ;
- enrichissement (`people/bulk_match`) : 1 crédit par personne trouvée, 0 si elle n'est pas trouvée ; 8 crédits de
  plus par numéro de mobile, seulement si vous les demandez (`apollo.mobiles` ou `--mobiles`) ; la documentation
  Apollo annonce de 1 à 9 crédits par personne. Les scripts ne demandent jamais d'email personnel et n'activent
  jamais les options « waterfall » (certains fournisseurs facturent chaque recherche, même sans résultat) ;
- création de comptes, de contacts, de listes et de champs, mise à jour de contacts : 0 crédit selon la
  documentation Apollo, mais ce sont des écritures dans votre compte, faites seulement avec `--go`, après
  votre accord ;
- repère d'une campagne précédente : environ 2 crédits par entreprise retenue (environ 230 crédits pour environ
  120 entreprises).

Les scripts limitent leur débit à 80 % de quotas Apollo courants, écrits dans `scripts/apollo_api.py`
(`LIMITES`). Si votre compte a des quotas plus bas, baissez ces valeurs : Apollo les affiche dans son tableau de
bord développeur, onglet « Usage ».

## Fichiers à compléter

### `campagne.toml`

Copiez `config/campagne.exemple.toml` dans le dossier de la campagne sous le nom `campagne.toml`. Les valeurs
écrites sont un **exemple fictif** (une PME qui vend un logiciel de planification de la maintenance aux PME
industrielles de Suisse romande) : remplacez chaque valeur marquée « À COMPLÉTER ». Syntaxe : texte entre
guillemets, listes entre crochets, `#` pour un commentaire. `verifier_installation.py --campagne` signale les
valeurs d'exemple restées en place, les clés mal orthographiées et les erreurs de type.

Colonne « Obligatoire » : **oui** = à remplir avant la première étape indiquée ; **non** = une valeur par défaut
s'applique.

**`[campagne]`**

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `nom` | nom court de la campagne : titres des rapports, des scripts et du fichier d'appel, contexte des agents | `"maintenance-romandie"` | non (défaut : nom du dossier) | 4, 5, 9 |
| `date_reference` | date qui sert d'« aujourd'hui » : fenêtres des signaux, « moins de 12 mois », début du plan de séquence. Format AAAA-MM-JJ | `""` (vide = aujourd'hui) | non | 5, 7, 8, 9 |

**`[offre]`** : qui prospecte, pour vendre quoi.

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `societe` | votre société | `"Exemple SA"` | oui | 2 (contexte des agents), 4, 5, 9 |
| `description` | ce que vous vendez, en une phrase | `"Nous éditons un logiciel qui planifie la maintenance préventive..."` | oui | 2, 4, 5, 9 |
| `argument_cle` | l'argument décisif | `"Les arrêts de production imprévus coûtent cher..."` | oui, avant l'étape 9 | 9 |
| `preuves` | résultats clients **réels**, jamais inventés : liste de `{ cas = "...", phrase = "..." }` | `[{ cas = "planification", phrase = "Chez un sous-traitant de Neuchâtel, ..." }]` | recommandé (sans preuve, les scripts ne citent ni client ni chiffre) | 5 (cas d'usage pour l'angle), 9 |
| `appelant` | qui appelle et signe | `"Prénom Nom"` | oui, avant l'étape 9 | 9 |
| `presentation_appelant` | réponse à « vous êtes qui ? » | `"une société de logiciels à Lausanne, ..."` | oui, avant l'étape 9 | 9 |
| `question_ouverte` | la question qui ouvre la conversation | `"Aujourd'hui, comment planifiez-vous la maintenance de vos machines ?"` | oui, avant l'étape 9 | 9 |
| `cta` | une seule question, avec deux créneaux | `"20 minutes en visio ... : mardi 10 h ou jeudi 14 h ?"` | oui, avant l'étape 9 | 9 |
| `lien_agenda` | lien de prise de rendez-vous | `""` | non | 9 |
| `signature_email` | signature des emails | `"Prénom Nom, Exemple SA"` | non (aucun script ne la lit : emails rédigés sur demande) | 8 |
| `concurrents` | qui vend la même chose que vous : ces entreprises plafonnent en tier B et ne passent jamais en score A | `"éditeurs de logiciels de maintenance (GMAO), ..."` | non | 5, 9 |
| `ne_jamais_dire` | phrases ou sujets interdits ; les phrases exactes sont contrôlées dans les scripts et le fichier d'appel | `["le nom d'un client sans son accord"]` | non | 9 |

**`[cible]`** : l'ICP, quelles entreprises viser.

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `description` | la cible en une phrase, pour les agents | `"PME industrielles de 10 à 200 personnes qui fabriquent en Suisse romande (...)"` | oui | 2, 4, 5 |
| `pays` | pays visés, codes ISO à deux lettres | `["CH"]` | recommandé (vide : la zone ne compte pas dans le fit) | 3 (région DuckDuckGo), 4, 5, 6, 9 |
| `regions_prioritaires` | régions les mieux notées : codes de canton pour la Suisse, ou `"romande"`, `"alémanique"`, `"italienne"` | `["GE", "VD", "NE", "JU", "FR", "VS"]` | non (vide : tout le pays) | 5 |
| `pays_voisins` | pays acceptés avec une note faible ; tout autre pays est hors zone | `["FR", "DE", "IT", "AT", "LI"]` | non | 4, 5, 6 |
| `taille_min`, `taille_max` | effectif idéal (note 3) | `10`, `200` | non (défauts 10 et 200) | 5 |
| `taille_limite` | au-delà : grand groupe, exclu | `1000` | non (défaut 1000) | 5 |
| `profil_secteurs` | règles de secteur fournies : `"industrie"` (fabricants notés 3, distributeurs et services moins) ou `"aucun"` | `"industrie"` | non (défaut `"industrie"`) | 5 |
| `[[cible.secteurs]]` | règles en plus, testées avant le profil : `nom`, `note` (0 à 3), `motifs` (expressions régulières, sans tenir compte de la casse), `exclure` (true sort de la cible) | `nom = "imprimerie"`, `note = 3`, `motifs = ["imprimerie", "druckerei"]` | non | 5 |
| `exclusions` | ce qui sort de la cible, en clair, pour les agents | `["distributeurs et revendeurs sans production", ...]` | non | 2, 5 |

**`[persona]`** : qui contacter dans chaque entreprise.

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `entree` | famille du premier contact, le décideur | `"direction"` | non (défaut `"direction"`) | 2 (ordre des contacts importés), 5, 6, 9 |
| `relais` | familles des contacts relais, par ordre de préférence | `["maintenance", "production", "qualite"]` | non | 5, 6, 8, 9 |
| `[persona.titres]` | intitulés de poste en plus (français, anglais, allemand, italien) pour une famille fournie, ou une nouvelle famille | `maintenance = ["responsable maintenance", "maintenance manager", "Leiter Instandhaltung"]` | oui pour une famille qui n'est pas fournie | 2, 6 |

Familles fournies : `direction`, `qualite`, `it`, `production`, `technique`, `service`, `ventes`, `finance`,
`achats`, `projet`.

**`[signaux]`**

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `fenetre_mois` | ancienneté maximale d'un signal, en mois | `24` | non (défaut 24) | 5, 9 |
| `registre_suisse` | interroger le registre du commerce suisse (Zefix) pour les entreprises suisses | `true` | non (défaut true) | 5 |
| `logiciels` | logiciels à repérer chez les prospects (colonne « Logiciels » du fichier d'appel) | `["SAP", "Odoo", "Microsoft Dynamics"]` | non (vide : pas de recherche de logiciels) | 5, 6, 9 |

**`[apollo]`** : la clé ne va jamais ici, mais dans `.env`.

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `liste_comptes` | nom exact de la liste de comptes Apollo | `"Industrie romande · comptes · Novembre"` | oui, avant l'étape 6 | 6 |
| `liste_contacts` | nom de base des listes de contacts, « Segment · Persona · Mois » ; les listes « - entrée » et « - relais » sont créées en plus | `"Industrie romande · Direction · Novembre"` | oui, avant l'étape 6 | 6, 8, 9 |
| `pays_contacts` | pays où un contact peut être basé (sauf les vrais dirigeants) | `["CH", "FR", "DE", "IT", "AT", "LI"]` | non (défaut : `pays` et `pays_voisins`) | 6 |
| `mobiles` | demander les numéros de mobile (8 crédits par numéro) | `false` | non (défaut false) | 6 |

**`[appels]`**

| Clé | Rôle | Exemple | Obligatoire | Lue à l'étape |
|---|---|---|---|---|
| `langues` | langues parlées par l'appelant : ces contacts passent en premier ; la première langue sert aussi aux agents | `["fr"]` | non (défaut `["fr"]`) | 5, 6, 8, 9 |

### Autres fichiers du dossier de campagne (tous facultatifs)

Fichiers CSV en UTF-8, séparés par des virgules ou des points-virgules, avec une ligne d'en-têtes.

| Fichier | Contenu | Colonnes | Lu à l'étape |
|---|---|---|---|
| `persona.md` | la réponse validée du prompt persona (intitulés, motivations, objections, calendrier, signaux d'achat) | texte libre | 1, puis relu par Claude |
| `exclure.csv` | vos clients et partenaires actuels : jamais prospectés | `nom`, `site` (reconnus aussi : `entreprise`, `company`, `name`, `raison sociale` ; `website`, `domaine`, `domain`) | 2 |
| `corrections.csv` | corrections manuelles de site et de LinkedIn | `nom`, `site`, `linkedin`. Cellule vide : rien à corriger ; une URL : remplace ; `-` : vide le champ ; `?` : garde la valeur trouvée avec une confiance basse ; `site` dans `linkedin` : relit la page LinkedIn sur le site | 3 |
| `arbitrages.csv` | vos décisions après la vérification par agents | `nom`, `champ` (`site`, `linkedin`, `nom_officiel`, `pays`, `ville`, `activite`, `exclure`, `a_revoir`, `note`), `valeur` (`aucun` vide le champ), `statut`, `note` | 4 |
| `noms-ambigus.csv` | noms trop courants, cherchés avec la ville dans les actualités | `nom` | 5 |
| `donnees/signaux/logiciels.json` | écrit par `collect_logiciels.py` (étape 5), à relire : les logiciels repérés chez les prospects. Seuls `probable` et `confirmé` sont cités dans le fichier d'appel | par entreprise : `statut` (`indice` à passer à `probable`, `confirmé` ou `aucun`), `logiciel`, `url`, `extrait` à corriger au besoin, `relu` = `oui` | 9 |
| `apollo/comptes-manuels.csv` | une entreprise dont le compte Apollo porte un autre nom | `entreprise`, `compte_apollo` (un morceau de chaque nom suffit) | 6 |
| `phrases-signal.csv` | les premières phrases des comptes A, rédigées sur votre demande | `id` ou `nom`, `phrase_signal` | 7, seulement avec `--phrases campagnes/<nom>/phrases-signal.csv` (à repasser à chaque relance de `reinjecter_apollo.py`, aperçu compris : sans l'option, `base-abc.csv` perd les phrases) |
| `appels/langue-contacts.json` | l'avis d'agents sur la langue de chaque contact | `{contact_id: {parle, langue_principale, raison}}` | 8 |
| `appels/corrections.json` | corrections du fichier d'appel | `{id: {pourquoi_maintenant, a_savoir}}` | 9 |
| `apprentissages.md` | enseignements datés de la campagne, au format « - [AAAA-MM-JJ] fait -> action » | texte libre | toutes |

## Démarrer une campagne

1. **Créer le dossier et copier la configuration**, depuis la racine du projet :

   ```bash
   mkdir -p campagnes/ma-campagne
   cp .claude/skills/prospection-base-client/config/campagne.exemple.toml campagnes/ma-campagne/campagne.toml
   ```

2. **Compléter `campagne.toml`** (section précédente) et, si vous avez des clients ou des partenaires,
   `exclure.csv`.
3. **Contrôler**, jusqu'à ce qu'aucune ligne ✗ ne reste :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py --campagne campagnes/ma-campagne
   ```

4. **Dans Claude Code**, demandez : « lance l'étape 1 du skill prospection-base-client pour la campagne
   campagnes/ma-campagne ». Claude valide d'abord le persona avec vous, puis avance étape par étape. Il vous
   demande votre accord avant chaque dépense et avant chaque écriture dans Apollo.

Pour savoir où en est une campagne, relancez le contrôle : il lit les fichiers présents et donne l'étape suivante.

## Les étapes et leurs commandes

Toutes les commandes se lancent depuis la racine du projet. `--help` sur un script donne toutes ses options.
Les workflows se lancent par Claude, avec l'outil Workflow de Claude Code (`scriptPath` = le fichier `.js`,
`args` = le contenu du fichier d'args préparé par le script indiqué). Le dossier d'un run se retrouve avec
`find ~/.claude/projects -type d -path '*workflows*' -name '<runId>'`.

**Étape 1, cible et persona.** Pas de script : Claude pose le prompt persona avec vous, puis vous rangez la
réponse dans `persona.md` et les familles dans `[persona]`.

**Étape 2, trouver les entreprises.** Découverte web (workflow, sur accord) :

```bash
# workflow : workflows/decouverte-entreprises.js, args {racine, campagne, icp, contexte, segments, exclusions?, sources?, max_complements?, cible_par_agent?, python?, skill?}
.venv/bin/python .claude/skills/prospection-base-client/scripts/consolider_decouverte.py --campagne campagnes/<nom> <dossier du run> [--deja <liste.csv>] [--exclure <csv>] [--linkedin <csv>] [--garder-hors-cible] [--garder-non-vues] [--ajouter]
.venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py --campagne campagnes/<nom>   # pages LinkedIn lues sur les sites, puis relancer la consolidation
```

Liste existante ou export Apollo (comptes ou contacts) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/importer_liste.py --campagne campagnes/<nom> <export.csv> [--exclure <csv>] [--deja <liste.csv>] [--col-nom "<en-tête>"] [--ajouter]
```

`--ajouter` combine les deux sources : les fichiers existants sont gardés, seules les entreprises et les contacts
nouveaux s'ajoutent, et une entreprise déjà exclue comme client ou partenaire le reste. Sans `--ajouter`, un
ancien `apollo/contacts-importes.csv` est renommé en `contacts-importes.precedent.csv`. Sorties :
`entreprises-toutes.csv` (tout, à relire) et `entreprises.csv` (la liste retenue).

**Étape 3, site et LinkedIn** (pour une liste sans sites) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_sites.py --campagne campagnes/<nom> [--workers 4] [--limite N]
```

**Étape 4, vérification par agents** (facultative, workflows sur accord) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/verif_preparer.py --campagne campagnes/<nom> [--mode auto|leger|profond] [--taille-profond 25] [--taille-leger 90] [--max N]
# workflow : workflows/verification.js, args = donnees/verification/args-passe1.json
.venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom> <run passe 1>
.venv/bin/python .claude/skills/prospection-base-client/scripts/verif_passe2.py --campagne campagnes/<nom> [--taille-resolution 7] [--taille-completion 17] [--max N]
# workflow : workflows/verification-passe2.js, args = donnees/verification/args-passe2.json
.venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom> <run passe 1> <run passe 2> [--arbitrages <csv>]
```

**Étape 5, signaux et priorités.** Collectes gratuites, puis recherche par agents (sur accord), puis score :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/entites.py --campagne campagnes/<nom>
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> [--workers 4]   # si signaux.registre_suisse
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_linkedin.py --campagne campagnes/<nom>             # lent : en arrière-plan
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_site.py --campagne campagnes/<nom> [--workers 8]
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> --refresh       # une fois LinkedIn fini
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_news.py --campagne campagnes/<nom> [--workers 3] [--fit-min 5]
.venv/bin/python .claude/skills/prospection-base-client/scripts/dossiers.py --campagne campagnes/<nom> [--par-lot 15] [--fit-min 5] [--max N]
# workflow : workflows/signaux-recherche.js, args = donnees/signaux/lots/args-recherche.json
.venv/bin/python .claude/skills/prospection-base-client/scripts/apply_recherche.py --campagne campagnes/<nom> <run> [<run suivant> ...]
.venv/bin/python .claude/skills/prospection-base-client/scripts/scorer.py --campagne campagnes/<nom>
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_logiciels.py --campagne campagnes/<nom> [--mot ERP] [--tiers A,B,C,D]   # puis relire donnees/signaux/logiciels.json
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom>          # aperçu : score A, B, C (base-abc.csv), sans écriture
```

Attention : `dossiers.py` sans `--complement` efface les lots précédents. Pour les entreprises entrées plus tard
dans le périmètre : `dossiers.py --complement`, le workflow sur ces lots, puis `apply_recherche.py` avec **tous**
les runs dans l'ordre. **Relancer (veille, avant chaque vague de contacts)** : `collect_zefix.py --refresh`,
`collect_linkedin.py --retry`, `collect_news.py --refresh`, puis `scorer.py` et `reinjecter_apollo.py` (aperçu,
avec `--phrases campagnes/<nom>/phrases-signal.csv` dès que ce fichier existe). Le rapport `rapport-signaux.md`
ajoute alors les nouveaux signaux depuis le précédent passage.

**Étape 6, contacts Apollo** (clé requise ; enrichissement sur accord) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/creer_comptes.py --campagne campagnes/<nom> [--tiers A,B,C,D] [--liste NOM]   # aperçu et CSV à importer ; --go crée la liste par l'API
.venv/bin/python .claude/skills/prospection-base-client/scripts/extraire_personas.py --campagne campagnes/<nom> [--tiers A,B,C,D]          # relire apollo/cibles-apercu.csv
.venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom> --entreprises "mot1,mot2"   # test, 0 crédit
.venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom>                             # 0 crédit
.venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_web.py --campagne campagnes/<nom>                                  # gratuit, en arrière-plan
.venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom>                             # une seule fois de plus
# relire la colonne garder de apollo/contacts-a-valider.csv
.venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom>                            # aperçu : plafond de crédits
.venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom> --limite 10 --go           # test, après accord
.venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom> --go [--mobiles non|entree|tous]
.venv/bin/python .claude/skills/prospection-base-client/scripts/exporter_listes.py --campagne campagnes/<nom> [--prefixe NOM]
```

**Étape 7, réinjection dans Apollo** (écriture sur accord, 0 crédit) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> [--contacts <csv>] [--phrases <csv>]   # aperçu
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> --phrases campagnes/<nom>/phrases-signal.csv --go --limite 1
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> --phrases campagnes/<nom>/phrases-signal.csv --go
```

Les premières phrases ne s'écrivent que sur demande (consigne des agents : `consignes/phrases-signal.md`).

**Étape 8, ordre d'appel et plan de séquence** (aucun appel réseau) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/ordre_appel.py --campagne campagnes/<nom> [--liste entree|relais] [--contacts <csv>] [--export <export de l'interface Apollo>]
.venv/bin/python .claude/skills/prospection-base-client/scripts/plan_sequence.py --campagne campagnes/<nom> [--comptes-semaine 15] [--scores A,B] [--debut AAAA-MM-JJ] [--contacts <csv>]
```

**Étape 9, scripts et fichier d'appel** (rédaction par des agents, sur demande) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py briefs --campagne campagnes/<nom> [--lots 4]
# agents : consignes/fichier-appel-redaction.md (appels/redaction/) et consignes/cartes-appel.md (appels/cartes/)
.venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py sources --campagne campagnes/<nom>
# agents : consignes/fichier-appel-sources.md (appels/sources/redaction/)
.venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py assembler --campagne campagnes/<nom> [--export <csv>]
.venv/bin/python .claude/skills/prospection-base-client/scripts/scripts_appel.py --campagne campagnes/<nom> [--ordre <csv>] [--cartes <json ou dossier>]
```

Le fichier remis au commercial : `appels/fichier-appel.xlsx` (ou `.csv`) ; les scripts : `appels/scripts-appel.md`.

## Arborescence du dossier de campagne

```
campagnes/<nom>/
  campagne.toml               configuration (vous)
  persona.md                  persona du décideur (étape 1)
  exclure.csv                 clients et partenaires actuels (vous, facultatif)
  corrections.csv             corrections de site et de LinkedIn (vous, facultatif)
  arbitrages.csv              décisions après vérification (vous, facultatif)
  entreprises-toutes.csv      étape 2 : tout ce qui a été trouvé, avec statut et preuves (à relire)
  entreprises.csv             étape 2 : la liste retenue
  entreprises-linkedin.csv    pages LinkedIn lues sur les sites (linkedin_site.py)
  entreprises-enrichi.csv     étape 3
  entreprises-verifie.csv     étape 4
  prospection-signaux.csv     étape 5 : une ligne par entreprise, tiers et signaux
  rapport-signaux.md          étape 5 : fiches du tier A, tableau du tier B, nouveaux signaux, alertes
  base-abc.csv                score A, B, C par entreprise (reinjecter_apollo.py)
  phrases-a-rediger.csv       comptes A sans première phrase
  apprentissages.md           enseignements datés
  donnees/
    decouverte-mentions.json  étape 2 : toutes les mentions des agents, avec le contrôle anti-invention
    cache/                    caches DuckDuckGo et pages LinkedIn des sites
    verification/             étape 4 : lots/, manifestes, args des workflows
    signaux/                  étape 5 : entites.json, zefix.json, linkedin.json, site.json, news.json,
                              lots/, recherche.json, signaux.json, logiciels.json, historique/
  apollo/                     étapes 6 et 7 : comptes-a-importer.csv, cibles.json, cibles-apercu.csv,
                              contacts-a-valider.csv, couverture.csv, comptes-apollo.json, trouves-web.json,
                              contacts-crees.csv, contacts-importes.csv, reinjection.csv, champs-apollo.json,
                              comptes-manuels.csv (vous), listes/, cache/
  appels/                     étapes 8 et 9 : ordre-appel.csv, ordre-appel-relais.csv, plan-sequence.csv,
                              briefs/, redaction/, sources/, cartes/, scripts-appel.md, scripts-appel.csv,
                              fichier-appel.xlsx, fichier-appel.csv
```

Ces fichiers contiennent des données nominatives (noms, emails, téléphones). Décidez dès le départ s'ils vont
dans git. Sinon, ajoutez `campagnes/` au `.gitignore`, ou au moins `campagnes/*/apollo/` et `campagnes/*/appels/`.

## Ce qui coûte, ce qui est gratuit

**Gratuit** (ni crédit ni token d'agent) : tous les scripts Python hors enrichissement Apollo. Recherche
DuckDuckGo, sites, pages LinkedIn publiques, registre du commerce suisse, recherche de personnes et de comptes
Apollo, export des listes, ordre d'appel, plan de séquence, assemblage des scripts et du fichier d'appel. Seul
le temps compte (repères d'une campagne précédente) :

| Script | Durée observée |
|---|---|
| `enrichir_sites.py` | environ 18 min pour 360 noms (4 en parallèle) |
| `collect_linkedin.py` | 2 à 3 pages par minute, soit environ 1 h 40 pour 290 pages |
| `collect_zefix.py`, `collect_site.py` | quelques minutes pour environ 300 entreprises |
| `collect_news.py` | environ 30 min pour 150 entreprises |
| `chercher_contacts.py`, `chercher_web.py` | environ 3 min et 15 min pour 120 entreprises |

**Crédits Apollo** : seulement l'enrichissement de l'étape 6 (voir « Clé API Apollo »).

**Tokens Claude**, pour les agents des workflows et de la rédaction (repères mesurés, à ajuster au périmètre) :

| Étape | Repère |
|---|---|
| 2, découverte web | environ 190 000 tokens par agent, soit environ 6 000 par entreprise trouvée. Agents d'un run : un par segment, un par source transverse, une critique, puis jusqu'à 6 compléments. Exemple : 8 segments et 3 sources, 18 agents, environ 3,4 M tokens |
| 4, vérification | environ 6 500 tokens par entreprise, deux passes comprises ; environ 2,4 M tokens et 45 min pour environ 380 entreprises (21 agents) |
| 5, recherche de signaux | environ 31 000 à 35 000 tokens par entreprise recherchée, soit environ 0,5 M par lot de 15 (recherche et contre-vérification) |
| 9, fichier d'appel | environ 1,5 M tokens pour 8 agents de rédaction (deux passes de 4 lots), pour une centaine de contacts |

Au-delà d'environ 3 M tokens, Claude découpe en workflows successifs, du plus utile au moins utile : une limite
de session peut couper un workflow, qui reprend ensuite là où il s'est arrêté.

## Données : répertoire des localités suisses

`donnees/localites-suisse.csv` est le répertoire officiel des localités de Suisse (Office fédéral de topographie
swisstopo, données ouvertes) : localité, numéro postal, commune, canton, langue. Les scripts s'en servent pour
déduire le canton et la région linguistique d'une ville suisse (consolidation, cible prioritaire, langue des
recherches et des contacts).

Source à citer si vous rediffusez ce fichier ou des résultats qui en dérivent : **« Source : Office fédéral de
topographie swisstopo »** (© swisstopo). Pour le mettre à jour, remplacez-le par la dernière version CSV publiée
par swisstopo, avec les mêmes colonnes (`Ortschaftsname`, `PLZ4`, `Gemeindename`, `Kantonskürzel`, `Sprache`...)
et le séparateur point-virgule.

## Dépannage

| Message ou symptôme | Cause et solution |
|---|---|
| `No module named 'ddgs'` (ou `requests`, `bs4`, `openpyxl`) | mauvais Python : lancez `.venv/bin/python`, pas `python3`. Sinon, réinstallez : `.venv/bin/pip install -r .claude/skills/prospection-base-client/requirements.txt` |
| « Python 3.11 ou plus est requis » | recréez le `.venv` avec un Python plus récent, puis réinstallez les paquets |
| « Dossier de campagne introuvable », « Configuration absente » | le chemin de `--campagne` part du dossier courant : lancez depuis la racine du projet |
| « erreur de syntaxe TOML » | guillemet ou crochet manquant dans `campagne.toml` : `verifier_installation.py --campagne` donne la ligne |
| « Clé Apollo introuvable » | créez `.env` à la racine du projet (là où vous lancez les commandes) avec `APOLLO_API_KEY=...` |
| « Apollo refuse ... (401 ou 403) » | clé invalide, ou point d'accès non coché pour cette clé : clé master, ou ajoutez le chemin affiché |
| Pauses `[429]` pendant un script Apollo | quota atteint : le script attend et reprend. Si ça dure, relancez plus tard : le cache garde ce qui est fait |
| Nom de liste Apollo refusé | `liste_comptes` doit être le nom exact de la liste dans Apollo ; le script affiche les noms disponibles |
| LinkedIn qui bloque (code 999, page de connexion) | `collect_linkedin.py` fait des pauses, puis s'arrête après 5 blocages d'affilée. Attendez, puis relancez avec `--retry`. Ne le lancez pas pendant que des agents ouvrent LinkedIn depuis la même connexion |
| DuckDuckGo sans résultat ou en erreur | panne passagère : les scripts réessayent. Relancez plus tard, le cache garde ce qui est fait |
| Le workflow refuse ses args | passez le contenu du fichier d'args écrit par le script de préparation ; `racine` doit être un chemin absolu |
| Beaucoup de valeurs écartées « non vues » pour un même agent | souvent une sortie d'outil trop longue que l'agent n'a pas relue, pas une invention : vérifiez quelques cas à la main. Gardez le journal dans son dossier de run (copié seul, il ne peut plus être contrôlé) |
| Workflow coupé par une limite de session | relancez le même workflow avec les mêmes args et `resumeFromRunId` : les agents terminés sont rejoués depuis le cache |
| Un script écrit dans le mauvais dossier | les sorties vont toujours dans le dossier passé à `--campagne` : vérifiez ce chemin |

## Contenu du skill

```
prospection-base-client/
  README.md                  ce fichier (installation, configuration, commandes)
  SKILL.md                   consignes de Claude : règles, carte des étapes
  requirements.txt           paquets Python
  exemple.env                modèle du fichier .env (clé Apollo)
  config/campagne.exemple.toml   modèle de configuration d'une campagne
  donnees/localites-suisse.csv   répertoire officiel des localités suisses (© swisstopo)
  etapes/                    une fiche par étape : méthode, contrôles, pièges
  reference/                 inventaire des outils, pièges, contrat entre étapes
  consignes/                 consignes des agents de rédaction (étapes 7 et 9)
  scripts/                   scripts Python, tous dans ce dossier ; outils_web.py et outils_signaux.py sont
                             les outils que les agents des workflows appellent
  workflows/                 workflows de Claude Code (étapes 2, 4 et 5)
```

## Partager le skill

Zippez le dossier sans les fichiers générés ni la clé. Depuis le dossier qui contient le skill (par exemple
`.claude/skills/`) :

```bash
zip -r prospection-base-client.zip prospection-base-client -x '*/__pycache__/*' '*.DS_Store' '*/.env'
```

Les scripts n'écrivent pas de `__pycache__`, mais un autre outil peut en créer un ; `verifier_installation.py` le
signale. Ne mettez jamais un dossier de campagne dans le zip : il contient des données nominatives (contacts,
téléphones, emails).
