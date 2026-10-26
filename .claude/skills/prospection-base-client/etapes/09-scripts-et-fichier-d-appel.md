# Étape 9 : scripts d'appel et fichier d'appel du commercial

## Objectif

Donner à l'appelant tout ce qu'il lui faut, contact par contact, dans l'ordre d'appel de l'étape 8 :

- **un script d'appel par contact** : un tronc commun construit depuis `[offre]` de `campagne.toml`, plus les
  parties propres au contact (pourquoi vous, relance, routage, objection probable), rédigées par des agents
  (`scripts_appel.py`, consigne [../consignes/cartes-appel.md](../consignes/cartes-appel.md)) ;
- **le fichier d'appel du commercial**, une ligne par contact : le contact, l'argument n°1 au téléphone et sa
  source, pourquoi maintenant, puis le détail (secteur, taille, lieu, logiciels, signaux, relais à demander, à
  savoir). En `.xlsx` (onglets Appels, Relais, Lisez-moi) et en `.csv` (`fichier_appel.py`, consignes
  `consignes/fichier-appel-*.md`) ;
- **la première phrase des comptes A** (`phrase_signal`), qui ouvre l'email 1 (consigne
  [../consignes/phrases-signal.md](../consignes/phrases-signal.md), réinjectée à l'étape 7).

Les scripts n'appellent aucun réseau et ne consomment aucun crédit : ils préparent les fiches pour les agents,
puis assemblent et contrôlent ce que les agents ont écrit.

## Règles

- **Rien n'est rédigé sans demande explicite.** Les agents de rédaction (sous-agents, ou un workflow) ne se
  lancent que sur demande, avec une estimation (section « Coûts »).
- **Que des faits de la fiche** : les agents n'ont ni recherche web ni connaissance extérieure. Aucun chiffre
  absent de la fiche ou des preuves de l'offre. Une information « indice », « à vérifier » ou « estimation » ne
  s'affirme jamais.
- **Une preuve seulement pour son propre cas d'usage** (`[offre] preuves`, champ `cas`), sans autre chiffre ni nom
  de client.
- **Jamais au prospect** : un signal négatif (il va dans « à savoir »), une phrase de `[offre] ne_jamais_dire`, la
  relation du prospect avec l'un de nos clients, « Apollo » ou « notre base », un lieu d'un autre pays (« en Suisse »
  à une entreprise française), un tiret cadratin ou demi-cadratin, un point d'exclamation.
- **Le ton de l'appel est direct** : demande de permission, raison en deux mots, une question ouverte, un seul CTA.
  L'email, lui, reste humble et au conditionnel (étape 8).

## Le tronc commun d'un appel

`scripts_appel.py` le construit depuis `[offre]` (`appelant`, `societe`, `presentation_appelant`, `description`,
`argument_cle`, `preuves`, `question_ouverte`, `cta`, `lien_agenda`, `ne_jamais_dire`). C'est le script en cinq
temps et deux minutes enseigné en formation :

1. **Ouverture**, puis on attend : « Bonjour Monsieur X, Prénom Nom, d'Exemple SA. Auriez-vous 30 secondes à
   m'accorder ou je tombe mal ? ». S'il dit non : demander quand rappeler, et raccrocher.
2. **« Vous êtes qui ? »** : une phrase (`presentation_appelant`), puis pivot immédiat.
3. **Raison de l'appel**, en deux mots (`description`, `argument_cle`), puis la preuve du même cas d'usage et la
   phrase « pourquoi vous » du contact.
4. **Question ouverte** (`question_ouverte`), puis silence : c'est le point le plus dur. Réponse courte : la relance
   du contact.
5. **CTA unique**, deux créneaux précis (`cta`).

S'y ajoutent : le message vocal (20 secondes : son nom, la raison, « je vous rappelle [jour] ») ; les objections de
la formation (« Envoyez-moi une documentation » : « Avec plaisir. Qu'est-ce qui vous serait le plus utile ? », puis
reproposer le rendez-vous ; « Pas de budget » : « Quand se décident vos budgets, et qui y participe ? » ; « On a déjà
un prestataire » : « Bon signe. Qu'est-ce qui marche bien avec lui ? » ; « Ce n'est pas moi » : « Qui serait la bonne
personne ? Je peux dire que je viens de votre part ? » ; « Rappelez plus tard » : deux créneaux précis ; « C'est
combien ? » : jamais de prix) ; et la liste « Jamais au téléphone ». Jamais « avez-vous reçu mon mail ? ».

## L'ordre des commandes

Depuis la racine du projet (adapter le chemin si le skill est installé ailleurs, par exemple dans
`~/.claude/skills/`). Prérequis : `appels/ordre-appel.csv` ([étape 8](08-sequence-et-ordre-d-appel.md)). Avant le
fichier d'appel, relire aussi `donnees/signaux/logiciels.json` ([étape 5](05-signaux-et-priorisation.md),
`collect_logiciels.py`) : seuls les statuts « probable » et « confirmé » peuvent être cités.

