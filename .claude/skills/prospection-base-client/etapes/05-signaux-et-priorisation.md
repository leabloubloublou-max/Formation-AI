# Étape 5 : signaux et priorisation

Commandes depuis la racine du projet, skill supposé dans `.claude/skills/prospection-base-client/` (sinon,
adaptez ce chemin, voir l'étape 1). `<nom>` : le dossier de la campagne.

## Objectif

Classer chaque entreprise en tiers de prospection **A, B, C, D ou Hors cible**. Le fit ICP fixe la base, les
signaux font monter : le A exige un bon fit **et** un signal. Chaque signal est daté et sourcé ; les signaux forts
sont contre-vérifiés par un agent adverse. L'étape produit aussi, pour les entreprises recherchées par agents :
- `pourquoi_maintenant` : la raison de contacter maintenant, en une ou deux phrases factuelles ;
- `angle` : une hypothèse de cas d'usage de l'offre, au conditionnel ;
- `persona_cible` et `cibles` : qui contacter (entrée, puis relais), lus à l'étape 6.

Enfin, le **score A, B, C de la formation** (« Prioriser ») se calcule sur ces sorties, sans rien relancer.

## Entrées

- La liste la plus avancée de la campagne : `entreprises-verifie.csv`, sinon `entreprises-enrichi.csv`, sinon
  `entreprises.csv`.
- `campagne.toml` : `[cible]` (fit), `[offre]` (contexte des agents, `preuves[].cas` pour l'angle,
  `concurrents`), `[persona]` (entrée et relais), `[signaux]` (`fenetre_mois`, `registre_suisse`, `logiciels`),
  `campagne.date_reference` (« aujourd'hui » des fenêtres).
- Aucune clé : registre du commerce suisse (Zefix, API publique), LinkedIn en vue invité, DuckDuckGo. Aucun
  crédit Apollo.
- Facultatif : `campagnes/<nom>/noms-ambigus.csv` (colonne `nom`) : noms à préciser par la ville ou le pays dans
  les recherches d'actualités.

## Version légère, pour une trentaine de comptes (« Enrichir » de la formation)

Sans collectes ni workflow : le prompt de la formation (slide 31), sur l'export Apollo ou `entreprises.csv`, dans
la conversation ou avec un agent par lot de 15 comptes :

> Voici notre extraction Apollo (fichier joint), une ligne par contact. Traite les lignes une par une, sans en sauter.
> 1. Cherche sur le web un signal de moins de 12 mois sur l'entreprise : levée de fonds, nomination, nouveau
> produit, recrutements, implantation. 2. Ajoute trois colonnes : signal et date, source (lien), première phrase du
> message. Si tu ne trouves rien, écris « aucun signal trouvé ». N'invente jamais un signal.

Règles : retirer la colonne « première phrase » du prompt si l'utilisateur n'a pas demandé de rédaction ; aucun
tiret cadratin. Puis vérifier chaque lien cité (ouvrir la source, chercher la date et le nom de l'entreprise),
trier en A, B, C (section « Score A, B, C ») et réinjecter (étape 7). Au-delà d'une cinquantaine de comptes, la
chaîne complète coûte moins cher par compte et contre-vérifie les signaux.

## Déroulé, chaîne complète

1. **Fiches entreprises** (sans réseau) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/entites.py --campagne campagnes/<nom> [--liste <csv>]
   ```

   Une fiche par entreprise dans `donnees/signaux/entites.json`. Les lignes « doublon » (colonne `exclure`) sont
   ignorées ; les doublons restants fusionnent (même nom, même nom officiel, ou même site et même page LinkedIn
   avec un mot distinctif commun). Drapeaux : exclure, particulier, administration, non identifiée, fermée ou en
   liquidation, renommée ou absorbée. `id` = slug du nom court : la clé de tous les caches et fichiers suivants. Ne
   pas le changer en cours de campagne. Le script affiche la liste lue : vérifier que c'est la bonne.

2. **Registre suisse** (si `signaux.registre_suisse = true` et s'il y a des entreprises suisses ; sinon sauter) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> --workers 4
   ```

   Repère : environ 2 minutes pour 360 entreprises. Correspondance scorée des candidats (sociétés radiées
   comprises) ; un candidat radié depuis plus de 8 ans est un ancien homonyme (`--radiees-ans N`, 0 = aucun
   filtre). Publications officielles lues en signaux sur `max(36, fenetre_mois)` mois.

3. **LinkedIn public**, en arrière-plan (le plus lent) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_linkedin.py --campagne campagnes/<nom>
   ```

   Repère : environ 2 à 3 pages par minute (environ 1 h 40 pour 290 pages). Test : `--limit 5`. Séquentiel, sans
   cookies, pauses de 4 à 8 secondes ; arrêt après 5 blocages d'affilée, puis reprise avec `--retry`. Pays de la
   cible d'abord, puis pays inconnu, voisins, exclues ; les autres pays seulement avec `--tous`. Ne pas le lancer
   pendant un workflow dont les agents ouvriraient LinkedIn depuis la même adresse.

4. **Sites web**, en parallèle de LinkedIn :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_site.py --campagne campagnes/<nom> --workers 8
   ```

   Repère : environ 3 minutes pour 290 sites. Stack technique, mentions tech, page carrières et postes tech,
   fraîcheur, signaux datés. `--refresh` refait tous les sites.

5. **Deuxième passage du registre**, une fois LinkedIn fini (le pays et le nom de la page débloquent des filiales
   suisses) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> --refresh
   ```

6. **Actualités**, après le registre, LinkedIn et les sites (ils affinent zone, taille et secteur, donc le
   périmètre) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_news.py --campagne campagnes/<nom> --workers 3 [--fit-min 5]
   ```

   Repère : environ 30 minutes. Périmètre : aucune exclusion et fit au moins `--fit-min` (5 par défaut).
   4 requêtes par entreprise (actualités du nom ; nom et nomination ; nom et levée ou rachat ; nom et IA ou
   digitalisation), dans la langue et la région de l'entreprise, avec un filtre anti-homonymes. Les résultats sont
   des signaux candidats, à confirmer par les agents.

7. **Dossiers et lots pour les agents** :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/dossiers.py --campagne campagnes/<nom> [--par-lot 15 | --lots N] [--fit-min 5] [--max N]
   ```

   Un dossier compact par entreprise du périmètre (registre, LinkedIn, site, actualités, signaux candidats).
   Priorité : fit + 0,2 × min(signaux candidats, 6), tourniquet entre les lots. Le script affiche un ordre de
   grandeur (environ 35 000 tokens par entreprise, contre-vérification comprise) et écrit `lots/L01.json...`,
   `lots/manifest.json` et `lots/args-recherche.json`. **Sans `--complement`, il efface les lots, le manifeste et
   les `args` précédents** : ne le relancer ainsi qu'avant le premier run de recherche. Il s'arrête si
   `offre.societe` et `offre.description` sont vides. `--max N` : un essai à petit coût.

8. **Accord, puis workflow de recherche** : outil Workflow, `scriptPath` = chemin absolu de
   `.claude/skills/prospection-base-client/workflows/signaux-recherche.js` (le script l'affiche), `args` = le
   contenu de `args-recherche.json`, tel quel. Le workflow enchaîne, lot par lot, la recherche puis un
   contre-vérificateur adverse qui démarre dès que la recherche du lot finit.
   - **Agent de recherche** (un par lot d'environ 15 dossiers) : activité réelle, catégorie de secteur, effectif
     avec sa source, groupe parent, `dans_icp` ; signaux datés (AAAA-MM-JJ ou AAAA-MM) avec une `source_url`
     réellement consultée et une confiance ; `adoption_tech` (fort, moyen, faible, 1 à 3 preuves, `concurrent` si
     l'entreprise vend ce que nous vendons) ; dirigeants ; `pourquoi_maintenant` (vide sans signal) ; `angle` ;
     `cibles` et `persona_cible` au format « Entrée : Prénom Nom (rôle) ; relais : rôle, rôle ». Budget : 3 à 6
     recherches par entreprise. Il n'ouvre pas linkedin.com avec les outils locaux.
   - **Contre-vérificateur** : il tente de réfuter chaque signal fort (la source dit-elle cela ? même entreprise,
     pas la maison mère étrangère ni un client cité ? date juste et dans la fenêtre ? le nouveau dirigeant est-il
     vraiment le patron ? preuves tech propres à l'entreprise ?). Signaux soumis : direction (nouveau dirigeant,
     succession, départ), financement, rachat ou fusion, négatifs, projet ERP ou numérique, tech « fort ». Les faits
     bruts d'un registre officiel ne sont pas soumis, sauf la direction.
   - Suivi et reprise : comme à l'étape 2 (point 5).

9. **Intégrer les résultats** (sans réseau) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/apply_recherche.py --campagne campagnes/<nom> "<dossier du run 1>" ["<dossier du run 2>" ...]
   ```

   Passer **tous** les runs de la campagne, dans l'ordre chronologique : un run plus récent remplace les résultats
   d'un même lot. Verdicts : réfuté = signal ignoré ; confirmé = confiance « vérifié » ; incertain = confiance
   « agent » (poids réduit), date corrigée appliquée ; tech « fort » incertaine = moyen, réfutée = faible.
   Contrôle anti-invention (transcripts à côté du journal) : la `source_url` d'un signal doit apparaître telle
   quelle dans les sorties d'outils de l'agent ou dans son lot ; sinon le signal passe en confiance « faible »,
   sauf si le contre-vérificateur l'a confirmé en voyant lui-même la source. Les tirets cadratins des agents sont
   remplacés. Ne pas utiliser `--sans-controle`, sauf pour diagnostiquer.

10. **Scorer** (déterministe, sans réseau, relançable à tout moment : après une correction du lexique, de la
    configuration ou de la recherche) :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/scorer.py --campagne campagnes/<nom>
    ```

11. **Compléments** : quand de nouvelles entreprises entrent dans le périmètre (tailles LinkedIn connues plus
    tard, configuration de la cible corrigée), préparer des lots pour elles seules :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/dossiers.py --campagne campagnes/<nom> --complement [--par-lot 15] [--fit-min 5]
    ```

    Puis le workflow sur ces nouveaux lots (`args-recherche.json` ne contient qu'eux), `apply_recherche.py` avec
    **tous** les runs, puis `scorer.py`.

12. **Score A, B, C** (aperçu, aucune écriture externe) :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> [--date AAAA-MM-JJ]
    ```

    Écrit `base-abc.csv` et `phrases-a-rediger.csv` (et `apollo/reinjection.csv`, vide tant qu'il n'y a pas de
    contacts). Sans `--go`, rien ne part dans Apollo : l'écriture est l'étape 7.

13. **Logiciels des prospects** (facultatif, utile au fichier d'appel de l'étape 9), après `scorer.py` :

    ```bash
    .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_logiciels.py --campagne campagnes/<nom> [--mot ERP] [--tiers A,B,C,D] [--workers 3] [--max N]
    ```

    Cherche les logiciels de `signaux.logiciels` (3 ou 4 requêtes par entreprise). Un résultat ne compte que s'il
    cite un logiciel de la liste ET parle de l'entreprise. Statut « indice » ou « aucun » : relire les preuves dans
    `donnees/signaux/logiciels.json`, passer le statut à « probable » ou « confirmé » (ou « aucun ») et `relu` à
    « oui ». Seuls « probable » et « confirmé » peuvent être cités à un prospect.

## Les signaux

| Famille | Sous-types | Sources |
|---|---|---|
| Direction | `nouveau_dirigeant`, `depart_dirigeant`, `succession` (transmission, reprise par le management), `nouveau_cadre` (IT, numérique, qualité, opérations, et les familles relais du persona), `conseil` | registre, posts LinkedIn, presse, agents |
| Financement | `levee`, `augmentation_capital`, `kapitalband` (marge de fluctuation du capital), `aide_publique` | registre (capital), presse, agents |
| Rachat ou fusion (`ma`) | `rachat`, `fusion_reprise`, `absorbe`, `absorbee_par` | registre, presse, agents |
| Croissance | `nouveau_site`, `nouveau_siege`, `recrutement` | registre, site, LinkedIn, agents |
| Projet | `erp_numerique` (ERP, MES ou numérique), `certification`, `lancement_produit`, `changement_nom`, `changement_but` | registre, site, LinkedIn, agents |
| Tech (adoption) | stack du site, mentions IA ou industrie 4.0, activité LinkedIn, postes tech, appréciation de l'agent, `concurrent` | site, LinkedIn, agents |
| Négatif | `faillite`, `sursis_concordataire`, `dissolution`, `faillite_annulee`, `reduction_capital`, `difficultes` | registre, presse, agents |

Fenêtres : registre `max(36, fenetre_mois)` mois ; détections automatiques et agents : `fenetre_mois` (24 par
défaut), plus, pour les agents, les événements structurants des 12 mois précédents, pondérés moins par la récence.
Les détections automatiques (posts LinkedIn, actualités) sont des candidats bruités : elles pèsent peu et ne
comptent dans le moment que pour les entreprises sans recherche par agent. Les détections du site nourrissent les
dossiers des agents et le score tech. Un signal d'agent dont la source n'a pas été vue (confiance « faible ») est
traité comme une détection automatique.

## Fit ICP (0 à 9)

Zone, taille et secteur, notés de 0 à 3 chacun, d'après `[cible]` (règles détaillées à l'étape 1). Le secteur se
lit dans l'ordre de fiabilité des sources : activité vérifiée, secteur LinkedIn, secteur de la liste, but social du
registre (coupé avant « La société peut »), spécialités et description LinkedIn, description du site.

Hors cible d'office (motifs d'exclusion) : colonne `exclure` remplie, particulier, administration, entité non
identifiée, radiée ou en liquidation, hors zone, secteur exclu, grand groupe. Après la recherche par agents, la
catégorie et l'effectif trouvés par l'agent priment ; `dans_icp = false` ajoute le motif « hors ICP selon
recherche ».

## Score et tiers (scorer.py)

- **Consolidation** : un signal d'agent non réfuté de même famille, à 25 jours près, remplace l'événement brut du
  registre ; une personne radiée puis réinscrite à 183 jours ou moins est un changement de signature (ignoré) ; une
  fiche registre déclarée homonyme par l'agent est ignorée.
- **Moment** (de -10 à 10) = poids × récence, un seul signal par sous-type (le plus fort). Poids principaux
  (registre / vérifié / agent / automatique) :

  | Signal | Poids |
  |---|---|
  | `nouveau_dirigeant` | 6 / 6 / 4,5 / 2 |
  | `levee` | 5 / 6 / 4,5 / 1,5 |
  | `succession` | 4 / 5 / 4 / 1,5 |
  | `rachat` | 5 / 5 / 4 / 1,5 |
  | `augmentation_capital` ; `fusion_reprise` | 4 / 4 / 3 / 1 ; 4 / 4 / 3,5 / 1,5 |
  | `erp_numerique` | 3 / 4 / 3,5 / 0,75 |
  | `depart_dirigeant` ; `nouveau_cadre` ; `nouveau_site` | 3 / 3 / 2,5 / 1 ; 2,5 / 3 / 2,5 / 1 ; 1,5 / 3 / 2,5 / 1 |
  | `aide_publique` ; `kapitalband` ; `recrutement` ; `certification` ; `conseil` | de 1 à 2,5 (hors automatique) |
  | `faillite`, `dissolution` / `sursis_concordataire` / `difficultes` | -10 / -7 / -6 (registre, vérifié), -4 à -7 (agent) |

  Ajustements : rôle au registre pour la direction (président × 0,5, signature × 0,3, inconnu × 0,8) ;
  `nouveau_cadre` dans un rôle clé, vérifié ou d'agent : +1 ; augmentation de capital d'au moins un million : +1 ;
  signaux `conseil` additionnés et plafonnés à 2. Récence : 12 mois ou moins × 1, 12 à 24 mois × 0,65, 24 à 36
  mois × 0,3, au-delà 0, sans date × 0,3 (vérifié ou agent seulement).
- **Tech** (0 à 10) : stack du site, contenus IA et industrie 4.0, activité LinkedIn, recrutement tech,
  appréciation de l'agent (fort 3, moyen 1,5).
- **Tier** : motif d'exclusion = Hors cible. Base : B si fit au moins 7,5, C si au moins 6, sinon D. +1 cran si
  moment au moins 4 ou tech au moins 6 ; +2 si les deux, ou si moment au moins 7 ; -1 si moment négatif. Un fit
  inférieur à 6 interdit le A. Un concurrent (il vend ce que nous vendons) plafonne en B.
- `fenetre_opportunite` = oui si tier A ou B et moment au moins 5. `score` = 2 × fit + moment + 0,8 × tech : il
  trie à l'intérieur d'un tier.

Poids et seuils sont des constantes en tête de `scorer.py` (`W`, `SEUIL_MOMENT`, `SEUIL_TECH`).

## Score A, B, C de la formation (« Prioriser », slide 32)

La formation trie en trois paquets : **A** cible et signal récent, on contacte cette semaine ; **B** cible sans
signal, en veille ; **C** hors cible, retirée. Attention : le **C de la formation est le « Hors cible » des
tiers**, pas le tier C (encore dans la cible). Dire « score A, B, C » ou « tier », jamais une lettre seule.

Calculé par `reinjecter_apollo.py` (point 12) :
- **A** : tier A ou B, et au moins un signal positif de moins de 12 mois (à la date de référence), de poids au
  moins 1, venu du registre ou d'une recherche par agent (les détections automatiques ne comptent pas) ; ni signal
  négatif grave de moins de 12 mois, ni concurrent. Un départ (radiation, sortie du conseil) est un changement,
  pas une accroche : il ne suffit pas, et une arrivée suivie du départ de la même personne ne compte plus.
- **B** : le reste de la cible ; `raison_abc` dit pourquoi (pas de signal récent, tier C ou D, signal négatif,
  concurrent).
- **C** : motif d'exclusion (Hors cible).
- Le signal retenu pour un compte A est la plus lourde de ses accroches, puis la plus récente, écrit comme dans la
  formation (« Ouverture d'un site à Sion, septembre 2026 »), avec son lien dans `source_signal`.
- Une seule voix par entreprise : une entreprise par ligne ici, un seul contact d'entrée à la fois ensuite
  (étape 8).

## Veille, avant chaque nouvelle vague de contact

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_zefix.py --campagne campagnes/<nom> --refresh
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_linkedin.py --campagne campagnes/<nom> --retry
.venv/bin/python .claude/skills/prospection-base-client/scripts/collect_news.py --campagne campagnes/<nom> --refresh
.venv/bin/python .claude/skills/prospection-base-client/scripts/scorer.py --campagne campagnes/<nom>
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> [--phrases campagnes/<nom>/phrases-signal.csv]
```

- `--phrases` dès que `phrases-signal.csv` existe (étape 7), sinon sans l'option : `reinjecter_apollo.py` ne lit
  ce fichier qu'avec elle, et sans elle `base-abc.csv` perd les premières phrases (`plan_sequence.py` signale
  alors les comptes A « sans première phrase »).
- `campagne.date_reference` doit être vide (ou avancée) : `scorer.py` écrit un instantané
  `donnees/signaux/historique/<date de référence>.json`, et le rapport n'ajoute la section « Nouveaux signaux
  depuis le <date> » que s'il existe un instantané d'une date strictement antérieure. Une relance le même jour
  écrase l'instantané du jour.
- Limites : `--retry` ne relit pas les pages LinkedIn déjà lues ; les entreprises déjà recherchées par agents ne
  captent plus que le registre, les posts et les actualités. Une nouvelle recherche par agents sur les tiers A et
  B n'est pas outillée (`dossiers.py --complement` ne reprend que les entreprises jamais envoyées) : la préparer
  avec l'utilisateur, accord et estimation à l'appui.

**Veille programmée** (formation : « B en veille, une tâche programmée vous prévient au prochain signal ») : une
fois la chaîne rodée, et sur accord, programmer ces commandes chaque semaine, puis signaler les comptes passés en
A. Avant la veille, garder le score précédent :

```bash
cp campagnes/<nom>/base-abc.csv campagnes/<nom>/donnees/base-abc-precedent.csv
```

Après la veille, les comptes passés en A :

```bash
.venv/bin/python -c "import csv; f = lambda p: {r['id']: (r['score_abc'], r['nom']) for r in csv.DictReader(open(p, encoding='utf-8-sig'))}; a, b = f('campagnes/<nom>/donnees/base-abc-precedent.csv'), f('campagnes/<nom>/base-abc.csv'); print('passés en A :', [b[i][1] for i in b if b[i][0] == 'A' and a.get(i, ('',))[0] != 'A'])"
```

Moyen : une tâche programmée (cron, launchd) sur la machine qui garde les caches et le `.venv` ; une routine dans
le cloud n'y a pas accès. On n'automatise que ce qu'on a déjà fait à la main.

## Sorties

- `campagnes/<nom>/prospection-signaux.csv` (utf-8 avec BOM), une ligne par entreprise, triée par tier puis
  score : `rang, tier, fenetre_opportunite, score, tier_fit, monte_de, fit_icp, timing, tech, nom, pays, canton,
  secteur, taille, activite, pourquoi_maintenant, signaux_direction, signaux_financement, signaux_rachat_fusion,
  signaux_croissance_projets, signaux_tech, signaux_negatifs, dirigeants, persona_cible, angle, site, linkedin,
  linkedin_corrige, registre, motifs_exclusion, recherche_agent, sources, id`. Chaque signal y est écrit
  « <phrase>, <mois année> (<source>) ».
- `campagnes/<nom>/rapport-signaux.md` : tiers, fiches du tier A, tableau du tier B, nouveaux signaux (veille),
  alertes (radiées, en liquidation, en difficulté), concurrents ou partenaires potentiels, pages LinkedIn
  corrigées, méthode.
- `campagnes/<nom>/base-abc.csv` : `rang, score_abc, raison_abc, tier, nom, signal_et_date, source_signal,
  phrase_signal, pourquoi_maintenant, site, id` ; `phrases-a-rediger.csv` : les comptes A sans première phrase.
- `donnees/signaux/` : `entites.json`, `zefix.json`, `linkedin.json`, `site.json`, `news.json` (caches des
  collectes, relances gratuites), `lots/` (dossiers, manifeste, `args-recherche.json`), `recherche.json`,
  `signaux.json`, `historique/<date>.json`, `logiciels.json`.
- `apprentissages.md` : les enseignements datés de la campagne (format « - [AAAA-MM-JJ] fait -> action »).

## Contrôles qualité

- Relire les fiches du tier A et la section **Alertes** du rapport avant tout contact : une entreprise peut être en
  A et en alerte (ancienne société en faillite dont l'activité a été reprise).
- Ouvrir la source de quelques signaux de chaque famille, et de 5 comptes A du score A, B, C : le signal y figure, à
  la bonne date, pour la bonne entreprise.
- Recompter depuis les fichiers avant d'écrire un chiffre (le scorer affiche la répartition par tier ;
  `reinjecter_apollo.py` celle des A, B, C).
- Aucun tiret cadratin ni demi-cadratin dans `pourquoi_maintenant`, `angle` et les colonnes reprises dans des
  messages.
- `persona_cible` au bon format pour l'étape 6 (« Entrée : ... ; relais : ... »).

## Coûts et accords

- Collectes gratuites (repères sur une liste d'environ 360 entreprises) : registre environ 2 min, LinkedIn environ
  1 h 40, sites environ 3 min, actualités environ 30 min.
- Workflow de recherche : **accord explicite**, estimation à l'appui (affichée par `dossiers.py`). Repère mesuré :
  environ 6,4 M tokens de sous-agents et environ 2 450 appels d'outils pour environ 180 entreprises en 13 lots
  (environ 35 000 tokens par entreprise). Au-delà d'environ 3 M tokens, découper en runs successifs, les lots les
  plus prioritaires d'abord (`--max`, puis `--complement`).
- Repère de qualité : sur les signaux forts contre-vérifiés d'une campagne, 92 confirmés, 11 réfutés (souvent un
  événement de la maison mère attribué à la filiale), 8 incertains.
- Score A, B, C : gratuit, aucune écriture externe sans `--go` (étape 7, accord).
- Commit, seulement sur demande : chemins explicites, jamais `git add -A`.

## Pièges principaux

- LinkedIn qui bloque (cookies, adresse partagée avec des agents) ; URL LinkedIn fausses ou numériques, corrigées
  par la collecte (colonne `linkedin_corrige`).
- Faux rattachements au registre (holdings, acronymes, homonymes radiés) ; fausses dissolutions et fausses fusions
  (republications) ; faux changements de dirigeant (changement de signature).
- Fabricants classés en services par les clauses types du but social ; distributeurs classés fabricants.
- Lexique bruité, homonymes dans les actualités (noms courts : `noms-ambigus.csv`).
- Double comptage registre et agent (réglé par la consolidation).
- `dossiers.py` relancé sans `--complement` : lots, manifeste et `args` effacés, et les anciens runs ne
  correspondent plus aux lots.
- `apply_recherche.py` lancé avec un seul run alors qu'il y en a plusieurs.
- Score A, B, C et tiers confondus ; départ de dirigeant pris pour une accroche ; détections automatiques prises
  pour des signaux.
- `date_reference` figée pendant la veille.
- Limite de session au milieu du workflow : intégrer d'abord les résultats partiels, puis reprendre avec
  `resumeFromRunId`.

Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 5 ».
