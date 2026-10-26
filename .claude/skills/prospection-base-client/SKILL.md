---
name: prospection-base-client
description: "Chaîne de prospection B2B de la cible au fichier d'appel du commercial, réglée par un fichier campagne.toml (offre, cible, persona) : définir le persona du décideur ; trouver les entreprises d'une cible (agents qui les cherchent sur le web, preuve publique à l'appui, ou un export Apollo ou une autre liste) ; trouver et vérifier leur site et leur page LinkedIn sans rien inventer ; les prioriser par signaux datés et sourcés (registre du commerce, LinkedIn, site, actualités ; tiers A à D, score A/B/C) ; retrouver les décideurs dans Apollo et y réinjecter signal, source, première phrase et score ; préparer l'ordre d'appel, le plan de séquence, les scripts d'appel et le fichier d'appel. À utiliser pour constituer ou qualifier une liste de prospects dans un secteur ou une région, pour faire passer une liste ou un export Apollo par cette chaîne (identifier, extraire, enrichir, réinjecter, prospecter), ou pour l'une de ses étapes."
---

# Prospection B2B : de la cible au fichier d'appel

Chaîne en 9 étapes. Chaque campagne a son dossier, `campagnes/<nom>/`, qui contient sa configuration
(`campagne.toml`, copie complétée de `config/campagne.exemple.toml`) et reçoit toutes les sorties ; rien ne
s'écrit dans le dossier du skill. Les scripts Python (`scripts/`) font le travail répétitif avec des caches ; les
workflows (`workflows/`, outil Workflow de Claude Code) font les recherches qui demandent du jugement. Chaque
étape peut se lancer seule si ses entrées existent.

Installation, clé Apollo, chaque clé de `campagne.toml` et les commandes exactes de chaque étape :
[README.md](README.md). Méthode, contrôles et pièges d'une étape : sa fiche dans `etapes/` (liens dans le tableau).

## Règles d'or (avant toute action)

1. **Accord explicite avant toute dépense ou écriture externe.** Crédits Apollo (enrichissement, mobiles),
   création de comptes, de contacts, de listes ou de champs dans Apollo, mise à jour de contacts, inscription en
   séquence (de vrais emails partent) : d'abord l'aperçu chiffré (le script sans `--go` : nombre, plafond de
   crédits), puis attendre le « go ». Mobiles et options « waterfall » : jamais sans un accord chiffré au pire
   cas. Ce qui est gratuit et en lecture (recherche Apollo de personnes, DuckDuckGo, sites, registre) se fait
   sans demander.
2. **Workflows multi-agents seulement sur demande explicite.** Les proposer est permis, chiffrés : nombre
   d'agents, durée, tokens (repères ci-dessous). Au-delà d'environ 3 M tokens, découper en workflows successifs,
   du plus utile au moins utile. Accord donné : enchaîner sans redemander (passe 2 comprise) et faire un bilan
   chiffré à la fin. Même règle pour les agents de rédaction des étapes 7 à 9. Avant d'écrire ou de modifier un
   workflow : charger le skill `workflow-authoring`.
3. **Aucun message rédigé sans demande explicite** : email, première phrase (`phrase_signal`), carte ou script
   d'appel, argument du fichier d'appel, message LinkedIn.
4. **Anti-invention.** Aucune URL, aucun nom, aucun signal qui ne soit apparu dans une sortie d'outil. Champ vide
   plutôt que faux, « inconnu » plutôt qu'une supposition ; un signal sans date ni source consultée n'est pas un
   signal. Toute valeur nouvelle passe par une contre-vérification sceptique, puis par le contrôle mécanique des
   transcripts d'agents (`consolider_decouverte.py`, `verif_appliquer.py`, `apply_recherche.py` : jamais
   `--sans-controle` sans raison). Les preuves de l'offre (`offre.preuves`) sont des résultats réels donnés par
   l'utilisateur, jamais inventés ni complétés.
5. **Caches partout.** Une relance reprend gratuitement et ne refacture aucun crédit. Ne jamais vider un cache
   sans raison (le cache Apollo vidé refacture l'enrichissement).
6. **Compter par script avant d'annoncer un chiffre** (lire le fichier, jamais de mémoire).
7. **Scripts et API REST, pas de navigateur ni de connecteur en boucle.** Le connecteur MCP Apollo coûte environ
   8 000 tokens par recherche ; un navigateur piloté est lent, fragile, et un clic peut consommer des crédits.
   Exception : une trentaine de comptes, dans la conversation, chaque action validée.
8. **Données nominatives et clé.** Les contacts portent emails et téléphones : trancher leur sort git avec
   l'utilisateur au démarrage (proposer un `.gitignore`, ne pas l'écrire sans accord ; sans réponse, ne commiter
   que des chemins explicites, jamais `git add -A`). Ne jamais afficher la clé API ni lire `.env` à l'écran :
   `verifier_installation.py` dit seulement si elle est présente.
