# Étape 6 : contacts Apollo (comptes, personas, recherche, enrichissement, listes)

## Objectif

Pour chaque entreprise des tiers A à D ([étape 5](05-signaux-et-priorisation.md)), retrouver dans Apollo les
personnes à contacter : celles que la recherche a nommées (`persona_cible` et `cibles` de l'étape 5) et les rôles
du persona (`[persona]` de `campagne.toml`, [étape 1](01-identifier-la-cible.md)). Compléter par le web ce qu'Apollo n'a pas. Faire valider la sélection.
Enrichir les emails : c'est la seule partie payante. Créer enfin les contacts dans trois listes Apollo :

- la liste globale, au nom de `[apollo] liste_contacts` (« Segment · Persona · Mois ») ;
- « <nom> - entrée » : le décideur, contacté en premier ;
- « <nom> - relais » : les profils opérationnels vers qui le décideur renvoie (qualité, IT, production...).

Dans la chaîne enseignée en formation, c'est « Extraire » : une liste de comptes et de contacts.

## Choisir la méthode

| Situation | Méthode |
|---|---|
| Mêmes profils dans toutes les entreprises | L'utilisateur le fait dans l'interface Apollo en 15 minutes : filtre sur la liste de comptes, intitulés FR, DE, EN, séniorité, lieu, puis « Enrich ». |
| Une trentaine de comptes | Connecteur MCP Apollo dans la conversation, chaque action validée. Compter environ 8 000 tokens par recherche de personnes. |
| Profils différents d'une entreprise à l'autre, au-delà d'une trentaine de comptes | Les scripts de cette fiche (API REST, presque aucun token). |
| Claude dans Chrome | Déconseillé : captures d'écran coûteuses, plusieurs minutes par entreprise, fenêtres fragiles, un clic peut consommer des crédits. |

## Prérequis

- **`prospection-signaux.csv`** (étape 5). Colonnes lues : `tier`, `rang`, `id`, `nom`, `pays`, `canton`,
  `site`, `linkedin`, `persona_cible`, `dirigeants`, `pourquoi_maintenant`. Facultatif :
  `donnees/signaux/recherche.json`, dont le champ `cibles` (`entree` et `relais`, listes de `{nom, role}`) est lu
  en priorité.
- **`campagne.toml`** :
  - `[apollo]` : `liste_comptes`, `liste_contacts`, `pays_contacts` (pays où un contact peut être basé ; vide :
    `[cible] pays` et `pays_voisins`), `mobiles` ;
  - `[persona]` : `entree`, `relais`, et `[persona.titres]` pour ajouter des intitulés ou une famille ;
  - `[signaux] logiciels` : ces mots ne sont jamais pris pour des noms de personne.
- **La clé `APOLLO_API_KEY`**, dans un fichier `.env` à la racine du projet (modèle : `exemple.env` du skill ;
  création de la clé : README.md, « Clé API Apollo »). Clé master, ou clé avec ces points d'accès :
  `mixed_people/api_search`, `people/bulk_match`, `webhook_result` (mobiles), `contacts` (création, recherche),
  `labels` (listes), `accounts` (recherche, création). Ne jamais afficher la clé. Vérifier seulement sa présence :
  `grep -c '^APOLLO_API_KEY=.' .env` (doit afficher 1) et `git check-ignore -q .env && echo ".env ignoré par git"`.
- **Les quotas du compte.** `apollo_api.py` reste à 80 % de plafonds courants (constante `LIMITES` : recherche de
  personnes 200 par minute et 6 000 par heure, enrichissement 1 000 par minute, contacts et comptes 200 par minute
  et 400 par heure). Baisser `LIMITES` si le plan Apollo du compte est plus petit.
- **La documentation Apollo**, lue en Markdown à moindre coût :
  `curl -s -L https://docs.apollo.io/reference/<page>.md` (index : `https://docs.apollo.io/llms.txt`). Pages
  utiles : people-api-search, bulk-people-enrichment, poll-webhook-result, bulk-create-contacts,
  bulk-create-accounts, get-a-list-of-all-lists, add-records-to-a-list, remove-records-from-a-list,
  search-for-contacts, view-credit-usage-stats.

## L'ordre exact

Toutes les commandes se lancent depuis la racine du projet, celle qui contient `.venv`. Si le skill est installé
ailleurs (par exemple `~/.claude/skills/prospection-base-client`), adapter le chemin du script.

0. **Liste de comptes Apollo** (le périmètre de la recherche ; 0 crédit). Aperçu, sans appel ni clé :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/creer_comptes.py --campagne campagnes/<nom>
   ```

   Il écrit `apollo/comptes-a-importer.csv` (tiers A à D ; `--tiers A,B` pour réduire). Deux façons de créer la
   liste, au choix de l'utilisateur :
   - à la main : il trie le fichier dans Excel, puis l'importe dans Apollo comme liste de comptes, sous le nom
     exact de `[apollo] liste_comptes` ;
   - par l'API, **après son accord** (écriture externe) : la même commande avec `--go`. Les comptes sont créés par
     lots de 100 (un compte déjà présent est repris tel quel), puis tous ajoutés à la liste.

   Deux entreprises du même domaine ne donnent qu'un compte. Apollo met la liste à jour en différé : attendre
   quelques secondes avant le point 2.
1. **Structurer les personas** (0 appel, sans LLM) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/extraire_personas.py --campagne campagnes/<nom>
   ```

   Sorties : `apollo/cibles.json` et `apollo/cibles-apercu.csv` (une ligne par cible). **Relire l'aperçu** : faux
   noms, rôles en trop ou manquants, entreprises au persona par défaut, entreprises marquées hors cible.
2. **Tester la recherche sur quelques entreprises** (0 crédit) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom> --entreprises "mot1,mot2"
   ```

   Les mots sont des morceaux de noms d'entreprises. Sorties : `apollo/contacts-a-valider-test.csv` et
   `apollo/couverture-test.csv`. Contrôler à la main les rapprochements : compte, personne, intitulé.
3. **Recherche complète** (0 crédit ; relance gratuite depuis le cache) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_contacts.py --campagne campagnes/<nom>
   ```

   Sorties : `apollo/contacts-a-valider.csv`, `apollo/couverture.csv`, `apollo/comptes-apollo.json`. Une entreprise
   dont le compte Apollo porte un autre nom : l'écrire dans `apollo/comptes-manuels.csv` (colonnes `entreprise`,
   `compte_apollo`), puis relancer. `--liste-comptes "<nom>"` remplace `[apollo] liste_comptes`.
