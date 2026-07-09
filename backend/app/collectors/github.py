"""
Atlas - GitHub Collector
=========================
Découvre des entreprises via leur présence open source sur GitHub.

Stratégie :
  Interroge l'API GitHub Search pour trouver les organisations
  ayant le plus de followers et de repos publics — signal proxy
  d'une forte activité tech.

  On cible les organisations (type=org) car elles correspondent
  à des entreprises, pas à des développeurs individuels.

API utilisée : https://api.github.com/search/users
- Authentification : token optionnel (rate limit 60/h sans, 5000/h avec)
- Token configuré via env var GITHUB_TOKEN

Signaux collectés :
- Nombre de repos publics → proxy d'activité
- Followers → proxy de réputation
- Description de l'org → description courte
- Blog/website → site web de l'entreprise
- Location → pays (approximatif)
- Email → contact

Limitations :
- La localisation GitHub est libre (pas de code pays standardisé)
- Beaucoup d'orgs n'ont pas de ticker (entreprises privées majoritairement)
- Le mapping location → country_code est approximatif
"""

import re

from app.collectors.base import BaseCollector, CollectorResult, CompanyData
from app.models.company import CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySourceName

# Mapping simplifié des termes de localisation → code pays ISO
LOCATION_COUNTRY_MAP: dict[str, str] = {
    "usa": "US", "united states": "US", "us": "US",
    "california": "US", "new york": "US", "san francisco": "US",
    "seattle": "US", "austin": "US", "boston": "US",
    "uk": "GB", "united kingdom": "GB", "england": "GB", "london": "GB",
    "germany": "DE", "deutschland": "DE", "berlin": "DE",
    "france": "FR", "paris": "FR",
    "canada": "CA", "toronto": "CA", "vancouver": "CA",
    "china": "CN", "beijing": "CN", "shanghai": "CN",
    "israel": "IL", "tel aviv": "IL",
    "india": "IN", "bangalore": "IN",
    "netherlands": "NL", "amsterdam": "NL",
    "sweden": "SE", "stockholm": "SE",
    "australia": "AU", "sydney": "AU",
    "switzerland": "CH", "zurich": "CH",
    "japan": "JP", "tokyo": "JP",
    "taiwan": "TW",
    "singapore": "SG",
    "brazil": "BR", "são paulo": "BR",
}


def _parse_country(location: str | None) -> str:
    """Tente d'extraire un code pays depuis la localisation libre GitHub."""
    if not location:
        return "US"  # défaut conservateur
    loc_lower = location.lower().strip()
    for keyword, code in LOCATION_COUNTRY_MAP.items():
        if keyword in loc_lower:
            return code
    return "US"


def _extract_website(blog: str | None) -> str | None:
    """Normalise le champ blog GitHub en URL propre."""
    if not blog:
        return None
    blog = blog.strip()
    if not blog.startswith(("http://", "https://")):
        blog = f"https://{blog}"
    return blog


class GitHubCollector(BaseCollector):
    """
    Collecteur d'organisations GitHub.

    Paramètres acceptés :
    - min_followers (int) : seuil de followers minimum (défaut 100)
    - min_repos (int) : seuil de repos publics minimum (défaut 10)
    - limit (int) : nombre d'organisations max (défaut 300)
    - queries (list[str]) : requêtes de recherche custom

    L'API GitHub Search retourne max 1000 résultats par requête.
    On effectue plusieurs requêtes ciblées pour maximiser la diversité.
    """

    BASE_URL = "https://api.github.com"
    # Requêtes de recherche couvrant différents segments tech
    DEFAULT_QUERIES = [
        "type:org followers:>1000",
        "type:org followers:>500 location:Europe",
        "type:org followers:>200 topic:artificial-intelligence",
        "type:org followers:>200 topic:cybersecurity",
        "type:org followers:>200 topic:blockchain",
    ]

    @property
    def source_name(self) -> DiscoverySourceName:
        return DiscoverySourceName.GITHUB

    def _build_client(self):
        import httpx
        from app.core.config import get_settings
        settings = get_settings()
        token = self.params.get("token") or getattr(settings, "github_token", None)
        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            headers=headers,
            follow_redirects=True,
        )

    async def collect(self, job: DiscoveryJob) -> CollectorResult:
        result = CollectorResult()
        limit = self.params.get("limit", 300)
        min_followers = self.params.get("min_followers", 100)
        queries = self.params.get("queries", self.DEFAULT_QUERIES)

        seen_logins: set[str] = set()
        collected = 0

        for query in queries:
            if collected >= limit:
                break

            page = 1
            while collected < limit:
                try:
                    resp = await self._get(
                        f"{self.BASE_URL}/search/users",
                        params={"q": query, "per_page": 30, "page": page},
                    )
                    if resp.status_code == 422:
                        break  # Requête invalide, passer à la suivante
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    result.add_error(f"search:{query}:page{page}", str(e))
                    break

                items = data.get("items", [])
                if not items:
                    break

                for item in items:
                    if collected >= limit:
                        break
                    login = item.get("login", "")
                    if login in seen_logins:
                        continue
                    seen_logins.add(login)

                    # Récupérer le détail de l'organisation
                    try:
                        org = await self._fetch_org_detail(login)
                        if not org:
                            continue
                        followers = org.get("followers", 0)
                        if followers < min_followers:
                            continue
                        company = self._normalize(org)
                        if company:
                            result.companies.append(company)
                            collected += 1
                    except Exception as e:
                        result.add_error(f"org_detail:{login}", str(e))

                # Vérifier si on a atteint la dernière page
                total = data.get("total_count", 0)
                if page * 30 >= min(total, 1000):
                    break
                page += 1

        result.meta["queries"] = queries
        result.meta["unique_orgs_seen"] = len(seen_logins)
        self.logger.info(
            "GitHub collection complete",
            companies=len(result.companies),
            errors=len(result.errors),
        )
        return result

    async def _fetch_org_detail(self, login: str) -> dict | None:
        """Récupère les détails complets d'une organisation."""
        resp = await self._get(f"{self.BASE_URL}/orgs/{login}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def _normalize(self, org: dict) -> CompanyData | None:
        """Transforme une org GitHub en CompanyData."""
        name = (org.get("name") or org.get("login", "")).strip()
        if not name:
            return None

        login = org.get("login", "")
        description = org.get("description") or None
        location = org.get("location")
        country = _parse_country(location)
        website = _extract_website(org.get("blog"))
        public_repos = org.get("public_repos", 0)
        followers = org.get("followers", 0)

        tags = ["open-source"]
        if public_repos > 100:
            tags.append("high-activity")
        if followers > 5000:
            tags.append("popular")

        return CompanyData(
            name=name,
            country=country,
            company_type=CompanyType.PRIVATE,  # par défaut — peut être public
            description_short=description[:500] if description else None,
            website=website,
            external_id=login,
            external_url=f"https://github.com/{login}",
            tags=tags,
            raw_data={
                "login": login,
                "public_repos": public_repos,
                "followers": followers,
                "location": location,
                "email": org.get("email"),
                "created_at": org.get("created_at"),
            },
        )
