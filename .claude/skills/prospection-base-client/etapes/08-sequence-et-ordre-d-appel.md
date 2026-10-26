# Étape 8 : séquence et ordre d'appel

## Objectif

Décider qui contacter, quand et par quel canal, en suivant la cadence enseignée en formation (« Prospecter ») :

- **l'ordre d'appel** d'une liste (entrée, puis relais) pour le phoning : `ordre_appel.py` ;
- **le plan de séquence**, une ligne par contact : vague, jours J1 à J22, voix, canal, condition :
  `plan_sequence.py` ;
- puis, **seulement sur accord**, la création des séquences et l'inscription des contacts dans Apollo.

Les deux scripts sont déterministes : aucun appel réseau, aucun crédit, quelques secondes.

## Règles avant de commencer

- **Aucune rédaction sans demande explicite** : emails, scripts d'appel, messages LinkedIn.
- **Inscrire en séquence envoie de vrais emails**, depuis la vraie boîte de l'utilisateur. Séquence créée
  inactive, récapitulatif (expéditeur, séquence, nombre de contacts, statut), accord, inscription ; activation
  seulement après un second accord.
- **Rafraîchir les signaux avant chaque vague** (ils perdent du poids avec l'âge) : `collect_zefix.py --refresh`
  (Suisse), `collect_linkedin.py --retry`, `collect_news.py --refresh`, puis `scorer.py`
  ([étape 5](05-signaux-et-priorisation.md)), puis l'aperçu de `reinjecter_apollo.py` (avec
  `--phrases campagnes/<nom>/phrases-signal.csv` dès que ce fichier existe : sans l'option, `base-abc.csv` perd les
  premières phrases) et, sur accord, son `--go` avec les mêmes options ([étape 7](07-reinjecter-dans-apollo.md)).
  Lire la section Alertes de `rapport-signaux.md`.
- **Ne jamais exploiter un signal négatif** (faillite, cyberattaque, licenciements) : il sert à l'appelant, jamais
  au prospect.
- **Une personne qui refuse sort tout de suite de toutes les campagnes** : arrêt de chacune de ses séquences et une
  note dans Apollo.
- **Aucune donnée d'un de nos clients** dans un message, et un client n'est cité comme référence qu'avec son accord
  (`[offre] preuves`, `ne_jamais_dire`).
- **Cadre légal** : prospection par email en Suisse (LCD, art. 3 al. 1 let. o), mention de l'annuaire qui refuse la
  publicité pour l'appel, nLPD, RGPD pour des contacts dans l'Union européenne, consentement avant d'enregistrer un
  appel. À faire valider par l'utilisateur ; ne rien affirmer au-delà.

## Entrées

- `base-abc.csv` (étape 7, aperçu de `reinjecter_apollo.py`) : obligatoire pour le plan de séquence.
- Les contacts, `--contacts` pour un autre fichier :
  - `ordre_appel.py` : l'export de la liste « <liste_contacts> - entrée » (ou « - relais ») fait par
    `exporter_listes.py` dans `apollo/listes/`, sinon `apollo/contacts-crees.csv`, sinon
    `apollo/contacts-importes.csv` ;
  - `plan_sequence.py` : `apollo/contacts-crees.csv`, sinon `apollo/contacts-importes.csv` (il ne lit pas l'export
    de liste) ; les téléphones, l'historique et les refus viennent de `appels/ordre-appel.csv` et
    `appels/ordre-appel-relais.csv`.