4. **Relire les rôles retenus**, intitulé par intitulé. Un intitulé mal rangé : ajouter l'intitulé juste dans
   `[persona.titres]` (familles fournies : direction, qualite, it, production, technique, service, ventes,
   finance, achats, projet ; on peut en créer une, par exemple maintenance). Relancer le point 3 : seules les
   requêtes nouvelles partent.
5. **Mesurer les trous** avec `couverture.csv`, et répondre à la question qui revient toujours (« combien de
   contacts par rapport à la base ? ») : cibles de départ (personnes nommées et rôles), cibles trouvées,
   pourcentages, répartition par tier, entreprises sans compte ou sans personne dans Apollo.
6. **Compléter par le web** (0 crédit, DuckDuckGo) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/chercher_web.py --campagne campagnes/<nom>
   ```

   Il cherche les personnes nommées absentes d'Apollo ou placées ailleurs, les dirigeants du registre des
   entreprises sans contact d'entrée, et les rôles manquants sur LinkedIn. Sortie : `apollo/trouves-web.json`.
   Compter 3 à 4 secondes par requête : au-delà de 600 secondes, lancer la commande en arrière-plan et attendre la
   notification de fin.
7. **Réintégrer** : relancer `chercher_contacts.py` (même commande qu'au point 3). Il cherche dans Apollo chaque
   personne trouvée sur le web, et garde sinon son URL LinkedIn. Ordre à suivre une seule fois : recherche, web,
   recherche.
8. **Faire valider** `apollo/contacts-a-valider.csv`. La colonne `garder` décide (`oui`, `o`, `x`, `1`, `yes`, `y`,
   `true`). L'utilisateur peut l'éditer dans Excel ou Google Sheets et renvoyer l'export (virgule ou point-virgule,
   BOM accepté). Signaler les personnes sans email connu (`email_dispo` = `non`) : Apollo facture 1 crédit dès
   qu'il renvoie des données, même sans email. Les décocher si la campagne passe seulement par email.
9. **Aperçu des crédits** (aucun appel, la clé n'est pas lue) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom>
   ```

   Un autre fichier de revue se passe en argument (`... enrichir_et_creer.py --campagne campagnes/<nom>
   revue.csv`). Le script affiche le nombre de personnes, le **plafond de crédits** et les pays acceptés. Annoncer
   ce plafond et **attendre l'accord explicite**. Mobiles : `--mobiles non`, `entree` ou `tous` (défaut :
   `[apollo] mobiles`, `true` valant `tous`), 8 crédits par numéro. Les décider maintenant, sur accord chiffré :
   demandés après coup, ils coûtent jusqu'à 9 crédits par personne.
