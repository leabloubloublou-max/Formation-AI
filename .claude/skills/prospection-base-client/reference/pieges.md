# Pièges et parades, par étape

Chaque entrée : le piège (et sa cause quand elle est connue), puis la parade. Tous ont été rencontrés sur des
campagnes réelles, sauf mention « déduit du code ». Quand un script du skill applique déjà la parade, c'est dit :
le piège reste utile pour comprendre un résultat ou relire un fichier.

Sommaire : Transverse ; Étape 1 (cible et persona) ; Étape 2 (trouver les entreprises) ; Étape 3 (enrichir site
et LinkedIn) ; Étape 4 (vérifier par agents) ; Étape 5 (signaux et priorisation) ; Étape 6 (contacts Apollo) ;
Étape 7 (réinjecter) ; Étape 8 (séquence et ordre d'appel) ; Étape 9 (scripts et fichier d'appel) ; Maintenance
du skill.

## Transverse

- **Limite de session au milieu d'un workflow** (« You've hit your session limit ») : une partie des agents échoue,
  la session principale est bloquée. Parade : intégrer d'abord les résultats partiels ; une fois la limite levée,
  reprendre avec l'outil Workflow (`scriptPath`, `resumeFromRunId`, mêmes `args`) : les agents terminés sont
  rejoués depuis le cache. Pas de relance aveugle. Prévention : lots du plus utile au moins utile, compléments dans
  un workflow séparé, découpage au-delà d'environ 3 M tokens estimés.
- **Journal d'une reprise** : l'exécution coupée et la reprise partagent le même `journal.jsonl` (même runId). Les
  agents coupés y sont `failed`, leurs relances apparaissent en nouveaux `started` puis `result`. Parade : lire tout
  le journal, ignorer `failed`, garder le dernier résultat par lot. Les scripts d'application le font
  (`consolider_decouverte.py`, `verif_appliquer.py`, `apply_recherche.py`). Ne jamais couper un journal.