1. **Briefs** : une fiche de faits par entreprise de la liste « entrée », en lots équilibrés (un agent par lot) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py briefs --campagne campagnes/<nom>
   ```

   `--lots 4` par défaut. Sorties : `appels/briefs/L<n>.json` et `appels/briefs/contexte.json` (offre, persona,
   langues de l'appelant, langue de rédaction). Si le découpage en lots change, la passe précédente (briefs,
   rédactions, cartes, sources) est rangée dans `appels/precedent/<date-heure>/` : ses cartes et rédactions sont à
   refaire.
2. **Rédaction par agents, sur demande** : un agent par lot, qui lit la consigne, son lot et `contexte.json`, et
   écrit :
   - les cartes d'appel, selon [../consignes/cartes-appel.md](../consignes/cartes-appel.md), dans
     `appels/cartes/L<n>.json` (ou `appels/cartes-appel.json` si un seul agent écrit tout) ;
   - le secteur, la description, la taille et l'argument de chaque contact, selon
     [../consignes/fichier-appel-redaction.md](../consignes/fichier-appel-redaction.md), dans
     `appels/redaction/L<n>.json`.

   Le même agent peut faire les deux pour son lot : le fait de « pourquoi vous » et celui de l'argument restent
   alors les mêmes. Chaque agent vérifie que son JSON se relit, et n'écrit aucun autre fichier.
3. **Scripts d'appel** :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/scripts_appel.py --campagne campagnes/<nom>
   ```

   Sorties : `appels/scripts-appel.md` (tronc commun, puis une fiche par contact dans l'ordre d'appel) et
   `appels/scripts-appel.csv` (`priorite, contact_id, nom, entreprise, script, a_savoir`). Options : `--ordre <csv>`,
   `--cartes <json ou dossier>`, `--maj-ordre` (ajoute `script_appel` et `a_savoir_appel` au fichier d'ordre d'appel,
   à refaire après chaque `ordre_appel.py`). Lire les alertes : champs manquants, tirets, signal négatif, phrase
   interdite, lieu d'un autre pays, preuve inconnue, nom corrigé par rapport à Apollo, cartes sans contact.
4. **Sources des arguments** : des faits numérotés avec leur lien, pour que chaque argument s'ouvre sur sa source
   (« J'ai vu sur votre page LinkedIn que ... ») :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py sources --campagne campagnes/<nom>
   ```

   Sortie : `appels/sources/briefs/L<n>.json`. Puis, sur demande, un agent par lot selon
   [../consignes/fichier-appel-sources.md](../consignes/fichier-appel-sources.md), qui écrit
   `appels/sources/redaction/L<n>.json` (argument et `source_id`). Le lien et la date sont posés par le script, jamais
   par l'agent. Cette passe suppose la rédaction du point 2 (elle part de l'argument déjà écrit).
5. **Assembler** le fichier remis au commercial :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py assembler --campagne campagnes/<nom>
   ```

   Sorties : `appels/fichier-appel.xlsx` (onglets Appels, Relais, Lisez-moi) et `appels/fichier-appel.csv`.
   Options : `--export <csv>` (export de la liste « entrée » fait depuis l'interface Apollo : effectif, technologies,
   standard), `--relais <csv>`, `--ordre <csv>`, `--maj-ordre` (écrit aussi ces colonnes dans le fichier d'ordre
   d'appel ; seulement sur demande). Contrôles : tirets, signal négatif ou phrase interdite, lieu d'un autre pays,
   chiffre ou nom absent de la fiche, logiciel nommé sans confirmation, argument manquant ou trop long, argument qui
   ne s'ouvre pas sur « J'ai vu » quand les sources existent. Une alerte se corrige dans le JSON de l'agent, puis on
   relance `assembler`.

Facultatif : `appels/corrections.json`, écrit à la main (`{id: {pourquoi_maintenant, a_savoir}}`), corrige un
« pourquoi maintenant » de l'étape 5 qui citait un signal négatif, ou ajoute une note pour l'appelant.

Les briefs ne couvrent que la liste « entrée » : les relais figurent dans l'onglet Relais (à demander au
téléphone), sans script propre.

## Première phrase des comptes A (`phrase_signal`)

Sur demande explicite seulement, puisqu'elle part chez les prospects. Entrée : `phrases-a-rediger.csv` (étape 7,
aperçu de `reinjecter_apollo.py`) ; langue du contact : `appels/ordre-appel.csv` (colonne `langue_principale`),
sinon pays et canton de `prospection-signaux.csv`. Sortie : `phrases-signal.csv` (mêmes colonnes, `phrase_signal`
rempli), dans le dossier de la campagne. Règles de [../consignes/phrases-signal.md](../consignes/phrases-signal.md) :
un seul fait du signal, daté ; fidèle à la source ; vouvoiement, la phrase parle d'eux ; dans la langue du contact ;
30 mots au plus ; ni tiret long, ni signal négatif, ni donnée d'un client, ni source interne. Exemples (fictifs) :
« Vous avez annoncé l'ouverture de votre site de Sion en septembre. » ; « Félicitations pour votre nomination à la
direction des opérations. ». Puis relancer l'aperçu de l'étape 7 avec `--phrases campagnes/<nom>/phrases-signal.csv`.

