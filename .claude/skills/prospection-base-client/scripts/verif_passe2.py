"""Étape 4, passe 2 : prépare les lots des cas restés ouverts (workflows/verification-passe2.js).

Entrée : entreprises-verifie.csv, résultat de la passe 1 (verif_appliquer.py). Sans passe 1, la liste de l'étape 2
ou 3 (entreprises-enrichi.csv, sinon entreprises.csv) : la passe 2 sert alors de complétion directe, par exemple
juste après une découverte web.
- lots R (résolution) : entités à revoir (a_revoir = oui), ou non identifiées et sans site -> identification par le
  registre du commerce et la recherche web ; la preuve de la source sert à départager les homonymes ;
- lots C (complétion) : entités identifiées à qui il manque le site, la page LinkedIn, ou les deux, sur l'une au
  moins de leurs lignes (alias compris).
Ignorées : les lignes exclues (colonne exclure remplie, sauf « non identifiée », qui est à résoudre) et les entités
complètes qui ne sont pas à revoir. Une entité est « non identifiée » si exclure vaut « non identifiée », si son nom
officiel est vide ou porte un marqueur laissé par un agent (« non identifiée », « inconnu »).
Même entreprise sous deux noms qui ne diffèrent que par la ponctuation ou les espaces (« Exemple-Tech » et
« Exemple Tech ») : une seule entité, les autres noms en alias ; les agents rendent une entrée par alias.
Ordre : incertitude (celle de la ligne la plus incertaine) puis ordre de la liste, réparti en tourniquet entre les
lots, comme la passe 1.

Sorties, dans <campagne>/donnees/verification/ :
- lots/R01.json..., C01.json... : entités {key, alias, champs de la source (nom, pays, ville, secteur, activite,
  source, preuve), passe1 : résultat de la passe 1 ou valeurs de la liste} (les anciens lots R et C sont effacés) ;
- manifeste-passe2.json : [{id, mode (resolve|complete), n, file, cles, alias}], file relatif à la campagne ;
- args-passe2.json : les args complets du workflow, à passer tels quels à l'outil Workflow.

Usage (depuis la racine du projet, celle qui contient .venv) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/verif_passe2.py --campagne campagnes/<nom>
      [--taille-resolution 7] [--taille-completion 17] [--max N]
Ensuite : outil Workflow, scriptPath = <skill>/workflows/verification-passe2.js, args = contenu de args-passe2.json ;
puis verif_appliquer.py avec les journaux des deux passes, dans l'ordre.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import Campagne, argument_campagne, lire_csv
from verif_preparer import (NON_IDENTIFIE, effacer_lots, ecrire_lots, ecrire_manifeste, entites_de, incertitude,
                            liste_de_base, repartir, resume)

# ce que la source disait de l'entreprise, puis ce que la passe 1 en a fait
CHAMPS_SOURCE = ["nom", "pays", "ville", "secteur", "activite", "taille", "source", "preuve"]
CHAMPS_PASSE1 = ["nom_officiel", "pays", "ville", "activite", "site", "site_statut", "site_confiance", "site_verif",
                 "linkedin", "linkedin_statut", "linkedin_source", "linkedin_verif", "verification",
                 "preuve_verification", "a_revoir", "exclure", "note"]


def sous(r: dict, champs: list[str], n: int = 400) -> dict:
    return {c: (r[c] if len(r[c]) <= n else r[c][:n] + "...") for c in champs if (r.get(c) or "").strip()}


def main() -> None:
    ap = argparse.ArgumentParser(description="Étape 4, passe 2 : prépare les lots des cas restés ouverts "
                                             "(résolution et complétion).")
    argument_campagne(ap)
    ap.add_argument("--taille-resolution", type=int, default=7, help="entités par lot de résolution (défaut 7)")
    ap.add_argument("--taille-completion", type=int, default=17, help="entités par lot de complétion (défaut 17)")
    ap.add_argument("--max", type=int, default=0, help="ne garder que les N entités les plus incertaines (essai)")
    a = ap.parse_args()

    camp = Campagne(a.campagne)
    chemin = camp.fichier("entreprises-verifie.csv")
    if not chemin.exists():
        chemin = liste_de_base(camp)
        print(f"Pas de passe 1 (entreprises-verifie.csv absent) : la passe 2 part de {chemin.name}.")
    ents = entites_de(lire_csv(chemin))

    # même entreprise sous deux clés qui ne diffèrent que par la ponctuation : un seul enregistrement, clés en alias
    fusion: dict[str, dict] = {}
    for e in ents.values():
        k = "".join(ch for ch in e["key"].casefold() if ch.isalnum())
        if k in fusion:
            fusion[k].setdefault("alias", []).append(e["key"])
            fusion[k]["lignes"] += e["lignes"]
        else:
            fusion[k] = e

    resolution, completion, ignorees = [], [], Counter()
    for e in fusion.values():
        lignes = e["lignes"]
        r = lignes[0]
        motifs = {(l.get("exclure") or "").strip() for l in lignes} - {""}
        if motifs - {"non identifiée"}:
            ignorees["exclue"] += 1
            continue
        nom_off = (r.get("nom_officiel") or "").strip()
        non_identifiee = bool(motifs) or not nom_off or bool(NON_IDENTIFIE.search(nom_off))
        # complète seulement si chaque ligne (alias compris) a son site et sa page LinkedIn
        complete = all(l.get("site") and l.get("linkedin") for l in lignes)
        fiche = {"key": e["key"]}
        if e.get("alias"):
            fiche["alias"] = e["alias"]
        fiche.update({c: v for c, v in sous(r, CHAMPS_SOURCE).items() if c != "nom" or v != e["key"]})
        fiche["passe1"] = sous(r, CHAMPS_PASSE1)
        rang = (-max(incertitude(l) for l in lignes), e["rang"], fiche)
        # identité : celle de la ligne principale, que l'agent voit dans passe1
        if any(l.get("a_revoir") == "oui" for l in lignes) or (non_identifiee and not r.get("site")):
            resolution.append(rang)
        elif not complete:
            completion.append(rang)
        else:
            ignorees["complète"] += 1
    resolution.sort(key=lambda t: t[:2])
    completion.sort(key=lambda t: t[:2])
    if a.max:
        garde = {t[2]["key"] for t in sorted(resolution + completion, key=lambda t: t[:2])[:a.max]}
        resolution = [t for t in resolution if t[2]["key"] in garde]
        completion = [t for t in completion if t[2]["key"] in garde]

    effacer_lots(camp, "RC")
    manifeste = (ecrire_lots(camp, repartir([t[2] for t in resolution], a.taille_resolution), "R", "resolve")
                 + ecrire_lots(camp, repartir([t[2] for t in completion], a.taille_completion), "C", "complete"))
    m, fa = ecrire_manifeste(camp, 2, manifeste)

    print(f"Liste : {chemin.name}, {len(fusion)} entités ({len(ents) - len(fusion)} alias fusionnés) ; "
          f"résolution {len(resolution)}, complétion {len(completion)}"
          + "".join(f", {k} {v}" for k, v in ignorees.items()) + (f" (--max {a.max})" if a.max else ""))
    if not manifeste:
        print("Rien à reprendre : aucune entité à revoir ni incomplète.")
        return
    for b in manifeste:
        print(f"  {b['id']} | " + " ; ".join(b["cles"]))
    print(f"Manifeste : {m}")
    resume(manifeste, 2, "verification-passe2.js", fa)


if __name__ == "__main__":
    main()
