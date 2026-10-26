---
name: direction-artistique
description: Crée la direction artistique de la landing page à partir des inspirations du fondateur - il colle 2 ou 3 sites ou captures qui lui font dire « waw », Claude crée trois directions sur mesure en vrai (haut de page en HTML), le fondateur choisit en voyant, la charte se remplit. Environ 10 minutes. À utiliser avant de construire la page, ou quand l'utilisateur parle de charte, couleurs, polices, style, inspiration.
argument-hint: "[rapide | complet]"
---

# Direction artistique

Le « waw » ne vient pas d'un prompt générique. Il vient des **inspirations du fondateur**, d'un **parti pris
assumé**, et de **vraies images**. Chaque projet doit avoir une page qui ne ressemble à aucune autre : tout
part de ce qu'il apporte.

**Objectif de temps : 10 minutes**, de la demande des inspirations aux trois aperçus. Tu travailles
**toi-même, dans la conversation**, sans lancer d'agent. En mode complet (`$ARGUMENTS` ou `projet.md`),
tu peux lancer `directeur-artistique`, qui explore plus longtemps (20 à 30 minutes).

Lis `00-mon-projet/projet.md`, et `02-landing-page/argumentaire.md` et `cahier-des-charges.md` s'ils sont
remplis : les aperçus utilisent le vrai nom, le vrai titre, la vraie promesse.

## 1 · Les inspirations (un seul message)

Regarde d'abord `00-mon-projet/apports/inspirations/` et `apports/charte/`. Demande ce qui manque **en un
seul message** :

« Pour ta direction artistique, quatre choses :
1. **deux ou trois sites qui te font dire « waw »**, pas forcément de ton secteur. Le mieux : une capture
   d'écran de chacun, glissée dans `00-mon-projet/apports/inspirations/`. Sinon, colle les liens.
   Pour chercher : godly.website, land-book.com, awwwards.com ;
2. **trois mots** pour l'impression que ta page doit laisser ;
3. **ce que tu ne veux surtout pas** (un style, une couleur, un cliché de ton secteur) ;
4. **tes images** : 3 à 5 photos dans `00-mon-projet/apports/photos/` (ton terrain, tes clients avec leur
   accord, ton équipe, ton produit). Pas encore de photos à toi ? Prends-en sur unsplash.com ou pexels.com
   (gratuites, usage commercial permis) en attendant. Si ton projet est humain (soin, service, famille,
   éducation), ce sont les photos qui feront l'effet, plus que la typographie. »

Une charte existante (logo, couleurs) fait foi. Note ses réponses dans `apports/inspirations/liens.md`.

**Vérifie la cohérence avant de créer.** Si les inspirations ne vont pas avec le projet (des sites de
gadgets techniques pour un projet de soin, un site sans aucune image pour un projet qui vit de la relation
humaine), dis-le en une phrase et demande s'il veut en ajouter une ou deux plus proches. C'est la seule
question en plus : elle évite trois directions à côté.

## 2 · Lire les inspirations (2 minutes)

- **Les captures** : regarde chacune (Read sur l'image). C'est la matière la plus fiable.
- **Les liens sans capture** : ce que tu sais du site ; s'il t'est inconnu, un seul WebFetch par lien. Pas
  de navigateur, pas de capture des sites.
- **Les photos** : regarde-les aussi. Leur lumière, leurs couleurs et leurs sujets donnent souvent la palette
  et le ton mieux que les sites d'inspiration.

Écris `02-landing-page/travail/inspirations.md`, court : pour chaque référence, ce qui fait l'effet
(typographie, échelle, couleur, composition, matière, mouvement) en deux lignes ; puis l'**ADN commun** en
trois traits.

## 3 · Trois directions sur mesure (5 minutes)

Trois partis pris qui ne se ressemblent pas :

- **A · fidèle** : la traduction la plus directe de l'ADN et des trois mots ;
- **B · audacieuse** : un trait de l'ADN poussé à l'extrême (une échelle, une couleur, une matière) ;
- **C · inattendue** : une idée tirée du produit ou du métier lui-même (son geste, son matériau, son
  vocabulaire), pas des inspirations.

Les trois ont chacune **leur paire de polices, leur palette et leur composition**. **S'il y a des photos,
au moins deux directions sont construites autour d'elles** (photo pleine page, recadrage serré sur un geste
ou un visage, bichromie aux couleurs de la page, mosaïque) : sur un projet humain, une page sans visage
est une page froide. Écris directement, sans
étape intermédiaire, `02-landing-page/travail/directions/direction-a.html`, `-b.html`, `-c.html` :

- un fichier autonome (CSS dans `<style>`), le haut de page et une section, le vrai contenu ; le vrai logo
  et les vraies photos s'ils existent, copiés (et allégés, 300 Ko au plus) dans
  `02-landing-page/travail/directions/images/` ;
- **polices** chargées par une ligne, depuis Fontsource sur jsDelivr :
  `<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fontsource-variable/<nom>@5/index.css">`
  (ou `@fontsource/<nom>@5/400.css` pour une police non variable). Pioche dans tout le catalogue
  (fontsource.org), pas dans les dix polices que tout le monde utilise ;
- **un seul moment fort** par direction ; au plus un effet de `02-landing-page/effets/` (en copiant son
  bloc `À COPIER`) ;
- en tête du fichier, un commentaire de cinq lignes : l'idée, les polices, les couleurs en hex, l'effet,
  ce qui vient de quelle inspiration ;
- texte lisible (contraste AA), et les **règles de mise en page** de `02-landing-page/CLAUDE.md` (contenu
  centré dans 1 200 px, lignes de 75 caractères au plus, espacements en multiples de 8, photos cadrées sur
  les visages).

**Interdit, parce que c'est le site « fait par une IA » qu'on reconnaît tout de suite** : Inter, Roboto,
Arial, Poppins, Montserrat, Space Grotesk ; dégradé violet ou bleu-violet ; titre centré sur fond à
« blob » flou ; grille de trois cartes à ombre portée ; icônes emoji ; effet verre dépoli ; « badge » au-dessus
du titre par réflexe. Pas de faux logo. Une photo d'ambiance (Unsplash, Pexels) illustre une situation ;
elle n'est jamais présentée comme un client, un utilisateur ou le produit (pas de nom, pas de citation
dessous).

## 4 · Une seule vérification

```
.venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/travail/directions --largeurs 390,1440,1920 --sans-reduit
```

Regarde le premier morceau de capture de chaque direction (dans `02-landing-page/travail/`). Corrige
**seulement** ce qui est cassé (débordement, contenu étalé, texte illisible, police non chargée), **une
fois**. Pas de
peaufinage : le fondateur n'a pas encore choisi.

Si Playwright n'est pas installé, saute cette étape : le fondateur ouvre les fichiers lui-même.

## 5 · Le fondateur choisit en voyant

Dis-lui d'ouvrir les trois fichiers (clic droit > *Show Preview*), et montre-lui les captures. Pour
chacune, une ligne : l'idée, et ce qu'elle emprunte à quelle inspiration.

Demande *(choix)* : A, B, C, ou un mélange (« la typo de A avec les couleurs de C »). Un mélange ou un
ajustement : fais-le tout de suite dans le fichier choisi, une fois ; puis il tranche.

## 6 · La charte

Remplis `02-landing-page/charte-graphique.md` à partir de la direction choisie : polices (avec leur ligne
Fontsource), tailles, couleurs en hex et leurs usages, le moment fort et l'effet, les interdits. Ajoute la
décision, datée, dans `00-mon-projet/projet.md`.

Ensuite : `/landing-page`, qui prolonge le fichier choisi à toute la page.
