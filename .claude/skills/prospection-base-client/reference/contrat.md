# Contrat entre étapes : fichiers, colonnes, clés

Ce que chaque étape écrit et ce que la suivante lit. Les noms de colonnes et les valeurs ci-dessous sont lus par
les scripts : ne pas les renommer. On peut ajouter des colonnes à droite, elles sont gardées ou ignorées. Les listes
de colonnes du contrat sont dans `scripts/commun.py` (`COLONNES_ENTREPRISES`, `COLONNES_CONTACTS`).

## Principes

- **Tout est dans le dossier de la campagne** (`--campagne campagnes/<nom>`), jamais dans le dossier du skill.
- **CSV** : lus en UTF-8 avec ou sans BOM, séparateur virgule ou point-virgule deviné ; écrits en UTF-8 avec BOM
  (`utf-8-sig`, lisible par Excel), séparateur virgule. Un CSV relu par un autre outil doit être lu en `utf-8-sig`,
  sinon la première colonne s'appelle « ﻿nom ».
- **Pays** : code ISO à deux lettres (`CH`, `FR`, `DE`...). **Dates** : `AAAA-MM-JJ` (ou `AAAA-MM` quand le jour est
  inconnu).
- **Clé d'une entreprise** : `id` = slug du nom court, posé par `entites.py` à l'étape 5. C'est la clé de tous les
  caches de l'étape 5 et de tous les fichiers suivants. Ne pas le changer en cours de campagne.
- **Clé d'un contact** : `contact_id` = id Apollo ; pour un contact importé absent d'Apollo, un id local
  `local-<entreprise>-<email ou prénom-nom>` (`ordre_appel.cle_contact`). Les briefs, cartes et rédactions des
  étapes 8 et 9 s'y rattachent.
- **Jointure d'un contact à son entreprise** : `entreprise_id`, sinon le nom normalisé (`commun.norm` : minuscules,
  sans accents ni forme juridique), sinon le domaine du site.
- **La liste lue par l'étape 5** : la plus avancée des trois, `entreprises-verifie.csv`, sinon
  `entreprises-enrichi.csv`, sinon `entreprises.csv` (`Campagne.liste_entreprises()`). Une liste plus avancée restée
  d'une liste précédente fausse donc la suite : refaire les étapes 3 et 4, ou la supprimer, après un nouvel import.

## Arborescence d'une campagne

```
<campagne>/
  campagne.toml                 configuration (copie complétée de config/campagne.exemple.toml)
  persona.md                    persona du décideur validé (étape 1)
  apprentissages.md             enseignements datés de la campagne
  exclure.csv, corrections.csv, arbitrages.csv, noms-ambigus.csv      fichiers facultatifs (section suivante)
  entreprises-toutes.csv        étape 2 : tout ce qui a été trouvé, lisible
  entreprises.csv               étape 2 : la liste retenue, au contrat
  entreprises-linkedin.csv      étape 2 ou 3 : pages LinkedIn lues sur les sites (linkedin_site.py)
  entreprises-enrichi.csv       étape 3
  entreprises-verifie.csv       étape 4
  prospection-signaux.csv       étape 5 ; rapport-signaux.md
  base-abc.csv                  étape 7 ; phrases-a-rediger.csv ; phrases-signal.csv (agent, sur demande)
  donnees/                      decouverte-mentions.json, cache/, verification/, signaux/
  apollo/                       étapes 2, 6 et 7 : contacts, listes, réinjection, cache/
  appels/                       étapes 8 et 9 : ordre d'appel, plan, briefs, cartes, scripts, fichier d'appel
```

## Fichiers à compléter par l'utilisateur (tous facultatifs sauf campagne.toml)