10. **Test sur 10**, après l'accord :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/enrichir_et_creer.py --campagne campagnes/<nom> --limite 10 --go
    ```

    Exactement 10 : c'est le premier lot du passage complet, relu ensuite depuis le cache sans nouvelle facture.
    Relire le résultat (pays, employeur, email) dans `apollo/contacts-crees.csv`.
11. **Passage complet** : la même commande sans `--limite` (et avec les mêmes options, `--mobiles` compris).
    `--liste "<nom>"` remplace `[apollo] liste_contacts`. Le script crée au besoin les trois listes. Ne plus toucher
    à `garder` après un `--go` : les lots de 10 se décaleraient et seraient refacturés.
12. **Exporter les listes** (0 crédit ; à relancer après toute modification des listes dans Apollo) :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/exporter_listes.py --campagne campagnes/<nom>
    ```

    Un CSV par liste dans `apollo/listes/` (contacts lus dans Apollo, qui fait foi, complétés par nos colonnes).
    `--prefixe "<nom>"` pour d'autres listes que celles de `[apollo] liste_contacts`.
13. **Bilan chiffré, compté par script** : listes et nombre de contacts, emails par statut, entreprises sans
    contact, personnes écartées (pays, introuvables), crédits réellement consommés. L'affichage du script additionne
    aussi les réponses relues du cache : recompter depuis le cache,

    ```bash
    .venv/bin/python -c "import json, glob; r = [json.load(open(f)) for f in glob.glob('campagnes/<nom>/apollo/cache/*.json') if not f.endswith('web.json')]; print(sum(d.get('credits_consumed') or 0 for d in r if isinstance(d, dict)))"
    ```

    ou dans Apollo (statistiques d'usage, 0 crédit). Signaler toute règle ajoutée sans demande, et noter les
    enseignements datés dans `<campagne>/apprentissages.md`.
14. **Suite** : réinjecter signal, source, première phrase et score dans ces contacts
    ([07-reinjecter-dans-apollo.md](07-reinjecter-dans-apollo.md)), puis l'ordre d'appel et la séquence
    ([08-sequence-et-ordre-d-appel.md](08-sequence-et-ordre-d-appel.md)).

## Ce que font les scripts (pour relire et corriger)

- **`creer_comptes.py`** : une ligne par entreprise des tiers demandés, en-têtes des exports Apollo (`Company Name`,
  `Website`, `Company Linkedin Url`). Avec `--go` : `accounts/bulk_create` par 100 (dédoublonnage Apollo), puis
  ajout explicite de tous les comptes, créés et déjà présents, à la liste (modalité `accounts`). `account_id` et
  `statut` sont reportés dans le CSV.
- **`extraire_personas.py`** : d'abord les `cibles` structurées de `recherche.json` ; sinon le texte
  `persona_cible`, au format « Entrée : Prénom Nom (CEO) ; relais : responsable qualité, responsable IT ». Le texte
  avant « relais », « puis » ou « routage » donne l'entrée, la suite le relais. Personnes nommées : motif « Prénom
  Nom (rôle) », sauf les mots qui annoncent un rôle ou un sigle (`PAS_UN_NOM`, logiciels de la config). Rôles : le
  reste du texte découpé, sans les incises de cas d'usage (« pour... ») ni les mentions négatives (« est
  probablement piloté par le groupe », « vérifier »...), puis rangé en familles (`persona.py`). Rien de reconnu :
  la famille d'entrée de `[persona]`, puis ses relais.