- `prospection-signaux.csv` (tier, rang, pays, canton, fenêtre d'opportunité, pourquoi maintenant, angle).
- `campagne.toml` : `[appels] langues` (langues parlées par l'appelant), `[apollo] liste_contacts`,
  `[campagne] date_reference`.
- Facultatifs : l'export de la même liste fait depuis l'interface Apollo (`--export` : téléphones révélés, étape,
  dernier contact, emails envoyés, ouverts, rebondis, réponses) ; `apollo/comptes-apollo.json` (standard du compte) ;
  `appels/langue-contacts.json` (avis d'agents sur la langue, voir plus bas).

## A. L'ordre d'appel (phoning)

Depuis la racine du projet (adapter le chemin si le skill est installé ailleurs, par exemple dans
`~/.claude/skills/`) :

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/ordre_appel.py --campagne campagnes/<nom>
.venv/bin/python .claude/skills/prospection-base-client/scripts/ordre_appel.py --campagne campagnes/<nom> --liste relais
```

Avec l'export de l'interface (recommandé : c'est là que sont les mobiles révélés et l'historique) :
`... ordre_appel.py --campagne campagnes/<nom> --export campagnes/<nom>/apollo/listes/<export-interface>.csv`.

Sorties : `appels/ordre-appel.csv` (entrée) et `appels/ordre-appel-relais.csv`. Tri, dans cet ordre :

1. en fin de liste, **seulement** les personnes qui ont répondu et décliné (étape Apollo « Not Interested » avec
   une réponse) ; un contact déjà touché sans réponse garde son rang, son historique est noté (`deja_contacte`) ;
2. la langue : d'abord les personnes qui parlent probablement une langue de l'appelant. Score d'indices : commune
   de la personne (répertoire des localités suisses du skill), sinon son canton ; lieu de l'entreprise ; langue de
   l'intitulé ; indicatif du mobile. Classes : parle la langue, probablement, incertain, autre langue ;
3. le téléphone déjà connu : mobile ou ligne directe, puis standard, puis aucun ;
4. le tier, puis le rang de l'entreprise.

`appels/langue-contacts.json`, s'il existe, remplace le classement automatique de la langue :
`{contact_id: {parle: oui | probable | incertain | peu probable | non, langue_principale, raison}}`. On peut le faire
écrire par quelques agents indépendants, arbitrés sur le web en cas de désaccord, mais **seulement sur demande
explicite** (agents multiples). Sans lui, les indices automatiques suffisent pour trier.

`contact_id` est la clé de toutes les étapes suivantes : l'id Apollo, sinon un id local « local-... » pour un contact
importé absent d'Apollo.

## B. Le plan de séquence

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/plan_sequence.py --campagne campagnes/<nom>
```

Options : `--comptes-semaine 15` (comptes par vague, 10 à 20 conseillés), `--scores A,B` (scores inclus, dans
l'ordre), `--debut AAAA-MM-JJ` (J1 de la première vague ; défaut : le lundi qui suit la date de référence),
`--contacts <csv>`. Lancer `ordre_appel.py` avant : le plan y prend les téléphones et les personnes à éviter.

Sortie : `appels/plan-sequence.csv`, une ligne par contact. Règles appliquées :

- **Vagues** : les comptes de score A d'abord, puis B, dans l'ordre du rang ; N comptes par semaine. Les comptes C
  et les contacts sans entreprise dans `base-abc.csv` restent « hors plan ».
- **Une seule voix par entreprise** (colonne `voix`) : d'abord le contact d'entrée (s'il y en a plusieurs : email
  vérifié d'abord, puis la séniorité la plus haute) ; puis les relais un par un, chacun 28 jours après la voix
  précédente (une séquence de 22 jours, puis la suivante), sans réponse, ou plus tôt si le dirigeant renvoie vers
  lui ; les autres contacts d'entrée en dernier. Une entreprise sans contact d'entrée commence par son premier
  relais ; si l'entrée a décliné, le relais passe en voix 1 « à valider ».
- **Canal** : email si `statut_email` vaut `verified` ; sinon appel si un numéro est connu ; sinon LinkedIn si le
  profil est connu ; sinon appel, numéro à trouver au standard.
- **Cadence**, en dates : colonnes `j1`, `j4`, `j8`, `j15`, `j22`.
- Un contact « à éviter » (a répondu et décliné) reste dans le fichier, sans canal. Un compte A sans première
  phrase est signalé dans `remarque`.

## La cadence enseignée en formation

À confirmer avec l'utilisateur pour chaque campagne :

| Jour | Canal | Contenu |
|---|---|---|
| J1 | email 1 | le signal et la proposition d'échange |
| J4 | appel | « Je vous ai écrit mardi, vous avez une minute ? » |
| J8 | email 2, dans le même fil | un élément nouveau |
| J15 | email 3 | un autre angle |
| J22 | email 4 | clôture courtoise : bon moment ? bonne personne ? |

- Sans email vérifié, les emails deviennent des appels ou des messages LinkedIn aux mêmes jours.
- LinkedIn en parallèle quand c'est pertinent : une note d'invitation de moins de 200 caractères, à la main ou avec
  un outil d'automatisation.
- Trois relances au plus, une semaine entre deux emails. **Tout s'arrête à la première réponse**, même un « non
  merci ».
- On mesure les réponses et les rendez-vous, pas les ouvertures. La séquence Apollo envoie ; on relit la première
  étape avant chaque envoi.
- **Les comptes de la semaine** : 10 à 20 comptes A. Pour chacun, on sait avant d'écrire la moindre ligne qui est
  la bonne personne, ce sur quoi elle est évaluée cette année et pourquoi maintenant.

## Une seule voix par entreprise

- Deux séquences : « <pays> - <segment> - entrée » (le décideur), puis « <pays> - <segment> - relais » (qualité,
  IT, planification...).
- Le relais n'est inscrit que si le décideur renvoie vers lui, ou une fois la séquence d'entrée finie sans réponse.
  Jamais deux personnes de la même entreprise la même semaine.
- On ne cite un renvoi (« Monsieur X m'a conseillé de vous appeler ») que s'il a vraiment eu lieu.
- Apollo refuse d'ailleurs par défaut un deuxième contact de la même entreprise dans une séquence : ne pas forcer ce
  drapeau.

## Emails vérifiés seulement

- Dans les étapes email, seulement les adresses au statut `verified`. Les autres (`extrapolated`, `unavailable`,
  `user managed`, sans statut) passent par le téléphone ou LinkedIn : c'est ce que fait la colonne `canal` du plan.
- À l'inscription, laisser à `false` les drapeaux `sequence_no_email` et `sequence_unverified_email`.

## Les emails (seulement sur demande)

Aucun script du skill ne rédige d'email. Sur demande explicite, ils s'écrivent dans la conversation (ou par des
agents, sur demande), d'après `plan-sequence.csv` et `base-abc.csv`. Anatomie de l'email 1, enseignée en formation :

- le signal, qui dit pourquoi vous et pourquoi maintenant : `{{phrase_signal}}` (étape 7) ;
- le lien avec l'offre (`[offre] description`, `argument_cle`), en hypothèse, au conditionnel ;
- la proposition d'un échange : **une seule question**, avec deux créneaux précis (`[offre] cta`, `lien_agenda`) ;
- **moins de 120 mots**, objet court, vouvoiement, pas de pièce jointe, ton humble, aucun chiffre absent des preuves
  (`[offre] preuves`) ;
- **jamais de tiret cadratin ni demi-cadratin** : les chercher dans tous les textes avant tout export
  (`grep -n -e "$(printf '\342\200\224')" -e "$(printf '\342\200\223')" <fichier>`).

Chargement dans Apollo : la variable `{{phrase_signal}}` dans l'étape de la séquence (étape 7), ou un import CSV, ou
le contenu par contact à l'inscription (connecteur MCP).

## Créer les séquences et inscrire (API Apollo, sur accord)

Aucun script du skill n'écrit de séquence. Trois voies : l'utilisateur le fait dans l'interface Apollo (le plus
sûr) ; des appels REST faits un par un, chacun annoncé puis accepté ; ou le connecteur MCP Apollo, chaque action
validée. 0 crédit selon la documentation Apollo, mais de vrais emails partent.

1. **Identifiants** : `GET /api/v1/email_accounts` (boîtes d'envoi : l'utilisateur choisit l'expéditeur, écrit dans
   le récapitulatif) ; la recherche d'utilisateurs, point d'accès `users/search` de l'API (`user_id`, pour
   l'inscription et les tâches).
2. **Créer la séquence inactive** : `POST /api/v1/sequences` avec `name`, `active: false`, `emailer_steps[]` dans
   l'ordre (types `auto_email`, `manual_email`, `call`, `action_item` ; `wait_time` et `wait_mode` en minute, heure
   ou jour). La `note` d'une étape est commune à tous les contacts.
3. **Inscrire par vague** : `POST /api/v1/emailer_campaigns/{sequence_id}/add_contact_ids` avec
   `emailer_campaign_id` (le même id), `contact_ids[]` de la vague (pas `label_names[]`, qui inscrit toute une liste
   d'un coup et ignore l'ordre), `send_email_from_email_account_id` (obligatoire). Drapeaux à décider avec
   l'utilisateur ; chacun, à `true`, inscrit des contacts qu'Apollo écarte sinon :
   `sequence_same_company_in_same_campaign`, `sequence_active_in_other_campaigns`,
   `sequence_finished_in_other_campaigns`, `sequence_no_email`, `sequence_unverified_email`, `sequence_job_change`.
   Règles de la formation (emails vérifiés seulement, une seule voix par entreprise) : laisser `sequence_no_email`,
   `sequence_unverified_email` et `sequence_same_company_in_same_campaign` à `false`. Départ différé possible avec
   `status=paused` et `auto_unpause_at`.
4. **Lire la réponse** : elle liste les contacts écartés (sans email, email non vérifié, déjà dans une autre
   séquence, même entreprise, changement de poste). Les traiter par appel ou LinkedIn.
5. **Activer**, seulement après le second accord : `POST /api/v1/emailer_campaigns/{sequence_id}/approve`. C'est ce
   qui fait partir les emails.
6. **Quand le décideur répond ou renvoie vers le relais** :
   `POST /api/v1/emailer_campaigns/remove_or_stop_contact_ids` (`emailer_campaign_ids[]`, `contact_ids[]`, `mode` =
   `mark_as_finished`, `stop` ou `remove`), puis inscrire le relais dans la séquence « - relais ».
7. **Historique des anciennes campagnes** (0 crédit) : `POST /api/v1/contacts/search` avec `contact_label_ids`
   renvoie `emailer_campaign_ids` et `contact_campaign_statuses` de chaque contact. Un contact actif dans une autre
   séquence se traite en relance, pas à froid.

Connecteur MCP Apollo : mêmes opérations (liste des boîtes d'envoi, recherche d'utilisateurs, création de
séquence, ajout de contacts, approbation, arrêt ou retrait). Chaque appel coûte des tokens : réservé aux petits
volumes.

| Accord à obtenir | Avant |
|---|---|
| Rédaction des emails | toute rédaction |
| Création de la séquence (inactive) | `POST /sequences` ou création dans l'interface |
| Chaque inscription, vague par vague | `add_contact_ids` |
| Activation | `approve` |
| Arrêt ou retrait de contacts | `remove_or_stop_contact_ids` (sauf un refus : on arrête tout de suite et on le dit) |
| Écriture des scripts dans les tâches | étape 9 |

## Sorties

- `appels/ordre-appel.csv` et `appels/ordre-appel-relais.csv` : `priorite, langue, parle_langue_appel,
  langue_principale, avis_langue, score_langue, indices_langue, telephone, type_telephone, tier, rang_entreprise,
  fenetre_opportunite, entreprise, entreprise_id, pays_entreprise, prenom, nom, titre, email, statut_email, linkedin,
  ville, pays, deja_contacte, a_eviter, pourquoi_maintenant, angle, ordre, cibles, contact_id` ;
- `appels/plan-sequence.csv` : `vague, j1, j4, j8, j15, j22, etapes, score_abc, rang, tier, entreprise,
  entreprise_id, voix, ordre, condition, prenom, nom, titre, email, statut_email, telephone, linkedin, canal, signal,
  source, phrase_signal, pourquoi_maintenant, deja_contacte, remarque, contact_id` ;
- dans Apollo, sur accord : les séquences et les inscriptions.

## Contrôles qualité

- Lire les répartitions affichées par les deux scripts : langue et téléphone, vagues, canal de la voix 1, comptes A
  ou B sans contact, comptes A sans première phrase.
- Vérifier quelques `deja_contacte` contre Apollo avant d'appeler à froid.
- Relire la première étape de chaque séquence avant l'activation.
- Recompter les contacts inscrits dans Apollo quelques secondes après l'inscription (index différé).

## Coûts et validations

- 0 crédit : ordre d'appel, plan, séquences, inscriptions et tâches (documentation Apollo). Les mobiles restent
  payants (étape 6).
- Scripts : quelques secondes. Avis de langue par agents : facultatif, sur demande seulement.
- Accords : tableau ci-dessus.

## Pièges principaux

BOM des CSV ; relais écartés sans bruit par Apollo (même entreprise) ; contacts écartés à l'inscription ;
inscription par liste qui ignore l'ordre ; note d'étape commune à tous ; anciennes campagnes mal repérées par les
seuls noms ; numéros inégaux selon la liste ; langue ; signaux qui vieillissent. Détail et parades :
[../reference/pieges.md](../reference/pieges.md), section « Étape 8 ».