9. **Ce qui se dit au prospect.** Français (ou la langue du contact) ; **jamais de tiret cadratin ni
   demi-cadratin** dans un texte destiné aux prospects (emails, répliques, `angle`, `pourquoi_maintenant`,
   `phrase_signal`) ; jamais un signal négatif (faillite, licenciements, cyberattaque) dit au prospect ; rien de
   `offre.ne_jamais_dire`. Une seule voix par entreprise ; nos clients et partenaires (`exclure.csv`) ne sont
   jamais prospectés ; toute personne qui refuse sort de toutes les campagnes.
10. **Toujours `.venv/bin/python`, depuis la racine du projet** (`python3` peut être un autre interpréteur, sans
    `ddgs`).

## Démarrer ou reprendre une campagne

Checklist de démarrage :

- [ ] Installation contrôlée :
      `.venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py` sans ✗.
- [ ] Dossier `campagnes/<nom>/` créé, `campagne.toml` copié de `config/campagne.exemple.toml` et complété : plus
      aucune valeur d'exemple (« Exemple SA », « Prénom Nom »...), preuves réelles ou aucune.
- [ ] `verifier_installation.py --campagne campagnes/<nom>` sans ✗ ; lire avec l'utilisateur les lignes « ! ».
- [ ] Persona du décideur validé avec l'utilisateur (étape 1) : `persona.md` et section `[persona]`.
- [ ] Nos clients et partenaires actuels dans `exclure.csv` (colonnes `nom`, `site`).
- [ ] Source de l'étape 2 choisie avec l'utilisateur : découverte web (workflow, donc accord), liste existante ou
      export Apollo, ou les deux (`--ajouter`).
- [ ] Sort git des données tranché.
- [ ] Avant l'étape 6 : clé Apollo présente (contrôle ci-dessus), quotas du compte connus, noms des listes dans
      `[apollo]`.

**Reprendre** : si l'utilisateur nomme une étape, aller à sa fiche. S'il nomme une campagne, lancer
`verifier_installation.py --campagne campagnes/<nom>` : il lit les fichiers présents et donne l'étape suivante.

Les commandes de ce skill s'écrivent depuis la racine du projet :
`.venv/bin/python .claude/skills/prospection-base-client/scripts/<script>.py --campagne campagnes/<nom> [...]`.
Si le skill est installé ailleurs (par exemple `~/.claude/skills/`), adapter ce chemin, et passer `skill` dans les
args du workflow de découverte. `--help` de chaque script : toutes ses options, sans réseau ni clé.

## La chaîne en 9 étapes