| Fichier | Colonnes ou format | Lu par | Rôle |
|---|---|---|---|
| `campagne.toml` | sections `campagne`, `offre`, `cible`, `persona`, `signaux`, `apollo`, `appels` (schéma : `config/campagne.exemple.toml`) | tous les scripts | configuration |
| `persona.md` | texte libre | l'agent (étapes 1, 5, 6, 9) | persona du décideur validé |
| `exclure.csv` | `nom`, `site` (colonnes devinées : nom, entreprise, company, name... ; site, website, domaine...) | `importer_liste.py`, `consolider_decouverte.py` (défaut de `--exclure`) | nos clients et partenaires actuels, jamais prospectés |
| `corrections.csv` | `nom, site, linkedin` ; une URL remplace, `-` vide, `?` garde avec une confiance basse, `site` (colonne linkedin) relit la page sur le site | `enrichir_sites.py` | corrections manuelles de l'étape 3 |
| `arbitrages.csv` | `nom, champ, valeur, statut, note` ; champ `site`, `linkedin`, `nom_officiel`, `pays`, `ville`, `activite`, `exclure`, `a_revoir` ou `note` ; valeur `aucun` = vide | `verif_appliquer.py` | décisions manuelles de l'étape 4, appliquées en dernier |
| `noms-ambigus.csv` | `nom` | `collect_news.py` | noms trop courants : ville ou pays ajouté aux requêtes |
| `apollo/comptes-manuels.csv` | `entreprise, compte_apollo` | `chercher_contacts.py` | entreprise dont le compte Apollo porte un autre nom |
| `donnees/signaux/logiciels.json` | champs `statut` (`indice` à passer à `probable`, `confirmé` ou `aucun`), `logiciel`, `url`, `extrait`, `relu` = `oui` | `fichier_appel.py` | relecture des logiciels repérés (étape 5) |
| `appels/langue-contacts.json` | `{contact_id: {parle: oui, probable, incertain, peu probable ou non, langue_principale, raison}}` | `ordre_appel.py` | avis sur la langue de chaque contact |
| `appels/corrections.json` | `{id: {pourquoi_maintenant, a_savoir}}` | `fichier_appel.py` | corrections du fichier d'appel |

## Étape 2 : trouver les entreprises

**`entreprises.csv`, `entreprises-enrichi.csv`, `entreprises-verifie.csv`** (les trois listes du contrat). Colonnes
`COLONNES_ENTREPRISES`, dans cet ordre, d'autres colonnes peuvent suivre :

`nom, nom_officiel, pays, ville, canton, region, site, site_statut, site_confiance, linkedin, linkedin_statut,
linkedin_source, linkedin_confiance, secteur, activite, taille, technologies, source, preuve, a_revoir, exclure,
deja_connue, note`

| Colonne | Valeurs |
|---|---|
| `pays` | code ISO |
| `canton`, `region` | Suisse seulement : code du canton ; région linguistique `romande`, `alémanique`, `italienne`, `plurilingue` ou `inconnue` |
| `site` | `https://domaine` |
| `linkedin` | `https://www.linkedin.com/company/<slug>/` |
| `site_statut`, `linkedin_statut` | `trouvé` (donné par la source ou la recherche), `confirmé` (vérifié), `corrigé`, `introuvable`, vide |
| `site_confiance`, `linkedin_confiance` | `haute`, `basse`, `à vérifier`, vide |
| `linkedin_source` | `site web`, `duckduckgo`, `agent`, `apollo`, `liste`, vide |
| `source` | `découverte web (...)`, `apollo`, `liste <fichier>` |
| `preuve` | URL et extrait (« url : « extrait » »), ou `Apollo, compte <id>`, ou `liste <fichier>` |
| `a_revoir` | `oui`, `non`, vide |
| `exclure` | vide = dans la liste ; sinon le motif : `client ou partenaire actuel`, `groupe`, `particulier`, `administration`, `non identifiée`, `fermée`, `doublon`, `aucune preuve vue`, `hors cible (motif)`... |
| `deja_connue` | `oui` ou vide (`--deja`) |

Colonnes en plus : `signaux` (découverte web) ; `compte_apollo, n_contacts` (import) ; dans
`entreprises-verifie.csv`, `verification, site_verif, linkedin_verif, preuve_verification`.

**`entreprises-toutes.csv`** (à relire, pas lu par la suite). Règle : `exclure` vide si et seulement si la ligne est
dans `entreprises.csv`.

- découverte web (`consolider_decouverte.py`) : `nom, autres_noms, pays, ville, canton, region, site, linkedin,
  linkedin_source, secteur, activite, taille, signaux, n_sources, sources, segments, types_preuve, preuve_1_url,
  preuve_1_extrait, preuves_autres, preuve_sur_le_site, controle, deja_connue, exclure, statut`. `statut` : `cible`,
  `hors cible (motif)`, `aucune preuve vue (à vérifier)`, `exclue (client ou partenaire actuel)`, plus « ; déjà dans
  nos listes » ou « ; ajoutée par ... » ; `controle` : ce que le contrôle anti-invention a écarté ;
- liste importée (`importer_liste.py`) : `nom, autres_noms, pays, pays_source, ville, canton, region, site, linkedin,
  secteur, taille, activite, technologies, compte_apollo, n_contacts, fichiers, deja_connue, exclure, statut`
  (`retenue` ou `exclue (...)`).

