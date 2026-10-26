# Le parcours · ce qui se passe quand vous lancez votre projet

Ce guide décrit, étape par étape, ce que vous vivez dans la conversation avec Claude Code : ce qu'il vous
demande, ce que vous apportez, ce que vous obtenez. Il vaut pour tout le monde : participants, formateurs,
et toute personne qui reprend le kit.

```
  Installer        Décrire           Étudier            Montrer                     Vendre
  /demarrer   →    /nouveau-projet → /etude-de-marche → /cahier-des-charges      →  prospection
  (une fois)       (10 min)          (rapide : 20 min)    /direction-artistique       (03-prospection)
                                                          /landing-page
                                                          /mettre-en-ligne
```

**Combien de temps, en mode rapide** (celui de l'atelier) : installer 5 min · décrire 10 min · étudier
15 à 20 min · argumentaire et cahier 15 min · direction artistique 10 min · landing page 15 min · mise en
ligne 10 min. Soit environ 1 h 40 du projet décrit à la page en ligne. Le mode complet prend deux à trois
fois plus, pour un travail sur mesure : on le choisit dans `projet.md`, étape par étape.

Vous pouvez entrer à n'importe quelle étape : si votre marché est déjà validé, commencez par la page.

---

## Comment se passe une conversation

- **Vous parlez normalement**, en français. Les commandes `/...` sont des raccourcis, pas une obligation :
  « Je veux faire ma landing page » fonctionne aussi.
- **Claude pose une question à la fois.** Quand les réponses possibles sont connues, il affiche des choix à
  cocher ; vous pouvez toujours écrire autre chose.
- **Quand il lui manque quelque chose que vous seul avez** (logo, photos, lien du formulaire, une preuve),
  il vous le demande au moment où il en a besoin, avec le dossier exact où le déposer. Vous glissez le
  fichier, puis vous écrivez « c'est déposé ». Si vous ne l'avez pas : « plus tard », et il laisse un
  emplacement marqué `[À FOURNIR]`.
- **Avant de lancer plusieurs agents**, il annonce combien, pour combien de temps, et attend votre « ok ».
- **Tout ce qui compte est écrit dans un fichier.** Vous pouvez fermer VS Code et reprendre demain :
  Claude relit `00-mon-projet/projet.md` et sait où vous en êtes.

---

## 0 · Installer · `/demarrer` (une seule fois, 5 minutes)

| | |
|---|---|
| **Claude vérifie** | Python, puis installe ce qu'il faut |
| **Vous fournissez** | rien, sauf installer Python si Claude vous le demande |
| **Vous obtenez** | un kit prêt, et l'orientation vers `/nouveau-projet` |

---

## 1 · Décrire le projet · `/nouveau-projet` (10 minutes)

**Claude vous pose huit questions, une à la fois** : le nom, le projet en une phrase, où vous en êtes, qui a
le problème et qui paie, où sont vos clients, les concurrents que vous connaissez, un prix envisagé (même
approximatif), un site ou un deck existant.

**Puis il fait l'inventaire de ce que vous avez déjà.** Rien n'est obligatoire tout de suite :

| Ce qui servira | Où le déposer | Quand il servira |
|---|---|---|
| Votre logo (SVG ou PNG) | `00-mon-projet/apports/logo/` | la landing page |
| 2 à 4 photos (produit, équipe, terrain) | `00-mon-projet/apports/photos/` | la landing page |
| 3 à 5 sites qui vous font dire « waw » | `00-mon-projet/apports/inspirations/liens.md` | la direction artistique |
| Une charte existante | `00-mon-projet/apports/charte/` | la direction artistique |
| Deck, présentation, notes | `00-mon-projet/apports/documents/` | tout de suite : Claude le lit |

**Enfin, vous choisissez le mode** :

- **Rapide** (recommandé en atelier) : un seul agent de recherche, une vérification ciblée, une landing
  testée une fois.
- **Complet** : quatre agents de recherche, chaque chiffre vérifié, relecture design et tests complets.

**Vous obtenez** : `00-mon-projet/projet.md`, la fiche que toutes les étapes relisent.

> **Exemple**
> **Claude** : Où en es-tu ? ☐ Idée ☐ Prototype ☐ Premiers clients ☐ En vente
> **Vous** : Prototype.
> **Claude** : Noté. Tu as un deck ? Si oui, dépose-le dans `00-mon-projet/apports/documents/` : je le lis et
> je complète la fiche.

---

## 2 · Étudier le marché · `/etude-de-marche`

| | |
|---|---|
| **Claude reprend** | tout ce qui est dans `projet.md`, et ne demande que ce qui manque pour le brief |
| **Vous validez** | le brief, puis le lancement des agents |
| **Les agents font** | la taille du marché, les segments, les concurrents ; le vérificateur classe chaque chiffre en fait, estimation ou hypothèse |
| **Vous décidez avec Claude** | les axes de positionnement, votre phrase « Pour [cible] qui [besoin], nous sommes les seuls à [différence] », puis creuser, pivoter ou arrêter |
| **Vous obtenez** | `01-etude-de-marche/resultats/` : concurrents, sources, tri, et la décision |
| **Durée** | rapide : 15 à 20 minutes (un agent, puis la vérification de 10 chiffres) ; complet : 30 à 45 minutes |

À savoir : l'étude vérifie aussi le nom de votre projet. Dans la démo du kit, elle a découvert que le nom
était déjà celui d'un produit concurrent.

---

## 3 · Montrer · la landing page

### 3a · L'argumentaire et le cahier des charges · `/cahier-des-charges`

Claude relit la fiche et l'étude, puis vous pose les questions qui manquent : pour qui, quel problème, quelle
promesse, quel parcours, ce que la page collecte. **Il vous demande le lien de votre formulaire ou de votre
agenda** (Tally, Calendly...). **Les réponses viennent de vous** : Claude propose, contredit, repère les
angles morts.

### 3b · La direction artistique · `/direction-artistique` (10 minutes)

1. **Vous apportez 2 ou 3 inspirations** : des sites qui vous font dire « waw », pas forcément de votre
   secteur (godly.website, land-book.com, awwwards.com). Le mieux : une capture d'écran de chacun, glissée
   dans `00-mon-projet/apports/inspirations/`. Plus trois mots pour l'impression voulue, ce que vous ne
   voulez surtout pas, et **3 à 5 photos** dans `00-mon-projet/apports/photos/` (les vôtres, ou en
   attendant des photos libres d'unsplash.com ou pexels.com). Claude vous demande tout ça en un seul
   message. Si votre projet est humain, ce sont les photos qui font l'effet.
2. **Claude crée trois directions sur mesure, en vrai** (le haut de votre page, avec votre nom, votre
   titre, votre logo) : une fidèle à vos inspirations, une audacieuse, une inattendue, tirée de votre
   métier. Elles partent de vos références : deux projets n'auront jamais la même page.
3. **Vous choisissez en voyant**, ou vous mélangez (« la typo de A avec les couleurs de C »).
4. La charte graphique se remplit à partir de votre choix.

### 3c · La construction · `/landing-page` (15 minutes)

| | |
|---|---|
| **Claude vérifie d'abord** | que le logo, les photos et le lien du formulaire sont là ; sinon il les demande |
| **Vous choisissez** | le titre du haut de page parmi deux |
| **Claude écrit** | toute la page, dans le style de la direction choisie, à partir de votre argumentaire et de votre étude ; puis il la vérifie une fois (téléphone compris) |
| **Vous vérifiez vous-même** | chaque texte, et la page sur votre vrai téléphone |
| **Vous obtenez** | `02-landing-page/site/`, prêt à mettre en ligne |

Pour changer un texte plus tard : « change le titre en ... ». En mode complet, quatre agents (designer,
copywriter, développeur, testeur) construisent et relisent la page : 45 à 90 minutes.

### 3d · La mise en ligne · `/mettre-en-ligne`

Claude ne la lance jamais seul. Il vérifie qu'aucune clé n'est dans le code, puis vous guide sur Vercel.

---

## 4 · Vendre · la prospection (`03-prospection/`)

| | |
|---|---|
| **Claude reprend** | la fiche, l'étude et le persona pour préparer votre campagne |
| **Vous fournissez** | qui appelle et signe, vos preuves réelles, vos clients et partenaires à exclure, et plus tard votre clé Apollo |
| **Vous obtenez** | une liste d'entreprises avec un signal daté par compte, les bons contacts, l'ordre d'appel, les scripts et le fichier d'appel |
| **Claude ne fait jamais sans votre accord** | dépenser des crédits Apollo, écrire dans Apollo, rédiger ou envoyer un message |

---

## Ce que Claude ne fera jamais sans vous

- Inventer un chiffre, un logo, une photo, un témoignage ou un client.
- Décider à votre place de la cible, de la promesse, du prix ou du nom.
- Envoyer un message, lancer une séquence, dépenser des crédits ou mettre en ligne.
- Lire ou afficher vos clés (`.env`).

## Si vous bloquez

- « Où j'en suis ? » : Claude relit `projet.md` et vous le dit.
- « Recommence cette étape » : chaque commande accepte de compléter ou de refaire.
- La conversation devient longue ou lente : tapez `/clear`, puis reprenez. Rien n'est perdu, tout est dans
  les fichiers.
- Votre quota baisse vite : passez en mode rapide (« passe en mode rapide »), et une tâche par conversation.

Une question, un blocage, ou quand ça marche : hugo@bumpslab.com · thibault@bumpslab.com