- **Retours d'agents enfouis dans le journal**, parfois en chaîne JSON. Parade : les scripts cherchent
  récursivement les objets attendus, y compris dans les chaînes qui commencent par « { ».
- **Journal copié hors de son dossier de run** : sans les transcripts `agent-<id>.jsonl` voisins, aucun contrôle
  anti-invention possible. Parade : passer le journal en place, ou le dossier du run ; les scripts le signalent.
- **6 agents au plus en même temps** sur une machine : 10 lots partent en deux vagues. Parade : en tenir compte
  dans les durées annoncées.
- **Estimations de coût et de durée peu fiables** : un workflow annoncé à 6 à 8 agents et 20 à 30 minutes en a
  demandé 21 et 45 minutes, parce que le périmètre a grandi en route ; un autre a pris trois fois moins que prévu.
  Parade : estimer sur le périmètre réel et complet, puis suivre l'avancement dans `journal.jsonl` avant de
  répondre « c'est fini ».
- **Chiffres annoncés de mémoire** (156 annoncés au lieu de 152 ; 305 signaux au lieu de 315). Parade : compter
  par script avant d'écrire un chiffre.
- **Peu d'appels d'outils ne prouve pas l'invention** : un agent enchaîne 6 à 8 commandes dans un seul Bash ou lance
  des lectures en parallèle ; un appel vaut alors 25 à 30 recherches. Parade : contrôle anti-invention mécanique
  sur les transcripts, quoi qu'il arrive.
- **Sorties d'outil trop longues** (environ 30 Ko et plus) : le transcript n'en garde qu'un aperçu de 2 Ko et le
  reste va dans un fichier (« Full output saved to »). Des valeurs justes seraient jugées « non vues ». Parade :
  les scripts relisent ce fichier ; les prompts demandent de tronquer (`head`, `cut`).
- **Agent qui écrit des fichiers** malgré « ne modifie aucun fichier ». Sans gravité ; la consigne est répétée
  dans les prompts.
- **Mauvais dossier de campagne** : une commande copiée d'une autre campagne réécrit ses sorties. Parade : relire
  `--campagne` avant chaque lancement ; chaque script n'écrit que dans le dossier passé.
- **Liste plus avancée restée d'une liste précédente** : l'étape 5 lit `entreprises-verifie.csv` s'il existe, même
  après un nouvel import. Parade : `importer_liste.py` et `consolider_decouverte.py` le signalent ; refaire les
  étapes 3 et 4, ou supprimer l'ancien fichier.
- **Workflow modifié en place** : les workflows du skill se lancent tels quels, tout passe par `args`. Parade : pour
  changer une consigne, copier le fichier dans `<campagne>/workflows/` et lancer la copie ; charger d'abord le skill
  `workflow-authoring`.
- **`python3` sans les dépendances** selon le PATH (autre version de Python, sans `ddgs`). Parade : toujours
  `.venv/bin/python` ; contrôle : `.venv/bin/python -c "import ddgs, requests, bs4, openpyxl"`.
- **macOS** : la commande `timeout` n'existe pas. Une commande Bash de plus de 600 secondes doit partir en
  arrière-plan, puis attendre la notification de fin.
- **DuckDuckGo échoue par intermittence** (« error sending request »), et `ddgs` lève une exception sur « No results
  found ». Parade : `commun.recherche_web` relance avec une attente croissante et rend une liste vide sans résultat.
- **Données nominatives commitées** sans décision. Parade : trancher le sort git au démarrage (bloc proposé dans
  [contrat.md](contrat.md)) ; chemins explicites à chaque commit, jamais `git add -A`, ne pas pousser sans demande.
- **Messages de suivi en anglais** alors que l'utilisateur écrit en français. Parade : tout en français.

## Étape 1 : cible et persona

- **Date de référence vide** : les fenêtres « moins de 12 mois » glissent d'un jour à l'autre, et deux passages
  donnent des scores différents. Parade : fixer `[campagne] date_reference` pour toute la durée d'une vague.
- **Cible trop large ou trop étroite** : un segment trop large dilue la recherche, un segment trop étroit épuise
  l'agent en quelques requêtes. Parade : 6 à 12 croisements « secteur, zone » de taille moyenne.
- **Famille de persona inconnue** dans `[persona]` : le script s'arrête et cite les familles connues. Parade :
  famille fournie, ou nouvelle famille déclarée dans `[persona.titres]`.
- **`[offre]` incomplète** : `dossiers.py` s'arrête si `societe` et `description` sont vides (le workflow les
  refuserait), et les scripts d'appel affichent « À COMPLÉTER ». Parade : remplir `[offre]` avant l'étape 5.
- **Preuves inventées ou enjolivées** dans `[offre] preuves` : elles partiront telles quelles chez les prospects.
  Parade : seulement des résultats réels, validés par le client cité ; sinon une formule anonyme (« un sous-traitant
  de la région »).
- **Client ou partenaire actuel prospecté à froid**. Parade : `exclure.csv` dès le départ, à demander à
  l'utilisateur.

## Étape 2 : trouver les entreprises

Découverte web par agents :

- **Site deviné à partir du nom** (`nom-entreprise.ch`). Parade : règle « site seulement si tu l'as vu » dans le
  prompt, puis contrôle anti-invention de `consolider_decouverte.py` (site, LinkedIn et preuve absents des sorties
  d'outils de l'agent : écartés).
- **Beaucoup de sites écartés chez un même agent** : souvent des sorties d'outils tronquées plutôt qu'une
  invention. Parade : vérifier quelques cas à la main avant de conclure.
- **Bruit des recherches génériques** : homonymes, mentions indirectes (sur un balayage large, 69 pistes sur 82
  étaient fausses). Parade : preuve littérale exigée, échantillon de 10 lignes relu.
- **Offres de cabinets de recrutement** (client anonyme), **filiales commerciales** de groupes étrangers,
  **distributeurs** sans production : hors cible ou sans valeur. Parade : consignes explicites, `hors_cible` avec
  motif, retenu seulement si la majorité des mentions le dit.
- **Doublons sous deux noms** (raison sociale et marque) sans site commun : la fusion par domaine ne les voit pas.
  Parade : relecture de `entreprises-toutes.csv` (même ville, noms proches).
