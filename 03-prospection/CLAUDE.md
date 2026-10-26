# Prospection et scraping

Ce dossier sert à passer de la cible aux premiers rendez-vous : des entreprises et des personnes précises,
un signal sourcé par compte, puis messages, appels et relances.

## Le moteur : le skill `prospection-base-client`

Tout le travail passe par le skill `prospection-base-client` (`.claude/skills/prospection-base-client/`).
Charge-le dès que l'utilisateur parle de prospection, de cible, de persona, de liste d'entreprises, de
scraping, d'Apollo, de signaux, de séquence ou d'appels. **Ses règles d'or s'appliquent sans exception**,
en particulier :

- accord explicite avant toute dépense (crédits Apollo, workflows multi-agents) et avant toute écriture
  dans Apollo ;
- aucun message rédigé sans demande explicite ;
- anti-invention : aucune URL, aucun nom, aucun signal qui ne soit apparu dans une sortie d'outil.

## Ce qui change dans ce repo

- **Les campagnes vivent dans `03-prospection/campagnes/<nom>/`.** Partout où le skill écrit
  `--campagne campagnes/<nom>`, utilise `--campagne 03-prospection/campagnes/<nom>`.
- **Les commandes se lancent depuis la racine du repo**, avec `.venv/bin/python`, comme le dit le skill.
  Le `.venv` et le `.env` (clé Apollo) sont à la racine.
- **Les données des campagnes ne partent jamais sur GitHub** : `03-prospection/campagnes/` est dans le
  `.gitignore` (emails, téléphones, noms). Le sort git des données est donc déjà tranché ; rappelle-le à
  l'utilisateur au démarrage plutôt que de lui reposer la question.

## Par où commencer

1. Contrôler l'installation :
   `.venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py`
2. Créer la campagne : `03-prospection/campagnes/<nom>/campagne.toml`, copié de
   `.claude/skills/prospection-base-client/config/campagne.exemple.toml`, puis complété **avec l'utilisateur**.
3. Suivre la checklist « Démarrer ou reprendre une campagne » du `SKILL.md`.

Remplis `campagne.toml` d'abord avec ce que contient `00-mon-projet/projet.md` (nom, offre, zone, cible,
concurrents) et, si l'étude de marché est faite, avec la cible, le persona probable et les concurrents de
`01-etude-de-marche/resultats/`. Dis-le à l'utilisateur, et ne pose que les questions qui manquent : qui
appelle et signe, les preuves réelles, les clients et partenaires à exclure (`exclure.csv`).

## Une cible hors industrie

Le fichier d'exemple est réglé pour des PME industrielles. Pour une autre cible (EMS, cabinets, commerces,
associations...) :

- `profil_secteurs = "aucun"`, puis une règle `[[cible.secteurs]]` par type d'établissement visé, avec ses
  mots-clés (`motifs`) et sa note de 0 à 3 ;
- `taille_min` et `taille_max` comptent des **salariés**, pas des lits, des clients ou des mètres carrés :
  traduis avec l'utilisateur ;
- si le persona n'entre dans aucune famille fournie (direction, qualite, it, production, technique, service,
  ventes, finance, achats, projet), crée la tienne dans `[persona.titres]` (par exemple `soins`), avec les
  intitulés en français, en anglais et en allemand.

`verifier_installation.py --campagne ...` contrôle le résultat.

## Le scraping seul

Pour une recherche web ponctuelle sans campagne (une liste de requêtes, des résultats en CSV), le script de
l'étude de marché suffit : `01-etude-de-marche/scripts/scraping.py` (mode d'emploi :
`01-etude-de-marche/scripts/README.md`). Pour une liste d'entreprises à enrichir (site, LinkedIn, signaux),
c'est le skill, étapes 2 à 5.

## La méthode vue en formation

| Formation | Dans le skill |
|---|---|
| 1. Identifier : le persona du décideur | étape 1 |
| 2. Extraire : comptes et contacts (Apollo, ou découverte web) | étapes 2, 3 et 6 |
| 3. Enrichir : un signal sourcé par compte, tri A / B / C | étapes 4 et 5 |
| 4. Réinjecter dans Apollo | étape 7 |
| 5. Prospecter : séquence, appels, scripts | étapes 8 et 9 |

Repères de la formation, à garder en tête : 30 comptes bien choisis valent mieux que 500 ; une seule voix par
entreprise ; emails et appels alternés (la cadence exacte est celle du plan de séquence du skill), et tout
s'arrête à la première réponse, même un « non merci » ; on mesure les réponses et les rendez-vous, pas les
ouvertures.
