# Étape 7 : réinjecter dans Apollo (score A, B, C, signal, source, première phrase)

## Objectif

Ce que l'enrichissement et le tri ont ajouté retourne dans Apollo, sur chaque contact, dans quatre champs
personnalisés. C'est « Réinjecter » dans la chaîne enseignée en formation : une seule base, à jour. Une séquence
peut alors ouvrir chaque email sur le signal du compte :
`Bonjour {{first_name}}, {{phrase_signal}} Je vous propose un échange de 20 minutes...`

| Champ de contact Apollo | Contenu | Type |
|---|---|---|
| `signal_et_date` | « Ouverture d'un site à Sion, septembre 2026 », ou « aucun signal trouvé » | texte long |
| `source_signal` | lien de la source consultée | texte long |
| `phrase_signal` | première phrase du message, rédigée seulement sur demande | texte long |
| `score_abc` | A, B ou C (section suivante) | texte |

## Le score A, B, C

La formation trie les comptes en trois paquets. Le script le calcule à partir des sorties de l'étape 5, sans rien
relancer :

- **A, on contacte** : tier A ou B, et au moins un signal positif de moins de 12 mois, de poids au moins 1, venu du
  registre ou d'une recherche par agent (les détections automatiques, bruitées, ne comptent pas). Ni signal négatif
  grave de moins de 12 mois, ni concurrent (une entreprise qui vend ce que nous vendons). Un départ (radiation,
  sortie du conseil) est un changement, pas une accroche : il ne suffit pas. Une arrivée suivie du départ de la même
  personne ne compte plus.
- **B, en veille** : le reste de la cible. La colonne `raison_abc` dit pourquoi (pas de signal récent, tier C ou D,
  signal négatif récent, concurrent).
- **C, retirée** : un motif d'exclusion de l'étape 5 (« Hors cible »).

Attention au vocabulaire : le **C du score est le « Hors cible »** des tiers, pas le tier C (encore dans la cible,
avec un fit plus faible). Dire « score A » ou « tier A », jamais une lettre seule. Le signal retenu pour un compte A
est le plus lourd de ses accroches, puis le plus récent, écrit « fait, mois année », avec son lien.

## Entrées

- `prospection-signaux.csv` et `donnees/signaux/signaux.json` ([étape 5](05-signaux-et-priorisation.md)) ;
  `donnees/signaux/recherche.json` s'il existe (champ `adoption_tech.concurrent`).
- Les contacts et leur id Apollo : `--contacts <csv>` (aussi un export de contacts fait depuis l'interface Apollo),
  sinon `apollo/contacts-crees.csv` ([étape 6](06-contacts-apollo.md)), sinon `apollo/contacts-importes.csv`
  ([étape 2](02-trouver-les-entreprises.md), export de contacts).
  Rattachement à l'entreprise par `entreprise_id`, sinon par le nom, sinon par le domaine du site.
- Facultatif : `--phrases <csv>`, les premières phrases (colonnes `id` ou `nom`, et `phrase_signal`).
- La date de référence des 12 mois : `[campagne] date_reference`, sinon aujourd'hui ; `--date AAAA-MM-JJ` pour une
  autre.

## Étapes

Depuis la racine du projet (adapter le chemin si le skill est installé ailleurs, par exemple dans
`~/.claude/skills/`).

1. **Aperçu** (aucun appel, aucune écriture externe) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom>
   ```

   Sorties : `base-abc.csv` (une ligne par entreprise), `apollo/reinjection.csv` (une ligne par contact),
   `phrases-a-rediger.csv` (les comptes A sans phrase). À l'écran : comptes A, B et C, contacts à réinjecter,
   contacts sans id Apollo, contacts dont l'entreprise n'est pas reconnue.
2. **Premières phrases, seulement sur demande explicite.** Une phrase par compte A, d'après son signal et sa source,
   selon [../consignes/phrases-signal.md](../consignes/phrases-signal.md) (dans la conversation, ou par un agent sur
   demande). Elle s'écrit dans `phrases-signal.csv`, dans le dossier de la campagne. Relire chaque phrase contre sa
   source, puis relancer l'aperçu :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> --phrases campagnes/<nom>/phrases-signal.csv
   ```

   Le script range les phrases dans `base-abc.csv` et liste, sans les reprendre, celles qui ont un tiret long ou
   demi-cadratin, plus de 30 mots ou un signal négatif. Détail de la rédaction :
   [09-scripts-et-fichier-d-appel.md](09-scripts-et-fichier-d-appel.md), section « Première phrase des comptes A ».
3. **Accord** : récapituler (contacts par score, champs à créer, trois ou quatre exemples de valeurs) et attendre le
   « go ».
4. **Test sur un contact** : la même commande, avec les mêmes options (`--phrases` compris), plus `--go --limite 1`.
   Ouvrir ce contact dans Apollo et lire les quatre champs.
5. **Passage complet** : la même commande avec `--go`. Le script crée au besoin les quatre champs de contact, puis
   met à jour les contacts par lots de 100. Il n'envoie jamais de valeur vide : une valeur saisie à la main dans
   Apollo n'est pas effacée. Ids des champs : `apollo/champs-apollo.json`.
6. **Dans la séquence** ([étape 8](08-sequence-et-ordre-d-appel.md)) : la variable `{{phrase_signal}}` en tête de l'email 1 (un champ de contact se
   cite par son nom) ; la vague de la semaine se filtre sur `score_abc` = A.

