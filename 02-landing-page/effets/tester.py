"""Tester des pages HTML dans un vrai navigateur : erreurs, captures, mouvement réduit.

À quoi ça sert
--------------
Ouvre chaque page .html d'un dossier dans Chromium (via Playwright), à plusieurs largeurs d'écran,
d'abord normalement puis avec le réglage « réduire les animations » activé. Pour chaque page :

- relève les erreurs de la console JavaScript et les fichiers qui ne se chargent pas ;
- fait défiler la page de haut en bas (pour déclencher les effets au défilement) ;
- prend une capture de la page entière, découpée en morceaux lisibles (1 600 px de haut au plus) ;
- signale un défilement horizontal (la page déborde sur le côté, souvent sur téléphone) ;
- sur grand écran : signale le contenu étalé (une section dont le contenu dépasse 1 280 px de large au
  lieu d'être centré), le texte étiré et les lignes trop longues (plus de 85 caractères environ) ;
- en mode « réduire les animations » : signale les animations encore en mouvement, et les textes
  restés invisibles (un effet qui cache le texte et ne le montre plus).

Il sert pour le catalogue d'effets (02-landing-page/effets/) comme pour le site (02-landing-page/site/).

Installation (une seule fois, depuis la racine du repo)
-------------------------------------------------------
    .venv/bin/pip install playwright
    .venv/bin/python -m playwright install chromium     # télécharge le navigateur, environ 150 Mo

Utilisation
-----------
    .venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/site
    .venv/bin/python 02-landing-page/effets/tester.py 02-landing-page/effets --largeurs 390,1280

Options :
    --largeurs 390,1280        largeurs d'écran testées, en pixels (par défaut 390, 1280 et 1920)
    --page index.html          ne tester qu'une page (option répétable)
    --sortie DOSSIER           où ranger les captures (par défaut 02-landing-page/travail/, dont les
                               .png sont ignorés par git ; noms en test-<page>-<largeur>-<mode>-<n>.png)
    --sans-reduit              ne pas tester le mode « réduire les animations »
    --cdn-local NODE_MODULES   sert les bibliothèques demandées à cdn.jsdelivr.net depuis un dossier
                               node_modules local, au lieu d'Internet. Utile quand le réseau bloque
                               les CDN. Préparer le dossier avec, par exemple :
                                 mkdir /tmp/libs && cd /tmp/libs && npm i gsap@3.15.0 lenis@1.3.27 ogl@1.0.11
                               puis : --cdn-local /tmp/libs/node_modules
                               Le script vérifie que la version installée est celle de l'URL.

Le script s'arrête avec le code 1 s'il trouve au moins une erreur, 0 sinon. Il lance son propre petit
serveur local (comme `python3 -m http.server`) et l'arrête à la fin.

Lire le résultat
----------------
ERREUR      : à corriger avant la mise en ligne (erreur JavaScript, fichier introuvable, texte caché
              en mode réduit, page qui déborde sur le côté).
ATTENTION   : à regarder (une animation tourne encore en mode réduit : acceptable si elle est très
              lente et décorative, sinon à couper).
Puis regardez les captures : c'est là qu'on voit si le rendu est juste.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import mimetypes
import re
import socketserver
import sys
import threading
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sys.exit(
        "Playwright n'est pas installé. Depuis la racine du repo :\n"
        "  .venv/bin/pip install playwright\n"
        "  .venv/bin/python -m playwright install chromium"
    )

HAUTEUR_ECRAN = 844  # hauteur d'un téléphone courant ; l'écran large utilise 800
HAUTEUR_MORCEAU = 1600  # hauteur maximale d'une capture découpée
CDN = "https://cdn.jsdelivr.net/npm/"

# Script exécuté sur grand écran : contenu étiré, lignes trop longues.
VERIF_MISE_EN_PAGE = r"""
() => {
  const res = { etires: [], longues: [], etales: [] };
  // Contenu étalé : dans une section, du premier élément au dernier, plus de 1 280 px de large
  const vw = window.innerWidth;
  for (const bloc of document.querySelectorAll('header, section, footer')) {
    let g = Infinity, d = -Infinity;
    for (const el of bloc.querySelectorAll('h1,h2,h3,p,li,summary,a,img,figure,svg,table')) {
      if (el.closest('[aria-hidden="true"]')) continue;
      const b = el.getBoundingClientRect();
      if (b.width === 0 || b.width >= vw * 0.95) continue;   // les fonds et photos bord à bord sont permis
      g = Math.min(g, b.left); d = Math.max(d, b.right);
    }
    if (d - g > 1280) {
      const titre = (bloc.querySelector('h1,h2,h3') || bloc).textContent.trim().replace(/\s+/g, ' ').slice(0, 40);
      res.etales.push(bloc.tagName.toLowerCase() + ' « ' + titre + ' » : ' + Math.round(d - g) + ' px');
    }
  }
  const vus = new Set();
  for (const el of document.querySelectorAll('h1,h2,h3,p,li,summary,blockquote,dd')) {
    const texte = el.textContent.trim().replace(/\s+/g, ' ');
    if (!texte || el.closest('[aria-hidden="true"]')) continue;
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || el.getClientRects().length === 0) continue;
    // largeur réelle occupée par le texte (pas celle de la boîte)
    const r = document.createRange(); r.selectNodeContents(el);
    const largeur = Math.max(...Array.from(r.getClientRects()).map(x => x.width), 0);
    const extrait = el.tagName.toLowerCase() + ' « ' + texte.slice(0, 40) + ' »';
    if (largeur > 1240 && !vus.has(extrait)) { res.etires.push(extrait + ' : ' + Math.round(largeur) + ' px'); vus.add(extrait); }
    const taille = parseFloat(s.fontSize);
    const caracteres = Math.round(largeur / (taille * 0.5));
    if (/^(p|li|dd|blockquote)$/i.test(el.tagName) && texte.length > 140 && caracteres > 85 && !vus.has(extrait)) {
      res.longues.push(extrait + ' : environ ' + caracteres + ' caractères par ligne'); vus.add(extrait);
    }
  }
  return res;
}
"""

# Script exécuté dans la page en mode « réduire les animations ».
VERIF_REDUIT = r"""
() => {
  const resultats = { animations: [], invisibles: [], gsapActifs: 0, lenis: false };
  // Animations CSS ou Web Animations encore en cours
  for (const a of document.getAnimations()) {
    if (a.playState !== 'running') continue;
    const cible = a.effect && a.effect.target;
    const nom = a.animationName || a.transitionProperty || a.constructor.name;
    const iter = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming().iterations : 1;
    if (iter === Infinity || a.animationName) {
      resultats.animations.push(nom + ' sur ' + (cible ? (cible.className || cible.tagName) : '?'));
    }
  }
  // Animations GSAP en cours
  if (window.gsap && gsap.globalTimeline) {
    resultats.gsapActifs = gsap.globalTimeline.getChildren(true, true, false).filter(t => t.isActive()).length;
  }
  resultats.lenis = document.documentElement.classList.contains('lenis-smooth');
  // Textes présents mais invisibles
  const textes = document.querySelectorAll('h1,h2,h3,h4,p,li,a,button,dt,dd,blockquote,figcaption,label');
  for (const el of textes) {
    if (!el.textContent.trim() || el.closest('[aria-hidden="true"]')) continue;
    const s = getComputedStyle(el);
    if (s.display === 'none' || el.getClientRects().length === 0) continue;
    let opacite = 1, n = el;
    while (n && n.nodeType === 1) { opacite *= parseFloat(getComputedStyle(n).opacity); n = n.parentElement; }
    if (s.visibility === 'hidden' || opacite < 0.1) {
      resultats.invisibles.push(el.tagName.toLowerCase() + ' « ' + el.textContent.trim().slice(0, 50) + ' »');
    }
  }
  return resultats;
}
"""


class ServeurSilencieux(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # pas de journal dans le terminal
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def lancer_serveur(dossier: Path):
    gestionnaire = functools.partial(ServeurSilencieux, directory=str(dossier))
    socketserver.TCPServer.allow_reuse_address = True
    serveur = socketserver.ThreadingTCPServer(("127.0.0.1", 0), gestionnaire)
    serveur.daemon_threads = True
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    return serveur, f"http://127.0.0.1:{serveur.server_address[1]}"


def route_cdn_local(node_modules: Path, problemes: list[str]):
    """Sert https://cdn.jsdelivr.net/npm/<paquet>@<version>/<chemin> depuis node_modules."""
    motif = re.compile(r"^https://cdn\.jsdelivr\.net/npm/((?:@[^/]+/)?[^@/]+)@([^/]+)/(.+?)(?:\?.*)?$")

    def gerer(route):
        url = route.request.url
        m = motif.match(url)
        if not m:
            problemes.append(f"ERREUR  URL CDN non reconnue (version absente ?) : {url}")
            return route.abort()
        paquet, version, chemin = m.groups()
        if chemin.endswith("+esm") or chemin == "+esm":
            problemes.append(f"ERREUR  '+esm' ne peut pas être servi en local : {url}")
            return route.abort()
        dossier = node_modules / paquet
        try:
            installe = json.loads((dossier / "package.json").read_text())["version"]
        except (OSError, ValueError, KeyError):
            problemes.append(f"ERREUR  paquet {paquet} absent de {node_modules}")
            return route.abort()
        majeure = version.isdigit() and installe.split(".")[0] == version  # ex. @5 (polices Fontsource)
        if installe != version and not majeure:
            problemes.append(f"ERREUR  {url} : la version {version} est demandée, {installe} est installée")
        fichier = dossier / chemin
        if not fichier.is_file():
            problemes.append(f"ERREUR  fichier introuvable dans le paquet : {url}")
            return route.fulfill(status=404, body="introuvable")
        type_mime = mimetypes.guess_type(fichier.name)[0] or "application/octet-stream"
        if fichier.suffix in (".js", ".mjs"):
            type_mime = "text/javascript"
        return route.fulfill(
            status=200,
            body=fichier.read_bytes(),
            headers={"Content-Type": type_mime, "Access-Control-Allow-Origin": "*"},
        )

    return gerer


