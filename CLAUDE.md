# BUMPSLAB × Zero to One

Un kit pour lancer un projet avec l'IA : de l'étude de marché aux premiers rendez-vous. Il est remis aux
participants de la formation BUMPSLAB « Lancer son projet avec l'IA ».

## À qui tu parles

À un fondateur ou une fondatrice qui lance un projet. Souvent pas développeur. Parle français, simplement,
sans jargon technique non expliqué. Quand tu lances une commande, dis en une phrase ce qu'elle fait.

## Avant tout : la fiche du projet

Lis `00-mon-projet/projet.md` au début de chaque session. C'est la fiche unique du projet (nom, cible, zone,
prix, mode rapide ou complet, décisions prises) et l'inventaire de ce que le fondateur a déposé dans
`00-mon-projet/apports/`. S'il est vide, propose `/nouveau-projet`.

Ne redemande jamais ce qui est déjà dans `projet.md`. Quand une décision est prise (nom, cible, prix,
direction artistique, « on creuse »), ajoute-la, datée, dans « Les décisions prises ».

## Les apports : demander au bon moment

Quand une étape a besoin de quelque chose que seul le fondateur possède (logo, photos, lien du formulaire,
preuve, chiffre interne, accord d'un client) :

1. regarde d'abord dans `00-mon-projet/apports/` ;
2. s'il manque, **demande-le à ce moment-là**, avec le chemin exact où le déposer (« Dépose ton logo dans
   `00-mon-projet/apports/logo/`, puis dis-moi c'est déposé »), et attends ;
3. seulement s'il répond « plus tard » : continue avec un emplacement clairement marqué
   `[À FOURNIR : ...]`, et note-le dans `projet.md`.

Ne fabrique jamais un logo, une photo, un témoignage ou un chiffre pour combler un manque.

## Rapide ou complet

`projet.md` indique le mode. **Rapide** (par défaut en atelier) : un agent de recherche et une
vérification ciblée pour l'étude ; pour la direction artistique et la page, Claude crée lui-même, sur
mesure, en un passage, sans agent. **Complet** : toutes les étapes, avec les équipes d'agents.
Avant une étape qui consomme beaucoup, rappelle le mode et la durée, et demande confirmation.

**Le temps du fondateur est la ressource rare.** Une étape en mode rapide se compte en minutes (durées
dans `PARCOURS.md`). Si une tâche s'allonge, arrête-toi, montre ce qui est fait et demande s'il faut
continuer, plutôt que de peaufiner en silence.

## Les dossiers

| Dossier | Sert à | Pour démarrer |
|---|---|---|
| `00-mon-projet/` | la fiche du projet et ce que le fondateur apporte | `/nouveau-projet` |
| `01-etude-de-marche/` | décider s'il y a un marché, et lequel | `/etude-de-marche` |
| `02-landing-page/` | mettre en ligne une page qui affiche l'argumentaire, ou un premier produit | `/cahier-des-charges`, `/direction-artistique`, `/landing-page`, `/mettre-en-ligne` |
| `03-prospection/` | trouver les bonnes entreprises et les bonnes personnes, puis obtenir des rendez-vous | skill `prospection-base-client` |

Chaque dossier a son `CLAUDE.md` : lis-le dès que tu travailles dans ce dossier. Chaque étape produit ce dont
la suivante a besoin : l'étude nourrit la page, la page et l'étude nourrissent la prospection, les entretiens
relancent l'étude.

Si `.venv/` n'existe pas encore : `/demarrer` (installation). Si le projet n'est pas encore décrit :
`/nouveau-projet`. Le parcours complet, côté utilisateur, est dans `PARCOURS.md`.

## Les règles de tout le repo

- **N'invente jamais un chiffre, un nom, une URL, une preuve ni un signal.** Une source, une date et une
  méthode pour chaque chiffre ; sinon « non trouvé ». Un champ vide vaut mieux qu'un champ faux.
- **Les réponses de fond viennent de l'utilisateur** : sa cible, sa promesse, ses convictions, ses choix.
  Tu poses les questions, tu proposes, tu contredis, tu repères les angles morts. Tu ne décides pas à sa place.
- **Tout ce qui compte s'écrit dans un fichier** du dossier concerné, pas seulement dans la conversation.
- **Accord avant de dépenser** : avant de lancer plusieurs agents, un workflow ou une action qui consomme
  des crédits (Apollo, tokens), annonce-le et attends le feu vert.
- **Rien ne part chez un vrai prospect sans relecture** de l'utilisateur. Aucun email envoyé, aucune
  séquence lancée sans son accord explicite.
- **Les clés restent secrètes.** Elles vivent dans `.env` à la racine (jamais commité). Tu n'affiches jamais
  le contenu d'un `.env`.

## Économiser les crédits

1. **Découper le travail** : une tâche, une conversation. Propose `/clear` quand l'utilisateur change de sujet.
2. **Limiter le contexte** : lis l'extrait utile d'un document, pas le document entier.
3. **Réserver la puissance** : le modèle le plus puissant et l'effort élevé là où ils changent le résultat
   (vérification, stratégie, prix) ; le plus rapide pour reformater un fichier.
4. **Arrêter de recoller** : ce que l'utilisateur recolle trois fois devient un fichier du repo.

## Environnement

- Python : toujours `.venv/bin/python` depuis la racine du repo (sous Windows : `.venv\Scripts\python.exe`).
- Les agents sont dans `.claude/agents/`, les commandes et les skills dans `.claude/skills/`.
