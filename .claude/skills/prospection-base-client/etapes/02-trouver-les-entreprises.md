# Étape 2 : trouver les entreprises

Commandes depuis la racine du projet, skill supposé dans `.claude/skills/prospection-base-client/` (sinon,
adaptez ce chemin, voir l'étape 1). `<nom>` : le dossier de la campagne.

## Objectif

Constituer la liste d'entreprises de la campagne, chacune avec une preuve, dans deux fichiers :
- `entreprises-toutes.csv` : tout ce qui a été trouvé, avec un statut (retenue, hors cible, sans preuve vue,
  exclue, déjà connue). C'est le fichier à relire ;
- `entreprises.csv` : la liste retenue, au contrat que lisent les étapes 3 à 5 (colonnes
  `commun.COLONNES_ENTREPRISES`, dans cet ordre : `nom, nom_officiel, pays, ville, canton, region, site,
  site_statut, site_confiance, linkedin, linkedin_statut, linkedin_source, linkedin_confiance, secteur, activite,
  taille, technologies, source, preuve, a_revoir, exclure, deja_connue, note`).

Deux voies, choisies à l'étape 1 :
- **voie 1, découverte web par agents** (par défaut, quand on part d'une cible sans liste) ;
- **voie 2, liste existante ou export Apollo** (« Extraire » de la formation).

Les deux se combinent avec `--ajouter`.

## Entrées

- `campagnes/<nom>/campagne.toml` (étape 1) : `[cible]` et `[offre]` pour la voie 1, `[persona]` pour l'ordre des
  contacts importés ;
- `campagnes/<nom>/exclure.csv` (étape 1), lu par défaut par les deux scripts ;
- nos listes déjà prospectées, pour `--deja` (facultatif) ;
- voie 1 : les segments, l'accord explicite de l'utilisateur ;
- voie 2 : un ou plusieurs CSV (export Apollo de comptes ou de contacts, ou toute liste qui a une colonne de nom
  d'entreprise).

## Déroulé, voie 1 : découverte web par agents

1. **Cadrer les segments** avec l'utilisateur : 6 à 12 croisements « secteur, zone », un agent chacun. Exemples :
   « Décolletage, Jura et Jura bernois », « Microtechnique, canton de Neuchâtel », « Dispositifs médicaux, Vaud et
   Genève ». Un segment trop large dilue la recherche ; trop étroit, l'agent s'épuise en quelques requêtes.
   Les signaux d'achat de `persona.md` peuvent inspirer des segments (entreprises qui recrutent, qui ouvrent un
   site...).

2. **Repérer les bonnes listes** par 5 à 10 recherches web : associations professionnelles, chambres de commerce,
   parcs technologiques et clusters, salons de la zone. Une liste riche (annuaire de membres, liste d'exposants)
   devient une source transverse dans `args.sources` : `{id, titre, consigne}`, avec l'URL de départ dans la
   consigne. Sans `sources`, trois sources par défaut : listes d'exposants des salons, annuaires d'associations et
   de clusters, offres d'emploi de la zone.

3. **Estimer le coût et obtenir l'accord.** Agents d'un run : un par segment, un par source transverse (3 par
   défaut), une critique de couverture, puis jusqu'à `max_complements` compléments (6 par défaut). Repère mesuré :
   environ 190 000 tokens par agent, soit environ 6 000 par entreprise unique trouvée. Exemple : 8 segments
   + 3 sources + 1 critique + 6 compléments = 18 agents, environ 3,4 M tokens. Au-delà d'environ 3 M, lancer deux
   workflows successifs, les segments les plus prometteurs d'abord. Durée non mesurée précisément : compter de
   l'ordre d'une à deux heures pour une vingtaine d'agents. Au plus 6 agents tournent en même temps (observé).

4. **Lancer le workflow** avec l'outil Workflow de Claude Code : `scriptPath` = chemin absolu de
   `.claude/skills/prospection-base-client/workflows/decouverte-entreprises.js`. Il se lance tel quel, tout passe
   par `args` (charger le skill `workflow-authoring` seulement pour le modifier). Exemple d'`args` :

   ```json
   {"racine": "/chemin/absolu/du/projet",
    "campagne": "campagnes/<nom>",
    "icp": "PME industrielles de 10 à 200 personnes qui fabriquent en Suisse romande (mécanique, décolletage, microtechnique, dispositifs médicaux, électronique).",
    "exclusions": ["distributeurs et revendeurs sans production", "groupes de plus de 1 000 personnes"],
    "contexte": "Exemple SA, à Lausanne, édite un logiciel qui planifie la maintenance préventive des machines dans les PME industrielles.",
    "segments": ["Décolletage, Jura et Jura bernois", "Microtechnique, canton de Neuchâtel"],
    "sources": [{"id": "salon-x", "titre": "Exposants du salon X", "consigne": "Liste des exposants du salon X (édition récente), à partir de https://... : recense les exposants de la cible."}]}
   ```

   - obligatoires : `racine` (chemin absolu du projet), `campagne`, `icp` (reprendre `cible.description`),
     `contexte` (qui prospecte et pour vendre quoi : `offre.societe` et `offre.description`), `segments` ;
   - facultatifs : `exclusions` (reprendre `cible.exclusions`), `sources`, `max_complements` (défaut 6 ; 0 = ni
     critique ni compléments), `cible_par_agent` (défaut 40), `python` (défaut `<racine>/.venv/bin/python`),
     `skill` (défaut `<racine>/.claude/skills/prospection-base-client` : à donner si le skill est ailleurs).

   Chaque agent rend, par entreprise : nom, ville, pays, site et page LinkedIn seulement s'il les a vus, secteur,
   activité, taille publiée, type de source, URL de preuve et extrait littéral (30 mots au plus), un signal récent
   s'il en croise un, et un motif `hors_cible` le cas échéant. Une critique de couverture lit le bilan et lance
   les compléments. Le workflow n'écrit aucun fichier.

5. **Suivre l'avancement** sans déranger l'utilisateur. L'outil Workflow donne un `runId` (`wf_...`). Dossier du
   run, quelle que soit la session :

   ```bash
   D=$(find ~/.claude/projects -type d -path '*workflows*' -name '<runId>')
   ```

   Point d'avancement (fait, en cours, échecs), à donner quand l'utilisateur demande où on en est :

   ```bash
   .venv/bin/python - "$D/journal.jsonl" <<'EOF'
   import json, sys
   from collections import Counter
   lab, etat = {}, {}
   for ligne in open(sys.argv[1], encoding="utf-8"):
       e = json.loads(ligne)
       t, a = e.get("type"), e.get("agentId")
       if not a:
           continue
       if t == "started":
           lab[a] = e.get("label") or e.get("key") or a
           etat[lab[a]] = "en cours"
       elif t in ("result", "failed"):
           etat[lab.get(a, a)] = "fait" if t == "result" else "échec"
   print(dict(Counter(etat.values())))
   print("en cours :", [k for k, v in etat.items() if v == "en cours"])
   print("échecs :", [k for k, v in etat.items() if v == "échec"])
   EOF
   ```

   Après une coupure (limite de session) : outil Workflow avec le même `scriptPath`, `resumeFromRunId` et les mêmes
   `args`. Les agents terminés sont rejoués depuis le cache ; la consolidation ne les compte qu'une fois.

6. **Consolider** (sans réseau ni LLM) :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/consolider_decouverte.py --campagne campagnes/<nom> "$D" [--deja <liste.csv>]...
   ```

   Passez le dossier du run (ou son `journal.jsonl` en place), plusieurs runs si besoin. Le script :
   - fait le **contrôle anti-invention** : un site, une page LinkedIn, une URL de preuve ou de signal absents des
     sorties d'outils de l'agent (transcripts `agent-<id>.jsonl` du dossier du run) sont écartés ; une
     entreprise sans aucune preuve vue sort de la liste ;
   - dédoublonne par nom normalisé, puis par domaine ;
   - classe hors cible seulement si la majorité des mentions le dit ;
   - ajoute canton et région linguistique pour la Suisse (répertoire officiel des localités du skill) ;
   - retire `exclure.csv` et marque les entreprises de `--deja`.

   Options : `--exclure <csv>` (répétable, à la place du fichier par défaut), `--linkedin <csv>`,
   `--garder-hors-cible`, `--garder-non-vues`, `--ajouter`. Un journal copié hors de son dossier de run ne peut
   plus être contrôlé : le script le signale.

7. **Compléter les pages LinkedIn manquantes** (gratuit), en les lisant sur les sites :

   ```bash
   .venv/bin/python .claude/skills/prospection-base-client/scripts/linkedin_site.py --campagne campagnes/<nom>
   ```

   Il lit `entreprises.csv` et écrit `entreprises-linkedin.csv` (cache par domaine dans `donnees/cache/`). Relancez
   ensuite la commande du point 6 : elle lit `entreprises-linkedin.csv` sans option.

8. **Relire et compter**, puis présenter un bilan chiffré : dans la cible, hors cible et motifs, sans preuve vue,
   exclues, déjà connues, sans site, sans LinkedIn.

   ```bash
   .venv/bin/python -c "import csv, collections; r = list(csv.DictReader(open('campagnes/<nom>/entreprises-toutes.csv', encoding='utf-8-sig'))); print(len(r), 'entreprises :', collections.Counter(x['statut'] for x in r).most_common())"
   .venv/bin/python -c "import csv; r = list(csv.DictReader(open('campagnes/<nom>/entreprises.csv', encoding='utf-8-sig'))); print(len(r), 'retenues ;', sum(not x['site'] for x in r), 'sans site ;', sum(not x['linkedin'] for x in r), 'sans LinkedIn ;', sum(x['deja_connue'] == 'oui' for x in r), 'déjà connues')"
   ```

   Suite : l'étape 3 est inutile (les sites ont été vus par les agents). L'étape 4 est facultative : un contrôle
   léger (`verif_preparer.py --mode leger`) ou une simple complétion (`verif_passe2.py` sans passe 1).

## Déroulé, voie 2 : liste existante ou export Apollo

### Extraire avec Apollo (formation, slides 29 et 30)

1. **Traduire le persona en filtres** : localisation ; effectif et secteur de la cible, pas plus large ;
   technologies qui rendent l'offre utile ; fonction et ancienneté du décideur (intitulés de `persona.md`) ;
   signal de croissance (l'entreprise recrute) ; pour les contacts, emails vérifiés uniquement. Repère de la
   formation : 30 comptes bien choisis valent mieux que 500.
2. **Nommer la liste** « Segment · Persona · Mois » (exemple : « Industrie · Direction · Novembre ») : on sait
   toujours d'où vient chaque contact. C'est aussi la convention de `apollo.liste_contacts` (étape 6).
3. **Exporter en CSV** depuis l'interface Apollo : comptes, ou contacts avec leur entreprise. La recherche est
   gratuite ; selon l'abonnement, l'export ou l'affichage des emails peut consommer des crédits : lire le compteur
   affiché par Apollo et obtenir l'accord de l'utilisateur avant de valider.

Petits volumes (une trentaine de comptes) : le connecteur MCP Apollo peut chercher en langage courant, chaque
action validée ; les crédits s'affichent avant toute dépense. Il coûte cher en contexte (environ 8 000 tokens par
recherche) : à réserver aux petits volumes. Au-delà, scripts et exports.

### Mettre la liste au contrat

```bash
.venv/bin/python .claude/skills/prospection-base-client/scripts/importer_liste.py --campagne campagnes/<nom> <export1.csv> [<export2.csv> ...] [--deja <liste.csv>]... [--col-nom "<en-tête>"] [--ajouter]
```

- Lit les CSV en virgule ou point-virgule, utf-8 avec ou sans BOM. En-têtes Apollo reconnus sans tenir compte de
  la casse (`Company Name`, `Website`, `Company Linkedin Url`, `Company City`, `Company Country`, `# Employees`,
  `Industry`, `Short Description`, `Keywords`, `Technologies`, `Apollo Account Id`, et pour les contacts
  `First Name`, `Last Name`, `Title`, `Seniority`, `Email`, `Email Status`, `Person Linkedin Url`, `City`,
  `Country`, `Apollo Contact Id`, `Stage`, `Last Contacted`), puis les noms usuels d'une autre liste. `--col-nom`
  si le nom d'entreprise n'est pas reconnu.
- Dédoublonne par domaine, puis par nom ; retire `exclure.csv` (ou `--exclure <csv>`, répétable) ; marque
  `--deja`. Sans réseau.
- Un export de contacts donne aussi `apollo/contacts-importes.csv` : `ordre` = entrée si l'intitulé relève de la
  famille `persona.entree` (ou séniorité Apollo owner, founder ou partner), relais sinon. **À relire.** Les
  colonnes `tier`, `entreprise_id` et `cibles` restent vides (étapes 5 et 6). L'étape 6 ne sert alors qu'aux rôles
  manquants.
- Ensuite : étape 3 si des sites manquent (`a_revoir` = oui pour les lignes sans site), puis étape 4.

## Combiner les deux voies : --ajouter

`--ajouter` (dans les deux scripts) garde les fichiers existants et n'y ajoute que les entreprises nouvelles (même
nom normalisé ou même domaine = déjà présente) et, pour l'import, les contacts nouveaux (même id Apollo, même email,
ou même nom dans la même entreprise = déjà présent). Une entreprise écartée avant et retenue cette fois est marquée
« ajoutée par » dans `entreprises-toutes.csv` ; une entreprise exclue comme client ou partenaire actuel le reste.