Toujours passer les mêmes options à l'aperçu et au `--go` : sans `--phrases`, la colonne `phrase_signal` est vide
et n'est donc pas envoyée.

## Les trois voies

| Voie | Quand | Comment |
|---|---|---|
| Script REST (`--go`) | au-delà d'une trentaine de contacts | étapes ci-dessus ; clé `APOLLO_API_KEY` du `.env` : clé master, ou droits `api/v1/typed_custom_fields/index`, `api/v1/fields/create` et `api/v1/contacts/bulk_update` |
| Import CSV dans l'interface | sans clé API | importer `apollo/reinjection.csv` et associer les quatre colonnes à des champs de contact. Apollo rapproche les contacts selon ses propres règles : essayer sur 2 ou 3 contacts avant l'import complet |
| Connecteur MCP Apollo | une trentaine de contacts, dans la conversation | ids des champs par la liste des champs (modalité `contact`), puis mise à jour contact par contact avec `typed_custom_fields` (clés = ids des champs), chaque action validée. Les champs doivent exister (interface ou script) |

## Sorties

- `base-abc.csv` : `rang, score_abc, raison_abc, tier, nom, signal_et_date, source_signal, phrase_signal,
  pourquoi_maintenant, site, id`, trié A, B, C puis par rang ;
- `phrases-a-rediger.csv` : `id, nom, signal_et_date, source_signal, phrase_signal` ;
- `apollo/reinjection.csv` : `contact_id, First Name, Last Name, Email, Company Name, ordre, entreprise_id,
  signal_et_date, source_signal, phrase_signal, score_abc` ;
- après `--go` : les quatre champs remplis dans Apollo, et `apollo/champs-apollo.json`.

`pourquoi_maintenant` reste interne : il n'est pas envoyé dans Apollo.

## Contrôles qualité

- Ouvrir la source de 5 comptes A : le signal y figure, à la bonne date, pour la bonne entreprise.
- Relire toutes les premières phrases avant l'accord : elles partiront chez les prospects.
- Après `--go`, compter dans Apollo les contacts filtrés sur `score_abc`, quelques secondes plus tard (index mis à
  jour en différé).

## Coûts et validations

- 0 crédit : création de champs et mise à jour de contacts. Un appel par lot de 100 contacts.
- Accord explicite avant `--go` (écriture externe), et avant toute rédaction de phrases.
- L'écriture a été testée contre une API simulée (champs manquants créés, champ de compte homonyme ignoré, lots de
  100, reprise sur 429, refus 403 expliqué) : faire toujours le test sur un contact avant le passage complet.

## Veille

Les signaux vieillissent. Après chaque veille de l'étape 5 et avant chaque vague de contact : relancer l'aperçu
(avec `--phrases campagnes/<nom>/phrases-signal.csv` dès que ce fichier existe), comparer `base-abc.csv` à la
version précédente (comptes passés de B à A), puis, sur accord, `--go` avec les mêmes options. Programmer cette
veille chaque semaine n'a de sens qu'une fois la chaîne rodée à la main, et seulement sur accord (tâche programmée
sur le poste qui a le `.venv` et les caches).

## Pièges

Champ de compte homonyme d'un champ de contact ; valeur vide qui effacerait une saisie manuelle ; mise à jour
asynchrone au-delà de 100 contacts ; import CSV qui crée des doublons ; contact sans id (« non créé » à l'étape 6),
jamais réinjecté. Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 7 ».

## Adapter à une autre campagne

Rien à copier : le script est générique. `--contacts` si les contacts viennent d'un export, `--date` pour figer la
fenêtre des 12 mois.
