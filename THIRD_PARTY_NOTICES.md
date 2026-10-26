# Composants tiers

Ce repo est sous licence MIT (voir `LICENSE`), à l'exception des éléments ci-dessous, qui gardent leur
propre licence.

| Élément | Emplacement | Origine | Licence |
|---|---|---|---|
| Skill `frontend-design` | `.claude/skills/frontend-design/` | Anthropic, [anthropics/skills](https://github.com/anthropics/skills) | Apache 2.0, texte complet dans `.claude/skills/frontend-design/LICENSE.txt` |
| Répertoire officiel des localités suisses | `.claude/skills/prospection-base-client/donnees/localites-suisse.csv` | Office fédéral de topographie swisstopo | données ouvertes, © swisstopo |

## Bibliothèques d'effets (chargées par CDN, non incluses dans le repo)

Le catalogue `02-landing-page/effets/` charge ces bibliothèques depuis jsdelivr, à version figée :
[GSAP](https://gsap.com) 3.15.0 (gsap, ScrollTrigger, SplitText ; licence « Standard no charge », gratuite
y compris pour un usage commercial, sauf intégration dans un outil d'animation visuelle sans code concurrent
de Webflow), [Lenis](https://github.com/darkroomengineering/lenis) 1.3.27 (MIT),
[OGL](https://github.com/oframe/ogl) 1.0.11 (Unlicense).

## Dépendances installées (non incluses dans le repo)

Installées par `pip install -r requirements.txt`, chacune sous sa propre licence :
`requests` (Apache 2.0), `beautifulsoup4` (MIT), `lxml` (BSD), `ddgs` (MIT), `openpyxl` (MIT).

## Inspirations

Les agents de ce repo ont été écrits pour lui, en s'inspirant des collections publiques
[VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) (MIT)
et [wshobson/agents](https://github.com/wshobson/agents) (MIT). Aucun fichier n'en est repris.

