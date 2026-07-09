"""
Atlas - Crunchbase Collector (Stub)
=====================================
Structure prête pour la connexion à l'API Crunchbase.

L'API Crunchbase Basic est payante ($49/mois minimum).
Ce stub implémente le contrat BaseCollector avec des données simulées
pour les tests et valide l'architecture sans nécessiter de clé API.

Pour activer :
1. Obtenir une clé API sur https://data.crunchbase.com/
2. Ajouter CRUNCHBASE_API_KEY dans les variables d'environnement
3. Remplacer _fetch_real_data() par les vrais appels API

Endpoints Crunchbase qui seront utilisés :
- GET /autocompletes : recherche d'organisations
- GET /entities/organizations/{id} : détail
- GET /searches/organizations : recherche avancée avec filtres

Données disponibles via Crunchbase (non disponibles ailleurs) :
- Montants de levées de fonds (series A, B, C…)
- Investisseurs / VCs
- Acquisitions
- IPO date
- Nombre d'employés plus précis
- Score de ranking propriétaire
"""

from app.collectors.base import BaseCollector, CollectorResult, CompanyData
from app.models.company import CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySourceName


class CrunchbaseCollector(BaseCollector):
    """
    Collecteur Crunchbase.

    État actuel : STUB — retourne des données simulées pour valider l'architecture.
    Prêt à être connecté dès qu'une clé API est disponible.

    Paramètres :
    - api_key (str) : clé API Crunchbase (ou via env CRUNCHBASE_API_KEY)
    - limit (int) : max d'entreprises (défaut 200)
    - categories (list[str]) : catégories à cibler
    - funding_min_usd (int) : levée minimale en USD
    """

    BASE_URL = "https://api.crunchbase.com/api/v4"

    @property
    def source_name(self) -> DiscoverySourceName:
        return DiscoverySourceName.CRUNCHBASE

    def _get_api_key(self) -> str | None:
        """Récupère la clé API depuis les params ou l'environnement."""
        key = self.params.get("api_key")
        if not key:
            try:
                from app.core.config import get_settings
                settings = get_settings()
                key = getattr(settings, "crunchbase_api_key", None)
            except Exception:
                pass
        return key

    async def collect(self, job: DiscoveryJob) -> CollectorResult:
        result = CollectorResult()
        api_key = self._get_api_key()

        if not api_key:
            # Mode stub : retourne des entreprises simulées pour valider le pipeline
            self.logger.warning(
                "Crunchbase API key not configured — running in stub mode",
                job_id=str(job.id),
            )
            result.companies = self._get_stub_companies()
            result.meta["mode"] = "stub"
            result.meta["reason"] = "No API key configured"
            return result

        # ── Implémentation réelle (activée dès qu'une clé API est présente) ───
        return await self._fetch_real_data(api_key, result)

    async def _fetch_real_data(self, api_key: str, result: CollectorResult) -> CollectorResult:
        """
        Implémentation réelle de la collecte Crunchbase.
        À compléter avec les vrais endpoints.
        """
        limit = self.params.get("limit", 200)
        categories = self.params.get("categories", ["artificial-intelligence", "cybersecurity"])

        # Recherche d'organisations via l'API Crunchbase Search
        search_payload = {
            "field_ids": [
                "identifier", "short_description", "website_url",
                "primary_role", "num_employees_enum", "founded_on",
                "categories", "location_identifiers", "stock_symbol",
                "stock_exchange_symbol", "ipo_status",
            ],
            "predicate": {
                "field_id": "facet_ids",
                "operator_id": "includes",
                "values": ["company"],
            },
            "limit": min(limit, 100),
        }

        try:
            resp = await self._get(
                f"{self.BASE_URL}/searches/organizations",
                params={"user_key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

            for entity in data.get("entities", []):
                company = self._normalize_entity(entity)
                if company:
                    result.companies.append(company)

        except Exception as e:
            result.add_error("crunchbase_search", str(e))

        result.meta["mode"] = "live"
        return result

    def _normalize_entity(self, entity: dict) -> CompanyData | None:
        """Normalise une entité Crunchbase en CompanyData."""
        props = entity.get("properties", {})
        identifier = props.get("identifier", {})
        name = identifier.get("value", "").strip()
        if not name:
            return None

        permalink = identifier.get("permalink", "")
        locations = props.get("location_identifiers", [])
        country = "US"
        for loc in locations:
            if loc.get("location_type") == "country":
                country = loc.get("short_description", "US")[:2].upper()
                break

        employees_enum = props.get("num_employees_enum", "")
        employees_map = {
            "c_00001_00010": 5, "c_00011_00050": 30,
            "c_00051_00100": 75, "c_00101_00250": 175,
            "c_00251_00500": 375, "c_00501_01000": 750,
            "c_01001_05000": 3000, "c_05001_10000": 7500,
            "c_10001_max": 15000,
        }

        return CompanyData(
            name=name,
            country=country,
            company_type=CompanyType.PRIVATE,
            description_short=props.get("short_description", "")[:500] or None,
            website=props.get("website_url"),
            employees=employees_map.get(employees_enum),
            external_id=permalink,
            external_url=f"https://www.crunchbase.com/organization/{permalink}",
            tags=["crunchbase"],
            raw_data=props,
        )

    def _get_stub_companies(self) -> list[CompanyData]:
        """Données simulées pour valider le pipeline sans clé API."""
        return [
            CompanyData(
                name="Anthropic",
                country="US",
                company_type=CompanyType.PRIVATE,
                sector="Technology",
                industry="Artificial Intelligence",
                description_short="AI safety company building reliable, interpretable AI systems.",
                website="https://anthropic.com",
                founded_year=2021,
                employees=500,
                external_id="anthropic",
                external_url="https://www.crunchbase.com/organization/anthropic",
                tags=["crunchbase", "artificial-intelligence", "stub"],
            ),
            CompanyData(
                name="Mistral AI",
                country="FR",
                country_name="France",
                company_type=CompanyType.PRIVATE,
                sector="Technology",
                industry="Artificial Intelligence",
                description_short="European AI company building frontier language models.",
                website="https://mistral.ai",
                founded_year=2023,
                employees=200,
                external_id="mistral-ai",
                external_url="https://www.crunchbase.com/organization/mistral-ai",
                tags=["crunchbase", "artificial-intelligence", "stub"],
            ),
            CompanyData(
                name="Wiz",
                country="US",
                company_type=CompanyType.PRIVATE,
                sector="Technology",
                industry="Cybersecurity",
                description_short="Cloud security platform protecting enterprise environments.",
                website="https://wiz.io",
                founded_year=2020,
                employees=1500,
                external_id="wiz-2",
                external_url="https://www.crunchbase.com/organization/wiz-2",
                tags=["crunchbase", "cybersecurity", "stub"],
            ),
        ]
