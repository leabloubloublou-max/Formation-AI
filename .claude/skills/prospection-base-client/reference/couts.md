# Coûts : ratios pour estimer tokens, durées et crédits

Ratios mesurés sur des campagnes réelles (quelques centaines d'entreprises), arrondis. Ce sont des ordres de
grandeur pour une estimation honnête avant un accord, pas des promesses : les estimations se trompent quand le
périmètre grandit en route (voir la fin). Compter par script le périmètre réel avant de calculer.

## Ce qui coûte quoi

| Ressource | Où | Gratuit ? |
|---|---|---|
| Tokens de sous-agents | workflows (étapes 2, 4, 5), agents de rédaction (étapes 7 à 9) | non : accord explicite avant tout lancement |
| Crédits Apollo | enrichissement des contacts et mobiles (étape 6) | non : aperçu chiffré, puis accord |
| Recherche web (DuckDuckGo), registre suisse, LinkedIn en vue invité, sites | étapes 3, 5, 6 | oui, mais lent (temps machine) |
| API Apollo hors enrichissement (recherche de personnes, comptes, contacts, listes, champs, séquences, tâches) | étapes 6 à 9 | oui (0 crédit), mais les écritures demandent un accord |
| Scripts sans réseau (consolidation, vérification, score, ordre d'appel, plan, scripts d'appel, fichier d'appel) | toutes les étapes | oui, quelques secondes |

## Tokens des workflows et des agents

| Étape | Ratio | Exemple |
|---|---|---|
| 2. Découverte web (`decouverte-entreprises.js`) | environ 190 000 tokens par agent ; environ 6 000 par entreprise unique trouvée | agents = segments + sources transverses + 1 critique + compléments (6 au plus par défaut) : 8 segments + 3 sources + 1 + 6 = 18 agents, environ 3,4 M tokens |
| 4. Vérification, passe 1 (`verification.js`) | environ 4 500 tokens par entité | 1 agent profond pour 25 entités, 1 agent léger pour environ 90, 1 contre-vérificateur pour 40 URL proposées ; environ 1 URL proposée pour 2 entités rendues |
| 4. Vérification, passe 2 (`verification-passe2.js`) | environ 10 000 tokens par entité restée ouverte | 1 contre-vérificateur pour 30 URL ; en général moins d'un cinquième des entités |
| 4. Vérification, deux passes | environ 6 500 tokens par entité | 380 entités : environ 2,4 M tokens, 21 agents, environ 45 minutes |
| 5. Recherche de signaux (`signaux-recherche.js`) | environ 31 000 tokens par entreprise recherchée (35 000 avec une reprise après coupure) ; environ 13 appels d'outils par entreprise | 0,5 M par lot de 15 (un agent de recherche et un contre-vérificateur) ; 180 entreprises : environ 6,4 M tokens |
| 8. Avis de langue par agents (facultatif) | non mesuré | quelques agents indépendants sur la liste d'entrée |
| 9. Rédaction du fichier d'appel (rédaction puis sources) | environ 15 000 tokens par contact | une centaine de contacts : 8 agents, environ 1,5 M tokens |
| 9. Cartes d'appel | non mesuré à part | compter le même ordre que la rédaction |
| Connecteur MCP Apollo | environ 8 000 tokens par recherche de personnes | 120 entreprises : 1 à 1,5 M tokens, contre presque rien en script |

`verif_preparer.py` et `verif_passe2.py` affichent eux-mêmes un ordre de grandeur en tokens d'après leurs lots.

## Durées

Scripts gratuits (temps machine, sans tokens) :

| Script | Ratio | Exemple |
|---|---|---|
| `enrichir_sites.py` (4 en parallèle) | environ 3 secondes par nom | 360 noms : environ 18 minutes |
| `linkedin_site.py` (12 en parallèle) | une à quelques secondes par site | quelques minutes pour quelques centaines de sites |
| `collect_zefix.py` (4 en parallèle) | moins d'une seconde par entreprise | 350 entreprises : environ 2 minutes |
| `collect_linkedin.py` (séquentiel) | 2 à 3 pages par minute, plus les pauses après blocage | 290 pages : environ 1 h 40 ; le plus lent, en arrière-plan |
| `collect_site.py` (8 en parallèle) | moins d'une seconde par site | 290 sites : environ 3 minutes |
| `collect_news.py` (3 en parallèle) | environ 12 secondes par entreprise (4 requêtes) | 150 entreprises : environ 30 minutes |
| `collect_logiciels.py` (3 en parallèle) | environ 10 secondes par entreprise (3 ou 4 requêtes) | 120 entreprises : environ 20 minutes |
| `chercher_contacts.py` | environ 2,5 appels par entreprise | 120 entreprises : environ 300 appels, environ 3 minutes ; relance depuis le cache presque instantanée |
| `chercher_web.py` | 3 à 4 secondes par requête (pause de 1,2 s) | 260 requêtes : environ 15 minutes |
| scripts sans réseau | quelques secondes | |

Workflows (6 agents au plus en même temps) :

| Workflow | Repère |
|---|---|
| Découverte | non mesuré précisément : de l'ordre d'une à deux heures pour une vingtaine d'agents |
| Vérification | passe 1 (14 agents) : environ 25 minutes ; passe 2 (7 agents) : environ 20 minutes |
| Recherche de signaux | environ 30 à 45 minutes pour une dizaine de lots ; un lot complémentaire de 2 agents : environ 30 minutes |

Une étape 5 complète (collectes, workflow, score) sur environ 350 entreprises a pris environ 2 h 40, dont une
demi-heure bloquée par une limite de session.

## Crédits Apollo

| Action | Crédits |
|---|---|
| Recherche de personnes, comptes, contacts, listes, champs personnalisés, séquences, tâches | 0 |
| Enrichissement d'une personne trouvée (`people/bulk_match`) | 1, même sans email ; 0 si non trouvée |
| Mobile demandé dès le premier enrichissement | 8 de plus par numéro trouvé |
| Mobile demandé après coup | jusqu'à 9 par personne (1 + 8) |
| Email personnel | payant : jamais demandé |
| Options waterfall (email, téléphone) | facturées par certains fournisseurs même sans résultat : jamais sans accord chiffré au pire cas (personnes x coût par recherche) |
| Enrichissement d'entreprise | 1 par entreprise : écarté, inutile ici |

Repères : environ 2 crédits par entreprise retenue (tiers A à D), soit environ 230 crédits pour 120 entreprises.
Le plafond affiché par `enrichir_et_creer.py` sans `--go` est le nombre de lignes gardées, plus 8 par mobile ; le
réel est un peu en dessous. Mobiles des seuls contacts d'entrée des meilleurs comptes : 35 contacts coûtent 280
crédits demandés d'emblée, jusqu'à 315 après coup.

## Volumes : à quoi s'attendre

Pour transformer un nombre d'entreprises en nombre d'agents, de contacts et de crédits :

| Passage | Repère |
|---|---|
| Recherche web seule (site, LinkedIn) | environ 1 lien sur 4 faux ou imparfait : prévoir la vérification |
| Liste de quelques centaines d'entreprises, après le score | environ un tiers dans les tiers A à D ; environ 10 % en tier A |
| Score A, B, C | environ 15 % des entreprises en score A, 18 % en B, le reste hors cible (liste large, non filtrée au départ) |
| Signaux forts contre-vérifiés | environ 83 % confirmés, 10 % réfutés (souvent un événement de la maison mère), 7 % incertains |
| Cibles couvertes par Apollo puis le web | environ 80 % des personnes nommées, 55 % des rôles, 64 % au total |
| Contacts gardés | environ 1,8 par entreprise retenue ; 2,7 en tier A |
| Entreprises sans aucun contact | environ 14 %, surtout des tiers C et D absents d'Apollo et du web |
| Emails | environ 87 % des contacts avec un email, 83 % au statut `verified` |
| Personnes basées hors des pays acceptés | environ 7 % des enrichis (crédit dépensé quand même) |
| Logiciel d'un prospect trouvé sur le web | environ une entreprise sur quatre, la moitié confirmée |

## Estimer avant de demander l'accord

1. Compter par script le périmètre réel de l'étape (entités, entreprises, contacts).
2. Appliquer les ratios ci-dessus ; annoncer le nombre d'agents, la durée et les tokens (ou les crédits), avec une
   fourchette.
3. **Au-delà d'environ 3 M tokens**, découper en workflows successifs, du plus utile au moins utile : une limite de
   session a déjà coupé des workflows après environ 2,3 M et 5,6 M tokens consommés.
4. Annoncer le périmètre **complet** dès l'estimation (contrôle léger, passe 2, compléments compris) : c'est en
   l'élargissant en route qu'une estimation a été dépassée d'un facteur 3.
5. Pendant un traitement long, suivre l'avancement dans `journal.jsonl` (commande dans
   [outils.md](outils.md)) avant de répondre.
6. En fin d'étape, donner le coût réel (tokens et durée du run, crédits recomptés depuis le cache Apollo).
