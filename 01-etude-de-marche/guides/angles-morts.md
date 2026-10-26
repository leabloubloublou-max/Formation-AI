# Ce que la recherche web n'atteint pas

Les agents s'appuient sur la recherche web. Elle s'arrête à ce qui est public et indexé, et ce n'est pas
tout le marché.

## 1. Les pages qu'il faut parcourir à la main

**Outil : Claude dans Chrome** (l'extension). Pour les annuaires à filtres, les comparateurs, les pages
derrière une connexion.

> Exemple : un annuaire d'entreprises qu'on ne peut lire qu'en cochant des filtres.

À savoir : il est lent et il échoue sur les interfaces compliquées. Gardez-le pour quelques pages, pas
pour des centaines.

## 2. Beaucoup de requêtes à la suite

**Outil : `scripts/scraping.py`** (DuckDuckGo, sans clé, pas de captcha bloquant comme sur Google).
Les résultats arrivent rangés dans un CSV, avec la requête, le lien et la date de collecte.
Mode d'emploi : [`../scripts/README.md`](../scripts/README.md).

## 3. Ce que vos concurrents dépensent vraiment

Ces outils sont publics et gratuits, mais ils se consultent à la main. Collez à Claude ce que vous voyez :
il le range dans `resultats/concurrents.csv`, colonne `messages_publicitaires`, avec la date.

| Outil | Ce qu'il montre | Lien |
|---|---|---|
| Bibliothèque publicitaire Meta | Les publicités actives d'un concurrent sur Facebook et Instagram : ses messages, ses offres, depuis quand elles tournent | https://www.facebook.com/ads/library/ |
| Google Ads Transparency Center | Les annonces Google et YouTube, annonceur par annonceur | https://adstransparency.google.com/ |

**À retenir** : une publicité qui tourne depuis des mois est un indice qu'elle rapporte.

## 4. Ce que les gens tapent vraiment

| Outil | Ce qu'il montre | Lien |
|---|---|---|
| Keyword Planner de Google Ads | Les recherches mensuelles sur les mots-clés de votre marché : un indice de la profondeur de la demande | https://ads.google.com/home/tools/keyword-planner/ |

Il demande un compte Google Ads et n'affiche que des fourchettes sans campagne active. Une fourchette reste
une **estimation**, pas un fait.

## 5. Garder la trace

Chaque donnée garde son lien et sa date de collecte dans `resultats/sources.csv` : une colonne lien, une
colonne date, une colonne méthode. C'est ce fichier que le vérificateur relit.

Respectez les conditions d'utilisation des sites et gardez des volumes raisonnables.
