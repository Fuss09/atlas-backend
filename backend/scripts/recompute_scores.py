"""
Atlas - Recompute Scores
========================
Recalcule le score d'opportunité de TOUTES les entreprises non supprimées.
Utile après un changement de données en masse (ex: suppression d'events
bruiteurs) qui invalide les scores déjà calculés.

Chaque entreprise est isolée : une erreur de calcul sur l'une n'interrompt
pas les suivantes.

Usage :
    python -m scripts.recompute_scores
"""

import asyncio

from sqlalchemy import select

from app.models import catalyst, discovery, event, graph, snapshot, theme, user, watchlist  # noqa: F401
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.company import Company
from app.services.opportunity import OpportunityScoreService

logger = get_logger(__name__)


async def recompute_all() -> None:
    async with AsyncSessionFactory() as session:
        companies = (
            (await session.execute(select(Company).where(Company.is_deleted == False)))  # noqa: E712
            .scalars()
            .all()
        )

        service = OpportunityScoreService(session)
        recomputed = 0
        errors = 0

        for company in companies:
            try:
                await service.recompute(company.id)
                recomputed += 1
            except Exception as exc:
                errors += 1
                logger.warning(
                    "Recompute failed",
                    company_id=str(company.id),
                    name=company.name,
                    error=str(exc),
                )

        await session.commit()
        logger.info(
            "Recompute complete",
            total=len(companies),
            recomputed=recomputed,
            errors=errors,
        )


def main() -> None:
    configure_logging()
    asyncio.run(recompute_all())


if __name__ == "__main__":
    main()