def defiler_toute_la_page(page):
    """Fait défiler par étapes jusqu'en bas, puis revient en haut."""
    page.evaluate(
        """async () => {
          const pause = (ms) => new Promise(r => setTimeout(r, ms));
          const pas = Math.max(200, Math.round(innerHeight * 0.6));
          for (let y = 0; y < document.documentElement.scrollHeight; y += pas) {
            window.scrollTo(0, y);
            await pause(120);
          }
          window.scrollTo(0, document.documentElement.scrollHeight);
          await pause(400);
          window.scrollTo(0, 0);
          await pause(600);
        }"""
    )


def capturer(page, base: Path, largeur: int) -> list[Path]:
    hauteur = page.evaluate("document.documentElement.scrollHeight")
    fichiers = []
    y, n = 0, 1
    while y < hauteur:
        h = min(HAUTEUR_MORCEAU, hauteur - y)
        chemin = base.with_name(f"{base.name}-{n}.png")
        page.screenshot(path=str(chemin), full_page=True, clip={"x": 0, "y": y, "width": largeur, "height": h})
        fichiers.append(chemin)
        y += HAUTEUR_MORCEAU
        n += 1
    return fichiers


def tester_page(navigateur, adresse, nom, largeur, reduit, sortie, cdn_local):
    problemes: list[str] = []
    contexte = navigateur.new_context(
        viewport={"width": largeur, "height": HAUTEUR_ECRAN if largeur < 700 else 800},
        reduced_motion="reduce" if reduit else "no-preference",
        device_scale_factor=1,
    )
    page = contexte.new_page()
    if cdn_local:
        page.route(CDN + "**", route_cdn_local(cdn_local, problemes))

    page.on("console", lambda m: m.type == "error" and problemes.append(f"ERREUR  console : {m.text}"))
    page.on("pageerror", lambda e: problemes.append(f"ERREUR  JavaScript : {e}"))
    page.on(
        "requestfailed",
        lambda r: problemes.append(f"ERREUR  chargement impossible : {r.url} ({r.failure})"),
    )
    page.on(
        "response",
        lambda r: r.status >= 400 and problemes.append(f"ERREUR  {r.status} pour {r.url}"),
    )

    try:
        page.goto(f"{adresse}/{nom}", wait_until="networkidle", timeout=30000)
    except Exception as e:  # noqa: BLE001
        problemes.append(f"ERREUR  la page ne se charge pas : {e}")
        contexte.close()
        return problemes, []
    page.wait_for_timeout(1500)  # laisse finir les animations d'entrée
    defiler_toute_la_page(page)

    deborde = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    if deborde > 1:
        problemes.append(f"ERREUR  la page déborde de {deborde}px sur le côté (défilement horizontal)")

    if largeur >= 1200 and not reduit:
        m = page.evaluate(VERIF_MISE_EN_PAGE)
        for t in m["etales"][:8]:
            problemes.append(f"ERREUR  contenu étalé sur grand écran, à centrer dans 1 200 px : {t}")
        for t in m["etires"][:6]:
            problemes.append(f"ATTENTION  contenu étiré sur grand écran (1200 px de large au plus) : {t}")
        for t in m["longues"][:6]:
            problemes.append(f"ATTENTION  lignes trop longues (75 caractères au plus) : {t}")

    if reduit:
        r = page.evaluate(VERIF_REDUIT)
        for a in r["animations"]:
            problemes.append(f"ATTENTION  animation en cours malgré le mode réduit : {a}")
        if r["gsapActifs"]:
            problemes.append(f"ATTENTION  {r['gsapActifs']} animation(s) GSAP en cours malgré le mode réduit")
        if r["lenis"]:
            problemes.append("ATTENTION  le défilement fluide (Lenis) est actif malgré le mode réduit")
        for t in r["invisibles"][:10]:
            problemes.append(f"ERREUR  texte invisible en mode réduit : {t}")

    mode = "reduit" if reduit else "normal"
    base = sortie / f"test-{Path(nom).stem}-{largeur}-{mode}"
    captures = capturer(page, base, largeur)
    contexte.close()
    # Retire les doublons en gardant l'ordre
    return list(dict.fromkeys(problemes)), captures


