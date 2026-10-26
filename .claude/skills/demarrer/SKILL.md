---
name: demarrer
description: Installe et présente le kit BUMPSLAB × Zero to One. Vérifie Python, crée l'environnement, contrôle l'installation, puis aide l'utilisateur à choisir par où commencer. À utiliser à la première ouverture du repo, quand .venv n'existe pas, ou quand l'utilisateur demande comment démarrer.
---

# Démarrer

## 1. Installer (une seule fois)

Explique en une phrase chaque commande avant de la lancer. Sous Windows, `.venv/bin/` devient `.venv/Scripts/`.

1. **Python 3.11 ou plus** : `python3 --version` (sous Windows : `py --version`).
   S'il manque ou s'il est trop ancien, donne le lien https://www.python.org/downloads/ et attends.
2. **L'environnement Python**, à la racine du repo, s'il n'existe pas :
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   Sous Windows : `py -m venv .venv` puis `.venv\Scripts\pip install -r requirements.txt`.
3. **Le contrôle** :
   `.venv/bin/python .claude/skills/prospection-base-client/scripts/verifier_installation.py`
   La clé Apollo absente est normale à ce stade : elle ne sert qu'à la prospection, étapes 6 et 7.
   Ignore la « prochaine action » affichée par ce script : elle concerne la prospection, et dans ce repo
   les campagnes vont dans `03-prospection/campagnes/<nom>`, pas dans `campagnes/<nom>`.
4. **Le navigateur de capture** (pour que Claude voie les pages qu'il crée, environ 150 Mo, 1 à 2
   minutes) : `.venv/bin/python -m playwright install chromium`. Si le réseau le bloque, ce n'est pas
   bloquant : l'utilisateur ouvrira les pages lui-même avec Live Preview.
5. **Node.js** n'est utile que pour mettre la page en ligne depuis le terminal : `node --version`. S'il
   manque, ce n'est pas bloquant aujourd'hui.

## 2. Présenter le kit, en quelques lignes

Trois dossiers, dans l'ordre d'un lancement :

1. `01-etude-de-marche` : y a-t-il un marché, et lequel ? Sortie : une décision, creuser, pivoter ou arrêter.
2. `02-landing-page` : une page en ligne qui affiche l'argumentaire.
3. `03-prospection` : les bonnes entreprises, les bonnes personnes, un signal par compte, puis les rendez-vous.

## 3. Choisir par où commencer

Demande à l'utilisateur où il en est, avec ces options :

- « J'ai une idée, je ne sais pas si le marché existe » → `/etude-de-marche`
- « Je sais à qui je vends, il me faut une page » → `/cahier-des-charges`
- « J'ai une page, il me faut des clients » → la prospection (`03-prospection/CLAUDE.md`)
- « Je veux juste essayer » → copie `01-etude-de-marche/exemple/brief-bumpslab.md` dans
  `01-etude-de-marche/brief.md`, puis `/etude-de-marche`

Rappelle la règle de la formation : on travaille sur de vraies données, mais rien ne part chez un vrai
prospect sans relecture.
