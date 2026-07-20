"""
Atlas - Company Import Service
==============================
Fait entrer une entreprise réelle dans Atlas par son ticker.

Idempotent : si le ticker existe déjà, l'entreprise existante est retournée
(created=False) — importer deux fois ne duplique rien.

Délègue la création à CompanyService.create : slug unique, unicité
ticker/ISIN, logs — un seul chemin de création dans toute l'app.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.company import Company
from app.providers.company_info import get_company_info_provider
from app.providers.prices import to_provider_symbol
from app.schemas.company import CompanyCreate
from app.services.company import CompanyService

logger = get_logger(__name__)


class CompanyImportService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.company_service = CompanyService(session)

    async def import_by_ticker(
        self,
        ticker: str,
        exchange: str | None,
        provider_name: str = "yfinance",
    ) -> tuple[Company, bool]:
        """Retourne (entreprise, created)."""
        ticker = ticker.strip().upper()

        existing = (
            await self.session.execute(
                select(Company).where(
                    Company.ticker == ticker,
                    Company.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing, False

        symbol = to_provider_symbol(ticker, exchange)
        provider = get_company_info_provider(provider_name)
        info = provider.fetch(symbol)
        if info is None:
            raise NotFoundError("Ticker", symbol)

        data = CompanyCreate(
            name=info.name,
            legal_name=info.legal_name,
            ticker=ticker,
            exchange=info.exchange or exchange,
            sector=info.sector,
            industry=info.industry,
            country=info.country,
            country_name=info.country_name,
            website=info.website,
            description=info.description,
            description_short=(info.description[:497] + "…") if info.description and len(info.description) > 500 else info.description,
            market_cap_usd=info.market_cap_usd,
            employees=info.employees,
            tags=["imported", f"provider:{provider.name}"],
        )
        company = await self.company_service.create(data)
        logger.info(
            "Company imported",
            ticker=ticker,
            symbol=symbol,
            name=company.name,
            provider=provider.name,
        )
        return company, True