Ordre conseillé : la découverte d'abord, LinkedIn compris (points 6 et 7), puis l'import avec `--ajouter`. Une
consolidation relancée sans `--ajouter` reconstruit `entreprises.csv` à partir des seuls journaux : les entreprises
importées en seraient retirées.

Sans `--ajouter`, les fichiers sont remplacés, et :
- un ancien `apollo/contacts-importes.csv` est renommé `contacts-importes.precedent.csv` (consolidation, ou import
  sans contact), car il ne correspond plus à la liste ;
- les deux scripts signalent un `entreprises-enrichi.csv` ou un `entreprises-verifie.csv` restés d'une liste
  précédente. L'étape 5 lit toujours la liste la plus avancée : refaire les étapes 3 et 4, ou retirer ces fichiers.

## Sorties

- `entreprises-toutes.csv` (à relire), une ligne par entreprise :
  - voie 1 : `nom, autres_noms, pays, ville, canton, region, site, linkedin, linkedin_source, secteur, activite,
    taille, signaux, n_sources, sources, segments, types_preuve, preuve_1_url, preuve_1_extrait, preuves_autres,
    preuve_sur_le_site, controle, deja_connue, exclure, statut` ; `statut` : cible, hors cible (motif), aucune
    preuve vue (à vérifier), exclue (client ou partenaire actuel), avec « déjà dans nos listes » le cas échéant ;
    `controle` dit ce que le contrôle anti-invention a écarté ;
  - voie 2 : `nom, autres_noms, pays, pays_source, ville, canton, region, site, linkedin, secteur, taille, activite,
    technologies, compte_apollo, n_contacts, fichiers, deja_connue, exclure, statut` (retenue ou exclue).
  Règle : `exclure` vide si et seulement si l'entreprise est dans `entreprises.csv`.