- **Fatigue des agents** : un agent s'arrête quand ses premières requêtes s'épuisent, la liste paraît complète.
  Parade : segments de taille moyenne, sources transverses (exposants, annuaires, clusters), critique de couverture
  puis compléments ; dire à l'utilisateur ce qui n'a pas été couvert.
- **Biais de visibilité** : les entreprises sans site ni présence en ligne échappent aux agents. Parade : un segment
  ou une source « registre du commerce » quand la zone compte beaucoup de petits sous-traitants.
- **Un groupe peut cacher une PME de la cible** (filiale autonome). Parade : relire les motifs hors cible.

Liste existante ou export Apollo :

- **Valeurs de l'interface Apollo** : séniorité « C suite », « Director » et statut « Verified », « User Managed »
  (l'API écrit `c_suite`, `verified`). `importer_liste.py` les met en minuscules. « user managed » n'est pas
  « verified » : ces contacts sortent des étapes email.
- **Entrée ou relais déduit de l'intitulé** : un « Directeur » seul, un président non exécutif ou un CFO peuvent
  être mal rangés ; « Titolare », « Chair » et « Chairperson » partent en relais, « Vice Chairman » en entrée
  (déduit du code). Parade : relire la colonne `ordre` de `apollo/contacts-importes.csv`.
- **Pays absent de la table des pays** (`commun.PAYS`) : code vide, valeur d'origine gardée dans `pays_source`.
  Parade : compléter la table si la cible sort d'Europe.
- **Import combiné** (découverte puis liste, ou deux exports) : sans `--ajouter`, le second import remplace le
  premier. Parade : `--ajouter` ; une entreprise déjà écartée et retenue par le nouvel ajout est marquée « ajoutée
  par » ; un client déjà exclu le reste.
- **Ancien `contacts-importes.csv`** qui ne correspond plus à la liste : l'ordre d'appel et le plan le liraient en
  repli. Parade : le script le renomme en `contacts-importes.precedent.csv`.

## Étape 3 : enrichir site et LinkedIn

- **Environ un lien sur quatre faux ou imparfait** avec la seule correspondance de nom : site d'offres d'emploi pour
  un fabricant, société étrangère homonyme, site d'un tournoi sportif, compagnie aérienne. Parade : domaines écartés
  (`BAD_DOMAINS` : annuaires, registres, réseaux sociaux, emploi), trois requêtes successives, et vérification par
  agents (étape 4) prévue d'emblée pour une vraie campagne.
- **Confiance « haute » trompeuse** : elle veut seulement dire qu'un mot du nom est dans le domaine ou le slug
  (piège des noms génériques). Parade : la vérification classe en solide, probable, faible, non recherché ;
  « solide » exige que le site officiel cite lui-même la page LinkedIn.
- **Page LinkedIn d'une filiale d'un autre pays ou du groupe** au lieu de l'entité. Parade : page de l'entité, sinon
  du groupe, jamais d'une filiale d'un pays tiers ; statut « page du groupe » assumé à l'étape 4.
- **Plusieurs pages `/company/` sur un site** : la première par ordre alphabétique est gardée (risque de page de
  groupe ou de partenaire). Parade : la contre-vérification de l'étape 4.
- **Préfixes de pays (`ch.`, `fr.`) et pages school ou showcase**. Parade : URL normalisée
  (`commun.linkedin_company`).
- **Correction ignorée en silence** : un nom de `corrections.csv` qui n'est pas exactement celui de la liste.
  Parade : `enrichir_sites.py` signale les noms sans correspondance.

## Étape 4 : vérifier par agents

- **Homonymes impossibles à trancher par le web seul** (société suisse ou allemande du même nom, deux sociétés
  étrangères au nom voisin). Parade : la preuve de la source sert d'oracle (activité, ville, produit) ; sans preuve,
  « ambigu » ou « introuvable », jamais forcé.
- **Pages de groupe** au lieu de l'entité (filiale renvoyant au site de sa maison mère, société renvoyant à celle
  qui l'a reprise). Parade : `arbitrages.csv` avec le statut « page du groupe » et une note.
- **Lien mort cité par le site officiel** (page LinkedIn en 404, page active sous un autre slug). Parade : le
  contre-vérificateur ouvre l'URL ; on retient la page active qu'il a vue, ou on vide le champ.
- **« corrigé » ou « trouvé » rendu sans valeur**. Parade : `verif_appliquer.py` le convertit en « introuvable ».
- **Verdicts « incertain » ou « réfuté » qui ne s'appliquent pas seuls**. Parade : `arbitrages.csv` (bonne URL vue
  par le contre-vérificateur, ou statut fixé). Un cas non arbitré reste à revoir.