**`donnees/decouverte-mentions.json`** : toutes les mentions rendues par les agents, avec les notes du contrôle.

**`apollo/contacts-importes.csv`** (export de contacts) : colonnes du contrat des contacts (étape 6), plus
`site_entreprise, stage, dernier_contact`. `tier`, `entreprise_id` et `cibles` restent vides. `ordre` déduit de
l'intitulé (famille d'entrée de `[persona]`), à relire. `statut` : `contact Apollo importé` ou
`importé, absent d'Apollo`. Sans `--ajouter` et sans contact, l'ancien fichier devient
`apollo/contacts-importes.precedent.csv`.

**`entreprises-linkedin.csv`** (`linkedin_site.py`) : le CSV d'entrée, plus `linkedin_company`,
`linkedin_profiles`, `linkedin_companies_all` (séparés par « | »).

## Étape 3 : enrichir site et LinkedIn

**`entreprises-enrichi.csv`** : mêmes colonnes que `entreprises.csv`. Seules les lignes sans site ou sans LinkedIn
sont cherchées ; `site_statut` et `linkedin_statut` `trouvé` ou `introuvable`, confiances, `linkedin_source`,
`a_revoir` = `oui` sans site sûr. Caches : `donnees/cache/enrichir-sites.json` (recherches) et
`donnees/cache/linkedin-sites.json` (pages lues, par domaine, partagé avec `linkedin_site.py`).

## Étape 4 : vérifier par agents

Dans `donnees/verification/` :

- `lots/D01.json`, `L01.json`... (passe 1, profonds et légers), `lots/R01.json`, `C01.json`... (passe 2, résolution
  et complétion) : entités `{key, champs de la liste}` ; en passe 2, plus `alias` et `passe1` ;
- `manifeste-passe1.json` : `[{id, mode (deep ou light), n, file, cles}]` ; `manifeste-passe2.json` :
  `[{id, mode (resolve ou complete), n, file, cles, alias}]` ; `file` relatif au dossier de la campagne ;
- `args-passe1.json`, `args-passe2.json` : les args complets des workflows, à passer tels quels ;
- `entreprises-verifie.precedent.csv` : la version précédente de `entreprises-verifie.csv`.

`entreprises-verifie.csv` : le contrat, puis les autres colonnes de la liste, puis `verification`, `site_verif`,
`linkedin_verif` (statut détaillé : `confirmé`, `confirmé (contrôle léger)`, `corrigé`, `trouvé`, `introuvable`,
`ambigu`, `réfuté`, `incertain`, `non vérifié`, `non contre-vérifié`, `écarté (non vu)`, `page du groupe`...),
`preuve_verification`. `a_revoir` = `oui` si un statut détaillé vaut ambigu, réfuté, incertain, non vérifié, non
contre-vérifié ou écarté (non vu).

## Étape 5 : signaux et priorisation

Dans `donnees/signaux/` :

| Fichier | Écrit par | Contenu |
|---|---|---|
| `entites.json` | `entites.py` | liste `{id, nom, nom_court, autres_noms[], pays, ville, canton, activite, secteur, taille, site, linkedin, site_statut, linkedin_statut, a_revoir, exclure, flags[], note}` ; `flags` : `exclure`, `particulier`, `administration`, `non_identifie`, `fermee_ou_liquidation`, `renommee_ou_absorbee` |
| `zefix.json` | `collect_zefix.py` | par id : correspondance au registre suisse, fiche, publications parsées, signaux |
| `linkedin.json` | `collect_linkedin.py` | par id : page publique (secteur, taille, siège, description, posts datés), statut, slug corrigé |
| `site.json` | `collect_site.py` | par id : stack, mentions tech, recrutement, fraîcheur |
| `news.json` | `collect_news.py` | par id : résultats d'actualités et signaux candidats |
| `lots/L01.json`..., `lots/manifest.json`, `lots/args-recherche.json` | `dossiers.py` | dossiers des agents ; manifeste `[{id, n, file (absolu), ids[]}]` ; args du workflow |
| `recherche.json` | `apply_recherche.py` | `{id: {id, lot, nom_verifie, activite, categorie, effectif_estime, groupe_parent, dans_icp, raison_hors_icp, signaux[{famille, sous_type, date, resume, source_url, confiance, verdict, raison_verdict, date_origine, controle, confiance_origine}], adoption_tech{niveau, preuves[], concurrent, verdict, raison_verdict}, dirigeants[{nom, role, depuis}], pourquoi_maintenant, angle, persona_cible, cibles{entree[{nom, role}], relais[{nom, role}]}, sources[]}}` |
| `signaux.json` | `scorer.py` | `{id: [{famille, sous_type, date, resume, url, confiance (registre, vérifié, agent ou auto), source, niveau, poids}]}` |
| `historique/<date>.json` | `scorer.py` | instantané des signaux pesants, pour la veille |
| `logiciels.json` | `collect_logiciels.py` | `{id: {logiciel, statut (confirmé, probable, indice ou aucun), source, url, extrait, autres[], relu, preuves[], ...}}` |

