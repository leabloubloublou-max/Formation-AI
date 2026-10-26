---
name: mettre-en-ligne
description: Met en ligne la landing page de 02-landing-page/site sur Vercel, en guidant l'utilisateur pas à pas, après une dernière vérification de sécurité. À utiliser quand l'utilisateur veut publier, déployer ou mettre à jour sa page en ligne.
disable-model-invocation: true
---

# Mettre en ligne

Le guide complet est dans `02-landing-page/guides/deployer-vercel.md`. Suis-le, une étape à la fois, en
attendant que l'utilisateur confirme chacune.

## 1. Dernière vérification

- `02-landing-page/travail/rapport-test.md` existe et dit « prêt à mettre en ligne : oui ». Sinon, propose
  `/landing-page tester` d'abord.
- Cherche dans `02-landing-page/site/` toute clé, jeton ou mot de passe. S'il y en a un : arrête-toi,
  explique le risque (`guides/securite.md`) et fais-le retirer.
- Demande à l'utilisateur s'il a ouvert la page sur son téléphone.

## 2. Choisir la méthode

Demande à l'utilisateur laquelle il préfère :

- **Depuis le terminal** (le plus rapide) : il faut Node.js. Vérifie avec `node --version`. S'il manque,
  donne le lien https://nodejs.org (version LTS) et attends.
- **Depuis GitHub** (mise à jour automatique à chaque `git push`) : il faut que son repo soit sur son
  compte GitHub.

## 3. Publier

**Terminal.** La première commande ouvre une connexion dans le navigateur et pose des questions :
c'est l'utilisateur qui doit les lancer et y répondre. Donne-lui les commandes à taper dans le terminal de
VS Code, depuis la racine du repo :

```bash
cd 02-landing-page/site
npx vercel
npx vercel --prod
```

Les réponses par défaut conviennent. Il te colle l'adresse obtenue.

**GitHub.** Guide-le sur vercel.com : *Add New > Project*, le repo, **Root Directory** :
`02-landing-page/site`, **Framework Preset** : *Other*, puis *Deploy*.

## 4. Après

- Ouvre l'adresse en ligne avec lui et vérifie que l'action principale fonctionne (lien d'agenda,
  formulaire).
- Nom de domaine : *Settings > Domains* dans le projet Vercel, puis les enregistrements DNS chez son
  registraire.
- Rappelle-lui qu'une modification se fait avec `/landing-page modifier ...`, puis `npx vercel --prod`
  (ou un `git push` avec la méthode GitHub).