- **Le contrôle léger ne rend ni pays ni activité** : des entreprises restent sans pays, ce qui gêne le score de
  zone. Parade : passer ces lignes en profond (`--mode profond`), ou compléter le pays à la main.
- **Contrôle léger trop généreux** : une valeur douteuse « confirmée » sans outil. Parade : `verif_appliquer.py` la
  note « confirmé (contrôle léger) » et ne passe en confiance haute que les valeurs déjà sûres.
- **Un échec HTTP ne prouve pas qu'un site est mort** (403 anti-robot, erreurs réseau locales). Parade : essayer
  https, http et www, puis une lecture par l'agent ; noter le site en panne avec sa date plutôt que de le vider.
- **Une même entreprise sous deux noms** (ponctuation, espaces) traitée deux fois. Parade : alias fusionnés par
  `verif_passe2.py`, une entrée par alias demandée aux agents.
- **Estimation dépassée** parce que le périmètre grandit en route (solides en contrôle léger, passe 2). Parade :
  annoncer le périmètre complet dès l'estimation.

## Étape 5 : signaux et priorisation

Collectes :

- **LinkedIn répond 999 dès la deuxième page** avec une session réutilisée (cookies). Parade : requête sans cookies
  à chaque page, pause de 4 à 8 s, séquentiel (`collect_linkedin.py`).
- **Blocages LinkedIn intermittents** (page de connexion). Parade : pauses croissantes, arrêt après 5 blocages
  d'affilée, relance `--retry` ; pays de la cible d'abord.
- **Agents et collecteur sur la même adresse IP**. Parade : les prompts interdisent aux agents d'ouvrir
  linkedin.com avec les outils locaux.
- **URL LinkedIn fausses (404) ou numériques** (`/company/<nombre>`, qui redirigent vers la connexion et ressemblent
  à un blocage). Parade : traitées comme un 404, slug cherché par DuckDuckGo, validé par le site ou les mots du nom
  (colonne `linkedin_corrige`).
- **Mauvaise page validée** (homonyme au nom proche). Parade : tous les mots du nom exigés quand il en compte deux
  ou moins.
- **Sociétés radiées invisibles dans le registre suisse**. Parade : recherche avec les sociétés radiées
  (`collect_zefix.py`) ; un homonyme radié depuis plus de 8 ans est écarté (`--radiees-ans`).
- **Faux rattachements au registre** : mots de statut (« en liquidation »), holdings et fondations, acronymes courts,
  pays inconnu. Parade : score des candidats et seuils de `collect_zefix.py` ; correspondance stricte quand le pays
  est inconnu.