- **`chercher_contacts.py`** :
  - rapprochement des entreprises et des comptes de la liste : domaine, puis `comptes-manuels.csv`, puis noms ;
  - vivier de chaque compte : les personnes de l'organisation Apollo (100 par page, 5 pages au plus), élargi par
    domaine et pays, en ne gardant que les employeurs actuels au nom proche (la recherche par domaine ramène aussi
    les anciens salariés) ;
  - personnes nommées : prénom et nom masqué (« Du***t » : début et fin du nom), puis recherche par nom, avec
    variantes (sans accents, nom de famille seul dans l'entreprise, ordre inversé, prénom composé, surnom ou
    initiale seulement dans l'entreprise) ; doublons Apollo : le profil avec email, puis le plus récent ;
  - personne nommée absente : repli sur le meilleur profil de son rôle, gardé s'il est au moins manager ;
  - rôles : intitulés de la famille (FR, DE, EN, IT), le plus senior d'abord (5 dirigeant, 4 directeur ou
    responsable, 3 manager, 2 spécialiste, 1 autre, 0 junior ; poste régional d'un autre pays : 2 crans de
    moins), gardé à partir de 2, un second proposé en « alternative » ; grandes organisations sans candidat :
    recherche ciblée par intitulés (`titres_api` de `persona.py`) ;
  - aucun contact d'entrée retenu : les dirigeants de la colonne `dirigeants` (registre) ;
  - résultats web : cherchés dans Apollo, sinon gardés avec leur URL LinkedIn.
