"""
Atlas - Sync Events
===================
Lit les dépôts SEC récents des entreprises et les transforme en événements
scorables (8-K, 10-K/Q, Form 4). Fait passer une entreprise de « vue mais
muette » à « surveillée, avec un score qui bouge ».

Usage :
    python -m scripts.sync_events --limit 100 --days 90
    python -m scripts.sync_events --provider fake      # sans réseau (validation)

Ne traite que les entreprises ayant un CIK (découverte SEC). Idempotent :
dédup par numéro d'accession. Recalcule le score des entreprises enrichies.
"""

import argparse
import asyncio
import hashlib
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import catalyst, discovery, graph, snapshot, theme, user, watchlist  # noqa: F401
from app.core.exceptions import AlreadyExistsError
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.company import Company
from app.providers.sec_events import get_sec_events_provider
from app.schemas.event import EventCreate
from app.services.event import EventService
from app.services.opportunity import OpportunityScoreService

logger = get_logger(__name__)

CIK_KEY = re.compile(r"^\d{6,10}$")


def _extract_cik(company: Company) -> str | None:
    sources = company.data_sources or {}
    for key in sources:
        if CIK_KEY.match(str(key)):
            return str(key)
    return None


def _fake_cik(company_id) -> str:
    """CIK pseudo-unique dérivé de l'id, pour le mode fake uniquement.

    Sans CIK réel, on ne peut pas partager un placeholder fixe entre
    entreprises : leurs source_id (dédup globale sur (source, source_id))
    entreraient en collision et les entreprises traitées après la première
    verraient tous leurs événements silencieusement rejetés en doublon.
    """
    digest = hashlib.sha256(str(company_id).encode()).hexdigest()
    return str(int(digest, 16))[:10].zfill(10)


async def sync(provider_name: str, limit: int, days: int) -> None:
    provider = get_sec_events_provider(provider_name)
    since = (datetime.now(UTC) - timedelta(days=days)).date()

    async with AsyncSessionFactory() as session:
        companies = (
            (await session.execute(select(Company).where(Company.is_deleted == False)))  # noqa: E712
            .scalars().all()
        )

        event_service = EventService(session)
        opp_service = OpportunityScoreService(session)

        processed = 0
        created_total = 0
        enriched_company_ids: set = set()

        for company in companies:
            cik = _extract_cik(company)
            if cik is None and provider_name != "fake":
                continue
            if processed >= limit:
                break
            processed += 1

            filings = await asyncio.to_thread(provider.fetch_filings, cik or _fake_cik(company.id), since)
            for f in filings:
                try:
                    await event_service.create(
                        EventCreate(
                            company_id=company.id,
                            event_type=f.event_type,
                            importance=f.importance,
                            title=f.title,
                            occurred_at=f.occurred_at,
                            source="sec_edgar",
                            source_url=f.url,
                            source_id=f.accession,
                        )
                    )
                    created_total += 1
                    enriched_company_ids.add(company.id)
                except AlreadyExistsError:
                    pass

        for company_id in enriched_company_ids:
            try:
                await opp_service.recompute(company_id)
            except Exception as exc:
                logger.warning("Recompute failed", company_id=str(company_id), error=str(exc))

        await session.commit()
        logger.info("Event sync complete", provider=provider.name,
                    companies_processed=processed, events_created=created_total,
                    companies_enriched=len(enriched_company_ids))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync SEC filing events")
    parser.add_argument("--provider", default="sec_edgar", choices=["sec_edgar", "fake"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    configure_logging()
    asyncio.run(sync(args.provider, args.limit, args.days))


if __name__ == "__main__":
    main()