- **Publications narratives mal lues** (« X n'est plus directeur », noms « Nom, Prénom »). Parade : lecture phrase
  par phrase.
- **Fausse dissolution** (« sa signature est radiée ») et **fausse fusion** (republication d'un transfert ancien).
  Parade : motifs resserrés ; distinguer faillite, sursis concordataire, faillite annulée et dissolution.
- **Faux changement de dirigeant** (une personne radiée puis réinscrite : changement de signature). Parade :
  allers-retours de 183 jours ou moins ignorés ; un « directeur » au registre n'est pas forcément le patron :
  l'agent tranche ; un président pèse moins.
- **Fabricants classés en services** par les clauses types du but social (« activité financière, commerciale ou
  industrielle »). Parade : but coupé avant « La société peut » ; sources par ordre de fiabilité.
- **Distributeurs classés fabricants**. Parade : la distribution est testée avant la fabrication.
- **Bruit du lexique** (« acquisition de données » lu comme un rachat ; « mit » lu comme IT ; « mes » lu comme MES ;
  « chatbot » trop large). Parade : exclusions, acronymes sensibles à la casse ; les détections automatiques restent
  des candidats à faible poids, jamais une raison de passer en score A.
- **Homonymes dans les actualités** (un nom court qui est aussi un mot courant). Parade : mot distinctif du nom
  exigé ; `noms-ambigus.csv` pour ajouter la ville ou le pays aux requêtes.
- **Caractères « gras mathématiques » Unicode** dans les posts LinkedIn. Parade : normalisation NFKC.

Workflow de recherche et score :

- **`dossiers.py` sans `--complement` efface les lots précédents** (lots, manifeste, args). Parade : toujours
  `--complement` après le premier passage ; le script l'annonce.
- **LinkedIn fini en dernier** : des tailles enfin connues font entrer de nouvelles entreprises jamais envoyées aux
  agents. Parade : `dossiers.py --complement` puis un workflow sur ces seuls lots.
- **Double comptage registre et agent**. Parade : le signal d'agent de même famille à 25 jours près remplace
  l'événement du registre ; les détections automatiques ne comptent que pour les entreprises non recherchées.
- **Fiche registre homonyme** retenue à tort. Parade : si l'agent écrit « homonyme » près de « registre », le
  scorer ignore la fiche.
- **Signal sans source vue** : `apply_recherche.py` le déclasse en confiance faible ; un « confirmé » dont la source
  n'apparaît pas chez le contre-vérificateur devient « incertain ».
- **Événement de la maison mère attribué à la filiale** : cause la plus fréquente des signaux réfutés. Parade : la
  contre-vérification adverse des signaux forts.
- **Tirets cadratins dans les textes des agents**. Parade : remplacés par `apply_recherche.py` ; règle répétée dans
  les prompts ; contrôle final sur les colonnes texte.
- **Une entreprise en tier A peut figurer dans les Alertes** (ancienne société en faillite dont l'activité a été
  reprise). Parade : lire la section Alertes du rapport avant tout contact.
- **Veille incomplète** (déduit du code) : `--retry` ne rafraîchit pas les pages LinkedIn déjà lues, et les
  entreprises déjà recherchées ne captent plus que le registre. Parade : relancer les agents sur les tiers A et B
  pour une vraie mise à jour.
- **Logiciel d'un prospect rarement public** : un logiciel identifié pour environ une entreprise sur quatre, dont
  une moitié seulement confirmée. Meilleures preuves : offres d'emploi (« connaissances du logiciel X »),
  témoignages d'intégrateurs, page publique d'une instance (Odoo : `/website/info`). Les technologies d'Apollo ne
  sont qu'un indice, souvent au niveau du groupe ; « GSAP » (bibliothèque JavaScript) n'est pas SAP. Parade :
  `collect_logiciels.py`, puis relecture à la main avec un statut.

## Étape 6 : contacts Apollo

- **Claude dans Chrome** : captures coûteuses, lent, fragile, clic payant possible. Parade : API REST et scripts.
- **Connecteur MCP Apollo en boucle** : environ 8 000 tokens par recherche de personnes. Parade : petits volumes
  seulement.
- **Nom de famille masqué** par la recherche gratuite (« Du***t »). Parade : prénom plus début et fin du nom ; le nom
  complet n'arrive qu'à l'enrichissement.
- **La recherche par domaine ramène aussi les anciens salariés**. Parade : recherche par organisation d'abord ; par
  domaine, seuls les employeurs actuels au nom proche sont gardés.
- **Prénom et nom inversés, prénoms composés, surnoms, initiales**. Parade : ordre inversé testé ; surnom et initiale
  acceptés seulement dans l'entreprise.
- **Homonymes ou départs** (une personne nommée placée ailleurs). Parade : « nom : autre employeur », `garder` vide ;
  « employeur lié » seulement si l'autre employeur est cité dans la fiche.
- **Profils en double dans Apollo**. Parade : le profil avec email, puis le plus récent.
- **Salariés rangés sous une société sœur** du groupe. Parade : élargissement par domaine et pays (un vivier de plus
  de cent personnes retrouvé ainsi pour une seule entreprise).
- **Personnel des filiales d'autres pays** ramené par l'élargissement. Parade : intitulés régionaux pénalisés ; filtre
  de pays après enrichissement, avec l'exception des vrais dirigeants (codée). Les crédits de ces personnes sont
  quand même dépensés : décocher avant l'enrichissement ce qu'un intitulé régional signale déjà.
- **Lecture de `persona_cible` par motifs** : un mot trouvé dans un autre (« usine » dans « business »), mentions
  négatives prises pour des cibles, rôles lus comme des noms. Parade : `cibles` structurées de l'étape 5 lues en
  priorité ; relecture de `cibles-apercu.csv`.
- **`persona_cible` vide**. Parade : le persona de la campagne par défaut (famille d'entrée, puis relais).
- **Motifs d'intitulés trop larges** (« Product Owner » lu comme propriétaire, « Ingénieur commercial » lu comme
  technique, « Project Manager » générique). Parade : exclusions de `persona.py`, intitulés précis dans
  `[persona.titres]`, relecture de chaque rapprochement.
- **Colonne `dirigeants`** (« ; » dans les parenthèses, format « Nom, Prénom », anciens dirigeants). Parade : découpe
  hors parenthèses, inversion, rôles « ancien, ex-, former, ehemalig » ignorés.
- **`PATCH /contacts/{id}` avec `label_names` remplace toutes les listes du contact**. Parade : ajout par
  `labels/add_entity_ids_to_label_names` (fait par les scripts).
- **Le dédoublonnage de `bulk_create` n'ajoute pas les contacts existants aux listes** (renvoyés à part). Parade :
  ajout explicite des créés et des existants (fait par les scripts).
- **Compteurs de listes et index mis à jour en différé**. Parade : recompter par `contacts/search` quelques secondes
  plus tard ; attendre aussi après la création de la liste de comptes.
- **Liste créée deux fois** : `POST /labels` renvoie 422 si le nom existe. Parade : lecture des listes d'abord, seules
  les manquantes sont créées.
- **Nom de liste faux** dans `campagne.toml`. Parade : le script s'arrête et cite les listes disponibles.
- **Crédit facturé même sans email** ; mobile à 8 crédits. Parade : signaler les personnes sans email connu avant
  l'accord ; mobiles décidés avant le premier enrichissement.
- **Options waterfall payantes même sans résultat**. Parade : jamais activées sans un accord chiffré au pire cas ; le
  connecteur MCP les propose : ne pas les cocher.
- **Personne trouvée sur le web rattachée par Apollo à un ancien employeur** (email périmé). Parade : email gardé
  seulement si l'employeur correspond ; la correspondance rejetée a quand même coûté son crédit.
- **Le web trouve bien les personnes nommées, mal les rôles** (beaucoup de bruit). Parade : rôles du web « à
  vérifier », profil du pays de l'entreprise seulement.
- **Un lieu à la place de l'employeur sur LinkedIn** (« Région de ... »). Parade : statut ramené à « cité » ; une
  citation ne vaut confirmation que sur le site de l'entreprise.
- **Deux entreprises pour un compte** (même domaine). Parade : `creer_comptes.py` n'en crée qu'un ; vérifier
  `compte_apollo` dans `couverture.csv`.
- **Comptes sans organisation Apollo**. Parade : recherche par domaine filtrée, sinon par mots-clés du nom.
- **Le cache de l'enrichissement dépend de la composition exacte des lots de 10**. Parade : figer `garder` avant
  `--go` ; tester avec `--limite 10` (le premier lot exact).
- **Affichage des crédits trompeur** : il additionne aussi les réponses relues du cache. Parade : recompter depuis le
  cache ou les statistiques d'usage d'Apollo.
- **Limitation de débit seulement locale** (pas de plafond journalier, autres processus non comptés). Parade : rester
  à 80 % des plafonds et s'appuyer sur le cache.
- **Cache permanent** : des réponses anciennes sont relues. Parade : supprimer les fichiers concernés de
  `apollo/cache/` pour rafraîchir.
- **Grandes organisations** (plus de 500 personnes, 5 pages au plus). Parade : recherche ciblée par intitulés quand
  aucun candidat n'est trouvé.

## Étape 7 : réinjecter dans Apollo

- **Champ cité par son id dans la séquence** : la variable d'un champ de contact s'écrit avec son nom
  (`{{phrase_signal}}`) ; l'id ne sert qu'à l'API.
- **Champ de compte homonyme** : un champ `signal_et_date` de modalité compte ne remplit pas les contacts. Parade : le
  script ne lit que les champs de contact.
- **Valeur vide envoyée** : elle effacerait une saisie manuelle. Parade : seules les valeurs non vides partent.
- **Mise à jour asynchrone au-delà de 100 contacts** : la réponse ne liste plus les contacts mis à jour. Parade :
  lots de 100.
- **Import CSV qui crée des doublons** au lieu de mettre à jour. Parade : essai sur 2 ou 3 contacts, ou `--go`, qui
  passe par l'id du contact.
- **`--go` lancé sans `--phrases`** : la colonne `phrase_signal` est vide et n'est pas envoyée. Parade : mêmes
  options à l'aperçu et au `--go`.
- **Aperçu relancé sans `--phrases` (veille)** : le script ne lit `phrases-signal.csv` qu'avec l'option ; sans elle,
  `base-abc.csv` perd les premières phrases et `plan_sequence.py` signale les comptes A « sans première phrase ».
  Parade : `--phrases campagnes/<nom>/phrases-signal.csv` à chaque relance, dès que le fichier existe.
- **Score A, B, C et tiers confondus** : le C du score est le « Hors cible » ; le tier C est encore dans la cible.
  Parade : dire « score » ou « tier », jamais une lettre seule ; lire `raison_abc`.
- **Signal récent qui n'est pas une accroche** : une radiation, une sortie du conseil, une entrée suivie du départ
  de la même personne quelques mois plus tard. Parade : le script ne les compte pas pour le A et retient la meilleure
  accroche.
- **Contact « non créé » à l'étape 6** : pas d'id, jamais réinjecté (compté « sans id Apollo »).

## Étape 8 : séquence et ordre d'appel

- **BOM en tête des CSV** : sans `utf-8-sig`, la première colonne porte un caractère invisible. Parade : toujours
  lire en `utf-8-sig`.
- **Apollo refuse par défaut un deuxième contact de la même entreprise dans une séquence** : le relais est écarté
  sans bruit. Parade : deux séquences (entrée, relais), conformes à « une seule voix par entreprise ».
- **Contacts écartés à l'inscription** (actifs dans une autre séquence, sans email, email non vérifié, changement de
  poste). Parade : lire la réponse, décider des drapeaux avec l'utilisateur, traiter les écartés par appel ou
  LinkedIn.
- **Inscription par `label_names[]`** : tout le monde d'un coup, ordre ignoré. Parade : par vague de `contact_ids`,
  ou `status=paused` et `auto_unpause_at`.
- **Inscrire envoie de vrais emails**. Parade : séquence inactive, récapitulatif, accord, puis activation sur un
  second accord.
- **La `note` d'une étape d'appel est commune à tous les contacts**. Parade : le script de chaque contact dans sa
  tâche (étape 9) ou dans un champ de contact.
- **Anciennes campagnes mal repérées par les seuls noms** : la comparaison des noms en a trouvé moins de la moitié.
  Parade : `deja_contacte` construit d'abord depuis le statut « déjà dans Apollo » de l'étape 6, l'export de
  l'interface (`Stage`, `Last Contacted`, emails) et les séquences passées (`contacts/search`), puis par les noms ;
  une relance plutôt qu'un appel à froid.
- **Un « Not Interested » sans réponse** n'est pas un refus. Parade : seul un refus avec réponse passe en fin de
  liste ; les autres gardent leur rang.
- **Numéros inégaux selon la liste** : l'enrichissement sans téléphone ne donne que des standards ; les mobiles
  révélés dans l'interface n'apparaissent que dans l'export de l'interface. Parade : `--export` ; tri par type de
  numéro ; demander la personne au standard.
- **Standards de groupe ou de filiale** (numéro d'un autre pays). Parade : vérifier le numéro avant d'appeler.
- **Langue** : une part des contacts ne parle pas la langue de l'appelant. Parade : tri par langue, scripts ou
  relais dans la langue du contact ; adapter tout lieu de l'offre au pays du contact.
- **Apollo confond les villes homonymes** (une ville d'un Land classée dans un autre). Parade : lieu LinkedIn
  d'abord, Apollo ensuite.
- **Signaux qui vieillissent** (poids x0,65 entre 12 et 24 mois, x0,3 entre 24 et 36). Parade : veille avant chaque
  vague.

## Étape 9 : scripts et fichier d'appel

- **Agent qui invente un chiffre ou un nom**. Parade : `assembler` signale tout chiffre et tout nom propre absents de
  la fiche et de l'offre ; corriger le JSON de l'agent, puis relancer.
- **Preuve citée hors de son cas d'usage** : elle ferait croire qu'on a déjà fait ce cas. Parade : champ `preuve` de
  la carte, preuve absente de l'offre signalée.
- **Lieu d'un autre pays** (« hébergé en Suisse » à une entreprise française). Parade : `lieux_a_eviter` dans les
  briefs, alerte des deux scripts ; reformuler sans lieu (« vos données restent chez vous »).
- **Logiciel nommé sur un simple indice**. Parade : seuls « probable » et « confirmé » se citent ; alerte sinon.
- **Même nom de famille dans une entreprise familiale** (père et fils, frères) : un rapprochement sur le seul nom
  attribuait au fils le rôle du fondateur. Parade : nom et prénom exigés pour relier une personne à un rôle du
  registre ou à un signal.
- **Prénom et nom inversés par Apollo**. Parade : `note_nom` dans les briefs, `nom_a_utiliser` dans la carte ;
  alerte « nom corrigé ».
- **Lots redécoupés après la rédaction** : une ancienne carte pourrait l'emporter sur la nouvelle. Parade : la passe
  précédente est rangée dans `appels/precedent/` ; refaire les cartes et rédactions des lots changés.
- **Script lu au prospect en entier** : il est fait pour guider, pas pour être lu. Parade : la rubrique « À savoir »
  ne se dit jamais ; le reste se dit avec ses mots.
- **`PATCH /tasks/{id}` remet la priorité à medium** si `priority` est omis, et le créateur à l'utilisateur de la clé.
  `call_script` ne s'écrit que sur une tâche `scheduled`. Le connecteur MCP n'expose pas `call_script`. Parade :
  toujours renvoyer `priority` et `creator_id` ; sinon mettre le script dans `note`.
- **Tâches d'appel créées seulement quand le contact atteint l'étape** (à vérifier). Parade : pousser les scripts
  chaque matin, ou créer des tâches autonomes.
- **Droits de la clé sur les tâches**. Parade : tester sur une seule tâche (403 = droit manquant).
- **Fuseaux horaires** : `due_at` en GMT par défaut, exports Apollo en heure du Pacifique. Parade : convertir depuis
  le fuseau de l'appelant.
- **Script automatique d'Apollo en anglais** dans d'anciennes tâches d'appel. Parade : l'écraser avec le script dans
  la langue du contact.
- **Tirets cadratins et emojis** dans des textes réutilisés. Parade : contrôle des deux scripts, et recherche du
  cadratin et du demi-cadratin dans tous les textes destinés aux prospects avant export.

## Maintenance du skill

- **Une page web résumée par un outil de lecture** perd les détails. Parade : télécharger la version Markdown
  (`https://docs.apollo.io/reference/<page>.md`, `https://code.claude.com/docs/en/skills.md`).
- **Nouveau dossier de skills non surveillé**. Parade : `/reload-skills` après la création.
- **YAML cassé par un « : » non entre guillemets** dans la description : le skill se charge sans métadonnées et ne se
  déclenche plus seul. Parade : description entre guillemets.
- **Le contenu d'un skill n'est pas relu après l'invocation**, et la compaction n'en garde que le début. Parade :
  garde-fous en tête de `SKILL.md`, détails dans les annexes.
