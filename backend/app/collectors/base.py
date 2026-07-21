"""
Atlas - Base Collector
======================
Contrat abstrait que chaque connecteur doit implémenter.

Architecture :
    BaseCollector
        ├── SecCollector       (SEC EDGAR)
        ├── GitHubCollector    (GitHub orgs)
        ├── YCombinatorCollector (YC startups)
        ├── CrunchbaseCollector  (stub)
        └── [futurs: FDA, USPTO, ArXiv, HuggingFace…]

Chaque collecteur est autonome et indépendant :
- Il ne connaît pas les autres collecteurs
- Il reçoit une session DB et un job en cours
- Il normalise ses données vers CompanyData (structure commune)
- Il délègue la persistance au DiscoveryService

Le BaseCollector gère :
- Le cycle de vie du httpx.AsyncClient (ouverture/fermeture)
- Les retries avec backoff exponentiel (via tenacity)
- Le logging structuré avec contexte du job
- La gestion des rate limits (429)

Décision : on n'utilise pas Celery dans ce module.
Les jobs sont async purs, déclenchés via l'API et exécutés dans le
process uvicorn. Si la volumétrie augmente (> 10k entreprises/run),
migrer vers Celery Beat + Redis broker — prévu pour Module 07.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.models.company import CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySourceName


@dataclass
class CompanyData:
    """
    Structure de données normalisée produite par tous les collecteurs.
    C'est le format pivot entre les sources externes et le modèle Company.

    Tous les champs sont optionnels sauf `name` et `country`.
    Les collecteurs remplissent ce qu'ils ont — le service fait la fusion.
    """

    # Requis
    name: str
    country: str                              # ISO alpha-2

    # Identifiants
    ticker: str | None = None
    isin: str | None = None
    exchange: str | None = None

    # Classification
    company_type: CompanyType = CompanyType.PUBLIC
    sector: str | None = None
    industry: str | None = None

    # Description
    description: str | None = None
    description_short: str | None = None
    website: str | None = None
    logo_url: str | None = None

    # Financier
    founded_year: int | None = None
    ipo_date: date | None = None
    market_cap_usd: int | None = None
    employees: int | None = None
    revenue_usd: int | None = None

    # Géographie
    country_name: str | None = None
    headquarters_city: str | None = None
    headquarters_state: str | None = None

    # Identifiant externe (pour la déduplication)
    external_id: str | None = None           # Ex: CIK pour SEC, org name pour GitHub
    external_url: str | None = None

    # Tags suggérés par le collecteur
    tags: list[str] = field(default_factory=list)

    # Données brutes conservées pour la traçabilité
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectorResult:
    """Résultat d'un run de collecteur."""

    companies: list[CompanyData] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)   # cursor, page, etc.

    def add_error(self, context: str, error: str) -> None:
        self.errors.append({"context": context, "error": error})


class BaseCollector(ABC):
    """
    Classe abstraite dont hérite chaque connecteur.

    Les sous-classes doivent implémenter :
        - source_name  : propriété retournant le DiscoverySourceName
        - collect()    : méthode principale de collecte

    Optionnellement, elles peuvent surcharger :
        - _build_client() pour configurer des headers spécifiques (auth, user-agent)
    """

    # Timeout HTTP par défaut pour tous les collecteurs
    DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
    # User-Agent clair pour les APIs publiques.
    # Construit depuis la config : SEC & co exigent un contact réel — voir
    # COLLECTOR_CONTACT_EMAIL. Property (pas constante) pour lire le .env.
    @property
    def USER_AGENT(self) -> str:
        from app.core.config import get_settings
        s = get_settings()
        return f"Atlas-Market-Intelligence/{s.app_version} (contact: {s.collector_contact_email})"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}
        self.logger = get_logger(f"collector.{self.source_name}")
        self._client: httpx.AsyncClient | None = None

    @property
    @abstractmethod
    def source_name(self) -> DiscoverySourceName:
        """Identifiant canonique de cette source."""
        ...

    @abstractmethod
    async def collect(self, job: DiscoveryJob) -> CollectorResult:
        """
        Méthode principale de collecte.
        Doit retourner un CollectorResult avec les entreprises normalisées.
        Les erreurs non fatales sont ajoutées à CollectorResult.errors.
        Les erreurs fatales lèvent une exception.
        """
        ...

    def _build_client(self) -> httpx.AsyncClient:
        """
        Crée le client HTTP. Surcharger pour ajouter des headers d'auth.
        """
        return httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self) -> "BaseCollector":
        self._client = self._build_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Collector must be used as async context manager")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        GET avec retry automatique (3 tentatives, backoff exponentiel).
        Gère les 429 (rate limit) avec un sleep forcé.
        """
        response = await self.client.get(url, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            self.logger.warning(
                "Rate limited",
                url=url,
                retry_after=retry_after,
                source=self.source_name,
            )
            await asyncio.sleep(retry_after)
            response = await self.client.get(url, **kwargs)

        return response
