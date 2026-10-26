"""Petit client de l'API REST Apollo (https://docs.apollo.io/reference/apollo-api), sans connecteur MCP.

- Clé : APOLLO_API_KEY, lue par commun.cle_apollo() (variable d'environnement, sinon fichier .env), jamais affichée.
- Débit : on reste sous 80 % de plafonds courants (LIMITES : appels par minute et par heure, en mémoire) et on reprend
  les erreurs 429 et 5xx (en-tête retry-after, sinon 5, 10, 20, 40, 60, 60 s ; 6 essais). Baisser LIMITES si le plan
  Apollo du compte est plus petit (voir les statistiques d'usage de l'API dans Apollo).
- Cache disque des recherches de personnes et de l'enrichissement dans <campagne>/apollo/cache/ : relancer un script
  ne refait pas les requêtes et ne recrédite rien. Le contenu des listes (comptes, contacts), les listes et les champs
  sont lus en direct : ils changent d'un passage à l'autre. Ces réponses contiennent des données personnelles : ne pas
  les partager.
- Crédits : seul enrichir() (people/bulk_match) en consomme, 1 par personne trouvée, plus 8 par mobile demandé.
  Tout le reste (recherche de personnes, comptes, contacts, listes, champs) est gratuit.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections import deque
from pathlib import Path

import requests

from commun import ORDRE_ENTREE, ORDRE_RELAIS, cle_apollo, code_pays

BASE = "https://api.apollo.io/api/v1"

# catégorie -> (appels max par minute, par heure) : 80 % de plafonds courants (recherche de personnes 200/min et
# 6 000/h ; enrichissement 1 000/min ; contacts et comptes 200/min et 400/h ; organisations 200/min et 400/h)
LIMITES = {
    "people_search": (160, 4800),
    "enrich": (800, None),
    "contacts": (160, 320),
    "org_search": (160, 320),
    "autre": (100, None),
}

# nom de pays attendu par Apollo (person_locations[]) pour un code ISO
PAYS_APOLLO = {"CH": "Switzerland", "FR": "France", "DE": "Germany", "IT": "Italy", "AT": "Austria",
               "LI": "Liechtenstein", "BE": "Belgium", "LU": "Luxembourg", "NL": "Netherlands", "ES": "Spain",
               "PT": "Portugal", "GB": "United Kingdom", "IE": "Ireland", "US": "United States", "CA": "Canada",
               "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "FI": "Finland", "PL": "Poland", "CZ": "Czechia",
               "HU": "Hungary", "RO": "Romania", "SI": "Slovenia", "SK": "Slovakia", "GR": "Greece", "MC": "Monaco"}


def nom_pays_apollo(code: str) -> str:
    return PAYS_APOLLO.get((code or "").upper(), "")


def code_pays_apollo(nom: str) -> str:
    """Pays renvoyé par Apollo (« Switzerland », « Monaco ») -> code ISO ; vide si inconnu."""
    return code_pays(nom) or next((k for k, v in PAYS_APOLLO.items() if v.lower() == (nom or "").strip().lower()), "")


def pays_contacts(config: dict) -> set[str]:
    """Pays où un contact peut être basé : [apollo] pays_contacts, sinon [cible] pays et pays_voisins (codes ISO).
    Vide : aucun filtre de pays."""
    liste = lambda v: [v] if isinstance(v, str) else list(v or [])
    pays = liste(config["apollo"].get("pays_contacts")) or \
        [*liste(config["cible"].get("pays")), *liste(config["cible"].get("pays_voisins"))]
    return {str(p).strip().upper() for p in pays if str(p).strip()}


def fichier_liste(nom: str) -> str:
    """Nom du CSV d'export d'une liste : « Industrie · Direction · Novembre - entrée » -> industrie-direction-novembre-entree.csv."""
    s = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") + ".csv"


def noms_listes(base: str) -> list[str]:
    """Les trois listes de contacts d'une campagne : globale, entrée, relais."""
    return [base, f"{base} - {ORDRE_ENTREE}", f"{base} - {ORDRE_RELAIS}"]


class ErreurApollo(RuntimeError):
    def __init__(self, statut: int, message: str):
        super().__init__(message)
        self.statut = statut


