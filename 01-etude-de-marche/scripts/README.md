# Scripts de l'étude de marché

## `scraping.py` · des dizaines de recherches, rangées dans un CSV

Lance une série de recherches DuckDuckGo (sans clé, sans compte) et range chaque résultat dans
`resultats/scraping.csv` : la requête, le rang, le titre, le lien, le domaine, l'extrait, la date de
collecte et la méthode.

**Le plus simple** : demandez-le à Claude Code.

> « Lance une recherche web sur ces requêtes et range les résultats : [vos requêtes] »

**À la main**, depuis la racine du repo :

```bash
.venv/bin/python 01-etude-de-marche/scripts/scraping.py --requete "votre requête"
.venv/bin/python 01-etude-de-marche/scripts/scraping.py --fichier 01-etude-de-marche/scripts/requetes.exemple.txt
```

| Option | Rôle | Par défaut |
|---|---|---|
| `--requete` | une requête, répétable | |
| `--fichier` | une requête par ligne | |
| `--max` | résultats par requête (30 au plus) | 10 |
| `--region` | `ch-fr`, `fr-fr`, `be-fr`, `wt-wt` (monde) | `ch-fr` |
| `--pause` | secondes entre deux requêtes | 4 |
| `--sortie` | CSV de sortie, complété, jamais écrasé | `resultats/scraping.csv` |
| `--refaire` | relancer les requêtes déjà faites | non |

### À savoir

- **Une requête déjà présente dans le CSV n'est pas relancée.** Relancer le script ne coûte rien.
- **Un extrait de moteur n'est pas une source.** Il sert à repérer les pages ; on ouvre la page avant de citer
  un chiffre.
- **DuckDuckGo limite les volumes** sans annoncer de seuil. Si le script affiche `RatelimitException`, il
  attend et réessaie ; au-delà, relancez plus tard. Gardez des lots de quelques dizaines de requêtes.
- Le script interroge uniquement DuckDuckGo (`backend="duckduckgo"`), pas Google ni Bing.
- Respectez les conditions d'utilisation des sites que vous ouvrez ensuite.
