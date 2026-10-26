---
name: etude-de-marche
description: Mène l'étude de marché de 01-etude-de-marche de bout en bout. Remplit le brief avec l'utilisateur, lance en parallèle les agents taille, segments et concurrents, puis le vérificateur, et aboutit aux trois livrables (positionnement, phrase de différenciation, tri faits/estimations/hypothèses avec la décision). À utiliser quand l'utilisateur veut étudier, valider ou dimensionner un marché, trouver ses concurrents, ou relancer une étude.
argument-hint: "[brief | lancer | livrables | relancer] [rapide | complet]"
---

# Étude de marché

Le but : une **décision** (creuser, pivoter, arrêter), pas un rapport. Lis d'abord
`01-etude-de-marche/CLAUDE.md` : ses règles s'appliquent à chaque étape.

Si l'utilisateur passe un argument (`$ARGUMENTS`) : `brief` → étape 1 ; `lancer` → étapes 2 et 3 ;
`livrables` → étape 4 ; `relancer` → étapes 2 et 3 en complétant l'étude existante, puis mise à jour
des livrables.

**Le mode** : lis-le dans `00-mon-projet/projet.md` (« Mode : rapide » ou « Mode : complet »), ou dans
l'argument (`rapide`, `complet`). Sans indication : **rapide**, et dis-le.

| | Rapide | Complet |
|---|---|---|
| Recherche | 1 agent, `etude-express` | 3 agents en parallèle : `taille-marche`, `segments`, `concurrents` |
| Vérification | `verificateur`, sur les 10 chiffres qui pèsent sur la décision | `verificateur`, sur tous les chiffres |
| Durée indicative | 10 à 15 minutes d'agents | 20 à 30 minutes d'agents |
| Consommation | environ 4 fois moins | la plus forte du kit |

## Étape 1 · Le brief

Ouvre `01-etude-de-marche/brief.md`. **Commence par y reporter ce que contient déjà
`00-mon-projet/projet.md`** (nom, phrase, zone, clients, concurrents, prix), dis-le à l'utilisateur, et ne
pose que les questions qui manquent. Si un document est dans `00-mon-projet/apports/documents/`, lis-le
aussi.

- S'il contient encore des crochets `[...]` (une ligne facultative peut aussi être supprimée), remplis-le **avec l'utilisateur** : pose une question à la fois,
  dans l'ordre du fichier, et écris ses réponses avec ses mots. Tu peux proposer une reformulation, mais les
  réponses viennent de lui. Tu peux montrer `01-etude-de-marche/exemple/brief-bumpslab.md` comme exemple.
- Ce qu'il ne sait pas encore va dans « Les incertitudes », pas dans une réponse inventée.
- Relis le brief rempli avec lui et demande sa validation avant de lancer quoi que ce soit.

## Étape 2 · Les agents de recherche

Avant de lancer, préviens en une phrase : le mode, le nombre d'agents, la durée indicative. **Attends son
accord.**

**Mode rapide** : lance `etude-express`. Il écrit `taille.md`, `segments.md`, `concurrents.csv`,
`concurrents.md` et un seul `sources-express.csv`.

**Mode complet** : lance **dans un même message** les trois agents, pour qu'ils tournent en parallèle :

- `taille-marche` → `resultats/taille.md`
- `segments` → `resultats/segments.md`
- `concurrents` → `resultats/concurrents.csv` et `resultats/concurrents.md`

Donne à chacun le chemin du brief et rappelle la règle : « N'invente jamais un chiffre. Pour chaque chiffre :
source, date, méthode. Sinon, écris « non trouvé ». »

Si une étude existe déjà dans `resultats/`, demande s'il faut la compléter (on garde l'existant) ou la
refaire. Par défaut : compléter.

## Étape 3 · Le vérificateur

Quand la recherche est finie, lance `verificateur`. Il rassemble `sources.csv` et écrit `resultats/tri.md`.
En mode rapide, dis-lui : « Vérifie seulement les 10 chiffres qui pèsent le plus sur la décision (taille,
prix, problème, concurrents directs), plus le nom du projet ; marque les autres « non vérifié ». Une dizaine de minutes au plus. » et
lance-le avec le modèle `sonnet` : en mode rapide, la vitesse compte plus que la dernière nuance.

Puis présente à l'utilisateur, en quelques lignes : la taille du marché (avec le statut de chaque chiffre), le
segment par lequel commencer, les trois concurrents les plus proches, le décompte faits / estimations /
hypothèses / erreurs. Pas de longue restitution : les détails sont dans les fichiers.

## Étape 4 · Les trois livrables, avec l'utilisateur

Les modèles sont dans `01-etude-de-marche/modeles/`. Copie chacun dans `resultats/` et remplis-le **avec**
l'utilisateur.

1. **Positionnement** (`modeles/positionnement.md` → `resultats/positionnement.md`). Tableau des concurrents
   tiré de `concurrents.csv`, statu quo compris, puis carte à deux axes. Demande à l'utilisateur quels axes
   comptent pour ses clients ; propose ceux de l'agent concurrents s'il hésite. Rappelle-lui qu'il peut
   compléter la colonne « messages publicitaires » à la main avec `guides/angles-morts.md`.
2. **Différenciation** (`modeles/differenciation.md` → `resultats/differenciation.md`). Les quatre questions,
   une à une. Puis la phrase : « Pour [cible] qui [besoin], nous sommes les seuls à [différence]. »
   Propose deux ou trois versions, contredis celles qui ne tiennent pas face au tableau des concurrents, et
   laisse l'utilisateur trancher.
3. **Synthèse et décision** (`modeles/synthese.md` → `resultats/synthese.md`). Faits, estimations et
   hypothèses repris de `tri.md`. Chaque hypothèse devient une question d'entretien. Puis la décision :
   creuser, pivoter ou arrêter, avec sa raison, datée. C'est l'utilisateur qui décide ; tu peux donner ton avis.
   Ajoute la décision, datée, dans `00-mon-projet/projet.md`.

## Après

- Les hypothèses deviennent les questions des entretiens (dossier `03-prospection`).
- La phrase de différenciation et le tableau servent au deck et à la landing page (`02-landing-page`) :
  propose de passer à `/cahier-des-charges` si la décision est de creuser.
- Le mois suivant, `/etude-de-marche relancer` complète l'étude sans repartir de zéro.
