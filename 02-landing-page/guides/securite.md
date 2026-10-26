# Trois risques que l'IA ne gère pas à votre place

Aucun des trois ne demande d'être développeur. Les trois demandent d'y avoir pensé.

Une **clé d'accès** (clé API), c'est un mot de passe qui permet à votre site de parler à un service : base de
données, paiement, IA, envoi d'emails.

## 1. Les clés d'accès

**Le risque.** Une clé posée dans le code part sur GitHub, et n'importe qui peut s'en servir à vos frais.
Des robots parcourent GitHub en permanence pour les trouver.

**Ce que vous faites.**
- Elles vivent dans un fichier `.env` sur votre ordinateur, et dans les réglages de l'hébergeur
  (Vercel : *Settings > Environment Variables*). Nulle part ailleurs.
- Le `.env` est déjà dans le `.gitignore` de ce repo : il ne part jamais sur GitHub.
- Une landing page statique (HTML et CSS) n'a en général **besoin d'aucune clé**. Si Claude en met une dans
  `index.html`, c'est une erreur : elle serait visible par tous les visiteurs.
- Une clé publiée par erreur : révoquez-la tout de suite dans le service concerné et créez-en une autre.
  La supprimer du code ne suffit pas, l'historique git la garde.

## 2. Les données personnelles

**Le risque.** Dès que votre formulaire collecte un nom et une adresse email, vous en devenez responsable
(LPD en Suisse, RGPD dans l'Union européenne).

**Ce que vous faites.**
- Ne collectez que ce dont vous avez besoin. Souvent : un prénom et un email, ou rien du tout (un lien vers
  votre agenda).
- Sachez dire **où c'est stocké** (quel outil, quel pays) et **qui y accède**.
- Ajoutez une phrase sous le formulaire : à quoi servent les données, et comment demander leur suppression.
- Pas de traceurs publicitaires sans bandeau de consentement.

## 3. La solidité

**Le risque.** Le code généré tient la démo. Il ne tient pas toujours la charge, les cas limites, ni les
tentatives d'abus.

**Ce que vous faites.**
- Pour une page vitrine et un lien d'agenda : ce que produisent les agents suffit, après le passage du testeur.
- **Avant de traiter des paiements, des comptes utilisateurs ou des données sensibles, faites relire par un
  développeur.** Pour un paiement, passez par un service établi (Stripe, Twint, Payrexx) plutôt que par du
  code maison.
