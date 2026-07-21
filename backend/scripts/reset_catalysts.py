"""
Atlas - Reset Catalysts
=======================
Maintenance : supprime DÉFINITIVEMENT des catalyseurs (hard delete).

Pourquoi un hard delete : la contrainte d'unicité sur external_id n'est PAS
filtrée par is_deleted — un catalyseur soft-deleted continuerait de bloquer
la recréation du même essai (NCT). Pour re-synchroniser proprement un essai
sur la bonne entreprise, il faut réellement retirer l'ancienne ligne.

Usage :
    python -m scripts.reset_catalysts --all
    python -m scripts.reset_catalysts --company meridian-genomics
    python -m scripts.reset_catalysts --source clinicaltrials
"""

import argparse
import asyncio

from sqlalchemy import delete, select

# Résolution du registre SQLAlchemy
from app.models import discovery, event, graph, opportunity, snapshot, theme, user, watchlist  # noqa: F401
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.catalyst import Catalyst
from app.models.company import Company

logger = get_logger(__name__)


async def reset(scope_all: bool, company_slug: str | None, source: str | None) -> None:
    if not (scope_all or company_slug or source):
        logger.warning("No scope given — use --all, --company or --source. Nothing done.")
        return

    async with AsyncSessionFactory() as session:
        stmt = delete(Catalyst)
        label = "all"
        if company_slug:
            company = (
                await session.execute(select(Company).where(Company.slug == company_slug))
            ).scalar_one_or_none()
            if not company:
                logger.warning("Company not found", slug=company_slug)
                return
            stmt = stmt.where(Catalyst.company_id == company.id)
            label = f"company={company_slug}"
        elif source:
            stmt = stmt.where(Catalyst.source == source)
            label = f"source={source}"

        result = await session.execute(stmt)
        await session.commit()
        logger.info("Catalysts reset (hard delete)", scope=label, deleted=result.rowcount)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hard-delete catalysts (maintenance)")
    parser.add_argument("--all", action="store_true", help="Supprimer TOUS les catalyseurs")
    parser.add_argument("--company", default=None, help="Limiter à un slug d'entreprise")
    parser.add_argument("--source", default=None, help="Limiter à une source (clinicaltrials, fake, manual)")
    args = parser.parse_args()
    configure_logging()
    asyncio.run(reset(args.all, args.company, args.source))


if __name__ == "__main__":
    main()
