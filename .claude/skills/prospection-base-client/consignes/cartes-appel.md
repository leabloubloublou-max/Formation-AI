# Consigne : cartes d'appel (parties personnalisées des scripts d'appel)

Le script d'appel de chaque contact a un tronc commun, construit par `scripts_appel.py` depuis la section `[offre]`
de `campagne.toml` (ouverture avec demande de permission, présentation, raison de l'appel, question ouverte, CTA
avec deux créneaux). Tu écris ce qui change d'un contact à l'autre : la **carte d'appel**. Tu n'écris qu'à partir
des faits de la fiche et du contexte : aucune recherche web, aucune connaissance extérieure.

## Ce que tu reçois

- Le lot `appels/briefs/L<n>.json` (écrit par `fichier_appel.py briefs`) : une fiche par entreprise (activité,
  signaux datés, logiciels, tech, `pourquoi_maintenant`, `angle`, `relais`, `lieux_a_eviter`,
  `a_ne_jamais_evoquer`) et ses contacts (`contact_id`, prénom et nom à dire, titre, langue, `faits_personne`,
  `note_nom`, `deja_contacte`, et `absent_d_apollo` pour un contact importé qui n'est pas dans Apollo).
- Le contexte `appels/briefs/contexte.json` : l'offre (`description`, `argument_cle`, `preuves` avec leur `cas`,
  `ne_jamais_dire`), le persona (famille d'entrée, familles des relais), `langue_redaction`.

## Ce que tu écris, pour chaque contact du lot

| Clé | Obligatoire | Contenu |
|---|---|---|
| `contact_id` | oui | l'identifiant du contact, recopié tel quel de la fiche : id Apollo, ou id local « local-... » d'un contact absent d'Apollo ; jamais vide |
| `pourquoi_vous` | oui | 1 phrase, 15 à 30 mots, dite à la fin de la raison de l'appel : le fait de la fiche qui justifie d'appeler CETTE personne maintenant (signal daté, prise de poste, projet), relié à l'offre, au conditionnel |
| `relance` | oui | une question ouverte, si la réponse à la question du tronc est courte, liée à leur contexte |
| `routage` | oui | la phrase si le dirigeant renvoie vers quelqu'un : demander le bon profil par son rôle (familles des relais du persona) et nommer le relais de la fiche s'il est connu |
| `nom_a_utiliser` | non | prénom et nom à dire, si la fiche les a corrigés (`note_nom`) |
| `civilite` | non | « Madame » ou « Monsieur », seulement si le prénom ne laisse aucun doute ; sinon, ne pas mettre la clé (le script dit alors « Bonjour Prénom Nom ») |
| `preuve` | non | le `cas` de la preuve de l'offre qui correspond au cas de `pourquoi_vous` ; « aucune » si aucune ne correspond. Sans cette clé, le script cite la preuve de l'offre seulement s'il n'y en a qu'une |
| `objection_probable` | non | l'objection la plus probable pour ce contact et la réponse, en une ligne : « « On a déjà un outil » -> réponse » |
| `exemple_pour_eux` | non | un cas d'usage concret pour eux, au conditionnel, si la conversation s'ouvre |
| `a_savoir` | non | liste de notes courtes pour l'appelant seulement, jamais lues : signal négatif de `a_ne_jamais_evoquer`, contact déjà touché, nom corrigé, langue, lieu |

## Règles

1. Que des faits de la fiche et du contexte. Aucun chiffre qui n'y figure pas ; une information marquée « indice »,
   « à vérifier » ou « estimation » ne s'affirme jamais.
2. Adapter au poste (dirigeant : croissance, temps des équipes, transmission ; technique : documentation,
   savoir-faire ; finance : chiffrage, reporting ; qualité : traçabilité, audits ; informatique : intégration,
   sécurité des données ; production et achats : planification, stocks, fournisseurs ; ventes : devis, suivi
   client).
3. Une preuve ne se cite que pour son propre cas d'usage ; jamais d'autre chiffre que celui de sa phrase.
4. Lieu : rien de `lieux_a_eviter` ; ne jamais situer l'offre dans un autre pays que celui de l'entreprise.
5. Ce qui se dit (`pourquoi_vous`, `relance`, `routage`, `objection_probable`) ne contient jamais : un signal
   négatif (il va dans `a_savoir`), une phrase de `offre.ne_jamais_dire`, la relation du prospect avec l'un de nos
   clients, « Apollo » ou « notre base », un tiret cadratin ou demi-cadratin, un point d'exclamation.
6. Écrire dans `langue_redaction`, à l'oral, vouvoiement, mots simples, phrases faciles à traduire.
7. Deux contacts de la même entreprise : deux `pourquoi_vous` différents, chacun adapté à son poste.
8. Si tu rédiges aussi l'argument du fichier d'appel pour le même contact (`consignes/fichier-appel-redaction.md`),
   le fait de `pourquoi_vous` et celui de l'argument sont les mêmes.

## Exemple (fictif)

Offre de l'exemple de configuration (logiciel de planification de la maintenance, preuve `planification`) ;
Entreprise A, Prénom Nom, directeur des opérations, signal « ouverture d'un site à Sion (09.2026) » :

```json
{"contact_id": "c-0001", "civilite": "Monsieur",
 "pourquoi_vous": "Vous ouvrez un site à Sion cette année : la maintenance des deux sites pourrait se planifier au même endroit dès le départ.",
 "relance": "Avec le site de Sion, qui va planifier la maintenance des nouvelles machines ?",
 "routage": "Qui s'occupe de la maintenance au quotidien chez vous ? Je peux lui dire que je viens de votre part ?",
 "preuve": "planification",
 "objection_probable": "« On a déjà un tableur pour ça » -> « Justement, c'est souvent là que les arrêts imprévus se cachent : je vous montre en vingt minutes ? »",
 "a_savoir": ["Déjà contacté par email en 2025, sans réponse"]}
```

## Format de sortie (JSON strict, UTF-8)

Une liste de cartes, une par contact du lot, dans l'ordre du lot. Le chemin est donné par l'orchestrateur :
`appels/cartes/L<n>.json` (un fichier par agent et par lot, même numéro que le lot), ou `appels/cartes-appel.json`
si un seul agent écrit toutes les cartes. `scripts_appel.py` lit les deux et rattache chaque carte à son contact
par `contact_id` ; une carte sans `contact_id` est ignorée. Si les briefs sont redécoupés en lots, les cartes
`appels/cartes/L<n>.json` de la passe précédente sont rangées dans `appels/precedent/` : elles sont à refaire.

Écrire le fichier avec l'outil Write, puis vérifier :
`python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(len(d))" <fichier>`. Aucun autre fichier.
Le script signale ensuite les champs obligatoires manquants, les tirets, les signaux négatifs, les phrases
interdites, un lieu d'un autre pays, une preuve inconnue et un nom différent de celui d'Apollo.
