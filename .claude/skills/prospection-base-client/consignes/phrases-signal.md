# Consigne : première phrase de chaque compte A (`phrase_signal`)

La séquence ouvre l'email 1 sur le signal du compte : `Bonjour {{first_name}}, {{phrase_signal}} ...`. Tu écris
cette première phrase pour chaque compte A, à partir de son signal daté et de sa source. Ces phrases partent chez les
prospects : elles ne s'écrivent que sur demande explicite de l'utilisateur, et il les relit avant la réinjection.

## Ce que tu reçois

- `phrases-a-rediger.csv` (dossier de la campagne, écrit par `reinjecter_apollo.py` en aperçu) : une ligne par
  compte A sans phrase, avec `id`, `nom`, `signal_et_date`, `source_signal` et `phrase_signal` (vide).
- Pour la langue du contact : `appels/ordre-appel.csv` (colonne `langue_principale`, par `entreprise_id` : code
  `fr`, `de`, `it`..., une langue de l'appelant si le contact la parle probablement, sinon sa langue la plus
  probable ; vide si rien ne l'indique) s'il existe, sinon `prospection-signaux.csv` (colonnes `pays` et `canton`,
  par `id`).

## Ce que tu écris

Les mêmes lignes et les mêmes colonnes, avec `phrase_signal` rempli, dans `phrases-signal.csv` (dossier de la
campagne, UTF-8, virgule). Ne pas réécrire `phrases-a-rediger.csv` : il est régénéré à chaque aperçu. Ensuite :

```
.venv/bin/python .claude/skills/prospection-base-client/scripts/reinjecter_apollo.py --campagne campagnes/<nom> \
    --phrases campagnes/<nom>/phrases-signal.csv
```

L'aperçu range les phrases dans `base-abc.csv` et refuse, en les listant, celles qui ont un tiret long ou
demi-cadratin, plus de 30 mots ou un signal négatif.

## Règles

1. **Un fait du signal, daté** : reprendre le fait de `signal_et_date` et sa date, dite simplement (« en septembre »,
   « cette année »). Une seule phrase.
2. **Fidèle à la source** : ouvrir `source_signal` en cas de doute ; ne pas grossir le fait, ne pas changer sa date,
   aucun chiffre absent du signal.
3. **Vouvoiement**, la phrase parle d'eux : « Vous avez annoncé ... », « Félicitations pour ... », « J'ai vu que
   vous ... ». Pas de présentation de notre offre (elle vient après dans l'email), pas de flatterie, pas de point
   d'exclamation.
4. **Dans la langue du contact** : français pour la Suisse romande, la France, la Belgique et le Luxembourg ;
   allemand pour la Suisse alémanique, l'Allemagne et l'Autriche ; italien pour le Tessin et l'Italie ; en cas de
   doute, la langue de l'appelant (`appels.langues` de `campagne.toml`).
5. **30 mots au plus.**
6. **Pas de tiret cadratin ni demi-cadratin** (les tirets longs) : une virgule ou deux-points à la place.
7. **Pas de signal négatif** (faillite, sursis, liquidation, licenciements, restructuration, cyberattaque,
   procédure) : si le seul signal du compte est négatif, laisser `phrase_signal` vide et le dire à l'utilisateur.
8. **Aucune donnée d'un de nos clients** (montant, commande, relation commerciale) et aucune source interne
   (« Apollo », « notre base », « on a analysé »).

## Exemples (fictifs)

- « Vous avez annoncé l'ouverture de votre site de Sion en septembre. »
- « Félicitations pour votre nomination à la direction des opérations. »
- « J'ai vu que vous recrutez un responsable de production à Neuchâtel. »
- « Sie haben im September die Eröffnung Ihres Standorts in Sitten angekündigt. »

## Vérification avant de rendre la main

- Chaque phrase : un seul fait, sa date, 30 mots au plus, aucun tiret long, aucun mot négatif.
- Relire 5 phrases contre leur source : le fait y figure, à la bonne date, pour la bonne entreprise.
- Lister à l'utilisateur les comptes laissés sans phrase et pourquoi.