| # | Étape | Ce qu'on fait | Scripts et workflows | Sorties | Coût | Accord |
|---|---|---|---|---|---|---|
| 1 | [Cible et persona](etapes/01-identifier-la-cible.md) | Cible (ICP) écrite avec l'utilisateur ; persona du décideur par le prompt ci-dessous ; clients et partenaires à exclure | aucun (`verifier_installation.py` contrôle la config) | `campagne.toml`, `persona.md`, `exclure.csv` | 0 | non |
| 2 | [Trouver les entreprises](etapes/02-trouver-les-entreprises.md) | **Découverte web** : un agent par segment « secteur, zone » et par source transverse, preuve publique exigée, critique de couverture, compléments ; consolidation avec contrôle anti-invention. **Ou liste existante** (export Apollo de comptes ou de contacts, salon, annuaire) mise au contrat | `workflows/decouverte-entreprises.js`, `consolider_decouverte.py`, `linkedin_site.py` ; `importer_liste.py` | `entreprises-toutes.csv` (à relire), `entreprises.csv` ; `apollo/contacts-importes.csv` pour un export de contacts | découverte : environ 190 000 tokens par agent ; liste : 0 | découverte : **oui** |
| 3 | [Site et LinkedIn](etapes/03-enrichir-site-linkedin.md) (liste sans sites) | DuckDuckGo : site officiel, puis page LinkedIn lue sur le site, sinon cherchée ; corrections manuelles facultatives | `enrichir_sites.py` | `entreprises-enrichi.csv` | gratuit, environ 18 min pour 360 noms | non |
| 4 | [Vérifier par agents](etapes/04-verifier-par-agents.md) (facultatif) | Lots profonds et légers, contre-vérification sceptique de chaque URL nouvelle, passe 2 sur les cas ouverts, arbitrages | `verif_preparer.py`, `workflows/verification.js`, `verif_appliquer.py`, `verif_passe2.py`, `workflows/verification-passe2.js` | `entreprises-verifie.csv` | environ 6 500 tokens par entreprise | **oui** |
| 5 | [Signaux et priorisation](etapes/05-signaux-et-priorisation.md) | Registre du commerce suisse, LinkedIn public, sites, actualités ; recherche par agents et vérificateur adverse ; fit ICP, tiers A à D ; logiciels ; score A, B, C (aperçu) | `entites.py`, `collect_zefix.py`, `collect_linkedin.py`, `collect_site.py`, `collect_news.py`, `dossiers.py`, `workflows/signaux-recherche.js`, `apply_recherche.py`, `scorer.py`, `collect_logiciels.py`, `reinjecter_apollo.py` (sans `--go`) | `prospection-signaux.csv`, `rapport-signaux.md`, `base-abc.csv`, `donnees/signaux/` | collectes gratuites ; agents environ 0,5 M tokens par lot de 15 | agents : **oui** |
| 6 | [Contacts Apollo](etapes/06-contacts-apollo.md) | Liste de comptes ; cibles par entreprise (entrée, relais) ; recherche gratuite, puis web, puis recherche ; validation de `garder` ; enrichissement et création des contacts ; export des listes | `creer_comptes.py`, `extraire_personas.py`, `chercher_contacts.py`, `chercher_web.py`, `enrichir_et_creer.py`, `exporter_listes.py` | `apollo/contacts-a-valider.csv`, `apollo/contacts-crees.csv`, listes « - entrée » et « - relais », `apollo/listes/` | recherche 0 crédit ; 1 crédit par personne enrichie (+8 par mobile) | **oui** (`--go`, après relecture de `garder`) |
| 7 | [Réinjecter dans Apollo](etapes/07-reinjecter-dans-apollo.md) | Score A, B, C, signal et date, source, première phrase (rédigée sur demande) dans quatre champs de contact, pour la variable `{{phrase_signal}}` des séquences | `reinjecter_apollo.py` ; `consignes/phrases-signal.md` | `base-abc.csv`, `phrases-a-rediger.csv`, `apollo/reinjection.csv`, champs Apollo | 0 crédit | **oui** (écriture ; phrases : rédaction) |
| 8 | [Séquence et ordre d'appel](etapes/08-sequence-et-ordre-d-appel.md) | Ordre d'appel (refus en fin, langue de l'appelant, téléphone, tier, rang) ; plan de séquence : comptes A de la semaine, une voix par entreprise, cadence J1 à J22 | `ordre_appel.py`, `plan_sequence.py` | `appels/ordre-appel.csv`, `appels/plan-sequence.csv` | 0 | séquence, emails, inscription : **oui** |
| 9 | [Scripts et fichier d'appel](etapes/09-scripts-et-fichier-d-appel.md) | Briefs par lots, agents de rédaction (secteur, description, taille, argument ouvert sur sa source ; cartes d'appel), assemblage contrôlé ; un script d'appel par contact | `fichier_appel.py` (`briefs`, `sources`, `assembler`), `scripts_appel.py` ; `consignes/*.md` | `appels/fichier-appel.xlsx` et `.csv`, `appels/scripts-appel.md` | environ 1,5 M tokens pour 8 agents de rédaction | **oui** (rédaction) |

Repères de coût, mesurés sur une campagne précédente : découverte, environ 6 000 tokens par entreprise trouvée
(8 segments et 3 sources : 18 agents, environ 3,4 M tokens) ; vérification, environ 2,4 M tokens et 45 min pour
environ 380 entreprises ; signaux, 31 000 à 35 000 tokens par entreprise recherchée ; Apollo, environ 2 crédits
par entreprise retenue. Environ 6 agents tournent en même temps : en tenir compte dans les durées annoncées.

### Étape 1 : le prompt persona

À lancer avec l'utilisateur (crochets à remplacer), puis ranger la réponse validée dans `persona.md` :

> Nous vendons [votre offre] à [type d'entreprise]. Donne-moi le persona du décideur : ses intitulés de poste en
> français et en anglais, ce sur quoi il est évalué, ses motivations, ses objections probables, son calendrier de
> décision, et cinq signaux publics qui montrent qu'il est prêt à acheter maintenant. Si une réponse dépend de notre
> contexte, pose-moi la question.

Les intitulés vont dans `[persona]` (familles et `[persona.titres]`), les signaux d'achat orientent les agents de
l'étape 5, les objections et le calendrier servent aux étapes 8 et 9.

## La chaîne enseignée en formation

La formation « Lancer son projet avec l'IA » (Pulse Digital, slides 27 à 33 et 39 à 42) présente la même chaîne
en cinq étapes, de la cible au premier rendez-vous. Chaque promesse des slides a sa place dans le skill :

| Étape de la formation | Promesse des slides | Où dans ce skill |
|---|---|---|
| 1. Identifier (Claude) | le persona du décideur : intitulés FR et EN, motivations, objections, calendrier, cinq signaux d'achat (slide 28) | étape 1 : prompt persona, `persona.md`, `[persona]` |
| 2. Extraire (Apollo) | une liste de comptes et de contacts : filtres tirés du persona, emails vérifiés, liste nommée « Segment · Persona · Mois » (slides 29 et 30) | étape 2, liste existante (`importer_liste.py`), ou découverte web ; contacts : étape 6 |
| 3. Enrichir (Claude), puis trier | un signal de moins de 12 mois, daté et sourcé, par compte (slide 31) ; trois paquets A, B, C (slide 32) | étape 5 : signaux, tiers A à D, puis score A, B, C |
| 4. Réinjecter (Apollo et MCP) | une base unique, à jour : signal et date, source, première phrase, score (slide 33) | étape 7 : quatre champs de contact Apollo, variable `{{phrase_signal}}` |
| 5. Prospecter (Apollo, téléphone, LinkedIn) | des rendez-vous : comptes A de la semaine (slide 39), premier email (slide 40), cadence sur trois semaines (slide 41), appel en cinq temps et objections (slide 42) | étapes 8 et 9 |

Vocabulaire :
- **Score A, B, C** de la formation (A : cible et signal récent, on contacte cette semaine ; B : cible sans
  signal, en veille ; C : hors cible) et **tiers A à D** du skill (C et D sont encore dans la cible, avec un fit
  plus faible) : deux lectures différentes. Le C de la formation est le « Hors cible » du skill. Dire « score A »
  ou « tier A », jamais une lettre seule.
- **Petits volumes** (une trentaine de comptes, le cas de la formation) : tout peut se faire dans la conversation,
  avec le connecteur MCP Apollo et les prompts des slides, chaque action validée. Les scripts et les workflows
  servent au-delà.

## Travailler avec l'utilisateur

- Sur la qualité, répondre honnêtement (« non, je n'ai pas tout contrôlé en profondeur »), avec un tableau de
  fiabilité et un avis coût et bénéfice selon l'usage (une démo n'a pas besoin de l'étape 4, une campagne si),
  avant d'engager des coûts. Recherche DuckDuckGo seule : environ un lien sur quatre faux ou imparfait.
- Pendant un traitement long : autonomie, pas de sollicitation. À « ça en est où ? », un point court et chiffré
  lu dans le journal du run (fait, en cours, échecs, résultats partiels). Dossier d'un run :
  `find ~/.claude/projects -type d -path '*workflows*' -name '<runId>'`.
- Workflow coupé (limite de session) : intégrer d'abord les résultats partiels, puis reprendre avec l'outil
  Workflow (même `scriptPath`, mêmes `args`, `resumeFromRunId`) : les agents terminés sont rejoués depuis le
  cache. Ne jamais tout relancer.
- En fin d'étape : un résumé rapide (fichiers, chiffres comptés par script, ce qui a été contrôlé, limites,
  question pour la suite). Signaler toute décision prise sans qu'elle ait été demandée.
- Ce qui a été proposé sans réponse n'est pas validé : ne pas le faire.
- Noter les enseignements réutilisables dans `<campagne>/apprentissages.md`, au format
  « - [AAAA-MM-JJ] fait -> action ».

## Annexes

- `etapes/01-identifier-la-cible.md` à `etapes/09-scripts-et-fichier-d-appel.md` : une fiche par étape (entrées,
  déroulé, sorties, contrôles qualité, coûts, pièges).
- [reference/outils.md](reference/outils.md) : scripts, workflows, journaux de run, point d'avancement ;
  [reference/pieges.md](reference/pieges.md) : pièges rencontrés et parades, par étape ;
  [reference/contrat.md](reference/contrat.md) : fichiers et colonnes échangés entre les étapes.
- `consignes/` : consignes des agents de rédaction (`phrases-signal.md`, `fichier-appel-redaction.md`,
  `fichier-appel-sources.md`, `cartes-appel.md`).
- [README.md](README.md) : installation, clé Apollo, fichiers à compléter, commandes, dépannage.
- `config/campagne.exemple.toml` : modèle commenté de la configuration.
