# Consigne de rédaction : fichier d'appel (secteur, description, taille, argument)

Tu reçois un lot de fiches d'entreprises (`appels/briefs/L<n>.json`, écrit par `fichier_appel.py briefs`), chacune
avec ses contacts à appeler, et le contexte de la campagne (`appels/briefs/contexte.json`). Pour chaque entreprise,
tu écris 3 champs courts ; pour chaque contact, l'argument n°1 que l'appelant placera au téléphone. Tu n'écris
**qu'à partir des faits de la fiche et du contexte** : aucune recherche web, aucune connaissance extérieure.

## Avant de commencer : le contexte

Lis `appels/briefs/contexte.json` :

- `offre` : qui nous sommes (`societe`, `description`), l'argument clé (`argument_cle`), les preuves (`preuves`,
  chacune avec son cas d'usage `cas` et sa `phrase`), ce qu'il ne faut jamais dire (`ne_jamais_dire`), les
  concurrents (`concurrents`) ;
- `persona` : la famille du contact d'entrée (le décideur) et celles des relais ;
- `langue_redaction` : la langue dans laquelle écrire (`fr`, `de`, `it`, `en`...).

## Champs à écrire

Par entreprise :

- `secteur` : 2 à 5 mots, le métier et le marché, sans forme juridique (« Usinage de précision pour le médical »,
  « Fabrication de machines d'emballage », « Électronique de mesure industrielle »).
- `description` : une phrase de 10 à 25 mots : ce qu'ils fabriquent ou font, pour qui. Faits de la fiche seulement.
- `taille` : 12 mots au plus, le meilleur effectif de `effectif_sources` avec une source courte : d'abord un chiffre
  publié par l'entreprise ou la presse, sinon la tranche LinkedIn, sinon Apollo (« environ 45 pers. à Sion (site,
  2025) », « 51-200 (LinkedIn), 80 selon Apollo »). Rien d'exploitable : « inconnue ».
- `pourquoi_maintenant` : seulement si celui de la fiche est vide. 1 ou 2 phrases tirées des signaux datés (le plus
  récent et le plus fort d'abord) ; sans signal daté : « Pas de signal daté : appel de découverte. » Sinon `null`.

Par contact :

- `argument` : ce que l'appelant dit pour donner envie de prendre rendez-vous. **1 ou 2 phrases, 20 à 45 mots**, à
  l'oral, vouvoiement, mots simples. Construction : [le fait le plus parlant pour CE contact : son signal, celui de
  son entreprise ou leur métier] + [ce que notre offre ferait concrètement pour lui, au conditionnel] + [la preuve du
  même cas d'usage, s'il y en a une].

## Règles de l'argument

1. Que des faits de la fiche (`signaux_dates`, `activite`, `faits_personne`, `logiciels`, `tech`) et du contexte.
   Aucun chiffre qui n'y figure pas. Une information marquée « indice », « à vérifier » ou « estimation » ne
   s'affirme jamais : elle sert au plus à poser une question.
2. Adapter au poste : dirigeant ou propriétaire (croissance, temps des équipes, savoir-faire qui repose sur quelques
   personnes, reprise ou transmission) ; technique ou R&D (documentation, savoir-faire, support) ; finance (chiffrage,
   reporting, logiciel de gestion) ; qualité (traçabilité, documentation, audits) ; informatique (intégration,
   sécurité des données) ; production, opérations ou achats (commandes, planification, stocks, fournisseurs) ;
   ventes (devis, offres, suivi client) ; service (interventions, support). Rattacher ce sujet au cas de l'offre qui
   le touche.
3. Lieu : `lieux_a_eviter` liste les mentions de lieu de notre offre qui ne valent pas pour cette entreprise (par
   exemple « en Suisse » ou « romand » pour une entreprise française) : ne jamais les écrire, reformuler sans lieu.
   Ne jamais situer l'offre dans un autre pays que celui de l'entreprise (`pays`).
4. Logiciels : si `logiciels` dit « confirmé » ou « probable », on peut le nommer (« branché sur votre logiciel
   X ») ; « indice » ou inconnu : ne jamais le nommer.
5. Preuves : une preuve ne se cite que pour son propre cas d'usage (`cas`). La citer pour un autre cas ferait croire
   que nous l'avons déjà fait. Sans preuve du même cas, pas de preuve. Jamais d'autre chiffre que celui de la phrase
   de la preuve, jamais un nom de client qu'elle ne donne pas.
6. Si `carte_existante` est remplie (script d'appel déjà rédigé), garder le même fait déclencheur que son
   `pourquoi_vous`, pour rester cohérent, mais en faire un seul argument.
7. Deux contacts de la même entreprise : deux arguments différents, chacun adapté à son poste.
8. Écrire dans `langue_redaction`, même pour un contact d'une autre langue (colonne `langue`), en phrases faciles à
   traduire.
9. Interdits : tiret cadratin et demi-cadratin ; tout ce qui figure dans `a_ne_jamais_evoquer` (difficultés,
   restructuration, licenciements, cyberattaque) ; tout ce que liste `offre.ne_jamais_dire` ; la relation d'un
   prospect avec l'un de nos clients ; « Apollo », « base de données », « on a analysé » ; un chiffre de notre
   société absent de l'offre ; les points d'exclamation ; « révolutionner », « disruptif ».

## Exemples du ton attendu (fictifs)

Offre de l'exemple de configuration : un logiciel qui planifie la maintenance préventive des machines, avec une
preuve « planification » (un sous-traitant de Neuchâtel, arrêts imprévus divisés par deux en six mois).

- Entreprise A, directeur des opérations, signal « ouverture d'un site à Sion (09.2026) » : « Vous ouvrez un site à
  Sion cette année : c'est souvent le moment où la maintenance se planifie encore à la main. On pourrait vous
  montrer comment la planifier pour les deux sites dès le départ. »
- Entreprise A, responsable maintenance, fait « Nouveau à ce poste (6 mois) » : « Vous avez repris la maintenance il
  y a six mois : on pourrait vous aider à faire baisser les arrêts imprévus, comme chez un sous-traitant de
  Neuchâtel où ils ont baissé de moitié en six mois. »

## Format de sortie (JSON strict, UTF-8)

Le chemin est donné par l'orchestrateur : `appels/redaction/L<n>.json`, même numéro que le lot. Une liste, une
entrée par entreprise du lot, dans le même ordre que le lot :

```json
[{"id": "...", "secteur": "...", "description": "...", "taille": "...", "pourquoi_maintenant": null,
  "contacts": [{"contact_id": "...", "argument": "..."}]}]
```

Tous les contacts du lot doivent y figurer, et seulement eux. `contact_id` est recopié tel quel du brief : id
Apollo, ou id local « local-... » d'un contact absent d'Apollo ; jamais vide. Le script ignore (et signale) une
entreprise ou un contact qui n'est pas dans le lot de même numéro, ou un `contact_id` vide. Écrire le fichier avec
l'outil Write, puis le relire avec
`python3 -c "import json,sys; json.load(open(sys.argv[1]))" <fichier>` pour vérifier que le JSON est valide.
Aucun autre fichier. Le script contrôle ensuite chaque argument (longueur au-delà de 60 mots, chiffre ou nom absent
de la fiche, lieu d'un autre pays, logiciel nommé sans confirmation, motifs interdits).
