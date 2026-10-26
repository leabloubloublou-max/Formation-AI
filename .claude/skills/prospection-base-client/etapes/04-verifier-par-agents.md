# Étape 4 : vérifier par agents, sans rien inventer

Commandes depuis la racine du projet, skill supposé dans `.claude/skills/prospection-base-client/` (sinon,
adaptez ce chemin, voir l'étape 1). `<nom>` : le dossier de la campagne. Lancez les scripts de préparation depuis
la racine du projet : ils y prennent `racine` pour les `args` du workflow.

## Objectif

Pour chaque entreprise : identifier l'entité réelle (nom officiel, pays, ville, activité), puis confirmer,
corriger ou trouver son site et sa page LinkedIn, avec une preuve et un statut par champ. Rien d'inventé :
- une URL rendue doit être apparue dans une sortie d'outil de l'agent (contrôle mécanique sur les transcripts) ;
- toute valeur nouvelle ou corrigée passe par un agent de contre-vérification sceptique ;
- un champ vide vaut mieux qu'un lien faux.

Quand la faire :
- la liste doit servir à prospecter (CRM, campagne, appels) : oui. Pour une démonstration, l'étape 3 suffit ;
- après une découverte web (étape 2, voie 1) : facultatif. Un contrôle léger (`--mode leger`) ou une simple
  complétion des manques (passe 2 seule) suffit ;
- après un import ou l'étape 3 : conseillé, en mode `auto`.

## Entrées

- La liste de l'étape 2 ou 3 : `entreprises-enrichi.csv`, sinon `entreprises.csv` (jamais
  `entreprises-verifie.csv`, reconstruit à chaque application). Les lignes dont `exclure` est rempli ne sont pas
  vérifiées.
- `campagne.toml` : `cible.description` (profil attendu), `offre.societe` et `offre.description` (contexte),
  `cible.pays` et `cible.pays_voisins` (registres du commerce cités aux agents).
- Les outils des agents, `scripts/outils_web.py` (sorties d'environ 1 000 tokens, pour qu'un agent traite 25 à 30
  entreprises) : `search` (`[i] titre | url | extrait`), `linkedin` (pages `/company/` candidates avec extrait),
  `peek` (statut HTTP, URL finale, titre, description, liens LinkedIn de la page, indices de pays et d'adresse,
  pages utiles).
- Les workflows `workflows/verification.js` (passe 1) et `workflows/verification-passe2.js` (passe 2).
- Facultatif : `campagnes/<nom>/arbitrages.csv` (décisions manuelles, point 7).
- L'accord explicite de l'utilisateur (multi-agents).

## Déroulé

1. **Tester les outils** (réseau, gratuit) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py search "Exemple SA Neuchâtel" -n 5
   .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py linkedin "Exemple SA" --region CH
   .venv/bin/python .claude/skills/prospection-base-client/scripts/outils_web.py peek https://www.exemple.ch
   ```

2. **Préparer la passe 1** :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_preparer.py --campagne campagnes/<nom> [--mode auto|leger|profond] [--taille-profond 25] [--taille-leger 90] [--max N]
   ```

   - Une entité = un nom (deux lignes au même nom, à la casse et aux espaces près, n'en font qu'une). Sa
     catégorie est celle de sa ligne la plus douteuse : solide, probable, faible, non recherché (définitions à
     l'étape 3).
   - `--mode auto` (défaut) : les solides en contrôle léger, le reste en profondeur. `--mode leger` : toute entité
     dont chaque ligne a un site et n'est pas à revoir passe en contrôle léger (cas d'une découverte web).
     `--mode profond` : tout en profondeur.
   - Lots « D » (profonds, 25 entités par défaut) et « L » (légers, 90 par défaut), jamais vides. Les entités sont
     classées par incertitude et réparties en tourniquet entre les lots ; dans chaque lot, les plus incertaines
     d'abord. `--max N` ne garde que les N plus incertaines : un essai à petit coût.
   - Le script affiche les catégories, les lots, un ordre de grandeur en tokens (environ 4 500 par entité) et la
     commande de lancement. Il écrit `donnees/verification/lots/`, `manifeste-passe1.json` et `args-passe1.json`
     (les anciens lots D et L sont effacés).

   Contrôle avant tout lancement (un `args` d'une autre campagne ne produit aucune erreur : les agents vérifient
   les mauvais lots, puis tout est marqué « non vérifié ») :

   ```bash
   .venv/bin/python -c "import json; a = json.load(open('campagnes/<nom>/donnees/verification/args-passe1.json', encoding='utf-8')); print(a['campagne'], len(a['batches']), 'lots')"
   ```

3. **Annoncer le coût et obtenir l'accord.** Estimer sur le périmètre réel : solides en contrôle léger compris, et
   passe 2 probable (repères dans « Coûts et accords »). Proposer `--max` pour un essai si l'utilisateur hésite.

