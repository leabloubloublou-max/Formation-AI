---
name: nouveau-projet
description: Accueille un fondateur et lance son projet dans le kit. Remplit 00-mon-projet/projet.md par questions, une à la fois, fait l'inventaire de ce qu'il a déjà (logo, photos, inspirations, documents) et lui dit quoi déposer et où, puis l'oriente vers la bonne étape. À utiliser au tout début, quand projet.md est vide, ou quand l'utilisateur dit « je commence », « j'ai un projet », « par où je commence ».
---

# Nouveau projet

Le but : en dix minutes, Claude connaît le projet, sait ce que le fondateur a déjà, et le fondateur sait ce
qui va se passer. **Tout ce qui est dit ici s'écrit dans `00-mon-projet/projet.md`**, pour ne plus jamais
le redemander.

## 0. Si le projet existe déjà

Si `00-mon-projet/projet.md` est déjà rempli (plus de crochets dans « L'essentiel »), ne repose pas les
questions : résume le projet en trois lignes, montre l'inventaire des apports, et demande où il veut
reprendre.

## 1. Accueillir, en deux phrases

« Je vais te poser huit questions courtes sur ton projet, puis on regarde ensemble ce que tu as déjà (logo,
photos, documents). Ensuite je te propose par où commencer. »

Tutoie ou vouvoie selon la façon dont l'utilisateur écrit.

## 2. Les questions, une à la fois

Pose-les dans cet ordre, **une par message**. Quand les réponses possibles sont connues, utilise l'outil de
questions à choix (l'utilisateur peut toujours écrire autre chose). Après chaque réponse, écris-la dans
`projet.md` avec ses mots.

1. Le nom du projet. (S'il hésite, note les candidats ; on vérifiera la disponibilité pendant l'étude.)
2. En une phrase : ce que tu vends, à qui, et ce que ça change pour eux. Propose de l'aider à la reformuler
   s'il bloque, mais garde ses mots.
3. Où tu en es : idée, prototype, premiers clients, en vente. *(choix)*
4. Qui a le problème, et qui paie ? Si ce n'est pas la même personne, note les deux.
5. Où sont tes clients : ville, canton, région, pays. *(choix + autre)*
6. Des concurrents que tu connais ? « Aucun » est une réponse valable.
7. Un prix envisagé, même approximatif ? « Je ne sais pas » est valable : l'étude fera trois scénarios.
8. Un site, une page, un deck existant ? Si oui, le lien ou le fichier.

S'il a un deck ou un document : propose de le déposer dans `00-mon-projet/apports/documents/`, lis-le, et
complète `projet.md` en disant ce que tu en as tiré. Ne recopie pas un chiffre d'un document sans dire d'où
il vient.

## 3. L'inventaire des apports

Regarde ce qu'il y a déjà dans `00-mon-projet/apports/`. Puis dis-lui, dans un seul message clair, ce qui
servira et où le déposer :

- **Logo** → `00-mon-projet/apports/logo/` (SVG de préférence, sinon PNG transparent)
- **Photos** du produit, de l'équipe, du terrain → `00-mon-projet/apports/photos/`
- **Inspirations** : 3 à 5 sites qui lui font dire « waw » → les liens dans
  `00-mon-projet/apports/inspirations/liens.md`, avec ce qu'il aime dans chacun ; captures bienvenues
- **Charte existante** → `00-mon-projet/apports/charte/`

Précise : « Rien n'est obligatoire maintenant. Je te redemanderai chaque élément au moment où j'en aurai
besoin. Dis-moi « c'est déposé » quand tu as glissé un fichier. »

Quand il dépose un fichier : ouvre-le (une image, tu peux la regarder), dis en une phrase ce que tu vois,
et mets à jour le tableau « Ce que vous avez déjà » de `projet.md`.

## 4. Choisir le mode

Explique en deux lignes, puis demande *(choix)* :

- **Rapide** (recommandé en atelier) : un seul agent de recherche, une vérification ciblée, une landing
  sans double relecture. Une à deux heures d'échange, consommation modérée.
- **Complet** : quatre agents de recherche, vérification de chaque chiffre, relecture design et tests
  complets. Pour un vrai lancement ; consomme nettement plus.

Note le choix dans `projet.md` (« Mode : rapide » ou « Mode : complet »). Toutes les commandes le relisent.

## 5. Orienter

Résume en trois lignes ce que tu as compris, puis propose la suite selon le stade :

- idée, pas sûr du marché → `/etude-de-marche`
- marché connu, il faut une page → `/direction-artistique` puis `/landing-page`
- page en ligne, il faut des clients → la prospection (`03-prospection/`)

Le parcours complet, expliqué pour l'utilisateur, est dans `PARCOURS.md` à la racine : mentionne-le.
