"""Étape 5 : site web de chaque entreprise -> maturité numérique + mentions tech + recrutement + fraîcheur.

Par site : page d'accueil + jusqu'à 6 pages internes choisies par mots-clés (actualités / presse / blog,
carrières / jobs, à propos, innovation / technologie), + sitemap.xml (dates <lastmod>).
  - stack : empreintes HTML/headers (CMS, framework moderne, analytics, marketing automation / CRM,
    chat / assistant IA, e-shop / portail client / configurateur, bannière cookies, CDN) ;
  - contenu : lexique (IA, industrie 4.0, digitalisation, automatisation, innovation ; nominations,
    levées, rachats, nouveaux sites, certifications...) avec la date la plus proche du passage ;
  - recrutement : page carrières, nombre approximatif d'offres, postes tech / IT / data / automation ;
  - fraîcheur : année du copyright, dernière date d'actualité, dernier lastmod du sitemap.

Entrée : donnees/signaux/entites.json (entreprises avec un site, sauf les particuliers).
Sortie : donnees/signaux/site.json (cache repris : une relance ne refait que les sites absents ou en échec).
Sans clé ; en repli, la vérification TLS est désactivée pour les sites au certificat invalide.

Usage (depuis la racine du projet) :
  .venv/bin/python .claude/skills/prospection-base-client/scripts/collect_site.py --campagne campagnes/<nom> \\
      [--workers 8] [--refresh]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlparse

sys.dont_write_bytecode = True  # aucun __pycache__ dans le dossier du skill, qui se partage tel quel

from commun import argument_campagne
from lexique import detect, tech_counts
from signaux_commun import (Store, all_dates, clip, domain, donnees, get, iso, load_entities, months_ago, ouvrir,
                            polite_sleep)

MAX_HTML = 600_000

# (nom, catégorie, regex) : testées sur le HTML brut de la home + headers HTTP
STACK = [
    ("WordPress", "cms", r"wp-content|wp-includes|wp-json"), ("Wix", "cms", r"static\.wixstatic|wix\.com|_wixCIDX"),
    ("Squarespace", "cms", r"squarespace"), ("Webflow", "cms_moderne", r"webflow"),
    ("Framer", "cms_moderne", r"framerusercontent|framer\.com/"), ("Shopify", "ecommerce", r"cdn\.shopify|myshopify"),
    ("TYPO3", "cms", r"typo3"), ("Drupal", "cms", r"drupal|sites/default/files"), ("Joomla", "cms", r"/media/jui/|joomla"),
    ("Jimdo", "cms", r"jimdo"), ("Contao", "cms", r"contao"), ("Craft CMS", "cms", r"craftcms|cpresources"),
    ("HubSpot CMS", "cms_moderne", r"hs-sites\.com|hubspotusercontent|\.hubspot\.net/hub"),
    ("Adobe AEM", "cms", r"/etc\.clientlibs/|/content/dam/"), ("Sitecore", "cms", r"sitecore"),
    ("Kentico", "cms", r"kentico"), ("Umbraco", "cms", r"umbraco"), ("Odoo", "cms", r"/web/assets/|odoo"),
    ("Magento", "ecommerce", r"mage/cookies|magento"), ("PrestaShop", "ecommerce", r"prestashop"),
    ("WooCommerce", "ecommerce", r"woocommerce"),
    ("Next.js", "framework", r"__NEXT_DATA__|/_next/static"), ("Nuxt", "framework", r"__NUXT__|/_nuxt/"),
    ("Gatsby", "framework", r"___gatsby"), ("Angular", "framework", r"ng-version="), ("React", "framework", r"data-reactroot|react-dom"),
    ("Vue.js", "framework", r"data-v-[0-9a-f]{8}|vue(?:\.min)?\.js"), ("Svelte", "framework", r"svelte-[a-z0-9]{5,}"),
    ("Google Tag Manager", "analytics", r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]{4,}"),
    ("Google Analytics 4", "analytics", r"gtag/js\?id=G-|G-[A-Z0-9]{8,}"), ("Matomo", "analytics", r"matomo|piwik"),
    ("Hotjar", "analytics", r"hotjar"), ("Microsoft Clarity", "analytics", r"clarity\.ms"),
    ("Plausible", "analytics", r"plausible\.io"),
    ("HubSpot", "marketing", r"js\.hs-scripts\.com|js\.hsforms|hs-analytics|hubspot"),
    ("Salesforce / Pardot", "marketing", r"pardot|salesforce|force\.com"), ("Marketo", "marketing", r"munchkin|marketo"),
    ("Mailchimp", "marketing", r"list-manage\.com|mailchimp|mc\.us\d"), ("Brevo / Sendinblue", "marketing", r"sibforms|sendinblue|brevo"),
    ("ActiveCampaign", "marketing", r"activecampaign|trackcmp"), ("Mautic", "marketing", r"mautic"),
    ("Leadfeeder / Dealfront", "marketing", r"lfeeder|leadfeeder|dealfront"), ("Apollo tracking", "marketing", r"assets\.apollo\.io"),
    ("ZoomInfo", "marketing", r"zoominfo"), ("LinkedIn Insight", "marketing", r"snap\.licdn\.com|_linkedin_partner_id"),
    ("Meta Pixel", "marketing", r"connect\.facebook\.net/[^\"']*/fbevents"),
    ("Intercom", "chat", r"widget\.intercom\.io|intercomcdn"), ("Drift", "chat", r"js\.driftt|drift\.com"),
    ("Crisp", "chat", r"client\.crisp\.chat"), ("Tidio", "chat", r"code\.tidio\.co"), ("Zendesk", "chat", r"zdassets|zopim"),
    ("Freshchat", "chat", r"freshchat|freshworks"), ("LiveChat", "chat", r"livechatinc"), ("tawk.to", "chat", r"embed\.tawk\.to"),
    ("HubSpot Chat", "chat", r"usemessages\.com"), ("Userlike", "chat", r"userlike"),
    ("Assistant IA (chatbot)", "chat_ia", r"chatbase\.co|voiceflow|botpress|landbot|botsonic|dante-ai|mendable|"
                                            r"<[^>]+(?:id|class)=[\"'][^\"']*(?:chatbot|ai-assistant|ki-assistent)"),
    ("Cookiebot", "consent", r"cookiebot"), ("OneTrust", "consent", r"onetrust|cookielaw"),
    ("Usercentrics", "consent", r"usercentrics"), ("Didomi", "consent", r"didomi"), ("Borlabs", "consent", r"borlabs"),
    ("Complianz", "consent", r"complianz"), ("CookieYes", "consent", r"cookieyes"), ("iubenda", "consent", r"iubenda"),
    ("Axeptio", "consent", r"axeptio"),
    ("Cloudflare", "infra", r"cdn-cgi/|cloudflare"), ("Vercel", "infra", r"vercel"), ("Netlify", "infra", r"netlify"),
    ("AWS CloudFront", "infra", r"cloudfront\.net|x-amz-cf"), ("Infomaniak", "infra", r"infomaniak"),
    ("Hostpoint", "infra", r"hostpoint"),
    ("Boutique en ligne", "ecommerce", r"add-to-cart|ajouter au panier|in den warenkorb|add to cart|/cart\b|/panier\b|warenkorb"),
    ("Portail client / login", "portail", r"espace client|kundenportal|customer portal|client portal|my account|mon compte|"
                                          r"mein konto|/login\b|/portal\b|extranet|b2b-?shop"),
    ("Configurateur / 3D", "portail", r"configurat(?:eur|or)|konfigurator|three\.js|sketchfab|model-viewer|3d viewer"),
    ("Calendly", "marketing", r"calendly\.com"), ("Typeform", "marketing", r"typeform"),
]
STACK_RX = [(n, c, re.compile(rx, re.I)) for n, c, rx in STACK]

PAGE_TYPES = {
    "actualites": re.compile(r"news|actualit|aktuell|neuigkeit|blog|presse|press|media|medien|communiqu|evenement|events?\b|magazin|stories", re.I),
    "carrieres": re.compile(r"job|career|carri|emploi|stellen|karriere|recrut|join-?us|rejoindre|offres|vacanc|work-with-us", re.I),
    "a_propos": re.compile(r"about|a-propos|qui-sommes|ueber-uns|uber-uns|unternehmen|company|entreprise|histoire|history|team|equipe", re.I),
    "innovation": re.compile(r"innovation|technolog|r-?d\b|recherche|forschung|industrie-?4|digital|engineering|competenc|savoir-faire", re.I),
}
QUOTA = {"actualites": 2, "carrieres": 2, "a_propos": 1, "innovation": 1}
# Une offre = une ligne avec un marqueur d'annonce (m/w/d, H/F, 80-100 %, apprenti...) ; « tech » = rôle IT / data / automation
JOB_ITEM = re.compile(r"\((?:m|w|f|h|d)\s*/\s*(?:m|w|f|h|d)(?:\s*/\s*(?:m|w|f|h|d|x))?\)|\b\d{2,3}\s*[-\u2013à]\s*\d{2,3}\s*%|"
                      r"\b100\s*%|\bH/F\b|\bF/H\b|\bm/w/d\b|\(all genders\)|\(a\)|\bapprenti|\bstagiaire|\bpraktik|"
                      r"\blehrstelle|\bCDI\b|\bCDD\b", re.I)
JOB_TECH = re.compile(r"informaticien|informatique|développeu|developpeu|developer|entwickler|software|logiciel|data\b|"
                      r"devops|cloud|cyber|automaticien|automation engineer|automatisierung|robot|machine learning|"
                      r"business analyst|system engineer|ingénieur système|informatiker|applikationsentwickler|"
                      r"digital|numérique|(?<![A-Za-z])(?:IT|ICT|ERP|SAP|IA|AI|KI|BI)(?![A-Za-z])")


COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-\u2013]\s*)?(20\d\d)", re.I)


def same_site(u: str, root: str) -> bool:
    a, b = domain(u), domain(root)
    return a == b or a.endswith("." + b) or b.endswith("." + a) or a.split(".")[-2:] == b.split(".")[-2:]


def soup_text(html: str) -> tuple:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html[:MAX_HTML], "lxml")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return soup, soup.get_text("\n", strip=True)


def nearest_date(text: str, pos: int, span: int = 350) -> str:
    win = text[max(0, pos - span): pos + span]
    ds = all_dates(win)
    return iso(max(ds)) if ds else ""


def scan_page(url: str, ptype: str) -> dict:
    r = get(url, timeout=15)
    if r is None or r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
        return {"type": ptype, "url": url, "statut": r.status_code if r is not None else "erreur"}
    soup, text = soup_text(r.text)
    dates = [d for d in all_dates(text) if months_ago(d) is not None and months_ago(d) >= -2]
    hits = []
    for h in detect(text):
        pos = text.find(h["terme"])
        hits.append({**h, "date": nearest_date(text, pos) if pos >= 0 else "", "source": f"site_{ptype}", "url": r.url})
    out = {"type": ptype, "url": r.url, "statut": r.status_code, "derniere_date": iso(max(dates)) if dates else "",
           "n_dates_24m": sum(1 for d in dates if months_ago(d) <= 24), "tech": tech_counts(text), "signaux": hits}
    if ptype == "carrieres":
        lines = [ln.strip() for ln in text.split("\n") if 8 <= len(ln.strip()) <= 120]
        jobs = [ln for ln in lines if JOB_ITEM.search(ln)]
        out["offres_estimees"] = len(dict.fromkeys(jobs))
        out["postes_tech"] = list(dict.fromkeys(j for j in jobs if JOB_TECH.search(j) or JOB_TECH.search(j.lower())))[:8]
        out["exemples_postes"] = list(dict.fromkeys(jobs))[:8]
    return out


def sitemap_info(root: str) -> dict:
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        r = get(urljoin(root, path), timeout=12)
        if r is None or r.status_code != 200 or "<" not in r.text[:200]:
            continue
        lastmods = re.findall(r"<lastmod>\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", r.text)
        return {"sitemap": r.url, "n_urls": r.text.count("<loc>"),
                "dernier_lastmod": max(lastmods) if lastmods else ""}
    return {}


def crawl(e: dict) -> dict:
    root = e["site"]
    if not root.startswith("http"):
        root = "https://" + root
    r = get(root, timeout=18)
    if r is None:
        return {"statut": "injoignable", "url": root}
    if r.status_code >= 400:
        return {"statut": f"http_{r.status_code}", "url": root}
    html = r.text[:MAX_HTML]
    blob = html + "\n" + "\n".join(f"{k}: {v}" for k, v in r.headers.items())
    stack = sorted({(n, c) for n, c, rx in STACK_RX if rx.search(blob)})
    soup, text = soup_text(html)
    langs = set()
    if soup.html and soup.html.get("lang"):
        langs.add(soup.html["lang"][:2].lower())
    for l in soup.find_all("link", hreflang=True):
        langs.add(l["hreflang"][:2].lower())
    links = {}
    for a in soup.find_all("a", href=True):
        u = urljoin(r.url, a["href"]).split("#")[0]
        if not u.startswith("http") or not same_site(u, r.url) or re.search(r"\.(pdf|jpe?g|png|zip|docx?)$", u, re.I):
            continue
        m = re.search(r"/(fr|de|en|it)(?:/|$)", urlparse(u).path)
        if m:
            langs.add(m.group(1))
        label = f"{urlparse(u).path} {a.get_text(' ', strip=True)}"
        for ptype, rx in PAGE_TYPES.items():
            if rx.search(label):
                links.setdefault(ptype, [])
                if u not in links[ptype] and u.rstrip("/") != r.url.rstrip("/"):
                    links[ptype].append(u)
    chosen = [(ptype, u) for ptype, us in links.items() for u in us[: QUOTA[ptype]]]
    home_hits = []
    for h in detect(text):
        pos = text.find(h["terme"])
        home_hits.append({**h, "date": nearest_date(text, pos) if pos >= 0 else "", "source": "site_accueil", "url": r.url})
    pages = [scan_page(u, ptype) for ptype, u in chosen[:6]]
    cr = [int(y) for y in COPYRIGHT.findall(html)]
    sm = sitemap_info(r.url)
    dates = [p.get("derniere_date") for p in pages if p.get("derniere_date")] + ([sm["dernier_lastmod"]] if sm.get("dernier_lastmod") else [])
    tech = Counter(tech_counts(text))
    for p in pages:
        tech.update(p.get("tech") or {})
    jobs = [p for p in pages if p["type"] == "carrieres" and p.get("statut") == 200]
    return {
        "statut": "ok", "url": r.url, "https": r.url.startswith("https"),
        "serveur": r.headers.get("server", ""), "titre": clip(soup.title.get_text() if soup.title else "", 120),
        "description": clip((soup.find("meta", attrs={"name": "description"}) or {}).get("content", "") if soup.find("meta", attrs={"name": "description"}) else "", 300),
        "stack": [n for n, _ in stack], "stack_categories": sorted({c for _, c in stack}),
        "langues": sorted(x for x in langs if re.fullmatch(r"[a-z]{2}", x)),
        "copyright": max(cr) if cr else None,
        "derniere_date": max(dates) if dates else "",
        "sitemap": sm,
        "tech": dict(tech),
        "pages": [{k: v for k, v in p.items() if k != "signaux"} for p in pages],
        "carrieres": {"url": jobs[0]["url"], "offres_estimees": max(p.get("offres_estimees", 0) for p in jobs),
                      "postes_tech": sorted({t for p in jobs for t in p.get("postes_tech", [])})[:8],
                      "exemples_postes": jobs[0].get("exemples_postes", [])} if jobs else {},
        "signaux": home_hits + [h for p in pages for h in p.get("signaux", [])],
        "collecte": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Sites web des entreprises de la campagne (stack, mentions tech, recrutement).")
    argument_campagne(ap)
    ap.add_argument("--workers", type=int, default=8, help="sites en parallèle (défaut 8)")
    ap.add_argument("--refresh", action="store_true", help="refait tous les sites (sinon : absents ou en échec)")
    a = ap.parse_args()
    ouvrir(a.campagne)
    store = Store(donnees() / "site.json")
    ents = [e for e in load_entities() if e.get("site") and "particulier" not in e["flags"]]
    todo = [e for e in ents if a.refresh or e["id"] not in store or store.get(e["id"], {}).get("statut") != "ok"]
    print(f"{len(ents)} sites, {len(todo)} à analyser", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(crawl, e): e for e in todo}
        for i, f in enumerate(as_completed(futs), 1):
            e = futs[f]
            try:
                rec = f.result()
            except Exception as err:  # noqa: BLE001
                rec = {"statut": f"erreur : {err.__class__.__name__}: {str(err)[:100]}"}
            store.put(e["id"], rec, flush_every=10)
            print(f"[{i}/{len(todo)}] {e['id']} -> {rec['statut']} | {', '.join(rec.get('stack', [])[:6])} | "
                  f"tech {rec.get('tech', {})} | jobs {rec.get('carrieres', {}).get('offres_estimees', '-')}", flush=True)
            polite_sleep(0.2, 0.6)
    store.flush()
    print(Counter(v["statut"] for v in store.data.values()))


if __name__ == "__main__":
    main()
