<div align="center">

# BUMPSLAB × Zero to One

**Lancer son projet avec l'IA.**
De l'étude de marché aux premiers rendez-vous, avec une équipe d'agents qui travaille dans Claude Code.

[Démarrer en 5 minutes](#démarrer-en-5-minutes) · [Le parcours](PARCOURS.md) · [Les dossiers](#les-dossiers) · [Les commandes](#les-commandes) · [Bonnes pratiques](#quatre-règles-pour-ne-pas-brûler-vos-crédits)

</div>

---

Vous ouvrez ce dossier dans VS Code, vous parlez à Claude Code en français, et des agents spécialisés se
mettent au travail : ils cherchent votre marché, vérifient chaque chiffre, écrivent votre page, la testent
et préparent votre prospection. **Vous fixez l'objectif, vous tranchez, vous validez.**

```
  01 · Marché            02 · Landing page          03 · Prospection
  ─────────────          ─────────────────          ────────────────
  Y a-t-il un marché ?   Une page en ligne          Les bonnes entreprises,
  Lequel ?               qui affiche votre          les bonnes personnes,
                         argumentaire               un signal par compte
        │                       │                          │
        ▼                       ▼                          ▼
  creuser / pivoter /    votre site sur Vercel      des rendez-vous
  arrêter
        ▲                                                  │
        └──────── les entretiens relancent la boucle ──────┘
```

Chaque étape produit ce dont la suivante a besoin.

## Démarrer en 5 minutes

### 1. Récupérer le kit

- **Avec un compte GitHub** (recommandé) : bouton vert **Use this template** > *Create a new repository*.
  Choisissez **Private** : votre brief, vos notes et vos résultats d'étude y seront enregistrés. Puis, dans
  VS Code : *Source Control* (ou la palette de commandes) > **Clone Repository**, et collez l'adresse de
  votre nouveau dépôt.
- **Sans GitHub** : bouton **Code** > *Download ZIP*, puis décompressez le dossier où vous voulez.

### 2. Ouvrir dans VS Code

*File > Open Folder*, choisissez **le dossier du kit** (la racine, pas un sous-dossier). Ouvrez Claude Code
dans le panneau latéral.

Quand VS Code demande si vous faites confiance aux auteurs de ce dossier, répondez **oui** (*Trust*) : sans
ça, les réglages et les agents du kit ne s'appliquent pas.

### 3. Taper deux commandes

```
/demarrer
/nouveau-projet
```

La première vérifie Python et installe ce qu'il faut. La seconde vous pose huit questions sur votre projet,
fait l'inventaire de ce que vous avez déjà (logo, photos, inspirations, documents) et vous dit par où
commencer.

**Ce qui se passe ensuite, étape par étape, et ce que vous aurez à fournir : [PARCOURS.md](PARCOURS.md).**

### Ce qu'il vous faut

| Outil | Pour | Indispensable |
|---|---|---|
| [VS Code](https://code.visualstudio.com) + l'extension **Claude Code** | tout | oui |
| Un abonnement Claude (Pro, Max, Team ou Enterprise) | tout | oui |
| [Python 3.11 ou plus](https://www.python.org/downloads/) | recherche web en série, prospection | oui |
| [Node.js LTS](https://nodejs.org) | mettre la page en ligne depuis le terminal | non |
| Un compte [Vercel](https://vercel.com) gratuit | mettre la page en ligne | pour l'étape 2 |
| Un compte [Apollo](https://www.apollo.io) avec accès API | contacts et séquences | pour la fin de l'étape 3 |

**Extensions VS Code utiles pour débuter** : *Claude Code* (l'agent dans l'éditeur), *Live Preview* (voir
le site sans quitter VS Code), *Rainbow CSV* ou *Edit CSV* (lire les fichiers de résultats), *Codex* si
besoin (un second agent pour comparer ou relire).

> **Sous Windows**
> - À l'installation de Python, cochez **« Add python.exe to PATH »**.
> - Installez [Git for Windows](https://git-scm.com/download/win) : Claude Code s'en sert pour lancer ses
>   commandes.
> - Dans les commandes de ce kit, `.venv/bin/python` s'écrit `.venv\Scripts\python`. Claude le sait : vous
>   n'avez rien à retenir.

## Les dossiers

### `00-mon-projet/` · La fiche du projet et ce que vous apportez

`projet.md` est la fiche unique de votre projet : toutes les étapes la relisent, vous ne recollez jamais
rien. Dans `apports/`, vous déposez votre logo, vos photos, vos inspirations et vos documents ; Claude vous
les demande au moment où il en a besoin.

### `01-etude-de-marche/` · Valider le marché, avant d'y aller

Vous remplissez un brief (ou Claude vous pose les questions). En mode **rapide**, un agent (`etude-express`)
fait une première passe et le vérificateur contrôle les chiffres qui comptent. En mode **complet**, trois
agents cherchent en parallèle et un quatrième vérifie tout.

| Agent | Écrit | Fait |
|---|---|---|
| `taille-marche` | `taille.md` | une estimation par les études publiées, une par le calcul clients × panier, croisées |
| `segments` | `segments.md` | qui achète, pourquoi maintenant, qui décide, qui ouvre la porte |
| `concurrents` | `concurrents.csv`, `concurrents.md` | offres, prix publics, cibles, positionnement, statu quo compris |
| `verificateur` | `sources.csv`, `tri.md` | ouvre chaque source et classe chaque chiffre : fait, estimation ou hypothèse |

**Vous en sortez avec** : le tableau des concurrents et la carte de positionnement, la phrase « Pour
[cible] qui [besoin], nous sommes les seuls à [différence] », et une décision.

Règle commune à chaque agent : *si tu ne trouves pas, écris « non trouvé ». N'invente jamais un chiffre.*

### `02-landing-page/` · Une page en ligne, un premier produit

Le cahier des charges et la direction artistique font la différence, pas le prompt.

**La direction artistique part de vos inspirations.** Vous apportez 3 à 5 sites qui vous font dire « waw » ;
l'agent `directeur-artistique` les analyse et construit **trois directions en vrai** (le haut de votre page,
avec votre contenu). Vous choisissez en voyant. Un catalogue d'effets testés (`02-landing-page/effets/` :
GSAP, Lenis, shaders légers) donne le moment fort, avec retenue.

| Rôle | Sa matière | Fini quand |
|---|---|---|
| `landing-designer` | votre charte graphique | chaque page respecte la charte |
| `landing-copywriter` | votre argumentaire | chaque section dit un bénéfice, pas une fonctionnalité |
| `landing-developpeur` | le cahier des charges | tout fonctionne en local |
| `landing-testeur` | le site, puis votre téléphone | aucune erreur ouverte |
| **Vous, l'arbitre** | ce que les quatre produisent | vous mettez en ligne |

Le site est en HTML et CSS, sans framework : vous le voyez dans VS Code avec Live Preview et Vercel le met
en ligne tel quel. Le skill de design d'Anthropic (`frontend-design`) évite le site par défaut que tout le
monde reconnaît.

### `03-prospection/` · Les entreprises, les décideurs, les premiers rendez-vous

Une chaîne complète, testée en interne chez BUMPSLAB, de la cible au fichier d'appel :

1. **Identifier** : le persona du décideur.
2. **Extraire** : une liste de comptes et de contacts (Apollo, ou découverte web par des agents).
3. **Enrichir** : un signal daté et sourcé par compte (registre du commerce, LinkedIn, site, actualités),
   puis un tri A / B / C.
4. **Réinjecter** dans Apollo : une seule base, à jour.
5. **Prospecter** : ordre d'appel, plan de séquence, scripts d'appel et fichier d'appel.

Claude demande votre accord avant toute dépense de crédits et avant toute écriture dans Apollo. Il ne
rédige aucun message sans demande. Les données de vos campagnes restent sur votre ordinateur : elles sont
exclues de git.

## Les commandes

Tapez-les dans Claude Code. Vous pouvez aussi simplement décrire ce que vous voulez : Claude choisit,
sauf pour `/mettre-en-ligne`, qu'il ne lance jamais seul.

| Commande | Ce qu'elle fait |
|---|---|
| `/demarrer` | installe le kit |
| `/nouveau-projet` | décrit votre projet, inventaire de ce que vous avez, choix du mode rapide ou complet |
| `/etude-de-marche` | brief, agents de recherche, vérification, puis les trois livrables avec vous |
| `/cahier-des-charges` | Claude vous pose les questions qui manquent ; les réponses viennent de vous |
| `/direction-artistique` | vos inspirations, trois directions en vrai, votre choix, la charte |
| `/landing-page` | l'équipe d'agents construit, relit et teste la page |
| `/mettre-en-ligne` | publication sur Vercel, pas à pas |
| « Lance une campagne de prospection » | la chaîne de `03-prospection`, étape par étape |

## Quatre règles pour ne pas brûler vos crédits

| | Règle | Exemple |
|---|---|---|
| 1 | **Découper le travail** : une tâche, une conversation | « Une étude de marché complète » devient trois demandes : taille, concurrents, synthèse |
| 2 | **Limiter le contexte** : un extrait propre vaut mieux qu'un rapport entier | les 10 pages du cahier des charges technique, pas les 200 du dossier |
| 3 | **Réserver la puissance** : le modèle le plus puissant seulement là où il change le résultat | le plus puissant pour votre grille tarifaire, le plus rapide pour reformater un CSV |
| 4 | **Arrêter de recoller** : ce que vous recollez trois fois devient un fichier | votre présentation d'entreprise devient un fichier du repo |

Dans Claude Code : `/clear` vide la conversation quand vous changez de sujet, `/compact` la résume,
`/context` montre ce qui la remplit, `/usage` montre votre consommation, `/effort` règle le temps de
réflexion (bas pour une mise en forme, élevé pour une analyse).

## Ce que l'IA ne fait pas à votre place

- **Les clés d'accès** vivent dans `.env`, jamais dans le code. Ce fichier n'est jamais envoyé sur GitHub.
- **Les données personnelles** : ne collectez que le nécessaire, sachez dire où elles sont et qui y accède.
- **La solidité** : avant de traiter des paiements ou des données sensibles, faites relire par un développeur.
- **Les décisions** : votre cible, votre promesse, votre prix. Claude pose les questions, vous répondez.

## Comment c'est construit

```
.
├── CLAUDE.md                     les règles communes, lues par Claude à chaque session
├── .claude/
│   ├── agents/                   les 10 agents (marché, direction artistique, landing page)
│   ├── skills/                   les commandes, le design, la prospection
│   └── settings.json             permissions : les .env ne sont jamais lus
├── PARCOURS.md                   le parcours, côté utilisateur
├── 00-mon-projet/                projet.md (la fiche) et apports/ (logo, photos, inspirations...)
├── 01-etude-de-marche/           brief, modèles, guides, script de recherche web, résultats
├── 02-landing-page/              argumentaire, cahier des charges, charte, effets/, guides, site/
└── 03-prospection/               campagnes/ (exclu de git)
```

Chaque dossier a son propre `CLAUDE.md`, que Claude lit quand il y travaille.

## Petit lexique

| Mot | Ce que c'est |
|---|---|
| **Repo** (dépôt) | un dossier de projet suivi par Git, souvent hébergé sur GitHub |
| **Cloner** | copier un repo de GitHub sur votre ordinateur |
| **Agent** | une IA à qui on confie un objectif ; elle enchaîne les étapes jusqu'au livrable |
| **Skill** | un mode d'emploi que Claude charge quand la tâche s'y prête ; certains se lancent par `/nom` |
| **CSV** | un tableau en texte, une ligne par élément, lisible dans Excel ou VS Code |
| **.venv** | l'environnement Python du projet, créé par `/demarrer` |
| **.env** | le fichier qui garde vos clés secrètes ; il ne part jamais sur GitHub |
| **MCP** | la prise standard qui permet à Claude de piloter un autre logiciel (Apollo, Pencil...) |
| **ICP** | le profil du client idéal : secteur, taille, zone |
| **WCAG** | les règles d'accessibilité du web (contrastes, tailles, lecture au clavier) |
| **DNS** | les réglages qui relient votre nom de domaine à votre site |

## Contact

Ce kit accompagne la formation BUMPSLAB « Lancer son projet avec l'IA ». Écrivez-nous dès que vous bloquez,
ou quand ça marche.

**BUMPSLAB** · [bumpslab.com](https://bumpslab.com) · Hugo : hugo@bumpslab.com · Thibault : thibault@bumpslab.com

Licence : voir [LICENSE](LICENSE) et [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