## Glisser chaque script dans sa tâche Apollo (sur accord)

Aucun script du skill n'écrit de tâche. 0 crédit selon la documentation Apollo.

- Une étape `call` d'une séquence crée une tâche `scheduled` quand le contact l'atteint : pousser les scripts chaque
  matin avant la session d'appels.
- Retrouver les tâches : `POST /api/v1/tasks/search` (filtrer ensuite par contact, type et statut).
- Écrire le script : `PATCH /api/v1/tasks/{id}` avec `call_script` (ou `note`), en renvoyant `priority` (sinon
  remise à medium) et `creator_id` (sinon remis à l'utilisateur de la clé). `call_script` ne s'écrit que tant que la
  tâche est `scheduled` ; sur une tâche terminée ou sautée, seuls `note`, `priority` et `contact_id` changent.
- Sans séquence : `POST /api/v1/tasks` (une tâche par contact : `user_id`, `contact_id`, `type` `call`, `status`
  `scheduled`, `due_at`, `priority`, `title`, `note`). La création en masse met la même note partout.
- Tester sur **une seule tâche** d'abord (un 403 signale une clé sans droit sur les tâches). `due_at` est en GMT par
  défaut, les exports Apollo en heure du Pacifique : convertir depuis le fuseau de l'appelant.
- Le connecteur MCP Apollo sait créer des tâches avec une note, mais sa mise à jour ne propose pas `call_script` :
  mettre alors le script dans `note`. Variante manuelle : copier chaque script du `.md` dans la tâche.

## Après les appels

1. Noter le résultat de chaque appel entre parenthèses à la fin du titre de sa fiche dans `scripts-appel.md` : il est
   gardé à la génération suivante.
2. Exporter les tâches et leurs dispositions depuis Apollo.
3. Relancer selon le résultat : message vocal, pas de réponse, standard, mauvais numéro (email de relance, sur
   demande) ; renvoyé vers le bon profil (le relais, en citant le décideur) ; décideur indisponible ; langue ; en
   cours ; ne pas relancer (refus : sortie de toutes les campagnes).
4. Noter les enseignements datés dans `<campagne>/apprentissages.md`, au format « - [AAAA-MM-JJ] fait -> action » :
   formulations qui marchent, objections, personas qui répondent.

## Sorties

- `appels/briefs/L<n>.json`, `appels/briefs/contexte.json` ;
- `appels/cartes/L<n>.json` ou `appels/cartes-appel.json`, `appels/redaction/L<n>.json` (agents) ;
- `appels/scripts-appel.md`, `appels/scripts-appel.csv` ;
- `appels/sources/briefs/L<n>.json`, `appels/sources/redaction/L<n>.json` (agents) ;
- `appels/fichier-appel.xlsx` et `appels/fichier-appel.csv` : **le fichier remis au commercial**. Colonnes, dans
  l'ordre de lecture : `N°, Tier, Entreprise, Prénom, Nom, Poste, Téléphone, Email, Langue, Top argument au
  téléphone, Source de l'argument, Pourquoi maintenant, Secteur, Ce qu'ils font, Taille, Pays, Canton /
  département, Ville, Logiciels, Signaux personne, Signaux direction et actionnariat, Signaux finances, Signaux
  activité et projets, Signaux tech, Relais à demander, À savoir (ne pas dire), Standard, LinkedIn, Site web, ID
  contact Apollo` ;
- `phrases-signal.csv` (agent, sur demande).

## Contrôles qualité

- Zéro alerte à `scripts_appel.py` et à `assembler`, ou chaque alerte lue et acceptée.
- Relire 5 fiches au hasard contre leur source : le fait de l'argument y figure, à la bonne date.
- Chercher les tirets longs dans tous les textes destinés aux prospects avant tout export (commande à l'étape 8).
- Vérifier que les logiciels cités sont « probable » ou « confirmé » dans `logiciels.json`.

## Coûts et validations

- Scripts : quelques secondes, 0 crédit, aucun réseau.
- Agents de rédaction : environ 1,5 M tokens pour 8 agents (4 pour la rédaction, 4 pour les sources) sur une
  centaine de contacts, soit environ 15 000 tokens par contact. Les cartes d'appel n'ont pas été mesurées à part :
  compter le même ordre que la rédaction. Autres ratios : [../reference/couts.md](../reference/couts.md).
- Accords : toute rédaction (cartes, arguments, sources, phrases) ; toute écriture dans les tâches Apollo.

## Pièges principaux

Agent qui invente un chiffre ou un nom ; preuve citée hors de son cas ; lieu d'un autre pays ; logiciel nommé sur
un simple indice ; même nom de famille dans une entreprise familiale ; prénom et nom inversés par Apollo ; lots
redécoupés après la rédaction ; `PATCH` de tâche qui remet la priorité ; script automatique d'Apollo en anglais.
Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 9 ».