- `entreprises.csv` (au contrat), puis `signaux` (voie 1) ou `compte_apollo, n_contacts` (voie 2). `source` :
  « découverte web (...) », `apollo` ou « liste <fichiers> » ; `preuve` : « url : « extrait » », « Apollo, compte
  <id> » ou « liste <fichiers> » ; `site_statut` « trouvé » quand la source donne un site ; `site_confiance`
  « haute » si la preuve de la découverte est sur le site, sinon « à vérifier » ; `linkedin_source` « agent »,
  « site web », `apollo` ou `liste` ; `a_revoir` = oui sans site.
- `donnees/decouverte-mentions.json` (voie 1) : toutes les mentions, avec les notes du contrôle.
- `entreprises-linkedin.csv` (voie 1, point 7) et son cache `donnees/cache/linkedin-sites.json`.
- `apollo/contacts-importes.csv` (voie 2, export de contacts) : `tier, entreprise, entreprise_id, ordre, cibles,
  prenom, nom, titre, seniorite, email, statut_email, linkedin, ville, pays, contact_id, statut`, puis
  `site_entreprise, stage, dernier_contact`.

## Contrôles qualité

- **Échantillon** : ouvrir la preuve et le site de 10 lignes prises au hasard. Une preuve introuvable ou un site
  d'homonyme suffit à prévoir la vérification de l'étape 4 sur tout le lot. Pour un export Apollo, contrôler aussi
  10 sites et 10 pages LinkedIn.