- **`chercher_web.py`** : requêtes `"Prénom Nom" entreprise` puis `"Prénom Nom" linkedin` ; pour un rôle,
  `site:linkedin.com/in "entreprise" mot-clé` dans la langue de l'entreprise (en Suisse, celle du canton) puis en
  anglais, région DuckDuckGo assortie, pause de 1,2 s. Statuts : confirmé (profil LinkedIn au nom de la personne qui
  cite l'entreprise), ailleurs, cité, introuvable, rôle trouvé. Les résultats d'un passage précédent qui ne sont pas
  recherchés de nouveau sont gardés.
- **`enrichir_et_creer.py`** : dédoublonnage (id Apollo, sinon LinkedIn, sinon prénom, nom et entreprise ; l'entrée
  l'emporte) ; `people/bulk_match` par 10, jamais d'email personnel ; contrôle de l'id ou du prénom renvoyé ; email
  d'une personne trouvée sur le web gardé seulement si Apollo la place chez l'entreprise ; personne basée hors des
  pays acceptés non créée, sauf un vrai dirigeant de l'entreprise (famille direction, séniorité 5, ni poste régional
  ni filiale d'un autre pays) ; `contacts/bulk_create` par 100, rattaché au compte de la liste ; ajout explicite aux
  listes des contacts créés **et** déjà présents (sans toucher à leurs autres listes) ; comptage final par
  `contacts/search`. Les lignes d'un passage précédent dont le contact n'est pas repris restent dans
  `contacts-crees.csv`.
- **`exporter_listes.py`** : chaque liste de contacts dont le nom commence par le préfixe ; téléphones séparés en
  standard, ligne directe et mobile ; colonnes locales (tier, entreprise, entreprise_id, ordre, cibles, historique)
  reprises de `contacts-crees.csv` et `contacts-importes.csv`.

Niveaux de confiance de la colonne `confiance` de `contacts-a-valider.csv` :

| Confiance | Sens | `garder` par défaut |
|---|---|---|
| nom : sûr | personne nommée trouvée dans l'entreprise | oui |
| nom : employeur lié | trouvée sous un employeur cité dans la fiche (maison mère, nouveau nom) | oui |
| nom : autre employeur | homonyme ou départ | vide |
| nom : dirigeant inscrit | dirigeant du registre trouvé dans Apollo | oui |
| rôle : dirigeant, responsable, manager, spécialiste | meilleur intitulé pour le rôle (dans `cibles` : « repli pour X » si X manquait) | oui (manager au moins pour un repli) |
| rôle : junior/autre, rôle : poste régional, alternative | deuxième choix ou profil douteux | vide |
| repli | direction sans candidat : le profil le plus haut placé | vide |
| web + Apollo | trouvé sur le web, puis dans Apollo chez l'employeur | oui si profil LinkedIn confirmé ou cité sur le site de l'entreprise, sinon vide |
| web : profil LinkedIn, web : site de l'entreprise (hors Apollo) | confirmé par son LinkedIn ou par le site | oui |
| web : rôle LinkedIn, web : cité ailleurs (à vérifier) | preuve faible | vide |

## Sorties

Toutes dans `<campagne>/apollo/` (colonnes détaillées : [../reference/contrat.md](../reference/contrat.md)) :

- `comptes-a-importer.csv` ; avec `--go`, les comptes et la liste de comptes dans Apollo ;
- `cibles.json`, `cibles-apercu.csv` ;
- `contacts-a-valider.csv` (fichier de revue, colonne `garder`), `couverture.csv` (une ligne par entreprise),
  `comptes-apollo.json` (comptes de la liste, tels qu'Apollo les renvoie) ;
- `trouves-web.json` ;
- `contacts-crees.csv` (colonnes du contrat des contacts, plus `site_entreprise`). Statuts : créé ; créé sans email ;
  créé (dirigeant basé à l'étranger) ; déjà dans Apollo, ajouté aux listes ; non créé (basé à l'étranger) ; non
  enrichi (introuvable) ;
- trois listes de contacts dans Apollo, et leurs exports `listes/<nom-de-la-liste>.csv` ;
- `cache/` : réponses brutes d'Apollo (données personnelles, à ne pas partager ni commiter).

## Contrôles qualité

- Relire `cibles-apercu.csv`, puis chaque rapprochement rôle et intitulé (comparer avant et après une correction de
  `[persona.titres]`).
- Vérifier la colonne `compte_apollo` de `couverture.csv` et les messages « sans compte Apollo ».
- Lire le test sur 10 avant le passage complet : pays, employeur, email.
- Recompter les listes par `contacts/search` (le script le fait) quelques secondes plus tard, jamais par le compteur
  affiché dans Apollo.

## Coûts en crédits

| Action | Script | Crédits Apollo |
|---|---|---|
| Liste de comptes (création des comptes, ajout à la liste) | `creer_comptes.py --go` | 0 |
| Recherche de personnes | `chercher_contacts.py` | 0 (environ 2,5 appels par entreprise) |
| Recherche web | `chercher_web.py` | 0 (DuckDuckGo) |
| Enrichissement | `enrichir_et_creer.py --go` | 1 par personne trouvée, même sans email ; 0 si non trouvée |
| Mobile | `--mobiles entree` ou `tous` | 8 de plus par numéro trouvé ; jusqu'à 9 par personne si demandé après coup |
| Email personnel | jamais demandé | (payant) |
| Options waterfall (`run_waterfall_email`, `run_waterfall_phone`) | jamais activées | facturées par certains fournisseurs même sans résultat : seulement sur accord chiffré au pire cas |
| Création des contacts, listes, comptage, export | `enrichir_et_creer.py --go`, `exporter_listes.py` | 0 |

Repère pour annoncer un ordre de grandeur : environ 2 crédits par entreprise retenue (un peu moins de 2 contacts
gardés par entreprise, près de 3 pour les comptes les mieux classés). Le plafond affiché par l'aperçu est le nombre
de lignes gardées ; le réel est un peu en dessous (personnes introuvables). Autres ratios :
[../reference/couts.md](../reference/couts.md).

## Accords

- Sans demander : tout ce qui est gratuit et en lecture (recherche Apollo, recherche web, export des listes).
- Accord explicite avant : `creer_comptes.py --go` ; `enrichir_et_creer.py --go` (après relecture de `garder` et
  l'aperçu chiffré) ; toute demande de mobiles ; toute création ou modification faite à la main dans Apollo.
- Aucun message rédigé à cette étape.

## Pièges principaux

Anciens salariés ramenés par la recherche par domaine ; nom de famille masqué ; homonymes et départs ; doublons
Apollo ; personnel des filiales d'autres pays ; `PATCH` d'un contact qui écrase ses listes ; dédoublonnage qui
n'ajoute pas les contacts existants aux listes ; compteurs mis à jour en différé ; cache lié à la composition des
lots de 10 ; affichage des crédits trompeur. Détail et parades : [../reference/pieges.md](../reference/pieges.md),
section « Étape 6 ».

## Adapter à une autre campagne

Rien à copier ni à modifier dans les scripts : tout passe par `campagne.toml` et par des fichiers facultatifs de la
campagne.

- `[persona]` et `[persona.titres]` : familles d'entrée et de relais, intitulés en plus.
- `[apollo]` : noms des listes, `pays_contacts`, `mobiles`.
- `apollo/comptes-manuels.csv` : comptes Apollo qui portent un autre nom que l'entreprise.
- Hors d'Europe seulement : compléter `PAYS_APOLLO` (`apollo_api.py`, noms de pays attendus par Apollo) et
  `REGIONS` (`chercher_contacts.py`, zones citées dans les intitulés).
- Un plan Apollo aux quotas plus petits : baisser `LIMITES` (`apollo_api.py`).
