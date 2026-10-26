# Mettre la page en ligne avec Vercel

Le site est du HTML et du CSS dans `02-landing-page/site/` : Vercel le publie tel quel, sans réglage.
Le plus simple : tapez `/mettre-en-ligne` dans Claude Code, il vous guide.

## Avant

- [ ] Le testeur n'a plus d'erreur ouverte.
- [ ] Vous avez relu la page sur votre téléphone.
- [ ] Aucune clé dans le code (voir `securite.md`).
- [ ] Un compte Vercel gratuit : https://vercel.com/signup (le plus simple : « Continue with GitHub »).

## Option 1 · Depuis le terminal de VS Code (le plus rapide)

Il faut Node.js (https://nodejs.org, version LTS). Depuis la racine du repo :

```bash
cd 02-landing-page/site
npx vercel          # première fois : connexion dans le navigateur, puis quelques questions
npx vercel --prod   # publie la version définitive
```

Aux questions de la première fois, les réponses par défaut conviennent. Vercel donne une adresse en
`.vercel.app` : c'est votre page en ligne.

## Option 2 · Depuis GitHub (mise à jour automatique)

1. Poussez votre copie du repo sur votre compte GitHub.
2. Sur vercel.com : *Add New > Project*, choisissez le repo.
3. **Root Directory** : `02-landing-page/site`. **Framework Preset** : *Other*. Rien d'autre à régler.
4. *Deploy*. Ensuite, chaque `git push` met la page à jour.

## Votre nom de domaine

Dans le projet Vercel : *Settings > Domains*, ajoutez votre domaine, puis recopiez chez votre registraire
(Infomaniak, OVH, Gandi...) les enregistrements DNS que Vercel affiche. Comptez de quelques minutes à
quelques heures.

## Pour aller plus loin

Un produit qui grandit (comptes, base de données, paiement) demandera un framework comme Next.js ou Astro,
et un hébergeur pour le serveur (Vercel, Railway). C'est une autre étape, à faire relire par un développeur.
