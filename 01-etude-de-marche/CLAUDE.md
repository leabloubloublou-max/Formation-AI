# Étude de marché

Ce dossier sert à répondre vite à une question : **y a-t-il un marché, et lequel ?**
La sortie attendue est une décision, pas un rapport : on creuse, on pivote ou on arrête.

## Le parcours

1. **Le brief** : `brief.md`. La question, le périmètre, les règles. S'il contient encore des crochets
   `[...]`, ne lance aucun agent : pose les questions à l'utilisateur une par une et remplis-le avec ses mots.
2. **Les agents** : la commande `/etude-de-marche` lance, en mode **rapide**, le seul agent `etude-express`
   puis une vérification ciblée ; en mode **complet**, trois agents en parallèle puis le vérificateur :
   - `taille-marche` → `resultats/taille.md`
   - `segments` → `resultats/segments.md`
   - `concurrents` → `resultats/concurrents.csv` et `resultats/concurrents.md`
   - `verificateur` relit tout → `resultats/sources.csv` et `resultats/tri.md`
3. **Les trois livrables** (modèles dans `modeles/`), rédigés avec l'utilisateur :
   - Livrable 1 : le tableau des concurrents et la carte de positionnement → `resultats/positionnement.md`
   - Livrable 2 : la phrase « Pour [cible] qui [besoin], nous sommes les seuls à [différence]. »
     → `resultats/differenciation.md`
   - Livrable 3 : le tri faits, estimations, hypothèses, et la décision → `resultats/synthese.md`

## Les règles, pour toi et pour chaque agent

- **N'invente jamais un chiffre.** Chaque chiffre porte sa source (lien), sa date et sa méthode.
  Sinon, écris « non trouvé ». Un « non trouvé » honnête vaut mieux qu'un chiffre plausible.
- **Trois statuts, jamais mélangés**, plus une colonne « vérifié » à part :
  - *fait* : chiffre lu tel quel dans une source datée (page ouverte) ;
  - *estimation* : calcul de l'agent, projection officielle, source faible, ou donnée ancienne (plus de cinq
    ans : l'année reste visible) ;
  - *hypothèse* : ni sourcé ni calculable ; elle devient une question d'entretien.
  Les agents de recherche écrivent `verifie=non` ; seul le vérificateur passe une ligne à `oui`.
  « Fait non vérifié » est donc normal avant le vérificateur.
- **Croise les deux méthodes de taille de marché** : les études publiées (descendante) et le calcul
  clients × panier (ascendante). Si les deux divergent d'un facteur 3 ou plus, dis-le. Pour un équipement
  vendu une fois, le « panier » se calcule sur la durée de vie (valeur du parc ÷ années d'usage).
- **Le nom du projet se vérifie aussi.** Un homonyme dans le même secteur, une marque déposée, un projet
  renommé : à signaler en tête des résultats.
- **Le web contredit le brief ?** Dis-le à l'utilisateur, avec la source, au lieu de suivre le brief.
- **Le statu quo est un concurrent.** « On continue à la main », un tableur, un stagiaire : à lister.
- **Tout s'écrit dans des fichiers.** Rien d'important ne reste seulement dans la conversation : le mois
  suivant, on relance l'étude en complétant les fichiers, sans repartir de zéro.
- **Respecte les sites.** Volumes raisonnables, pauses entre les requêtes, conditions d'utilisation.

## Ce que la recherche web n'atteint pas

- Pages à filtres, annuaires, pages derrière une connexion : propose à l'utilisateur **Claude dans Chrome**.
- Beaucoup de requêtes à la suite : le script `scripts/scraping.py` (DuckDuckGo, sans clé, résultats
  rangés en CSV). Mode d'emploi : `scripts/README.md`.
- **Si le script échoue** (réseau, blocage) : passe à WebSearch et WebFetch, sans t'arrêter. Repère : 15 à 30
  recherches et 10 à 20 pages ouvertes par agent, en commençant par les sources officielles (offices de
  statistique, cantons, associations professionnelles).
- **Si une page refuse de s'ouvrir** (robots, PDF, Excel) : cherche une autre page qui reprend le chiffre ;
  sinon écris « non lu » et propose à l'utilisateur de télécharger le fichier dans `resultats/` ou de
  l'ouvrir avec Claude dans Chrome.
- **WebFetch rend un résumé, pas le texte brut.** Écris « lu via WebFetch » dans la méthode : le vérificateur
  saura qu'une relecture du document original peut être utile.
- Publicités et demande réelle : voir `guides/angles-morts.md` (bibliothèque publicitaire Meta,
  Google Ads Transparency Center, Keyword Planner). Ces outils se consultent à la main ; l'utilisateur colle
  ce qu'il a vu, tu le ranges dans `resultats/concurrents.csv` avec la date.

## Économiser les crédits

- Une question par agent, une tâche par conversation. Pour une simple relecture, pas besoin de relancer
  les agents.
- Les agents de recherche tournent sur un modèle intermédiaire ; le vérificateur, lui, hérite du modèle de
  la session : c'est l'étape où une erreur coûte cher.
- Avant de lancer les quatre agents, annonce-le à l'utilisateur : c'est la partie qui consomme le plus.

## Exemple complet

`exemple/` contient le brief du lancement de BUMPSLAB (connecter les données internes des PME à l'IA),
l'exemple suivi pendant la formation. Il sert de modèle, pas de résultat : ne recopie jamais ses chiffres.
