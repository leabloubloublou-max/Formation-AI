# Étape 1 : identifier la cible et le persona

Toutes les commandes se lancent depuis la racine du projet, le dossier qui contient `.venv`. Elles supposent le
skill dans `.claude/skills/prospection-base-client/`. S'il est ailleurs (par exemple dans
`~/.claude/skills/prospection-base-client/`), adaptez ce chemin dans chaque commande. `<nom>` est le nom du
dossier de la campagne.

## Objectif

Fixer avec l'utilisateur, avant toute recherche :
- ce que l'on vend, et à qui (la cible) ;
- qui contacter dans chaque entreprise (le persona du décideur, puis les relais) ;
- qui ne jamais contacter (nos clients et partenaires actuels) ;
- d'où viendra la liste d'entreprises (la source de l'étape 2).

Tout est écrit dans le dossier de la campagne. Les étapes suivantes le relisent.

## Entrées

- Une conversation avec l'utilisateur : l'offre, les preuves clients réelles, la cible (secteurs, zone, taille),
  les exclusions, qui appelle et signe.
- Le modèle de configuration du skill : `config/campagne.exemple.toml`.
- La liste de nos clients et partenaires actuels (nom et site).
- S'il en existe : une liste d'entreprises (export Apollo, exposants d'un salon, annuaire) et nos listes des
  campagnes précédentes.

## Déroulé

### 1. Créer le dossier de la campagne

```bash
mkdir -p campagnes/<nom>
cp .claude/skills/prospection-base-client/config/campagne.exemple.toml campagnes/<nom>/campagne.toml
```

Le dossier peut être ailleurs : chaque script prend `--campagne <dossier>`, relatif au dossier courant ou absolu.
Toutes les sorties vont dans ce dossier, jamais dans celui du skill.

Contrôle de l'installation, une fois (README.md, « Installation ») : aucune ligne ✗.

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py
```

Il contrôle Python, les paquets, les fichiers du skill et la clé Apollo (présente ou non, jamais affichée), sans
réseau. Lancez toujours `.venv/bin/python` : selon le PATH, `python3` peut être un autre interpréteur, sans `ddgs`.

Données nominatives : les fichiers de la campagne contiendront des noms de dirigeants, puis des emails et des
téléphones (Apollo). Décidez avec l'utilisateur, avant la première écriture, si le dossier de la campagne entre
dans git. Sans réponse, ne commitez rien de ce dossier et reposez la question au premier commit demandé. Bloc à
proposer pour `.gitignore` (ne pas l'écrire sans accord) :

```gitignore
campagnes/<nom>/*.csv
campagnes/<nom>/donnees/
campagnes/<nom>/apollo/
campagnes/<nom>/appels/
```

### 2. Identifier le persona du décideur

On cible un décideur, pas seulement une entreprise. Prompt de la formation (« Identifier », slide 28), à lancer
avec l'utilisateur, crochets à remplacer :

> Nous vendons [votre offre] à [type d'entreprise]. Donne-moi le persona du décideur : ses intitulés de poste en
> français et en anglais, ce sur quoi il est évalué, ses motivations, ses objections probables, son calendrier de
> décision, et cinq signaux publics qui montrent qu'il est prêt à acheter maintenant. Si une réponse dépend de notre
> contexte, pose-moi la question.

Posez les questions à l'utilisateur, faites valider la réponse, puis écrivez-la dans `campagnes/<nom>/persona.md`.
Aucun script ne lit ce fichier : c'est la référence de la campagne. Il sert à chaque étape :
- les **intitulés de poste** : section `[persona]` de `campagne.toml` (point 3) et filtres « fonction et
  ancienneté » d'Apollo (étape 2) ;
- les **signaux d'achat** : choix des segments de la découverte (étape 2), lecture des signaux et score A, B, C
  (étape 5) ;
- les **motivations, objections et calendrier** : cadence et scripts d'appel (étapes 8 et 9), écrits seulement
  sur demande.

Repère de terrain : on entre souvent par le dirigeant (autorité, accès), mais la conversation utile bascule vite
vers des profils opérationnels (qualité, planification, informatique, maintenance...). Ce sont les relais : les
nommer dès maintenant dans `persona.relais`.

### 3. Compléter campagne.toml

Remplacez chaque valeur marquée « À COMPLÉTER ». Les valeurs déjà écrites sont un exemple fictif. La clé Apollo
ne va jamais ici, mais dans le fichier `.env` (modèle : `exemple.env`), et seulement à partir de l'étape 6.

| Section | Clés | Qui s'en sert |
|---|---|---|
| `[campagne]` | `nom`, `date_reference` | `nom` : titres du rapport des signaux (étape 5), des scripts et du fichier d'appel (étape 9), contexte des agents (étapes 4 et 5) ; les noms des listes Apollo viennent de `[apollo]`. `date_reference` (AAAA-MM-JJ) fige « aujourd'hui » pour les fenêtres de signaux ; vide = la date du jour |
| `[offre]` | `societe`, `description`, `argument_cle`, `preuves`, `appelant`, `presentation_appelant`, `question_ouverte`, `cta`, `lien_agenda`, `signature_email`, `concurrents`, `ne_jamais_dire` | contexte des agents (étapes 2, 4 et 5 : `societe` et `description`, écrits dans `contexte` pour la découverte), angle des signaux (`preuves[].cas`), scripts d'appel et emails (étapes 8 et 9). `dossiers.py` (étape 5) s'arrête si `societe` et `description` sont vides |
| `[cible]` | `description`, `pays`, `regions_prioritaires`, `pays_voisins`, `taille_min`, `taille_max`, `taille_limite`, `profil_secteurs`, `exclusions`, `[[cible.secteurs]]` | consignes des agents (étapes 2, 4 et 5), fit ICP et tiers (étape 5) ; `pays` règle aussi la région des recherches web (étapes 3, 5 et 6) |
| `[persona]` | `entree`, `relais`, `[persona.titres]` | ordre entrée ou relais des contacts importés (étape 2), recherche des personnes par les agents (étape 5), contacts Apollo (étape 6), fichier d'appel (étape 9) |
| `[signaux]` | `fenetre_mois`, `registre_suisse`, `logiciels` | étape 5 ; `fenetre_mois` et `logiciels` aussi à l'étape 9 |
| `[apollo]` | `liste_comptes`, `liste_contacts`, `pays_contacts`, `mobiles` | étape 6 ; `liste_contacts` aussi aux étapes 8 et 9 |
| `[appels]` | `langues` | étapes 5 et 6 (langue des recherches web), 8 et 9 (ordre d'appel, fichier d'appel) |

**La cible donne le fit sur 9** (zone + taille + secteur, chacun noté de 0 à 3, détail à l'étape 5) :
- zone : `regions_prioritaires` note 3 (codes de canton pour la Suisse, ou « romande », « alémanique »,
  « italienne »), reste de `pays` note 2, `pays_voisins` note 1, pays inconnu 1, tout autre pays 0 et hors cible ;
  sans `pays`, la zone ne compte pas (note 3 pour tous) ;
- taille : de `taille_min` à `taille_max` note 3, jusqu'à 2,5 fois `taille_max` note 2, petites et jusqu'à
  `taille_limite` note 1, au-delà 0 et hors cible (grand groupe), inconnue 1,5 ;
- secteur : les règles `[[cible.secteurs]]` d'abord (`nom`, `note` de 0 à 3, `motifs` en expressions régulières,
  `exclure`), puis le profil fourni : `profil_secteurs = "industrie"` note les fabricants 3, la distribution, les
  services techniques et le logiciel 1, les institutions et les services non industriels 0 ; `"aucun"` ne garde que
  vos règles. Secteur inconnu : 2.

**Le persona en familles.** Familles fournies : `direction`, `qualite`, `it`, `production`, `technique`,
`service`, `ventes`, `finance`, `achats`, `projet`. `entree` est la famille du premier contact, `relais` les
familles suivantes, par ordre de préférence. Dans `[persona.titres]`, ajoutez des intitulés (français, anglais,
allemand, italien) à une famille fournie, ou créez une famille (exemple du modèle : `maintenance`). Reprenez les
intitulés de `persona.md`. Une famille inconnue arrête les scripts avec un message clair.

**Les preuves** (`offre.preuves`) : seulement des résultats réels, que l'utilisateur accepte de citer. Jamais de
chiffre ni de client inventé.

### 4. Lister nos clients et partenaires : exclure.csv

Fichier `campagnes/<nom>/exclure.csv`, colonnes `nom, site` (les en-têtes `entreprise`, `company`, `name`,
`website`, `domaine`... sont aussi reconnus) :

```csv
nom,site
Entreprise A SA,https://entreprise-a.ch
```

`importer_liste.py` et `consolider_decouverte.py` (étape 2) le lisent sans option. Les entreprises qui y figurent
(même nom normalisé ou même domaine) sortent de la liste, motif « client ou partenaire actuel ». Règle de la
formation : une seule voix par entreprise, sans nos clients ni nos partenaires.

Nos listes déjà prospectées (une ancienne `prospection-signaux.csv`, un export) ne vont pas ici : elles passent
en `--deja` à l'étape 2. Ces entreprises restent dans la liste, marquées « déjà connue ».

### 5. Choisir la source de la liste

| Situation | Source | Étape 2 | Ensuite |
|---|---|---|---|
| Une cible à couvrir, pas de liste | découverte web par agents (par défaut) | `workflows/decouverte-entreprises.js`, puis `consolider_decouverte.py` | étape 3 inutile (sites vus par les agents) ; étape 4 facultative (contrôle léger ou complétion) ; étape 5 |
| Un export Apollo de comptes ou de contacts | « Extraire » de la formation | `importer_liste.py` | étape 3 si des sites manquent ; étape 4 conseillée ; étape 5 |
| Une autre liste (salon, annuaire, scraping) | liste existante | `importer_liste.py` (`--col-nom` si besoin) | étape 3 (souvent sans sites) ; étape 4 ; étape 5 |
| Une trentaine de comptes (démonstration, formation) | export Apollo ou liste courte | `importer_liste.py` | étape 5, version légère |
| Élargir une liste | les deux | le second passage avec `--ajouter` | comme ci-dessus |

La découverte web lance des agents : elle demande l'accord explicite de l'utilisateur, avec l'estimation de
l'étape 2. Pour elle, écrivez aussi les segments avec l'utilisateur (6 à 12 croisements « secteur, zone » : voir
l'étape 2).

### 6. Vérifier la configuration

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py --campagne campagnes/<nom>
```

À relancer jusqu'à ce qu'aucune ligne ✗ ne reste. Le script lit `campagne.toml` comme le feront les scripts
(`[cible]` et `[persona]` passent par `icp.py` et `persona.py`) et signale : l'erreur de syntaxe TOML avec sa
ligne, les clés inconnues ou mal typées, les clés à remplir, une famille de persona inconnue, les valeurs de
l'exemple restées en place (✗ pour celles à remplacer, ! pour celles qui peuvent convenir), les fichiers
facultatifs absents (`persona.md`, `exclure.csv`). Relire les lignes « ! » avec l'utilisateur. Il affiche aussi la
cible et le persona tels qu'il les a compris : les faire confirmer.

## Sorties

- `campagnes/<nom>/campagne.toml`, complété ;
- `campagnes/<nom>/persona.md`, validé par l'utilisateur ;
- `campagnes/<nom>/exclure.csv` (facultatif, fortement conseillé) ;
- la source choisie et, pour la découverte, les segments ;
- `campagnes/<nom>/apprentissages.md` (facultatif) : décisions et enseignements datés de la campagne, au format
  « - [AAAA-MM-JJ] fait -> action ». À compléter en fin d'étape, surtout aux étapes 2, 4 et 5.

## Contrôles qualité

- `verifier_installation.py --campagne campagnes/<nom>` (point 6) sans ligne ✗, ses lignes « ! » relues.
- Plus aucune valeur de l'exemple : le script les signale ; relire quand même `campagne.toml` ligne à ligne (les
  commentaires « À COMPLÉTER » restent après remplissage, ils ne servent pas de contrôle).
- `persona.md` et `exclure.csv` relus par l'utilisateur.
- Les preuves de `[offre]` sont réelles et citables.

## Coûts et accords

Gratuit, rien d'externe. À faire valider : la cible, le persona, les exclusions, la source, le sort git des
données.

Règles valables pour toute la chaîne :
- **Accord explicite avant toute dépense ou toute écriture externe** : crédits Apollo, création ou mise à jour
  dans Apollo. D'abord un aperçu chiffré (script sans `--go`), puis le « go » de l'utilisateur. Ce qui est
  gratuit et en lecture (DuckDuckGo, registres publics, recherche Apollo gratuite) se fait sans demander.
- **Workflow multi-agents seulement sur demande explicite.** Le proposer est permis, chiffré (agents, durée,
  tokens). Une fois l'accord donné, enchaîner sans redemander et prévenir à la fin avec un bilan chiffré.
- **Rien d'inventé** : aucune URL, aucun nom, aucun signal qui ne soit apparu dans une sortie d'outil. Un champ
  vide vaut mieux qu'un champ faux.
- **Aucun message rédigé sans demande** (email, script d'appel, message LinkedIn, première phrase).
- **Caches** : les scripts qui interrogent le web gardent un cache dans `donnees/` ; une relance reprend
  gratuitement. Ne jamais vider un cache sans raison.
- **Compter par script** avant d'annoncer un chiffre, jamais de mémoire.
- **Pas de tiret cadratin** dans les textes destinés aux prospects.

## Pièges principaux

- Cible trop large : les agents se dispersent et le fit ne trie plus rien.
- Persona réduit au dirigeant : les relais manquent aux étapes 5 et 6.
- Client actuel oublié dans `exclure.csv` : il recevrait une prospection à froid.
- Preuve client inventée, ou non autorisée, dans `offre.preuves`.
- `date_reference` laissée figée en veille : les fenêtres « moins de 12 mois » ne bougent plus.
- `python3` au lieu de `.venv/bin/python` : `ddgs` introuvable.

Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 1 ».