- **Anti-invention** (voie 1) : lire la ligne « contrôle anti-invention » de la consolidation. Beaucoup de valeurs
  écartées chez un même agent signalent plutôt des sorties d'outils tronquées qu'une invention : vérifier quelques
  cas à la main avant de conclure.
- **Doublons** : un même domaine est fusionné ; deux noms sans site pour une même entreprise (raison sociale et
  marque) restent séparés. Les chercher à la relecture (même ville, noms proches). Après la dernière
  consolidation, écrire « doublon » dans la colonne `exclure` de la ligne en trop : l'étape 5 l'ignore.
- **Hors cible** : relire les motifs ; une filiale autonome peut cacher une PME de la cible (`--garder-hors-cible`
  au besoin).
- **Couverture** : les agents trouvent d'abord les entreprises visibles (sites, salons, annuaires). Si la zone
  compte beaucoup de petits sous-traitants sans site, prévoir un segment ou une source « registre du commerce ».
  Dire à l'utilisateur ce qui n'a pas été couvert (tâches non lancées, agents en échec : dans le résultat du
  workflow).
- **Contacts importés** : relire la colonne `ordre` (un « Directeur » seul, un président non exécutif, un
  directeur financier peuvent être mal rangés).
- **Compter par script** (point 8) avant d'annoncer un chiffre.

