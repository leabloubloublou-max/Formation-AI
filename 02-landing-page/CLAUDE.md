# Landing page et MVP

Ce dossier sert à mettre en ligne **une page qui affiche l'argumentaire**, ou un premier produit minimal qui
rend déjà service. Le cahier des charges et la direction artistique font la différence, pas le prompt.

## Le parcours

1. **Les notes** : `notes.md`. Les pages qui plaisent à l'utilisateur, les produits des concurrents, ce qu'il
   garde de chacun. Avant la première ligne de code.
2. **L'argumentaire** : `argumentaire.md`. Trois convictions, le problème dit avec les mots du client,
   un argument par levier (temps, argent, risque, dépendance levée), les preuves. Rempli avec
   l'utilisateur, question par question. C'est la matière du copywriter, du deck et des messages.
3. **Le cahier des charges** : `cahier-des-charges.md`, avec `/cahier-des-charges`.
   Pour qui, quel problème, quelle promesse, quel parcours, ce que la page collecte, les contraintes.
4. **La direction artistique** : `/direction-artistique` (10 minutes). Le fondateur apporte 2 ou 3
   inspirations (`00-mon-projet/apports/inspirations/`), Claude crée trois directions sur mesure en vrai
   (`travail/directions/`), le fondateur choisit en voyant, et `charte-graphique.md` se remplit.
5. **La construction** : `/landing-page` (15 minutes en mode rapide). Claude prolonge la direction choisie
   à toute la page dans `site/`. En mode complet, l'équipe d'agents.
6. **La mise en ligne** : `/mettre-en-ligne` (Vercel).

## La règle d'or

**Les réponses viennent de la tête de l'utilisateur, pas de toi.** Tu poses les questions qui manquent, tu
repères les angles morts, tu proposes et tu contredis. Tu ne remplis jamais un champ du cahier des charges ou
de la charte avec une réponse inventée : un champ sans réponse reste marqué « à décider ».

Ne construis rien tant que `argumentaire.md`, `cahier-des-charges.md` et `charte-graphique.md` contiennent
des crochets `[...]`. Propose plutôt de remplir l'argumentaire avec l'utilisateur, `/cahier-des-charges` ou
`/direction-artistique`.

## La vitesse

Le fondateur attend devant son écran. En mode rapide : **pas d'agent**, tu écris toi-même ; **un passage**
de création, **une** vérification avec `effets/tester.py`, **un** tour de correction. Tu ne peaufines pas
ce qu'il n'a pas encore vu : tu lui montres, il choisit, puis on affine.

## Les règles de mise en page

Elles valent pour les aperçus, la page et toute modification. `effets/tester.py` contrôle les trois
premières automatiquement (à 390, 1 280 et 1 920 px).

1. **Le contenu est centré dans 1 200 px au plus.** Seuls les fonds et les photos pleine largeur vont
   d'un bord à l'autre. En CSS, une variable suffit :
   `--bord: max(var(--marge), calc((100% - 1200px) / 2));` puis `padding-inline: var(--bord)` sur chaque
   section, l'en-tête et le pied. Sans ça, sur un écran de 27 pouces, le texte part à gauche, l'image à
   droite et un trou se creuse au milieu.
2. **Des lignes de 45 à 75 caractères** (`max-width: 65ch` sur les paragraphes), des titres de 15 à 22
   caractères de large (`max-width: 18ch` à `22ch`).
3. **Rien ne déborde sur le côté**, de 360 à 2 560 px.
4. **Une échelle d'espacement**, en multiples de 8 : 8, 16, 24, 32, 48, 64, 96, 128 px. Entre deux
   sections : 96 à 128 px sur ordinateur, 64 à 80 px sur téléphone (`clamp()`). À l'intérieur d'une
   section, des écarts nettement plus petits : ce qui va ensemble est proche, ce qui est séparé est loin.
5. **Deux colonnes** : un écart de 32 à 96 px, les colonnes alignées en haut ou au centre. Sous 860 px,
   une seule colonne, l'image d'abord quand elle porte le message.
6. **Un axe d'alignement par section** (le bord gauche du contenu). Le texte centré, seulement pour un
   bloc court (l'appel final), avec une largeur limitée.
7. **Le premier écran se suffit** : à 1 440 × 900 et à 390 × 844, on lit le titre et on voit le bouton
   sans défiler.
8. **Les photos sont cadrées sur les personnes** : `aspect-ratio` fixe, `object-fit: cover` et un
   `object-position` choisi pour garder les visages, vérifié sur téléphone (un cadrage large peut couper
   la moitié de la scène).
9. **Zones cliquables de 44 px au moins**, marges latérales de 16 à 24 px sur téléphone.

## L'équipe (mode complet)

| Rôle | Agent | Sa matière | Fini quand |
|---|---|---|---|
| Designer | `landing-designer` | la charte graphique | chaque page respecte la charte |
| Copywriter | `landing-copywriter` | l'argumentaire, le cahier des charges, l'étude de marché | chaque section dit un bénéfice, pas une fonctionnalité |
| Développeur | `landing-developpeur` | le cahier des charges, les textes, le plan du designer | tout fonctionne en local |
| Testeur | `landing-testeur` | le site en local, puis sur téléphone | aucune erreur ouverte |
| **Arbitre** | **l'utilisateur** | ce que les quatre produisent | il met en ligne |

Un agent qui fait, un agent qui relit, et l'utilisateur qui tranche. Présente-lui les choix, ne les fais pas
à sa place.

## Le site

- Tout vit dans `site/` : `index.html`, `styles.css`, `script.js` si besoin, `images/`.
- **Polices** : chargées depuis Fontsource sur jsDelivr, une ligne par police
  (`https://cdn.jsdelivr.net/npm/@fontsource-variable/<nom>@5/index.css`). Rien à télécharger.
- **Pas de framework, pas d'étape de build** : du HTML et du CSS, plus au besoin un ou deux effets du
  catalogue `effets/` (GSAP, Lenis, OGL, chargés par CDN à version figée). On l'ouvre avec Live Preview dans VS Code,
  et Vercel le met en ligne tel quel. Next.js ou Astro viendront plus tard, si le produit grandit.
- Les couleurs, polices et espacements sont des variables CSS (`:root`) tirées de `charte-graphique.md`.
  Aucune valeur en dur quand une variable existe.
- Mobile d'abord : la page est pensée pour un téléphone, puis élargie.

## Trois risques que l'IA ne gère pas à la place de l'utilisateur

Détails : `guides/securite.md`.

1. **Les clés d'accès** vivent dans un fichier `.env` sur l'ordinateur et dans les réglages de l'hébergeur.
   Jamais dans le code, jamais dans git. Tu n'affiches jamais le contenu d'un `.env`.
2. **Les données personnelles** : un formulaire qui collecte un nom et un email rend l'utilisateur
   responsable. Ne collecter que le nécessaire, et savoir dire où c'est stocké et qui y accède.
3. **La solidité** : le code généré tient la démo. Avant de traiter des paiements ou des données sensibles,
   l'utilisateur fait relire par un développeur. Dis-le quand c'est le cas.

## Exemples

`exemples/` contient l'argumentaire, le cahier des charges et la charte de BUMPSLAB, l'exemple suivi en formation. Ce sont
des modèles de forme : ne reprends jamais leur contenu, leurs couleurs ni leurs textes pour un autre projet.