**`prospection-signaux.csv`** (`scorer.py`), une ligne par entreprise, triée par tier puis score :

`rang, tier, fenetre_opportunite, score, tier_fit, monte_de, fit_icp, timing, tech, nom, pays, canton, secteur,
taille, activite, pourquoi_maintenant, signaux_direction, signaux_financement, signaux_rachat_fusion,
signaux_croissance_projets, signaux_tech, signaux_negatifs, dirigeants, persona_cible, angle, site, linkedin,
linkedin_corrige, registre, motifs_exclusion, recherche_agent, sources, id`

- `tier` : `A`, `B`, `C`, `D`, `Hors cible` (un motif dans `motifs_exclusion`) ;
- `score` = 2 x fit + moment + 0,8 x tech ; `fenetre_opportunite` = `oui` si tier A ou B et moment d'au moins 5 ;
- `persona_cible` : « Entrée : Prénom Nom (rôle) ; relais : rôle, rôle » ; `angle` : hypothèse d'usage au
  conditionnel ; `linkedin` porte déjà l'URL corrigée, `linkedin_corrige` vaut `oui` dans ce cas.

**`rapport-signaux.md`** : tiers, fiches du tier A, tableau du tier B, nouveaux signaux (veille), alertes,
concurrents, pages LinkedIn corrigées, méthode.

## Étape 6 : contacts Apollo

Dans `apollo/` :

| Fichier | Écrit par | Colonnes ou format |
|---|---|---|
| `comptes-a-importer.csv` | `creer_comptes.py` | `rang, tier, Company Name, Website, Company Linkedin Url, pays, canton, pourquoi_maintenant, id, account_id, statut` |
| `cibles.json` | `extraire_personas.py` | `[{id, nom, tier, pays, domaine, site, linkedin, persona_cible, source_cibles, hors_cible_selon_persona, cibles[{type (personne ou rôle), nom, famille, familles[], role_texte, ordre, vu_dans_dirigeants}]}]` |
| `cibles-apercu.csv` | `extraire_personas.py` | `tier, entreprise, id, domaine, source, type, personne, famille, role_texte, ordre, vu_dans_dirigeants` |
| `contacts-a-valider.csv` (`-test` avec `--entreprises`) | `chercher_contacts.py` | `garder, tier, entreprise, entreprise_id, cibles, ordre, confiance, prenom, nom_masque, titre, email_dispo, employeur_apollo, apollo_id, compte_apollo, account_id, note, domaine, linkedin` |
| `couverture.csv` (`-test`) | `chercher_contacts.py` | `tier, entreprise, entreprise_id, compte_apollo, recherche, personnes_apollo, cibles, trouvees, nommees, non_trouvees` |
| `comptes-apollo.json` | `chercher_contacts.py` | comptes de la liste, tels qu'Apollo les renvoie (lus pour le standard et le code postal) |
| `trouves-web.json` | `chercher_web.py` | `[{id, entreprise, cible, ordre, nom, statut, linkedin, poste, entreprise_linkedin, source}]` |
| `contacts-crees.csv` | `enrichir_et_creer.py` | `COLONNES_CONTACTS` puis `site_entreprise` |
| `listes/<nom-de-la-liste>.csv` | `exporter_listes.py` | `tier, entreprise, entreprise_id, ordre, prenom, nom, titre, email, statut_email, linkedin, telephone_standard, telephone_direct, mobile, ville, pays, cibles, contact_id, statut, stage, dernier_contact` |
| `cache/` | `apollo_api.py`, `chercher_web.py` | réponses Apollo (`<hash>.json`, `webhook-<id>.json`) et recherches web (`web.json`) |

**Contacts** (`contacts-crees.csv`, `contacts-importes.csv`) : colonnes `COLONNES_CONTACTS`,