## Coûts et accords

- Voie 1 : workflow multi-agents, **accord explicite** de l'utilisateur, estimation à l'appui (point 3). 0 crédit
  Apollo ; recherche web, WebFetch et DuckDuckGo.
- Voie 2 : les scripts sont gratuits ; l'export Apollo peut consommer des crédits selon l'abonnement : accord
  avant de valider.
- Consolidation, import et lecture des LinkedIn sur les sites : gratuits, relançables à volonté (caches).

## Pièges principaux

- Agent qui devine un site à partir du nom : écarté par le contrôle anti-invention.
- Sorties d'outils tronquées (sortie longue enregistrée dans un fichier que l'agent n'a pas relu) : valeurs justes
  écartées. Le prompt demande de tronquer et de relire ; la consolidation lit aussi le fichier complet.
- Journal copié hors de son dossier de run : plus de contrôle possible.
- Offres d'emploi de cabinets de recrutement (client anonyme), filiales commerciales de groupes étrangers,
  distributeurs sans production : hors cible ou sans valeur.
- Doublons sous deux noms, fatigue des agents (liste qui paraît complète), biais de visibilité.
- Exports Apollo : séniorité et statut d'email écrits autrement que par l'API (« Verified », « User Managed ») ;
  « User Managed » n'est pas un email vérifié.
- Pays absent de la table des pays de `commun.py` : code vide, valeur d'origine gardée dans `pays_source`.
- Relance de la consolidation sans `--ajouter` après un import : les entreprises importées disparaissent.
- Anciennes listes enrichie ou vérifiée laissées en place : l'étape 5 lirait une liste périmée.

Détail et parades : [../reference/pieges.md](../reference/pieges.md), section « Étape 2 ».
