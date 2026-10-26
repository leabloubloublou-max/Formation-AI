# Inventaire des outils : scripts, workflows, consignes

Chaque script : son rôle, sa commande exacte (options d'après son `--help`), ce qu'il lit et ce qu'il écrit. Les
colonnes des fichiers sont détaillées dans [contrat.md](contrat.md), les coûts dans [couts.md](couts.md).

Toutes les commandes se lancent **depuis la racine du projet** (celle qui contient `.venv` et `.env`), avec
`.venv/bin/python`. Si le skill est installé ailleurs que dans `.claude/skills/prospection-base-client/` (par
exemple `~/.claude/skills/prospection-base-client/`), adapter le chemin du script. `campagnes/<nom>` désigne le
dossier de la campagne. Chaque `--help` marche sans réseau, sans clé et sans campagne.

Sommaire : 1. Environnement ; 2. Modules partagés ; 3. Outils des agents ; 4. Étape 2 ; 5. Étape 3 ; 6. Étape 4 ;
7. Étape 5 ; 8. Étape 6 ; 9. Étape 7 ; 10. Étape 8 ; 11. Étape 9 ; 12. Workflows : lancer, reprendre, suivre ;
13. Consignes et données du skill.

## 1. Environnement

- **Python 3.11 ou plus**, dans un environnement virtuel `.venv` à la racine du projet, avec les paquets de
  `requirements.txt` du skill : `requests`, `beautifulsoup4`, `lxml`, `ddgs` (DuckDuckGo, sans clé), `openpyxl`
  (fichier d'appel `.xlsx`). Installation : README.md. Contrôle :
  `.venv/bin/python -c "import ddgs, requests, bs4, openpyxl"`. Toujours `.venv/bin/python` : selon le PATH,
  `python3` peut être un autre interpréteur, sans ces paquets.
- **`.env`** à la racine du projet : `APOLLO_API_KEY=...` (modèle : `exemple.env`), lu par `commun.cle_apollo()`
  (variable d'environnement, sinon `.env` du dossier courant ou d'un dossier parent, sinon `.env` du skill). Seules
  les étapes 6 et 7 (et `creer_comptes.py --go`) en ont besoin. Ne jamais l'afficher ; vérifier sa présence :
  `grep -c '^APOLLO_API_KEY=.' .env` et `git check-ignore -q .env && echo ".env ignoré par git"`.
- **Outil Workflow de Claude Code** pour les workflows multi-agents (section 12), lancés seulement sur demande
  explicite de l'utilisateur.
- **`verifier_installation.py`** : contrôle de l'installation et, avec `--campagne`, du dossier de campagne (sans
  réseau ; la clé n'est jamais affichée).

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py [--campagne campagnes/<nom>]
  ```

  Lit : Python et les paquets du `.venv`, les fichiers du skill, la présence de la clé Apollo (et si `.env` est
  ignoré par git) ;
  avec `--campagne`, `campagne.toml` (sections, clés, types, valeurs d'exemple restées) et les fichiers facultatifs.
  Écrit : rien. Affiche une ligne par contrôle et la prochaine action ; code de sortie 1 s'il reste un point à
  corriger.

## 2. Modules partagés (importés, sans commande)

| Module | Rôle |
|---|---|
| `commun.py` | Dossier de campagne (`Campagne` : `.dossier`, `.config`, `.donnees`, `.signaux`, `.verification`, `.apollo`, `.appels`, `.liste_entreprises()`, `.date_reference()`), lecture de `campagne.toml` fusionnée avec les valeurs par défaut, CSV (`lire_csv`, `ecrire_csv`), noms et sites (`norm`, `domaine`, `site_propre`, `linkedin_company`), `--deja` et `--exclure` (`charger_noms`), localités suisses (`charger_localites`, `region`), pays (`code_pays`, `region_recherche`), DuckDuckGo avec relances (`recherche_web`), clé Apollo (`cle_apollo`), colonnes du contrat (`COLONNES_ENTREPRISES`, `COLONNES_CONTACTS`). |
| `persona.py` | Familles de rôles (direction, qualite, it, production, technique, service, ventes, finance, achats, projet) : mots pour lire `persona_cible`, intitulés Apollo FR, EN, DE, IT et faux amis, intitulés de recherche, requêtes web. Classe `Persona(config)` : fusion avec `[persona.titres]`, familles d'entrée et de relais ; séniorité d'un intitulé ; lecture de la colonne `dirigeants`. |
| `apollo_api.py` | Client REST Apollo : clé jamais affichée, débit à 80 % des quotas (`LIMITES`), reprise des 429 et 5xx, arrêt clair sur 401 et 403, cache disque `<campagne>/apollo/cache/`. Méthodes : listes, comptes, personnes, contacts, champs, enrichissement (seule méthode qui consomme des crédits), mobiles asynchrones, création de contacts, de comptes, de listes et de champs, ajout et retrait de listes, mise à jour de contacts. |
| `signaux_commun.py` | Base de l'étape 5 : `ouvrir(--campagne)` fixe la date de référence, la fenêtre des signaux et le dossier `donnees/signaux/` ; HTTP tolérant, dates FR, DE, EN, IT, cache JSON partagé entre threads. |
| `lexique.py` | Règles de détection des signaux dans un texte libre (familles direction, financement, ma, croissance, projet, tech, negatif). À adapter : programmes publics, certifications, famille tech. |
| `auto.py` | Recalcule les signaux automatiques depuis les textes déjà collectés, avec le lexique courant (corriger le lexique suffit, sans refaire la collecte). |
| `icp.py` | Fit de chaque entreprise (zone, taille, secteur, 0 à 3 chacun, sur 9) et motifs d'exclusion, d'après `[cible]` ; ajustement par les agents ; catégories de secteur passées au workflow. |

## 3. Outils des agents

Utilisés par les agents des workflows (sorties courtes, environ 1 000 tokens) ; aussi utiles à la main. N'écrivent
aucun fichier, sans clé.

- **`outils_web.py`** : recherche DuckDuckGo, pages LinkedIn d'une entreprise, lecture d'une page.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py search "<requête>" [-n 8] [--region ch-fr]
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py linkedin "<nom entreprise>" [--region ch-fr]
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py peek <url>
  ```

  Lit : DuckDuckGo, la page demandée. Sorties : `[i] titre | url | extrait` ; pages `/company/` candidates ; pour
  `peek`, statut HTTP, URL finale, titre, description, liens LinkedIn de la page, indices de pays et d'adresse,
  pages utiles, extrait. `--region` : région DuckDuckGo (`ch-fr`, `de-de`...) ou code pays (`CH`, `FR`...).
- **`outils_signaux.py`** : registre du commerce suisse, LinkedIn public, actualités datées.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_signaux.py zefix "<nom de société>" [--langue fr]
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_signaux.py li <url linkedin company>
  .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_signaux.py news "<requête>" [--region ch-fr]
  ```

  Lit : API publique du registre suisse (Zefix), LinkedIn en vue invité, DuckDuckGo. `zefix` donne l'URL de la
  fiche, à citer comme source ; hors de Suisse, chercher le registre du pays avec `outils_web.py search`.

## 4. Étape 2 : trouver les entreprises

Détail : [../etapes/02-trouver-les-entreprises.md](../etapes/02-trouver-les-entreprises.md).

- **`workflows/decouverte-entreprises.js`** (multi-agents, sur demande explicite) : un agent par segment
  (« secteur, zone ») et par source transverse (défaut : listes d'exposants, annuaires d'associations et de
  clusters, offres d'emploi), chacun rend les entreprises avec une preuve publique ; puis une critique de couverture
  et des compléments.
  - Lancement : outil Workflow, `scriptPath` = `<skill>/workflows/decouverte-entreprises.js`, `args` =
    `{racine, campagne, icp, contexte, segments: [...], exclusions?, sources?: [{id, titre, consigne}], python?,
    skill?, max_complements? (6), cible_par_agent? (40)}`. `racine` : chemin absolu du projet.
  - Lit : `args` ; les agents utilisent WebSearch, WebFetch et `outils_web.py`.
  - Écrit : rien. Les retours restent dans le journal du run, que lit `consolider_decouverte.py`.
- **`consolider_decouverte.py`** : consolide les journaux de la découverte. Contrôle anti-invention sur les
  transcripts des agents (site, LinkedIn, URL de preuve ou de signal non vus : écartés), dédoublonnage par nom puis
  par domaine, canton et région linguistique pour la Suisse, statut de chaque entreprise.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/consolider_decouverte.py --campagne campagnes/<nom> <journal.jsonl ou dossier du run> [...] [--deja <liste.csv>]... [--exclure <csv>]... [--linkedin <csv>] [--garder-hors-cible] [--garder-non-vues] [--ajouter]
  ```

  - Lit : les journaux et les `agent-<id>.jsonl` voisins (sorties volumineuses relues dans leur fichier complet) ;
    `--deja` (nos listes) ; `--exclure` (défaut : `exclure.csv` de la campagne) ; `--linkedin` (défaut :
    `entreprises-linkedin.csv` de la campagne) ; `donnees/localites-suisse.csv` du skill.
  - Écrit : `donnees/decouverte-mentions.json`, `entreprises-toutes.csv` (à relire), `entreprises.csv` (au
    contrat). `--ajouter` garde les fichiers existants et n'ajoute que les entreprises nouvelles. Sans `--ajouter`,
    un ancien `apollo/contacts-importes.csv` devient `contacts-importes.precedent.csv`.
- **`importer_liste.py`** : met au contrat un export Apollo (comptes ou contacts) ou toute liste CSV qui a un nom
  d'entreprise ; dédoublonne par domaine puis par nom ; retire nos clients et partenaires ; marque les entreprises
  déjà connues.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/importer_liste.py --campagne campagnes/<nom> <export1.csv> [<export2.csv> ...] [--exclure <csv>]... [--deja <liste.csv>]... [--col-nom "<en-tête>"] [--ajouter]
  ```

  - Lit : les CSV (en-têtes Apollo reconnus : `Company Name`, `Website`, `Company Linkedin Url`, `# Employees`,
    `Industry`, `Technologies`... ; pour les contacts : `First Name`, `Last Name`, `Title`, `Seniority`, `Email`,
    `Email Status`, `Apollo Contact Id`, `Stage`, `Last Contacted`...), `--exclure`, `--deja`, `[persona]`.
  - Écrit : `entreprises-toutes.csv`, `entreprises.csv` ; pour un export de contacts, `apollo/contacts-importes.csv`
    (ordre entrée ou relais déduit de l'intitulé, à relire). `--ajouter` : comme ci-dessus, contacts compris.
- **`linkedin_site.py`** : pages LinkedIn lues sur le site de chaque entreprise (sans moteur de recherche), pour
  compléter celles que les agents n'ont pas vues.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py --campagne campagnes/<nom>
  .venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py <fichier.csv> [--campagne campagnes/<nom>] [--col-site <colonne>] [--col-nom <colonne>] [--workers 12] [--limite N]
  ```

  - Lit : le CSV (défaut : `entreprises.csv` de la campagne) ; cache `donnees/cache/linkedin-sites.json`.
  - Écrit : `<csv sans extension>-linkedin.csv` à côté du CSV (pour la campagne : `entreprises-linkedin.csv`, que
    `consolider_decouverte.py` relit par défaut).

## 5. Étape 3 : enrichir site et LinkedIn

Détail : [../etapes/03-enrichir-site-linkedin.md](../etapes/03-enrichir-site-linkedin.md).

- **`enrichir_sites.py`** : site officiel puis page LinkedIn des entreprises qui n'en ont pas, par DuckDuckGo (page
  LinkedIn lue sur le site quand il est sûr). Corrections manuelles facultatives.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_sites.py --campagne campagnes/<nom> [--workers 4] [--limite N]
  ```

  - Lit : `entreprises.csv` ; `corrections.csv` (facultatif : `nom, site, linkedin`) ; caches
    `donnees/cache/enrichir-sites.json` et `donnees/cache/linkedin-sites.json`.
  - Écrit : `entreprises-enrichi.csv` (candidats à vérifier à l'étape 4). Une relance ne refait que ce qui manque.

## 6. Étape 4 : vérifier par agents

Ordre : `verif_preparer.py`, workflow de passe 1, `verif_appliquer.py` ; s'il reste des cas ouverts,
`verif_passe2.py`, workflow de passe 2, `verif_appliquer.py` avec les deux journaux. Détail :
[../etapes/04-verifier-par-agents.md](../etapes/04-verifier-par-agents.md).

- **`verif_preparer.py`** : lots de la passe 1. Catégorie de chaque entité (solide, probable, faible, non
  recherché) ; contrôle léger des solides, vérification profonde du reste.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_preparer.py --campagne campagnes/<nom> [--mode auto|leger|profond] [--taille-profond 25] [--taille-leger 90] [--max N]
  ```

  - Lit : `entreprises-enrichi.csv`, sinon `entreprises.csv` (jamais `-verifie.csv`) ; `campagne.toml`.
  - Écrit : `donnees/verification/lots/D*.json` et `L*.json` (anciens lots D et L effacés),
    `manifeste-passe1.json`, `args-passe1.json`. Affiche un ordre de grandeur en tokens.
- **`workflows/verification.js`** (multi-agents, sur accord) : un agent par lot (profond : environ 3 appels d'outils
  par entité, 6 au plus ; léger : jugement sans outil), puis contre-vérification sceptique de chaque URL corrigée ou
  trouvée, par paquets de 40.
  - Lancement : `scriptPath` = `<skill>/workflows/verification.js`, `args` = contenu de `args-passe1.json`.
  - Écrit : rien (journal du run).
- **`verif_passe2.py`** : lots de la passe 2 : R (résolution des entités à revoir ou non identifiées) et C
  (complétion des sites et pages LinkedIn manquants). Fusionne les alias.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_passe2.py --campagne campagnes/<nom> [--taille-resolution 7] [--taille-completion 17] [--max N]
  ```

  - Lit : `entreprises-verifie.csv` (sans lui, la liste de l'étape 2 ou 3 : complétion directe).
  - Écrit : `donnees/verification/lots/R*.json` et `C*.json`, `manifeste-passe2.json`, `args-passe2.json`.
- **`workflows/verification-passe2.js`** (multi-agents, sur accord) : résolution, complétion, contre-vérification
  par paquets de 30. `args` = contenu de `args-passe2.json`. Écrit : rien (journal du run).
- **`verif_appliquer.py`** : applique les journaux dans l'ordre (le dernier l'emporte), avec la contre-vérification,
  le contrôle anti-invention sur les transcripts, le marquage « non vérifié » des entités sans retour, puis les
  arbitrages manuels. Relançable à volonté : le résultat ne dépend que de la liste, des journaux et des arbitrages.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom> <journal passe 1> [<journal passe 2> ...] [--arbitrages <csv>] [--sans-controle]
  ```

  - Lit : les journaux (ou dossiers de run) et les transcripts voisins, `entreprises-enrichi.csv` sinon
    `entreprises.csv`, les manifestes, `arbitrages.csv` (facultatif), les localités suisses.
  - Écrit : `entreprises-verifie.csv` ; l'ancienne version dans
    `donnees/verification/entreprises-verifie.precedent.csv`. Refuse d'écrire si aucun lot n'est trouvé.

## 7. Étape 5 : signaux et priorisation

Ordre : `entites.py` ; `collect_zefix.py` (Suisse) ; `collect_linkedin.py` en arrière-plan, `collect_site.py` en
parallèle ; `collect_zefix.py --refresh` ; `collect_news.py` ; `dossiers.py` ; workflow de recherche (sur accord) ;
`apply_recherche.py` ; `scorer.py` ; `collect_logiciels.py` puis relecture de `logiciels.json`. Veille avant
chaque vague : `collect_zefix.py --refresh`, `collect_linkedin.py --retry`, `collect_news.py --refresh`,
`scorer.py`, puis l'aperçu de `reinjecter_apollo.py` (avec `--phrases` dès que `phrases-signal.csv` existe).
Détail : [../etapes/05-signaux-et-priorisation.md](../etapes/05-signaux-et-priorisation.md).

- **`entites.py`** : une fiche par entreprise ; fusion des doublons (même nom ou nom officiel, ou même site et même
  LinkedIn avec un mot commun) ; drapeaux. Pose l'`id`, clé de tout ce qui suit.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/entites.py --campagne campagnes/<nom> [--liste <csv>]
  ```

  Lit : la liste la plus avancée (ou `--liste`). Écrit : `donnees/signaux/entites.json`.
- **`collect_zefix.py`** : registre du commerce suisse et publications officielles ; seulement si
  `[signaux] registre_suisse` est vrai, et pour les entreprises suisses ou de pays inconnu.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> [--refresh] [--workers 4] [--radiees-ans 8]
  ```

  Lit : `entites.json`, `linkedin.json` (facultatif), l'API publique Zefix. Écrit : `donnees/signaux/zefix.json`
  (une relance ne traite que les nouvelles entreprises ; `--refresh` refait tout).
- **`collect_linkedin.py`** : page LinkedIn publique (secteur, taille, siège, description, derniers posts datés) ;
  corrige les URL fausses. Lent et séquentiel : en arrière-plan, jamais en même temps que des agents qui ouvrent
  LinkedIn depuis la même adresse.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_linkedin.py --campagne campagnes/<nom> [--retry] [--limit N] [--tous]
  ```

  Lit : `entites.json`, `zefix.json`, linkedin.com en vue invité. Écrit : `donnees/signaux/linkedin.json`.
  `--retry` refait les échecs ; `--tous` traite aussi les pays hors cible et hors voisins.
- **`collect_site.py`** : site de chaque entreprise (accueil, pages internes, sitemap) : stack, mentions tech,
  recrutement, fraîcheur.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_site.py --campagne campagnes/<nom> [--workers 8] [--refresh]
  ```

  Lit : `entites.json`, les sites. Écrit : `donnees/signaux/site.json`.
- **`collect_news.py`** : actualités DuckDuckGo des entreprises du périmètre (fit d'au moins `--fit-min`), quatre
  requêtes chacune, filtre anti-homonymes.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_news.py --campagne campagnes/<nom> [--workers 3] [--refresh] [--fit-min 5]
  ```

  Lit : `entites.json`, `zefix.json`, `linkedin.json`, `site.json`, `noms-ambigus.csv` (facultatif). Écrit :
  `donnees/signaux/news.json`.
- **`dossiers.py`** : un dossier compact par entreprise du périmètre et les lots du workflow de recherche.
  **Sans `--complement`, les lots précédents sont effacés.**

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/dossiers.py --campagne campagnes/<nom> [--lots N | --par-lot 15] [--fit-min 5] [--complement] [--max N]
  ```

  Lit : `entites.json`, `zefix.json`, `linkedin.json`, `site.json`, `news.json` ; avec `--complement`,
  `lots/manifest.json` et `recherche.json` ; `campagne.toml`. Écrit : `donnees/signaux/lots/L*.json`,
  `lots/manifest.json`, `lots/args-recherche.json`.
- **`workflows/signaux-recherche.js`** (multi-agents, sur accord) : par lot d'environ 15 entreprises, un agent de
  recherche (ICP, signaux datés et sourcés, adoption tech, dirigeants, personnes à contacter), puis un
  contre-vérificateur qui tente de réfuter les signaux forts.
  - Lancement : `scriptPath` = `<skill>/workflows/signaux-recherche.js`, `args` = contenu de
    `lots/args-recherche.json`.
  - Écrit : rien (journal du run).
- **`apply_recherche.py`** : intègre les journaux du workflow de recherche, avec les verdicts et un contrôle
  anti-invention des `source_url` ; remplace les tirets cadratins.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/apply_recherche.py --campagne campagnes/<nom> <journal.jsonl ou dossier du run> [<journal 2> ...] [--sans-controle]
  ```

  Lit : les journaux (tous ceux de la campagne, dans l'ordre chronologique) et les transcripts voisins, les lots,
  `entites.json`, `recherche.json` existant. Écrit : `donnees/signaux/recherche.json` (fusionné).
- **`scorer.py`** : consolide les signaux, calcule moment, tech, fit, tiers A, B, C, D ou Hors cible, fenêtre
  d'opportunité et score. Déterministe, relançable à tout moment.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/scorer.py --campagne campagnes/<nom>
  ```

  Lit : `entites.json` et les autres fichiers de `donnees/signaux/` (facultatifs), `historique/`, `[cible]` et
  `[persona]`. Écrit : `prospection-signaux.csv`, `rapport-signaux.md`, `donnees/signaux/signaux.json`,
  `donnees/signaux/historique/<date de référence>.json`.
- **`collect_logiciels.py`** (après `scorer.py`) : cherche sur le web le logiciel de chaque entreprise des tiers A à
  D, parmi `[signaux] logiciels`, sans rien deviner.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_logiciels.py --campagne campagnes/<nom> [--workers 3] [--refresh] [--mot ERP] [--tiers A,B,C,D] [--max N]
  ```

  Lit : `prospection-signaux.csv`, `entites.json`. Écrit : `donnees/signaux/logiciels.json` (statut `indice` ou
  `aucun`, à relire et passer à `probable` ou `confirmé` ; une entrée relue n'est jamais écrasée).

## 8. Étape 6 : contacts Apollo

Ordre : `creer_comptes.py`, `extraire_personas.py`, `chercher_contacts.py` (test, puis complet), `chercher_web.py`,
`chercher_contacts.py`, validation, `enrichir_et_creer.py` (aperçu, `--limite 10 --go`, `--go`),
`exporter_listes.py`. Détail : [../etapes/06-contacts-apollo.md](../etapes/06-contacts-apollo.md).

- **`creer_comptes.py`** : liste de comptes Apollo des tiers choisis. Sans `--go` : aperçu et CSV d'import, aucun
  appel. Avec `--go` (accord, 0 crédit) : comptes créés par 100 et ajoutés à la liste.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/creer_comptes.py --campagne campagnes/<nom> [--tiers A,B,C,D] [--liste NOM] [--go]
  ```

  Lit : `prospection-signaux.csv`, `[apollo] liste_comptes`. Écrit : `apollo/comptes-a-importer.csv` ; avec `--go`,
  les comptes et la liste dans Apollo.
- **`extraire_personas.py`** : structure les cibles de chaque entreprise (entrée et relais, personnes nommées,
  familles de rôles), sans réseau.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/extraire_personas.py --campagne campagnes/<nom> [--tiers A,B,C,D]
  ```

  Lit : `prospection-signaux.csv`, `donnees/signaux/recherche.json` (facultatif), `[persona]`, `[signaux]
  logiciels`. Écrit : `apollo/cibles.json`, `apollo/cibles-apercu.csv`.
- **`chercher_contacts.py`** : recherche gratuite des contacts dans Apollo, compte par compte ; fichier de revue.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom> [--entreprises "mot1,mot2"] [--liste-comptes NOM]
  ```

  Lit : `apollo/cibles.json`, `prospection-signaux.csv`, la liste de comptes Apollo, `apollo/trouves-web.json` et
  `apollo/comptes-manuels.csv` (facultatifs), l'API Apollo (0 crédit). Écrit : `apollo/contacts-a-valider.csv`,
  `apollo/couverture.csv` (suffixe `-test` avec `--entreprises`), `apollo/comptes-apollo.json`, le cache.
- **`chercher_web.py`** : cherche sur DuckDuckGo les personnes nommées et les rôles qu'Apollo n'a pas trouvés, et
  les dirigeants des entreprises sans contact d'entrée.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_web.py --campagne campagnes/<nom>
  ```

  Lit : `apollo/cibles.json`, `apollo/couverture.csv`, `apollo/contacts-a-valider.csv`, `prospection-signaux.csv`.
  Écrit : `apollo/trouves-web.json` (résultats précédents gardés), cache `apollo/cache/web.json`.
- **`enrichir_et_creer.py`** : partie payante. Enrichit les personnes gardées, puis les crée en contacts dans les
  listes « <nom> », « - entrée » et « - relais ». Sans `--go` : aperçu chiffré, aucun appel, clé non lue.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom> [fichier.csv] [--go] [--liste NOM] [--limite N] [--mobiles {non,entree,tous}]
  ```

  Lit : `apollo/contacts-a-valider.csv` (ou le fichier passé), `prospection-signaux.csv`, `[apollo]`, `[persona]`,
  `[cible]`. Écrit : `apollo/contacts-crees.csv` (lignes d'un passage précédent gardées), les contacts et les trois
  listes dans Apollo, le cache.
- **`exporter_listes.py`** : exporte en CSV chaque liste de contacts Apollo dont le nom commence par le préfixe
  (0 crédit).

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/exporter_listes.py --campagne campagnes/<nom> [--prefixe NOM]
  ```

  Lit : les listes Apollo, `apollo/contacts-crees.csv`, `apollo/contacts-importes.csv`, `prospection-signaux.csv`.
  Écrit : `apollo/listes/<nom-de-la-liste>.csv`.

## 9. Étape 7 : réinjecter dans Apollo

Détail : [../etapes/07-reinjecter-dans-apollo.md](../etapes/07-reinjecter-dans-apollo.md).

- **`reinjecter_apollo.py`** : score A, B, C de chaque compte, signal et date, source, première phrase ; avec
  `--go`, crée les quatre champs de contact et met à jour les contacts par lots de 100 (0 crédit). Sans `--go` :
  aperçu, aucune écriture externe.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> [--date AAAA-MM-JJ] [--contacts <csv>] [--phrases <csv>] [--go [--limite N]]
  ```

  Lit : `prospection-signaux.csv`, `donnees/signaux/signaux.json`, `donnees/signaux/recherche.json` (facultatif),
  les contacts (`--contacts`, sinon `apollo/contacts-crees.csv`, sinon `apollo/contacts-importes.csv`),
  `--phrases`. Écrit : `base-abc.csv`, `phrases-a-rediger.csv`, `apollo/reinjection.csv` ; avec `--go`, les champs
  dans Apollo et `apollo/champs-apollo.json`.

## 10. Étape 8 : séquence et ordre d'appel

- **`ordre_appel.py`** : ordre d'appel d'une liste (refus avec réponse en fin, langue de l'appelant, téléphone
  connu, tier et rang). Aucun réseau. Sert aussi de module aux scripts des étapes 8 et 9 (chargement des contacts,
  clé `contact_id`, jointure à l'entreprise).

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/ordre_appel.py --campagne campagnes/<nom> [--liste {entree,relais}] [--contacts <csv>] [--export <csv>]
  ```

  Lit : les contacts (export de la liste dans `apollo/listes/`, sinon `contacts-crees.csv`, sinon
  `contacts-importes.csv`), `prospection-signaux.csv`, `[appels] langues` ; facultatifs : `--export` (export de
  l'interface Apollo), `apollo/comptes-apollo.json`, `donnees/signaux/entites.json`, `appels/langue-contacts.json`,
  les localités suisses. Écrit : `appels/ordre-appel.csv` (ou `appels/ordre-appel-relais.csv`).
- **`plan_sequence.py`** : plan de séquence, une ligne par contact : vagues de comptes A puis B, une seule voix par
  entreprise, canal, cadence J1 à J22. Aucun réseau.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/plan_sequence.py --campagne campagnes/<nom> [--comptes-semaine 15] [--scores A,B] [--debut AAAA-MM-JJ] [--contacts <csv>]
  ```

  Lit : `base-abc.csv` (obligatoire), les contacts (`--contacts`, sinon `apollo/contacts-crees.csv`, sinon
  `apollo/contacts-importes.csv`), `appels/ordre-appel.csv` et `appels/ordre-appel-relais.csv` (facultatifs),
  `[campagne] date_reference`. Écrit : `appels/plan-sequence.csv`.

Aucun script ne crée de séquence ni n'inscrit de contact : voir
[../etapes/08-sequence-et-ordre-d-appel.md](../etapes/08-sequence-et-ordre-d-appel.md) (API, accords).

## 11. Étape 9 : scripts et fichier d'appel

Détail : [../etapes/09-scripts-et-fichier-d-appel.md](../etapes/09-scripts-et-fichier-d-appel.md).

- **`scripts_appel.py`** : un script d'appel complet par contact, dans l'ordre d'appel : tronc commun tiré de
  `[offre]`, parties propres au contact tirées des cartes des agents ; contrôles. Sert aussi de module à
  `fichier_appel.py` (lieux par pays, motifs interdits, cartes).

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/scripts_appel.py --campagne campagnes/<nom> [--ordre <csv>] [--cartes <json ou dossier>] [--maj-ordre]
  ```

  Lit : `campagne.toml` (`[offre]`, `[cible] pays`), `appels/ordre-appel.csv`, les cartes
  (`appels/cartes-appel.json` et `appels/cartes/*.json`), l'ancien `appels/scripts-appel.md` (résultats notés).
  Écrit : `appels/scripts-appel.md`, `appels/scripts-appel.csv` ; avec `--maj-ordre`, deux colonnes ajoutées au
  fichier d'ordre d'appel.
- **`fichier_appel.py`** : fichier d'appel du commercial, en trois commandes, dans cet ordre.

  ```bash
  .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py briefs --campagne campagnes/<nom> [--lots 4] [--ordre <csv>] [--relais <csv>] [--export <csv>]
  .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py sources --campagne campagnes/<nom> [--ordre <csv>]
  .venv/bin/python .claude/skills/prospection-base-client/scripts/fichier_appel.py assembler --campagne campagnes/<nom> [--ordre <csv>] [--relais <csv>] [--export <csv>] [--maj-ordre]
  ```

  - Lit (aucun réseau) : `appels/ordre-appel.csv`, `prospection-signaux.csv`, `donnees/signaux/` (`signaux.json`,
    `recherche.json`, `linkedin.json`, `logiciels.json`, `entites.json`), `apollo/cache/` (parcours des personnes),
    les relais (export « - relais », sinon `contacts-crees.csv`), `apollo/comptes-apollo.json`, les cartes, les
    rédactions et sources des agents ; facultatifs : `--export`, `appels/corrections.json`.
  - Écrit : `briefs` : `appels/briefs/L*.json`, `appels/briefs/contexte.json` (passe précédente rangée dans
    `appels/precedent/<date-heure>/` si le découpage change) ; `sources` : `appels/sources/briefs/L*.json` ;
    `assembler` : `appels/fichier-appel.xlsx` (onglets Appels, Relais, Lisez-moi) et `appels/fichier-appel.csv`.

## 12. Workflows : lancer, reprendre, suivre

Les quatre workflows du skill (`decouverte-entreprises.js`, `verification.js`, `verification-passe2.js`,
`signaux-recherche.js`) se lancent **tels quels** avec l'outil Workflow : `scriptPath` = le fichier du skill,
`args` = l'objet JSON décrit en tête du fichier (pour les trois derniers, le fichier `args-*.json` écrit par le
script de préparation). Rien de propre à une campagne n'est écrit dans les scripts. Aucun ne modifie de fichier : les
retours restent dans le journal du run, lu ensuite par un script Python. Chacun rend un résumé avec une clé `suite`
qui donne la commande d'après.

- **Accord** : un workflow multi-agents ne se lance que sur demande explicite de l'utilisateur, après une estimation
  chiffrée (agents, durée, tokens : [couts.md](couts.md)). Une fois l'accord donné, enchaîner sans redemander (passe
  2 comprise) et prévenir à la fin avec un bilan chiffré.
- **Adapter une consigne** : copier le workflow dans `<campagne>/workflows/`, le modifier, lancer la copie. Charger
  d'abord le skill `workflow-authoring`.
- **Reprise après une coupure** (limite de session) : même `scriptPath`, `resumeFromRunId: "<runId>"` et mêmes
  `args` ; les agents terminés sont rejoués depuis le cache.
- **Où sont les journaux** : pour une session `<session>` du projet, dans `~/.claude/projects/<projet>/` :
  - `<session>/subagents/workflows/<runId>/journal.jsonl` : une ligne par événement (`launched`, `started` avec
    `agentId` et `label`, `result` avec le retour de l'agent, `failed`) ;
  - `<session>/subagents/workflows/<runId>/agent-<agentId>.jsonl` : le transcript de chaque agent (sert au contrôle
    anti-invention) ;
  - `<session>/workflows/<runId>.json` : `args`, résultat, `durationMs`, `totalTokens`, `totalToolCalls` (le coût
    réel du run).
- **Retrouver le dossier d'un run** (l'outil Workflow ne donne que le runId) :
  `find ~/.claude/projects -type d -path '*workflows*' -name '<runId>'`. Derniers runs, toutes sessions :
  `ls -td ~/.claude/projects/*/*/subagents/workflows/wf_* | head -5`. Passer aux scripts le **dossier du run** (ou
  son `journal.jsonl` en place), jamais une copie du journal seul.
- **Point d'avancement** (fait, en cours, échecs), sans interrompre le run, `D` étant le dossier du run :

  ```bash
  .venv/bin/python - "$D/journal.jsonl" <<'EOF'
  import json, sys
  from collections import Counter
  lab, etat = {}, {}
  for l in open(sys.argv[1]):
      e = json.loads(l)
      t, a = e.get("type"), e.get("agentId")
      if t == "started":
          lab[a] = e.get("label") or e.get("key")
          etat[lab[a]] = "en cours"
      elif t in ("result", "failed") and a in lab:
          etat[lab[a]] = "fait" if t == "result" else "échec"
  print(dict(Counter(etat.values())), "| en cours :", [k for k, v in etat.items() if v == "en cours"],
        "| échecs :", [k for k, v in etat.items() if v == "échec"])
  EOF
  ```

## 13. Consignes et données du skill

| Fichier | Rôle |
|---|---|
| `config/campagne.exemple.toml` | schéma commenté de `campagne.toml`, à copier dans le dossier de la campagne |
| `donnees/localites-suisse.csv` | répertoire officiel des localités suisses (swisstopo, séparateur `;`) : commune vers canton et langue |
| `consignes/phrases-signal.md` | première phrase de chaque compte A (étape 7, sur demande) |
| `consignes/cartes-appel.md` | parties personnalisées des scripts d'appel (étape 9) |
| `consignes/fichier-appel-redaction.md` | secteur, description, taille et argument du fichier d'appel (étape 9) |
| `consignes/fichier-appel-sources.md` | argument ouvert sur sa source, « J'ai vu sur ... que ... » (étape 9) |
| `requirements.txt`, `exemple.env` | dépendances Python et modèle du fichier `.env` |
