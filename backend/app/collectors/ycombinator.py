"""
Atlas - Y Combinator Collector
================================
Collecte les startups YC via l'API publique du YC Company Directory.

API : https://api.ycombinator.com/v0.1/companies
- Pas d'authentification requise
- Données riches : batch, statut, description, tags, fondateurs
- ~4 000 entreprises indexées (toutes promotions depuis 2005)

Données récupérées :
- Nom, slug, description courte et longue
- Site web, logo
- Batch YC (W23, S22…) → année de fondation approximative
- Industries/tags → sector/tags Atlas
- Statut (Active, Acquired, Inactive, Public)
- Taille (Small, Medium, Large) → employees approximatif
"""

import re

from app.collectors.base import BaseCollector, CollectorResult, CompanyData
from app.models.company import CompanyStatus, CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySourceName

# Mapping batch YC → année approximative de fondation
def _batch_to_year(batch: str | None) -> int | None:
    if not batch:
        return None
    # Format : W23, S22, W2024, IK12, etc.
    m = re.search(r"(\d{2,4})$", batch)
    if not m:
        return None
    year_str = m.group(1)
    if len(year_str) == 2:
        year = 2000 + int(year_str)
    else:
        year = int(year_str)
    return year if 2005 <= year <= 2030 else None


YC_STATUS_MAP = {
    "Active": CompanyStatus.ACTIVE,
    "Inactive": CompanyStatus.INACTIVE,
    "Acquired": CompanyStatus.ACQUIRED,
    "Public": CompanyStatus.ACTIVE,
}

# Mapping industries YC → sector Atlas
YC_INDUSTRY_MAP = {
    "B2B": None,
    "Consumer": "Consumer Discretionary",
    "Healthcare": "Healthcare",
    "Fintech": "Financials",
    "Education": "Consumer Discretionary",
    "Real Estate": "Real Estate",
    "Climate": "Energy",
    "Hard Tech": "Technology",
    "Government": "Industrials",
    "Biotech": "Healthcare",
    "Robotics": "Technology",
    "Security": "Technology",
    "Developer Tools": "Technology",
    "Infrastructure": "Technology",
    "Artificial Intelligence": "Technology",
    "Machine Learning": "Technology",
}

YC_EMPLOYEES_MAP = {
    "1-10": 5,
    "11-50": 30,
    "51-200": 100,
    "201-500": 350,
    "501-1000": 750,
    "1000+": 1500,
}


class YCombinatorCollector(BaseCollector):
    """
    Collecteur Y Combinator.

    Paramètres :
    - limit (int) : max d'entreprises à collecter (défaut 1000)
    - batch (str) : filtrer par batch (ex: "W24") — optionnel
    - status (str) : filtrer par statut ("Active", "Public"…) — optionnel
    """

    BASE_URL = "https://api.ycombinator.com/v0.1/companies"

    @property
    def source_name(self) -> DiscoverySourceName:
        return DiscoverySourceName.YCOMBINATOR

    async def collect(self, job: DiscoveryJob) -> CollectorResult:
        result = CollectorResult()
        limit = self.params.get("limit", 1000)
        batch_filter = self.params.get("batch")
        status_filter = self.params.get("status")

        page = 1
        collected = 0

        while collected < limit:
            params: dict = {"page": page}
            if batch_filter:
                params["batch"] = batch_filter

            try:
                resp = await self._get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                result.add_error(f"fetch:page{page}", str(e))
                break

            companies = data.get("companies", [])
            if not companies:
                break

            for entry in companies:
                if collected >= limit:
                    break
                # Filtre statut si demandé
                if status_filter and entry.get("status") != status_filter:
                    continue
                company = self._normalize(entry)
                if company:
                    result.companies.append(company)
                    collected += 1

            # Pagination
            if not data.get("nextPage"):
                break
            page += 1

        result.meta["pages_fetched"] = page
        self.logger.info(
            "YC collection complete",
            companies=len(result.companies),
            errors=len(result.errors),
        )
        return result

    def _normalize(self, entry: dict) -> CompanyData | None:
        name = (entry.get("name") or "").strip()
        if not name:
            return None

        slug = entry.get("slug", "")
        batch = entry.get("batch")
        status_str = entry.get("status", "Active")
        status = YC_STATUS_MAP.get(status_str, CompanyStatus.ACTIVE)
        industries = entry.get("industries", [])
        tags_yc = entry.get("tags", [])

        # Sector depuis industries YC
        sector = None
        for ind in industries:
            if ind in YC_INDUSTRY_MAP and YC_INDUSTRY_MAP[ind]:
                sector = YC_INDUSTRY_MAP[ind]
                break

        # Employees depuis team_size
        team_size = entry.get("teamSize") or entry.get("team_size") or ""
        employees = YC_EMPLOYEES_MAP.get(str(team_size))

        # Tags combinés
        tags = ["ycombinator"]
        if batch:
            tags.append(f"yc-{batch.lower()}")
        tags.extend([t.lower().replace(" ", "-") for t in tags_yc[:5]])

        desc_long = entry.get("long_description") or entry.get("description") or None
        desc_short = entry.get("one_liner") or entry.get("short_description") or None
        if desc_short:
            desc_short = desc_short[:500]

        # Type : Public si le statut est "Public"
        company_type = CompanyType.PUBLIC if status_str == "Public" else CompanyType.PRIVATE

        return CompanyData(
            name=name,
            country="US",  # YC est majoritairement US
            country_name="United States",
            company_type=company_type,
            sector=sector,
            industry=", ".join(industries[:2]) if industries else None,
            description=desc_long,
            description_short=desc_short,
            website=entry.get("website") or entry.get("url"),
            logo_url=entry.get("smallLogoUrl") or entry.get("logo_url"),
            founded_year=_batch_to_year(batch),
            employees=employees,
            external_id=slug or name,
            external_url=f"https://www.ycombinator.com/companies/{slug}" if slug else None,
            tags=tags,
            raw_data={
                "slug": slug,
                "batch": batch,
                "status": status_str,
                "industries": industries,
                "team_size": team_size,
            },
        )
