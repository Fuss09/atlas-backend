"""
Atlas - Sync Catalysts
======================
Synchronise les catalyseurs d'essais cliniques (ClinicalTrials.gov) pour les
entreprises du secteur santé/biotech.

Usage :
    python -m scripts.sync_catalysts                          # toutes les Healthcare
    python -m scripts.sync_catalysts --company meridian-genomics
    python -m scripts.sync_catalysts --company meridian-genomics --sponsor-name "Abivax"
    python -m scripts.sync_catalysts --provider fake          # sans réseau (validation)

--sponsor-name permet de mapper une entreprise Atlas sur le nom de sponsor
exact du registre (utile quand le nom légal diffère, et pour tester la
plomberie réseau sur un sponsor réel depuis le dataset de démo).

Déduplication par external_id (NCT + type de date) : relancer ne crée jamais
de doublon ; une date qui change chez le sponsor met à jour le catalyseur.
"""

import argparse
import asyncio

from sqlalchemy import select

# Résolution du registre SQLAlchemy (relations déclarées par chaîne)
from app.models import discovery, event, graph, opportunity, snapshot, theme, user, watchlist  # noqa: F401
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.catalyst import Catalyst
from app.models.company import Company
from app.providers.catalysts import get_catalyst_provider

logger = get_logger(__name__)


async def sync(provider_name: str, company_slug: str | None, sponsor_override: str | None) -> None:
    provider = get_catalyst_provider(provider_name)

    async with AsyncSessionFactory() as session:
        query = select(Company).where(Company.is_deleted == False)  # noqa: E712
        if company_slug:
            query = query.where(Company.slug == company_slug)
        else:
            query = query.where(Company.sector == "Healthcare")
        companies = (await session.execute(query)).scalars().all()

        if not companies:
            logger.warning("No matching companies", company_slug=company_slug)
            return

        existing_by_ext = {
            c.external_id: c
            for c in (
                await session.execute(
                    select(Catalyst).where(Catalyst.external_id.is_not(None))
                )
            )
            .scalars()
            .all()
        }

        created = updated = unchanged = 0
        for company in companies:
            sponsor = sponsor_override or company.legal_name or company.name
            trials = await asyncio.to_thread(provider.fetch_for_sponsor, sponsor)
            for t in trials:
                existing = existing_by_ext.get(t.external_id)
                if existing is None:
                    session.add(
                        Catalyst(
                            company_id=company.id,
                            catalyst_type="clinical_readout",
                            title=t.title,
                            expected_date=t.expected_date,
                            date_precision=t.date_precision,
                            status="upcoming",
                            source=provider.name,
                            source_url=t.source_url,
                            external_id=t.external_id,
                        )
                    )
                    created += 1
                elif (
                    existing.expected_date != t.expected_date
                    or existing.date_precision != t.date_precision
                ):
                    existing.expected_date = t.expected_date
                    existing.date_precision = t.date_precision
                    updated += 1
                else:
                    unchanged += 1

        await session.commit()
        logger.info(
            "Catalyst sync complete",
            provider=provider.name,
            companies=len(companies),
            created=created,
            updated=updated,
            unchanged=unchanged,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync clinical-trial catalysts")
    parser.add_argument("--provider", default="clinicaltrials", choices=["clinicaltrials", "fake"])
    parser.add_argument("--company", default=None, help="Limiter à un slug d'entreprise")
    parser.add_argument("--sponsor-name", default=None, help="Nom de sponsor exact dans le registre")
    args = parser.parse_args()
    configure_logging()
    asyncio.run(sync(args.provider, args.company, args.sponsor_name))


if __name__ == "__main__":
    main()