`tier, entreprise, entreprise_id, ordre, cibles, prenom, nom, titre, seniorite, email, statut_email, linkedin, ville,
pays, contact_id, statut`

- `ordre` : `entrée` ou `relais` ; `pays` : code ISO ; `statut_email` en minuscules (`verified`, `extrapolated`,
  `unavailable`, `user managed`...) ; `seniorite` : valeur Apollo (`owner`, `founder`, `c_suite`, `partner`, `vp`,
  `head`, `director`, `manager`, `senior`, `entry`, `intern`) ;
- `statut` (`contacts-crees.csv`) : `créé`, `créé sans email (...)`, `créé (dirigeant basé à l'étranger : ...)`,
  `déjà dans Apollo, ajouté aux listes`, `non créé (basé à l'étranger : ...)`, `non enrichi (introuvable)`.

**Listes Apollo** : nom de base = `[apollo] liste_contacts` (« Segment · Persona · Mois ») ; le script crée
« <nom> », « <nom> - entrée » et « <nom> - relais ». Nom du fichier d'export : minuscules sans accents, tout autre
caractère remplacé par un tiret (« Industrie · Direction · Novembre - entrée » donne
`industrie-direction-novembre-entree.csv`).

## Étape 7 : réinjecter dans Apollo

| Fichier | Colonnes |
|---|---|
| `base-abc.csv` | `rang, score_abc, raison_abc, tier, nom, signal_et_date, source_signal, phrase_signal, pourquoi_maintenant, site, id` |
| `phrases-a-rediger.csv` | `id, nom, signal_et_date, source_signal, phrase_signal` (comptes A sans phrase) |
| `phrases-signal.csv` | mêmes colonnes, `phrase_signal` rempli (écrit par un agent, sur demande) |
| `apollo/reinjection.csv` | `contact_id, First Name, Last Name, Email, Company Name, ordre, entreprise_id, signal_et_date, source_signal, phrase_signal, score_abc` |
| `apollo/champs-apollo.json` | `{signal_et_date, source_signal, phrase_signal, score_abc}` : ids des champs de contact Apollo |

`score_abc` : `A` (on contacte), `B` (en veille), `C` (hors cible). Champs de contact Apollo de même nom :
`signal_et_date`, `source_signal`, `phrase_signal` (texte long), `score_abc` (texte).

## Étape 8 : séquence et ordre d'appel

| Fichier | Écrit par | Colonnes |
|---|---|---|
| `appels/ordre-appel.csv` (`ordre-appel-relais.csv` avec `--liste relais`) | `ordre_appel.py` | `priorite, langue, parle_langue_appel, langue_principale, avis_langue, score_langue, indices_langue, telephone, type_telephone, tier, rang_entreprise, fenetre_opportunite, entreprise, entreprise_id, pays_entreprise, prenom, nom, titre, email, statut_email, linkedin, ville, pays, deja_contacte, a_eviter, pourquoi_maintenant, angle, ordre, cibles, contact_id` |
| `appels/plan-sequence.csv` | `plan_sequence.py` | `vague, j1, j4, j8, j15, j22, etapes, score_abc, rang, tier, entreprise, entreprise_id, voix, ordre, condition, prenom, nom, titre, email, statut_email, telephone, linkedin, canal, signal, source, phrase_signal, pourquoi_maintenant, deja_contacte, remarque, contact_id` |

- `parle_langue_appel` : `oui`, `probable`, `incertain`, `non` (vide si `[appels] langues` est vide) ;
  `type_telephone` : `mobile`, `ligne directe`, `standard`, `aucun` ;
- `vague` : numéro, ou `hors plan` ; `canal` : `email`, `appel`, `LinkedIn`, `aucun` (à éviter, hors plan).

Export de l'interface Apollo (`--export`) : en-têtes anglais d'Apollo, dont `Apollo Contact Id`, `First Name`,
`Last Name`, `Title`, `Mobile Phone`, `Work Direct Phone`, `Corporate Phone`, `Company Phone`, `Stage`,
`Last Contacted`, `Email Sent`, `Email Open`, `Email Bounced`, `Replied`.

## Étape 9 : scripts et fichier d'appel

