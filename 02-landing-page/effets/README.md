# Catalogue d'effets testés

Huit effets prêts à copier dans `site/`, chacun dans un fichier autonome (HTML, CSS et JS dans le même
fichier, police système, couleurs en variables CSS en tête). Ouvrez `index.html` avec Live Preview pour
les voir. En tête de chaque fichier, un commentaire dit ce que fait l'effet, quand l'utiliser, quand
l'éviter et quoi copier : les blocs à reprendre sont entre des repères `À COPIER`.

Ils servent à une chose : éviter le site « généré par IA » qu'on reconnaît au premier coup d'œil, avec
un vrai moment de surprise, **mais un seul**. Pour le designer IA (`landing-designer`,
`directeur-artistique`) : on ne prend que les effets retenus dans `charte-graphique.md`, et on reprend le
code du fichier d'exemple tel quel, en changeant les textes et les variables.

## Les effets

Poids : ce que le navigateur télécharge, compressé, la première fois. Les bibliothèques partagées ne se
paient qu'une fois (GSAP sert au titre, à la section épinglée et à la liaison avec Lenis).

| Effet | Fichier | Bibliothèque | Poids approx. | Accessibilité | À utiliser pour | À éviter si |
|---|---|---|---|---|---|---|
| Titre révélé ligne par ligne | `titre-revele.html` | GSAP + SplitText | 32 Ko | Mouvement réduit : titre affiché d'emblée. Lecteur d'écran : phrase entière (aria-label). Titre réaffiché si le CDN ne répond pas. | LE titre du haut de page, une phrase courte et forte (2 à 4 lignes). | Titres de section (devient le « fade-up » générique), texte courant, titre de plus de 5 lignes sur téléphone. |
| Section épinglée en trois étapes | `section-epinglee.html` | GSAP + ScrollTrigger | 46 Ko | Mouvement réduit ou sans JS : les étapes s'affichent l'une sous l'autre, en liste `<ol>`. | Une vraie suite de 3 ou 4 étapes : « comment ça marche », avant / pendant / après. | Étapes qui ne sont pas une suite, plus de 3 lignes de texte par étape, haut de page, autre effet de défilement sur la page. |
| Défilement fluide | `defilement-fluide.html` | Lenis (+ GSAP et ScrollTrigger si la page en a déjà) | 6 Ko seul | Mouvement réduit : Lenis n'est pas démarré. Clavier inchangé. Téléphone : défilement natif. | Page longue et éditoriale, ou accompagnement d'une section épinglée (l'épinglage paraît plus propre). Peut s'ajouter à l'effet principal. | Page courte, long formulaire, zones qui défilent seules non marquées `data-lenis-prevent`, inertie forte. |
| Bandeau de texte défilant | `bandeau-defilant.html` | aucune (CSS) | < 1 Ko | Bouton pause (règle WCAG 2.2.2), pause au survol et au clavier. Texte lu une fois. Mouvement réduit : bandeau immobile, à la ligne. | Séparation entre deux sections : mots de l'univers (métiers, villes, matières) ou slogan de 3 à 6 mots. | Information à lire absolument (prix, promesse, conditions), logos de clients non autorisés, deux bandeaux sur la page. |
| Grain sur le fond | `grain.html` | aucune (CSS + SVG) | < 1 Ko | Décoratif, immobile, n'intercepte pas les clics. Vérifier le contraste du texte une fois posé. | Aplat de couleur franche, fond sombre, haut de page sans photo. Se combine avec un autre effet. | Par-dessus des photos, opacité au-delà de 0,15, fond déjà texturé. |
| Fond animé en dégradé organique | `fond-shader.html` | OGL (WebGL) | 29 Ko | Mouvement réduit, pas de WebGL ou CDN coupé : dégradé CSS fixe aux mêmes couleurs. Calcul arrêté hors écran. | Moment fort d'un haut de page sans photo, pour un produit abstrait (service, logiciel, conseil). | Vous avez une vraie photo ou une capture du produit, texte long par-dessus, toute la page, autre mouvement dans le même écran. |
| Bouton magnétique et aperçu | `suivi-souris.html` | aucune (JS) | 1 Ko | Rien sur écran tactile ni en mouvement réduit. Le bouton reste un vrai lien, cliquable à sa place. | A : le seul bouton d'appel à l'action. B : une liste de 3 à 8 éléments qui ont chacun une vraie photo. | Tous les boutons, bouton d'envoi d'un formulaire, B sans vraies images, curseur personnalisé. |
| Chiffre qui s'anime | `compteur.html` | aucune (JS) | 1 Ko | Valeur finale écrite dans le HTML. Lecteur d'écran : valeur finale seulement. Mouvement réduit : affichée d'emblée. | 1 à 3 chiffres **sourcés** (source, date, méthode) qui prouvent la promesse. | Chiffre sans source, prix, petits nombres (1 à 10), cliché « gros chiffre + libellé + dégradé » en haut de page. |

Associations qui marchent : grain + titre révélé ; grain + fond shader ; défilement fluide + section
épinglée. Associations à proscrire : deux effets en mouvement dans le même écran (shader + bandeau, titre
révélé + bouton magnétique juste dessous).

## Les règles d'or

1. **Un moment fort par page.** Choisissez l'endroit où la page prend un risque visuel, et un seul. Le
   reste est immobile et sobre : c'est le contraste qui crée l'effet. Rarement plus de deux effets par
   page, et le second est alors discret (grain, défilement fluide).
2. **Toujours respecter « réduire les animations ».** Chaque fichier vérifie
   `prefers-reduced-motion` : l'effet se coupe et le contenu reste complet et lisible. Ne retirez jamais
   cette vérification en copiant le code.
3. **Pas d'effet sur le texte courant.** Les paragraphes, les listes d'arguments, les prix et les
   formulaires ne bougent pas. Pas d'apparition en fondu sur chaque section ni d'effet au survol sur
   chaque carte : c'est la signature des sites générés.
4. **Penser au téléphone d'abord.** La plupart des visiteurs arrivent sur un téléphone. Les effets à la
   souris n'y existent pas, le shader y tourne en basse définition, et chaque bibliothèque se paie en
   temps de chargement. Testez sur un vrai téléphone avant la mise en ligne.
5. **Le contenu avant l'effet.** Un effet sert une phrase, une étape, un chiffre déjà écrits et justes.
   Jamais de chiffre inventé pour remplir un compteur, jamais d'effet pour masquer qu'une section n'a
   rien à dire.
6. **Versions figées.** Chaque lien CDN porte un numéro de version exact (jamais `@latest`) : la page
   ne change pas toute seule le jour où une bibliothèque sort une nouvelle version.

## Les liens CDN (versions figées)

À copier tels quels. Les fichiers ne sont pas copiés dans le repo : le navigateur les télécharge depuis
jsdelivr.

```html
<!-- GSAP 3.15.0 -->
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/ScrollTrigger.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/SplitText.min.js"></script>

<!-- Lenis 1.3.27 (la CSS dans <head>, le script avant </body>, après GSAP s'il y en a) -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/lenis@1.3.27/dist/lenis.css">
<script src="https://cdn.jsdelivr.net/npm/lenis@1.3.27/dist/lenis.min.js"></script>
```

OGL 1.0.11 n'existe qu'en modules ES : `fond-shader.html` importe ses fichiers sources depuis
`https://cdn.jsdelivr.net/npm/ogl@1.0.11/src/` (`core/Renderer.js`, `core/Program.js`, `core/Mesh.js`,
`extras/Triangle.js`, plus leurs dépendances que le navigateur va chercher seul), dans un
`<script type="module">`. L'alternative en un seul fichier, `https://cdn.jsdelivr.net/npm/ogl@1.0.11/+esm`,
est générée par jsdelivr à la demande : elle fonctionne aussi, mais n'a pas pu être testée hors ligne
(voir plus bas).

## Licences

- **GSAP** (gsap, ScrollTrigger, SplitText) : licence « Standard no charge » de GreenSock
  (<https://gsap.com/standard-license>). Depuis le rachat par Webflow, GSAP et tous ses plugins, SplitText
  compris, sont gratuits, **y compris pour un usage commercial**, sur tout site ou application. La
  licence interdit seulement de l'intégrer à un outil qui permet de créer des animations visuellement,
  sans code, en concurrence avec Webflow : une landing page n'est pas concernée. On charge GSAP depuis
  le CDN, on ne copie pas ses fichiers dans le repo.
- **Lenis** : licence MIT.
- **OGL** : licence Unlicense (domaine public).

## Tester

`tester.py` ouvre chaque page dans Chromium, à 390 et 1280 px de large, normalement puis en mode
« réduire les animations ». Il relève les erreurs JavaScript et les fichiers introuvables, fait défiler
la page, signale une page qui déborde sur le côté, une animation qui tourne encore en mode réduit ou un
texte resté invisible, et prend des captures découpées en morceaux lisibles. Les captures vont dans
`02-landing-page/travail/` (ignorées par git).

```bash
# une fois : installer Playwright et son navigateur (environ 150 Mo)
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium

# tester le site, ou le catalogue
.venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/site
.venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/effets --page titre-revele.html
```

Si le réseau bloque les CDN (réseau d'entreprise, machine de test), installez les bibliothèques dans un
dossier à part et passez-le avec `--cdn-local` : le script sert alors les liens jsdelivr depuis ce dossier
et vérifie que la version installée est bien celle du lien.

```bash
mkdir -p /tmp/libs && cd /tmp/libs && npm i gsap@3.15.0 lenis@1.3.27 ogl@1.0.11
.venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/site --cdn-local /tmp/libs/node_modules
```

Le script ne remplace pas le regard : ouvrez les captures, puis la page sur un vrai téléphone.

## Ce qui a été vérifié (25 octobre 2026)

Chromium 1243 (Playwright), bibliothèques servies depuis les paquets npm exacts, à 390 et 1280 px :

- aucune erreur console sur les huit pages, en mode normal et en mode réduit ;
- titre révélé : les lignes montent bien depuis leur masque, l'aria-label porte la phrase entière, le
  titre réapparaît si le CDN est coupé ;
- section épinglée : épinglage et passage d'étape à la molette, calage sur l'étape suivante, libération
  de la page après la troisième ; liste normale en mode réduit et sans CDN ;
- défilement fluide : inertie active, ancres qui glissent, barre ScrollTrigger synchronisée ; défilement
  natif en mode réduit ;
- fond shader : rendu WebGL, repli sur le dégradé CSS en mode réduit, sans WebGL et sans CDN ;
- bouton magnétique et aperçu : attraction puis retour en place, aperçu qui suit le pointeur ; rien sur
  écran tactile ;
- compteur : comptage puis valeur finale au format français, valeur affichée d'emblée en mode réduit ;
- bandeau : défilement continu, immobile et à la ligne en mode réduit ;
- aucune page ne déborde sur le côté à 390 px.