def main():
    racine_repo = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description="Tester des pages HTML : erreurs, captures, mouvement réduit.")
    p.add_argument("dossier", help="dossier à servir, ex. 02-landing-page/site")
    p.add_argument("--largeurs", default="390,1280,1920", help="largeurs en pixels, séparées par des virgules")
    p.add_argument("--page", action="append", help="ne tester que cette page (répétable)")
    p.add_argument("--sortie", default=str(racine_repo / "02-landing-page" / "travail"))
    p.add_argument("--sans-reduit", action="store_true", help="ne pas tester le mode réduit")
    p.add_argument("--cdn-local", help="dossier node_modules servant cdn.jsdelivr.net en local")
    args = p.parse_args()

    dossier = Path(args.dossier).resolve()
    if not dossier.is_dir():
        sys.exit(f"Dossier introuvable : {dossier}")
    pages = args.page or sorted(f.name for f in dossier.glob("*.html"))
    if not pages:
        sys.exit(f"Aucune page .html dans {dossier}")
    largeurs = [int(x) for x in args.largeurs.split(",") if x.strip()]
    cdn_local = Path(args.cdn_local).resolve() if args.cdn_local else None
    if cdn_local and not cdn_local.is_dir():
        sys.exit(f"Dossier node_modules introuvable : {cdn_local}")
    sortie = Path(args.sortie).resolve()
    sortie.mkdir(parents=True, exist_ok=True)

    serveur, adresse = lancer_serveur(dossier)
    modes = [False] if args.sans_reduit else [False, True]
    nb_erreurs = 0
    print(f"Pages servies depuis {dossier} ({adresse})")
    print(f"Captures dans {sortie}\n")
    try:
        with sync_playwright() as pw:
            navigateur = pw.chromium.launch()
            for nom in pages:
                print(f"== {nom}")
                for largeur in largeurs:
                    for reduit in modes:
                        problemes, captures = tester_page(
                            navigateur, adresse, nom, largeur, reduit, sortie, cdn_local
                        )
                        mode = "mouvement réduit" if reduit else "normal"
                        etat = "OK" if not any(x.startswith("ERREUR") for x in problemes) else "À CORRIGER"
                        print(f"   {largeur}px, {mode} : {etat}, {len(captures)} capture(s)")
                        for x in problemes:
                            print(f"      {x}")
                        nb_erreurs += sum(1 for x in problemes if x.startswith("ERREUR"))
            navigateur.close()
    finally:
        serveur.shutdown()

    print(f"\n{nb_erreurs} erreur(s). Regardez maintenant les captures dans {sortie}.")
    sys.exit(1 if nb_erreurs else 0)


if __name__ == "__main__":
    main()