4. **Lancer la passe 1** : outil Workflow, `scriptPath` = chemin absolu de
   `.claude/skills/prospection-base-client/workflows/verification.js` (le script de préparation l'affiche),
   `args` = le contenu de `args-passe1.json`, tel quel.
   - Phase **Recherche** : un agent par lot. Lot profond : chaque entité vérifiée, environ 3 appels d'outil, 6 au
     plus (`args.appels`, `args.appels_max`). Lot léger : jugement sans outil (nom, domaine, slug, pays, activité
     plausibles ?), outils seulement pour les cas suspects ; les clés inchangées vont dans `confirmes`.
   - Phase **Contre-vérification** : chaque URL « corrigé » ou « trouvé » part, par paquets de 40 (`args.paquet`),
     chez des agents sceptiques (« chaque proposition est fausse jusqu'à preuve du contraire »), lot par lot dès
     que la recherche du lot finit.
   - Suivi et reprise : comme à l'étape 2 (point 5) : dossier du run par son `runId`, point d'avancement, reprise
     avec `resumeFromRunId` et les mêmes `args`.

5. **Appliquer** (sans réseau ni LLM, relançable à volonté) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom> "<dossier du run passe 1>"
   ```

   Règles, par champ (site, LinkedIn) :
   - « confirmé » : valeur gardée ; dans un lot léger, « confirmé (contrôle léger) » ;
   - « corrigé » ou « trouvé » sans valeur : « introuvable » ; avec une valeur, selon la contre-vérification :
     réfuté = champ vidé, raison en note ; incertain = valeur gardée, à revoir ; pas de verdict = « non
     contre-vérifié », à revoir ;
   - « introuvable », « ambigu », « particulier » : champ vidé, ancienne valeur en note ;
   - contrôle anti-invention (transcripts à côté du journal) : URL absente des sorties d'outils de l'agent =
     « écarté (non vu) », à revoir ; « confirmé » dont l'URL n'apparaît pas chez le contre-vérificateur =
     « incertain » ;
   - entité confiée à un lot qui ne l'a pas rendue : « non vérifié », à revoir.
   Le script affiche les compteurs par statut et chaque ligne à revoir avec ce qui bloque.

6. **Lire les lignes à revoir** et la note de chacune (raison du contre-vérificateur, candidats écartés).

7. **Arbitrer à la main (facultatif)** dans `campagnes/<nom>/arbitrages.csv`, une ligne par décision, colonnes
   `nom, champ, valeur, statut, note` (`nom` = la clé de l'entité) :

   ```csv
   nom,champ,valeur,statut,note
   Exemple SA,site,https://www.exemple-groupe.com,page du groupe,site du groupe vu par le contre-vérificateur
   Entreprise B Sàrl,linkedin,aucun,introuvable,
   ```

   Champ `site` ou `linkedin` : `valeur` = la bonne URL, vide pour garder l'actuelle, « aucun » pour vider ;
   `statut` = statut posé (« corrigé », « page du groupe », « introuvable », « ambigu »...). Champs `nom_officiel`,
   `pays`, `ville`, `activite`, `exclure`, `a_revoir`, `note` : valeur posée telle quelle (« aucun » = vide ; la
   note s'ajoute). Puis relancer la commande du point 5 (le fichier est lu sans option ; `--arbitrages <csv>` pour
   un autre fichier).

8. **Passe 2, sur les cas restés ouverts** (sans redemander si l'accord couvrait la vérification) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_passe2.py --campagne campagnes/<nom> [--taille-resolution 7] [--taille-completion 17] [--max N]
   ```

   - Lots « R » (résolution) : entités à revoir, ou non identifiées et sans site ; lots « C » (complétion) :
     entités identifiées à qui il manque le site ou la page LinkedIn sur l'une de leurs lignes.
   - Deux noms qui ne diffèrent que par la ponctuation ou les espaces (« Exemple-Tech » et « Exemple Tech ») : une
     seule entité, les autres en alias ; les agents rendent une entrée identique par alias.
   - Ordre de grandeur affiché : environ 10 000 tokens par entité. Écrit `lots/R*.json`, `lots/C*.json`,
     `manifeste-passe2.json`, `args-passe2.json`.

   Lancer : outil Workflow, `scriptPath` = `.../workflows/verification-passe2.js` (chemin absolu), `args` = le
   contenu de `args-passe2.json`. Différences avec la passe 1 : recherche web et lecture de pages en priorité (un
   autre moteur que DuckDuckGo) ; registres du commerce pour la raison sociale, jamais comme site ; « change
   d'angle » ; une petite entreprise sans site ou sans LinkedIn est un résultat valable ; environ 5 appels d'outil
   par entité, 10 au plus ; contre-vérification par paquets de 30.

   Appliquer les deux passes, **dans l'ordre** (la plus récente l'emporte) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_appliquer.py --campagne campagnes/<nom> "<dossier du run passe 1>" "<dossier du run passe 2>"
   ```

   Passe 2 seule, juste après une découverte web : `verif_passe2.py` sans passe 1 lit `entreprises-enrichi.csv` ou
   `entreprises.csv` et sert de complétion directe ; puis `verif_appliquer.py` avec le seul run de la passe 2.

9. **Livrer** : un tableau final (sites et LinkedIn renseignés, vérifiés en profondeur, en contrôle léger, vides
   justifiés, à revoir), la liste des lignes à revoir avec ce qui bloque, les découvertes (groupe d'appartenance,
   renommages, reprises). Reporter les enseignements datés dans `apprentissages.md`.

## Sorties

- `campagnes/<nom>/entreprises-verifie.csv` : colonnes du contrat, autres colonnes de la liste, puis
  `verification, site_verif, linkedin_verif, preuve_verification`.
  - `site_statut` : « confirmé », « corrigé » (valeur changée par la vérification) ou « introuvable » ;
    `site_confiance` : « haute » (vérifié) ou « à vérifier » (incertain, non contre-vérifié). Même règle pour
    LinkedIn. Après un contrôle léger, « haute » seulement si la valeur était déjà sûre sur toutes les lignes.
  - `site_verif` et `linkedin_verif` : le statut détaillé (« confirmé (contrôle léger) », « réfuté »,
    « incertain », « écarté (non vu) », « page du groupe »...).
  - `a_revoir` = oui si un statut détaillé vaut ambigu, réfuté, incertain, non vérifié, non contre-vérifié ou
    écarté (non vu).
  - `exclure` : motif rendu par l'agent (particulier, administration, fermée, non identifiée).
  - `nom_officiel` vient de l'agent ; `pays`, `ville` et `activite` ne sont complétés que s'ils sont vides (un pays
    différent est signalé en note) ; canton et région suivent la ville pour la Suisse. La preuve de la source
    reste dans `preuve`, celle de l'agent va dans `preuve_verification`.
- La version précédente : `donnees/verification/entreprises-verifie.precedent.csv`.
- `donnees/verification/` : `lots/`, `manifeste-passe1.json`, `manifeste-passe2.json`, `args-passe1.json`,
  `args-passe2.json`.

L'étape 5 lit ce fichier de préférence aux deux autres.

## Contrôles qualité

- Compteurs par statut affichés par `verif_appliquer.py` ; chaque ligne à revoir traitée (arbitrage, passe 2, ou
  laissée à revoir et signalée).
- Contrôle anti-invention actif : passer le dossier du run (ou son `journal.jsonl` en place, avec les
  `agent-<id>.jsonl`). Ne pas utiliser `--sans-controle`, sauf pour diagnostiquer.
- Contrôle HTTP des sites : aucun script fourni. Ouvrir un échantillon. Un 403 ou un délai dépassé signale une
  protection anti-robot, pas un site mort ; essayer https, http, avec et sans www avant de conclure.
- Le contrôle léger juge sans outil : ce n'est pas une vérification profonde. Le dire dans le tableau final.
- Compter par script avant d'annoncer un chiffre.

## Coûts et accords

- Multi-agents : **accord explicite** de l'utilisateur, estimation à l'appui. Une fois l'accord donné, enchaîner
  (passe 2 comprise) et prévenir à la fin avec un bilan chiffré. Pendant le traitement : autonomie ; à « ça en est
  où ? », un point court lu dans le journal du run.
- 0 crédit Apollo.
- Repères mesurés sur une liste d'environ 380 entreprises :

  | Passe | Agents | Durée | Tokens de sous-agents | Appels d'outils |
  |---|---|---|---|---|
  | 1 (10 lots et 4 contre-vérifications) | 14 | environ 25 min | environ 1,7 M | environ 390 |
  | 2 (6 lots et 1 contre-vérification, 70 entités) | 7 | environ 19 min | environ 0,73 M | environ 255 |
  | Total | 21 | environ 45 min | environ 2,44 M | environ 640 |

- Au plus 6 agents tournent en même temps (observé) : 10 lots partent en deux vagues.
- Une estimation se dépasse quand le périmètre s'élargit en cours de route (solides en contrôle léger, passe 2) :
  annoncer le périmètre complet dès l'estimation.

## Pièges principaux

- Homonymes (même nom, autre pays ou autre métier) : la preuve de la source sert à départager ; sans preuve,
  « ambigu » ou « introuvable », jamais forcé.
- Pages de groupe au lieu de l'entité (filiale renvoyant au site de sa maison mère, société reprise) : arbitrage
  « page du groupe » avec une note.
- Lien mort cité par le site officiel (page LinkedIn supprimée, renommée) : le contre-vérificateur teste l'URL.
- Verdicts « incertain » ou « réfuté » qui ne s'appliquent pas seuls : `arbitrages.csv` ou passe 2.
- Peu d'appels d'outils ne prouve pas l'invention : un agent enchaîne parfois plusieurs commandes dans un seul
  appel. Le contrôle mécanique tranche.
- Sortie d'outil trop longue enregistrée dans un fichier : le prompt demande à l'agent de relire ce fichier, et
  `verif_appliquer.py` le lit aussi pour le contrôle anti-invention.
- `args` ou manifeste d'une autre campagne : contrôle du point 2 avant chaque lancement.
- Limite de session au milieu du run : appliquer d'abord les résultats partiels, puis reprendre avec
  `resumeFromRunId` ; ne pas tout relancer.

Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 4 ».