class Apollo:
    def __init__(self, cache: str | Path):
        self.s = requests.Session()
        self.s.headers.update({"x-api-key": cle_apollo(), "Content-Type": "application/json",
                               "Cache-Control": "no-cache", "accept": "application/json"})
        self.hist = {k: deque() for k in LIMITES}
        self.appels = 0
        self.quota = {}
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _attendre(self, cat):
        par_min, par_h = LIMITES[cat]
        h = self.hist[cat]
        while True:
            now = time.time()
            while h and now - h[0] > 3600:
                h.popleft()
            derniere_min = sum(1 for t in h if now - t < 60)
            if derniere_min < par_min and (par_h is None or len(h) < par_h):
                break
            time.sleep(1)
        h.append(time.time())

    def _envoyer(self, cat, meth, path, params=None, body=None):
        """Réponse brute, après reprise des 429 et 5xx."""
        for essai in range(6):
            self._attendre(cat)
            r = self.s.request(meth, BASE + path, params=params, json=body, timeout=60)
            self.appels += 1
            self.quota = {k: v for k, v in r.headers.items()
                          if "usage" in k.lower() or "left" in k.lower() or "limit" in k.lower()}
            if r.status_code == 429 or r.status_code >= 500:
                pause = int(float(r.headers.get("retry-after") or 0)) or min(60, 5 * 2 ** essai)
                print(f"  [{r.status_code}] {path} : pause {pause}s")
                time.sleep(pause)
                continue
            if r.status_code in (401, 403):
                raise SystemExit(f"Apollo refuse {meth} {path} ({r.status_code}) : clé invalide ou sans ce droit. "
                                 "Utilisez une clé master, ou ajoutez ce point d'accès à la clé (Settings > "
                                 "Integrations > API, README.md).")
            return r
        raise ErreurApollo(0, f"{meth} {path} : abandon après 6 essais")

    def _req(self, cat, meth, path, params=None, body=None, cache=False):
        fichier = None
        if cache:
            brut = json.dumps([meth, path, params, body], sort_keys=True, ensure_ascii=False)
            fichier = self.cache / (hashlib.sha1(brut.encode()).hexdigest()[:20] + ".json")
            if fichier.exists():
                return json.loads(fichier.read_text(encoding="utf-8"))
        r = self._envoyer(cat, meth, path, params, body)
        if r.status_code >= 400:
            raise ErreurApollo(r.status_code, f"{meth} {path} -> {r.status_code} : {r.text[:400]}")
        data = r.json() if r.content else {}
        if fichier:
            fichier.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data

    # --- lecture (0 crédit) ---
    def listes(self):
        """Toutes les listes (labels) du compte : [{id, name, modality, cached_count...}]."""
        d = self._req("autre", "GET", "/labels")
        return d if isinstance(d, list) else d.get("labels") or []

    def liste(self, nom, modality):
        """La liste de ce nom ; sinon arrêt avec les noms disponibles."""
        toutes = [l for l in self.listes() if l.get("modality") == modality]
        trouvee = next((l for l in toutes if l.get("name") == nom), None)
        if not trouvee:
            dispo = ", ".join(f"« {l.get('name')} »" for l in toutes) or "aucune"
            raise SystemExit(f"Liste Apollo introuvable : « {nom} » ({modality}). Listes disponibles : {dispo}. "
                             "Corrigez le nom dans campagne.toml ([apollo]) ou créez la liste (creer_comptes.py).")
        return trouvee

    def comptes(self, label_ids=None, page=1, per_page=100):
        """Comptes enregistrés dans des listes (lecture directe, sans cache : la liste fait foi, et elle se remplit
        après coup quand creer_comptes.py --go ou un import à la main passe après un premier essai)."""
        body = {"page": page, "per_page": per_page}
        if label_ids:
            body["account_label_ids"] = label_ids
        return self._req("contacts", "POST", "/accounts/search", body=body)

    def personnes(self, organization_ids=None, domaines=None, nom=None, titres=None, mots=None, lieux=None,
                  page=1, per_page=100):
        params = {"page": page, "per_page": per_page}
        if lieux:
            params["person_locations[]"] = lieux
        if mots:
            params["q_keywords"] = mots
        if organization_ids:
            params["organization_ids[]"] = organization_ids
        if domaines:
            params["q_organization_domains_list[]"] = domaines
        if nom:
            params["q_person_name"] = nom
        if titres:
            params["person_titles[]"] = titres
        return self._req("people_search", "POST", "/mixed_people/api_search", params=params, cache=True)

    def contacts_search(self, label_ids, page=1, per_page=100):
        """Contacts enregistrés dans des listes (lecture directe, sans cache : la liste fait foi)."""
        return self._req("contacts", "POST", "/contacts/search",
                         body={"contact_label_ids": label_ids, "page": page, "per_page": per_page})

    def champs(self, modality="contact"):
        """Champs personnalisés {nom: id} d'une modalité (contact ou account)."""
        d = self._req("autre", "GET", "/typed_custom_fields")
        return {c["name"]: c["id"] for c in d.get("typed_custom_fields") or [] if c.get("modality") == modality}

    def resultat_webhook(self, request_id, essais=8):
        """Résultat d'un enrichissement asynchrone (mobiles) : attend tant qu'Apollo répond « result_pending »."""
        fichier = self.cache / f"webhook-{re.sub(r'[^0-9A-Za-z-]', '', str(request_id))}.json"
        if fichier.exists():
            return json.loads(fichier.read_text(encoding="utf-8"))
        for _ in range(essais):
            r = self._envoyer("enrich", "GET", f"/webhook_result/{request_id}")
            data = r.json() if r.content else {}
            if r.status_code == 404 and data.get("error_code") == "result_pending":
                time.sleep(float(data.get("retry_after_seconds") or 10))
                continue
            if r.status_code >= 400:
                print(f"  résultat {request_id} indisponible ({r.status_code} {data.get('error_code', '')})")
                return {}
            if data.get("status") == "success":
                fichier.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        print(f"  résultat {request_id} encore en cours : relancer plus tard (le cache garde la demande)")
        return {}

    # --- écriture / crédits ---
    def enrichir(self, details, mobiles=False):
        """bulk_match (10 max) : {"id"} ou {"linkedin_url", "first_name", "last_name", "domain"} ; 1 crédit par
        personne trouvée, sans email personnel ; mobiles=True : +8 crédits par numéro, résultat asynchrone
        (request_id, à lire avec resultat_webhook)."""
        assert len(details) <= 10
        params = {"reveal_personal_emails": "false", "reveal_phone_number": "true" if mobiles else "false"}
        if mobiles:
            params["poll_only"] = "true"
        return self._req("enrich", "POST", "/people/bulk_match", params=params, body={"details": details}, cache=True)

    def creer_contacts(self, contacts, listes):
        """bulk_create (100 max), dédoublonnage Apollo activé, ajout aux listes nommées (les contacts déjà présents
        reviennent dans existing_contacts et doivent être ajoutés aux listes à part)."""
        assert len(contacts) <= 100
        return self._req("contacts", "POST", "/contacts/bulk_create",
                         body={"contacts": contacts, "append_label_names": listes, "run_dedupe": True})

    def creer_comptes(self, comptes):
        """accounts/bulk_create (100 max), dédoublonnage activé : les comptes déjà présents reviennent dans
        existing_accounts, inchangés. Deux lignes du même domaine dans un lot créent deux comptes : les fusionner avant."""
        assert len(comptes) <= 100
        return self._req("contacts", "POST", "/accounts/bulk_create", body={"accounts": comptes, "run_dedupe": True})

    def creer_liste(self, nom, modality="contacts"):
        """liste vide (le nom doit être unique pour la modalité : 422 sinon)."""
        return self._req("contacts", "POST", "/labels", body={"name": nom, "modality": modality})

    def ajouter_aux_listes(self, ids, noms_listes, modality="contacts"):
        """ajoute des contacts ou des comptes à des listes sans toucher à leurs autres listes (crée les listes
        manquantes)."""
        return self._req("contacts", "POST", "/labels/add_entity_ids_to_label_names",
                         body={"entity_ids": ids, "label_names": noms_listes, "modality": modality})

    def retirer_des_listes(self, ids, noms_listes, modality="contacts"):
        """retire des contacts ou des comptes de listes (l'enregistrement lui-même n'est pas supprimé)."""
        return self._req("contacts", "POST", "/labels/remove_entity_ids_from_label_names",
                         body={"entity_ids": ids, "label_names": noms_listes, "modality": modality})

    def creer_champ(self, label, modality="contact", type_="textarea"):
        """champ personnalisé ; renvoie son id."""
        d = self._req("autre", "POST", "/fields", body={"label": label, "modality": modality, "type": type_})
        cree = next((c for c in d.get("typed_custom_fields") or [] if c.get("name") == label), None)
        if not cree:
            raise ErreurApollo(0, f"création du champ {label} : réponse inattendue {str(d)[:200]}")
        return cree["id"]

    def maj_contacts(self, attributs):
        """contacts/bulk_update (100 max, traité tout de suite) : [{id, typed_custom_fields: {id_champ: valeur}}]."""
        assert len(attributs) <= 100
        return self._req("contacts", "POST", "/contacts/bulk_update", body={"contact_attributes": attributs})
