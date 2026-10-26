# Étape 3 : enrichir le site et la page LinkedIn

Commandes depuis la racine du projet, skill supposé dans `.claude/skills/prospection-base-client/` (sinon,
adaptez ce chemin, voir l'étape 1). `<nom>` : le dossier de la campagne.

## Objectif

Trouver, pour chaque entreprise d'une liste qui n'en a pas, son **site officiel** et sa **page LinkedIn
entreprise** (`linkedin.com/company/...`, pas les personnes), sans clé API, avec un niveau de confiance par ligne
et un cache qui rend chaque relance gratuite. Moteur : DuckDuckGo (paquet `ddgs`), sans compte ni captcha.

Quand la faire :
- liste importée sans sites, ou avec des sites mais sans pages LinkedIn (étape 2, voie 2) ;
- **inutile après une découverte web** : les agents ont rendu les sites qu'ils ont vus, et `linkedin_site.py`
  (étape 2, point 7) a complété les pages LinkedIn.

À dire à l'utilisateur dès le départ : sur une campagne précédente, environ **un lien sur quatre** trouvé ainsi
était faux ou imparfait (homonymes, filiales d'un autre pays, annuaires). Cette étape produit des candidats ; la
vérification fiable est l'étape 4.

## Entrées

- `campagnes/<nom>/entreprises.csv` (étape 2). Seules les lignes sans site ou sans LinkedIn sont cherchées ; les
  lignes dont `exclure` est rempli sont recopiées telles quelles.
- `campagne.toml` : `cible.pays` (pays par défaut d'une ligne sans pays, pour la région de recherche).
- Facultatif : `campagnes/<nom>/corrections.csv`, corrections manuelles (point 4).
- `.venv` avec `ddgs`, `requests`, `beautifulsoup4` (README.md, « Installation »).

## Déroulé

1. **Tester sur 5 entreprises** :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_sites.py --campagne campagnes/<nom> --limite 5
   ```

   Lire les 5 résultats affichés (`nom -> site | linkedin`). Un domaine faux qui revient souvent (annuaire du pays,
   site d'emploi) peut s'ajouter à `BAD_DOMAINS` dans le script : c'est ainsi que les sites d'emploi y sont entrés.

2. **Lancer le passage complet**, en arrière-plan (une commande de plus de 10 minutes doit partir en arrière-plan
   dans Claude Code) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_sites.py --campagne campagnes/<nom> --workers 4
   ```

   Repère : environ 18 minutes pour 360 noms avec 4 workers. Le script affiche d'abord « N lignes, M entreprises à
   chercher », puis une ligne par entreprise et un total (sites et LinkedIn, par confiance). Une relance ne cherche
   que ce qui manque. Pour forcer une nouvelle recherche d'un nom, supprimer sa clé dans
   `donnees/cache/enrichir-sites.json`.

3. **Compter** par script (sur les lignes non exclues) :

   ```bash
   .venv/bin/python -c "import csv, collections; r = [x for x in csv.DictReader(open('campagnes/<nom>/entreprises-enrichi.csv', encoding='utf-8-sig')) if not x['exclure']]; print(len(r), 'lignes ; site :', collections.Counter(x['site_confiance'] or 'vide' for x in r).most_common(), '; LinkedIn :', collections.Counter(x['linkedin_source'] or 'vide' for x in r).most_common(), '; à revoir :', sum(x['a_revoir'] == 'oui' for x in r))"
   ```

4. **Corrections manuelles (facultatif)** dans `campagnes/<nom>/corrections.csv`, colonnes `nom, site, linkedin`
   (`nom` tel qu'il est écrit dans la liste) :

   ```csv
   nom,site,linkedin
   Exemple SA,https://exemple.ch,site
   Entreprise B Sàrl,-,
   ```

   Valeur d'une cellule : vide = rien à corriger ; une URL = remplace (statut « corrigé », confiance haute) ; « - »
   = vide le champ (confiance « à vérifier ») ; « ? » = garde la valeur trouvée avec une confiance basse ; `site`
   dans la colonne `linkedin` = relire la page LinkedIn sur le site. Relancer la commande du point 2 : les
   corrections s'appliquent à l'écriture, sans refaire les recherches. Un nom absent de la liste est signalé
   (« noms absents de la liste ») : corriger sa graphie. Recommandation : si l'utilisateur accepte l'étape 4,
   sauter cette relecture et passer directement aux agents ; elle prend du temps et ne se réutilise pas.

5. **Livrer honnêtement** : un tableau de fiabilité, puis un avis coût et bénéfice selon l'usage (pour une
   démonstration, s'arrêter ici ; pour un CRM ou une campagne, l'étape 4 s'impose). Catégories, les mêmes qu'à
   l'étape 4 :
   - **solide** : site sûr (confiance haute) et page LinkedIn sûre (lue sur le site officiel, ou confiance haute) ;
   - **probable** : site sûr seul ;
   - **faible** : site douteux, ou cherché sans succès ;
   - **non recherché** : ni site ni recherche.

   La répartition s'obtient gratuitement avec
   `.venv/bin/python .claude/skills/prospection-base-client/scripts/verif_preparer.py --campagne campagnes/<nom>`
   (première ligne affichée : « catégories »). Ce script prépare aussi les lots de l'étape 4, sans rien lancer.

### Méthode du script, pour le relire

- **Site** : jusqu'à 3 requêtes DuckDuckGo (`"<nom>"` exact, `<nom>`, `<nom> official website`), dans la région
  du pays de l'entreprise (en Suisse, selon la langue de la commune). Annuaires, registres, réseaux sociaux,
  places de marché et sites d'emploi écartés (`BAD_DOMAINS`). Premier domaine qui contient un mot distinctif du
  nom : confiance « haute » ; sinon premier candidat de la première requête non vide : « basse ».
- **LinkedIn** : quand le site est sûr (donné par la liste, ou trouvé avec une confiance haute), lien
  `/company/` lu sur le site (accueil, puis contact, à propos, mentions légales, impressum...) : source « site
  web », confiance « haute ». Sinon DuckDuckGo `<nom> linkedin company` : « haute » si le slug ou le titre contient
  un mot distinctif du nom, sinon premier lien, « basse » (source « duckduckgo »).
- **Robustesse** : relances avec attente croissante ; cache écrit au fil de l'eau.
- Liste qui a déjà ses sites et à qui il ne manque que les pages LinkedIn : `linkedin_site.py` suffit aussi
  (`--campagne campagnes/<nom>`, ou un CSV quelconque avec `--col-site` et `--col-nom`), sans moteur de recherche.

## Sorties

- `campagnes/<nom>/entreprises-enrichi.csv` : mêmes colonnes que `entreprises.csv` ; `site_statut` et
  `linkedin_statut` « trouvé » ou « introuvable » (« corrigé » après correction) ; `site_confiance` et
  `linkedin_confiance` « haute », « basse » ou « à vérifier » ; `linkedin_source` « site web », « duckduckgo »
  (ou la source de la liste) ; `a_revoir` = oui sans site sûr.
- Caches : `donnees/cache/enrichir-sites.json` (recherches) et `donnees/cache/linkedin-sites.json` (pages lues,
  par domaine, partagé avec `linkedin_site.py`).

Les étapes 4 et 5 lisent ce fichier de préférence à `entreprises.csv`.

## Contrôles qualité

- Comptes par confiance et par source, par script (point 3).
- Relecture rapide des lignes « basse » et des domaines sans rapport visible avec le nom.
- Aucun nom de `corrections.csv` signalé comme absent.
- Fichiers en utf-8 avec BOM : ils s'ouvrent dans Excel.

## Coûts et accords

- Gratuit (DuckDuckGo et lecture des sites). Aucun accord nécessaire.
- L'étape 4 coûte des tokens d'agents : la proposer avec une estimation, ne pas la lancer sans accord explicite.

## Pièges principaux

- Faux positifs : homonymes, filiale d'un autre pays, annuaire, site d'emploi, site sans rapport (événement
  sportif, compagnie aérienne...).
- Confiance « haute » trompeuse : elle dit seulement qu'un mot du nom est dans le domaine ou le slug (piège des
  noms génériques).
- Page LinkedIn du groupe ou d'une filiale d'un autre pays au lieu de l'entité.
- Site qui cite plusieurs pages `/company/` : la première par ordre alphabétique est gardée (risque de page de
  groupe ou de partenaire) ; la contre-vérification de l'étape 4 tranche.
- DuckDuckGo qui échoue par intermittence : relances intégrées ; relancer la commande, le cache garde l'acquis.
- `python3` au lieu de `.venv/bin/python` : `ddgs` introuvable.

Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 3 ».
