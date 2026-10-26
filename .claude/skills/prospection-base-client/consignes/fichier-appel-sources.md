# Consigne : ouvrir chaque argument sur sa source (« J'ai vu sur ... que ... »)

L'appelant a déjà un argument par contact (`argument_actuel`, rédigé avec `consignes/fichier-appel-redaction.md`).
Il doit maintenant dire d'où vient l'information, « j'ai vu que ... » : l'appel devient crédible et montre qu'on
s'est renseigné. Tu réécris chaque argument et tu indiques le fait utilisé (`source_id`) ; le script posera lui-même
le lien et la date à partir de cet id. Aucune recherche web, aucune connaissance extérieure.

## Ce que tu reçois

Le lot `appels/sources/briefs/L<n>.json` (écrit par `fichier_appel.py sources`) et le contexte
`appels/briefs/contexte.json` (offre, preuves, langue de rédaction). Par entreprise : `faits_entreprise`, une liste
de faits numérotés (`S1`, `S2`... signaux datés ; `A` activité ; `L` page LinkedIn ; `E` logiciel utilisé,
confirmé ou probable ; `T1`... indices tech), chacun avec `date`, `fait`, `source` et `url` ; `lieux_a_eviter`,
`logiciels`, `a_ne_jamais_evoquer`. Par contact : `argument_actuel` et `faits_personne` (`P1`, `P2`...).

## Ce que tu écris, pour chaque contact

- `argument` : 1 ou 2 phrases, **25 à 50 mots**, à l'oral, vouvoiement, qui **commencent par « J'ai vu »** (ou
  « J'ai lu » pour un article) suivi de la source dite simplement, puis de « que » et du fait :
  - registre du commerce : « J'ai vu au registre du commerce que ... » (changements de direction, de conseil,
    de capital, de siège) ;
  - page LinkedIn de l'entreprise : « J'ai vu sur votre page LinkedIn que ... » ;
  - profil LinkedIn du contact : « J'ai vu sur votre profil LinkedIn que ... » (poste, ancienneté, parcours
    professionnel seulement : jamais d'activité personnelle ou de loisir) ;
  - site de l'entreprise : « J'ai vu sur votre site que ... » ;
  - offre d'emploi : « J'ai vu dans votre offre d'emploi sur <site> que ... » (le site est donné par la source) ;
  - article : « J'ai lu dans <média> que ... », le média étant reconnaissable par son domaine
    (journal-exemple.ch : « le Journal Exemple ») ; si le domaine ne dit rien, « J'ai lu dans la presse que ... ».
  Ensuite, garder l'essentiel de `argument_actuel` : ce que notre offre ferait pour lui et, s'il y en a une, la
  preuve du même cas d'usage.
- `source_id` : l'id du fait annoncé par « J'ai vu ». Il doit vraiment contenir ce que dit la phrase.

## Règles

1. Choisir de préférence le fait déjà utilisé par `argument_actuel`, s'il a un id. Sinon, le fait daté le plus
   récent et le plus parlant pour ce contact. Préférer un fait avec `url` ; un `T` seulement à défaut.
2. Rester fidèle au fait : ne pas le grossir, ne pas changer sa date. Aucun chiffre qui n'est pas dans la fiche ou
   dans la phrase d'une preuve.
3. Toutes les règles de la rédaction restent valables : rien de `lieux_a_eviter`, jamais l'offre située dans un
   autre pays que celui de l'entreprise ; une preuve seulement pour son propre cas d'usage, sans autre chiffre ;
   rien de `a_ne_jamais_evoquer` ni de `offre.ne_jamais_dire` ; un logiciel n'est nommé que si `logiciels` dit
   « confirmé » ou « probable » ; aucun tiret cadratin ni demi-cadratin ; pas de point d'exclamation.
4. Deux contacts de la même entreprise : si possible deux sources différentes.
5. Jamais « Apollo », « base de données » ou « on a analysé » : seulement la source publique.
6. Écrire dans la langue de rédaction (`langue_redaction` du contexte).

## Exemple (fictif)

- Avant : « Vous ouvrez un site à Sion cette année : on pourrait vous montrer comment planifier la maintenance des
  deux sites dès le départ, comme chez un sous-traitant de Neuchâtel. »
- Après : « J'ai vu sur votre page LinkedIn que vous ouvrez un site à Sion cette année : on pourrait vous montrer
  comment planifier la maintenance des deux sites dès le départ, comme chez un sous-traitant de Neuchâtel. »
  (`source_id` : le fait `S` qui annonce ce site)

## Format de sortie (JSON strict, UTF-8)

Le chemin est donné par l'orchestrateur : `appels/sources/redaction/L<n>.json`, même numéro que le lot. Une liste
plate, un objet par contact du lot, dans l'ordre du lot :

```json
[{"contact_id": "...", "argument": "J'ai vu ...", "source_id": "S1"}]
```

`contact_id` est recopié tel quel du lot (id Apollo, ou id local « local-... » d'un contact absent d'Apollo ;
jamais vide). Une réponse pour un contact qui n'est pas dans le lot de même numéro est ignorée et signalée.

Écrire le fichier avec l'outil Write, puis vérifier :
`python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(len(d))" <fichier>`. Aucun autre fichier.
Le script refuse un `source_id` inconnu (colonne « Source de l'argument » vide et alerte) et signale un argument
qui ne s'ouvre pas sur « J'ai vu », « J'ai lu », « J'ai remarqué » ou « J'ai noté ».