| Fichier | Écrit par | Format |
|---|---|---|
| `appels/briefs/L<n>.json` | `fichier_appel.py briefs` | une fiche par entreprise : `id, entreprise, tier, pays, code_pays, canton_ou_departement, ville, lieux_a_eviter, categorie, activite, linkedin, apollo, effectif_sources, groupe_parent, signaux_dates, tech, finances, logiciels, pourquoi_maintenant, angle, a_ne_jamais_evoquer, relais, contacts[{contact_id, prenom, nom, note_nom, titre, langue, deja_contacte, faits_personne, carte_existante, absent_d_apollo}]` |
| `appels/briefs/contexte.json` | `fichier_appel.py briefs` | `campagne, date_reference, offre{societe, description, argument_cle, preuves, appelant, ne_jamais_dire, concurrents}, persona{entree, relais}, langues_appelant, langue_redaction, consignes` |
| `appels/cartes/L<n>.json` ou `appels/cartes-appel.json` | agent (`consignes/cartes-appel.md`) | `[{contact_id, pourquoi_vous, relance, routage, nom_a_utiliser?, civilite?, preuve?, objection_probable?, exemple_pour_eux?, a_savoir?[]}]` |
| `appels/redaction/L<n>.json` | agent (`consignes/fichier-appel-redaction.md`) | `[{id, secteur, description, taille, pourquoi_maintenant, contacts[{contact_id, argument}]}]` |
| `appels/sources/briefs/L<n>.json` | `fichier_appel.py sources` | par entreprise : `faits_entreprise` numérotés (`S1`... signaux datés, `A` activité, `L` LinkedIn, `E` logiciel, `T1`... tech) ; par contact : `argument_actuel`, `faits_personne` (`P1`...) |
| `appels/sources/redaction/L<n>.json` | agent (`consignes/fichier-appel-sources.md`) | `[{contact_id, argument, source_id}]` |
| `appels/scripts-appel.md`, `appels/scripts-appel.csv` | `scripts_appel.py` | `.md` : tronc commun puis une fiche par contact ; `.csv` : `priorite, contact_id, nom, entreprise, script, a_savoir` |
| `appels/fichier-appel.xlsx`, `appels/fichier-appel.csv` | `fichier_appel.py assembler` | onglets Appels, Relais, Lisez-moi ; colonnes de l'onglet Appels et du CSV : voir l'étape 9 |
| `appels/precedent/<date-heure>/` | `fichier_appel.py briefs` | lots d'une passe précédente, rangés quand le découpage change |

Le numéro de lot relie tout : une carte, une rédaction ou une source n'est reprise que du lot de même numéro que
le brief où se trouve le contact.

## Configuration : qui lit quoi

| Clé de `campagne.toml` | Lue par |
|---|---|
| `campagne.nom`, `campagne.date_reference` | rapports, fenêtres de récence (étape 5), score A, B, C (étape 7), début du plan (étape 8) |
| `offre.*` | workflows (contexte des agents), `dossiers.py`, `scripts_appel.py`, `fichier_appel.py` |
| `cible.*` | `icp.py` (fit et motifs d'exclusion), workflows, `enrichir_sites.py` (pays par défaut), `collect_linkedin.py` (ordre), filtre de pays des contacts à défaut d'`apollo.pays_contacts` |
| `persona.entree`, `persona.relais`, `persona.titres` | `persona.py` : `importer_liste.py`, `extraire_personas.py`, `chercher_contacts.py`, `chercher_web.py`, `enrichir_et_creer.py`, `scorer.py`, `dossiers.py` |
| `signaux.fenetre_mois`, `signaux.registre_suisse`, `signaux.logiciels` | collectes et workflow de l'étape 5, `collect_logiciels.py`, `extraire_personas.py`, `fichier_appel.py` |
| `apollo.liste_comptes`, `apollo.liste_contacts`, `apollo.pays_contacts`, `apollo.mobiles` | étape 6 ; `ordre_appel.py` (nom de l'export de liste) |
| `appels.langues` | `ordre_appel.py`, `chercher_web.py` (langue par défaut), `fichier_appel.py` (langue de rédaction) |

## Données nominatives (git)

Les dossiers `apollo/` et `appels/`, les caches et les CSV de contacts contiennent des noms, des emails et des
téléphones. Trancher leur sort git avec l'utilisateur dès le départ. Bloc à **proposer** (ne pas l'écrire sans son
accord) :

```gitignore
.env
campagnes/*/apollo/
campagnes/*/appels/
campagnes/*/donnees/
campagnes/*/*.csv
```

Restent alors versionnés `campagne.toml`, `persona.md`, `apprentissages.md` et `rapport-signaux.md` (à vérifier :
il cite des dirigeants). Sans réponse : ne pas toucher au `.gitignore`, et à chaque commit demandé, lister les
fichiers un par un.
