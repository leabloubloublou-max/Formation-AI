---
name: landing-page
description: Construit la landing page de 02-landing-page en prolongeant la direction artistique choisie à toute la page - en mode rapide, Claude l'écrit lui-même en un passage (environ 15 minutes) ; en mode complet, avec l'équipe d'agents (designer, copywriter, développeur, testeur). L'utilisateur est l'arbitre. À utiliser pour créer, refaire ou faire évoluer la page.
argument-hint: "[rapide | complet | modifier <ce qui change>]"
---

# Construire la landing page

Lis d'abord `02-landing-page/CLAUDE.md` et le mode dans `00-mon-projet/projet.md` (`$ARGUMENTS` peut le
forcer).

| | Rapide (atelier, par défaut) | Complet |
|---|---|---|
| Comment | Claude écrit la page lui-même, en un passage, à partir de la direction choisie | quatre agents, deux relectures |
| Durée | **15 minutes** | 45 à 90 minutes |

## Avant de commencer (les deux modes)

- **La direction est choisie** : `charte-graphique.md` est rempli et
  `travail/directions/direction-x.html` existe. Sinon : `/direction-artistique`.
- **La matière** : `argumentaire.md` et `cahier-des-charges.md`. S'ils sont vides en mode rapide, pose
  dans la conversation les questions qui manquent (pour qui, quel problème, quelle promesse, ce que la
  page demande de faire) : cinq minutes valent mieux qu'une page fausse.
- **Les apports, en un seul message**, avec le chemin exact :
  - le **logo** → `00-mon-projet/apports/logo/` ;
  - **1 à 4 photos** (produit, équipe, terrain) → `00-mon-projet/apports/photos/` ;
  - le **lien du formulaire ou de l'agenda** (Tally, Calendly...) → à coller dans la conversation ;
  - les **preuves** (citations de clients avec accord, partenaires, chiffres sourcés).
  Attends « c'est déposé » ou « plus tard ». Pour ce qui vient « plus tard » : `[À FOURNIR : ...]` dans
  la page et une ligne dans `projet.md`.

## Mode rapide

Tu travailles toi-même, sans agent.

1. **Les textes, d'abord dans la conversation** (3 minutes). Propose deux titres pour le haut de page ; il
   choisit. Les autres textes, tu les écris directement dans la page, avec ces règles :
   - chaque section dit un **bénéfice** pour le client, avec ses mots, pas une fonctionnalité ;
   - un chiffre n'entre que s'il est « fait » dans `01-etude-de-marche/resultats/tri.md`, avec sa source
     en petit ;
   - pas de preuve inventée : sans preuve réelle, pas de section de témoignages ;
   - un seul appel à l'action, le même lien en haut et en bas ;
   - typographie française : espace insécable avant `; : ! ?` et à l'intérieur des « ».
2. **La page, en un passage** (8 minutes). Pars du fichier de la direction choisie : mêmes polices, mêmes
   couleurs, même moment fort. Écris `02-landing-page/site/index.html` et `site/styles.css` (et
   `site/script.js` si un effet le demande). Sections : haut de page, problème, comment ça marche,
   bénéfices, preuves s'il y en a, questions fréquentes (`<details>`), appel final, pied de page. Copie
   le logo et les photos retenus dans `site/images/`. Couleurs et polices en variables CSS (`:root`).
   Varie le rythme d'une section à l'autre : ne pose pas six fois la même mise en page. Applique les
   **règles de mise en page** de `02-landing-page/CLAUDE.md`, la première surtout : le contenu centré dans
   1 200 px, pour qu'un écran de 27 pouces ne l'étale pas.
3. **Une vérification** (2 minutes) :
   ```
   .venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/site
   ```
   Il teste à 390, 1 280 et 1 920 px. Corrige les ERREUR (dont « contenu étalé ») et ce qui est cassé
   dans les captures, **un tour**. Pas de peaufinage.
4. **L'arbitre.** Dis-lui d'ouvrir `02-landing-page/site/index.html` (clic droit > *Show Preview*) et sur
   son téléphone, de relire chaque texte, et donne la liste des `[À FOURNIR]`.

## Mode complet

Annonce que quatre agents vont travailler, 45 à 90 minutes, et **attends l'accord**.

1. **Design et textes, en parallèle**, dans un même message : `landing-designer` (mission 1) →
   `travail/design-plan.md` et `site/styles.css` ; `landing-copywriter` → `travail/textes.md`. La direction
   choisie sert de base. Présente les trois titres proposés, le moment fort, les `[PREUVE À FOURNIR]` ;
   **attends sa validation** et reporte ses choix dans les fichiers.
2. **Construction** : `landing-developpeur` construit `site/` et le vérifie en local.
3. **Relecture et tests, en parallèle** : `landing-designer` (mission 2) et `landing-testeur`
   (→ `travail/rapport-test.md`). Fais corriger par le bon agent, puis relance le testeur. Toute correction
   de texte passe d'abord par `travail/textes.md`. Deux tours au plus.
4. **L'arbitre** : ce qui est construit, les erreurs ouvertes, ce qu'il doit vérifier lui-même.

## Ensuite

C'est lui qui décide de mettre en ligne : `/mettre-en-ligne`.

`/landing-page modifier <ce qui change>` : en rapide, modifie la page directement puis relance le testeur ;
en complet, passe par l'agent concerné puis par le testeur.
