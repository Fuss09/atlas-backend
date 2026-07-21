"""
Atlas - Remove Demo Companies
=============================
Retire les entreprises FICTIVES du seed de démo, une fois qu'Atlas tourne sur
de vraies données (découverte SEC, imports).

Sécurité (suppression irréversible) :
- DRY-RUN par défaut : liste ce qui serait supprimé, ne supprime rien.
  Ajouter --confirm pour exécuter réellement.
- Double marqueur : website en `.example.com` (les fictives du seed) ET
  exclusion de tout ce qui est tagué "imported" (protège les entreprises
  réelles importées à la main, comme Abivax, même si un fournisseur renvoyait
  une URL bizarre).
- Suppression en cascade automatique (FK ondelete=CASCADE) : événements,
  scores, snapshots, catalyseurs, watchlist, thèmes sont nettoyés avec.

Usage :
    python -m scripts.remove_demo_companies              # dry-run (liste)
    python -m scripts.remove_demo_companies --confirm     # supprime
"""

import argparse
import asyncio

from sqlalchemy import delete, func, select

# Résolution du registre SQLAlchemy
from app.models import (  # noqa: F401
    catalyst, discovery, event, graph, opportunity, snapshot, theme, user, watchlist,
)
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.company import Company

logger = get_logger(__name__)

DEMO_WEBSITE_MARKER = "%.example.com%"


def _is_demo(c: Company) -> bool:
    tags = c.tags or []
    return bool(c.website) and ".example.com" in c.website and "imported" not in tags


async def run(confirm: bool) -> None:
    async with AsyncSessionFactory() as session:
        rows = (
            (
                await session.execute(
                    select(Company).where(
                        Company.website.like(DEMO_WEBSITE_MARKER),
                        Company.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        targets = [c for c in rows if _is_demo(c)]
        protected = [c for c in rows if not _is_demo(c)]

        logger.info("Demo cleanup — scan", matched=len(rows), to_delete=len(targets), protected=len(protected))
        for c in targets:
            logger.info("  will DELETE", name=c.name, ticker=c.ticker or "-", website=c.website)
        for c in protected:
            logger.info("  PROTECTED (imported)", name=c.name, ticker=c.ticker or "-")

        if not confirm:
            logger.info("DRY-RUN — rien supprimé. Ajoute --confirm pour exécuter.")
            return

        if not targets:
            logger.info("Aucune entreprise de démo à supprimer.")
            return

        ids = [c.id for c in targets]
        result = await session.execute(delete(Company).where(Company.id.in_(ids)))
        await session.commit()
        logger.info("Demo companies removed (cascade)", deleted=result.rowcount)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove demo/fictional companies")
    parser.add_argument("--confirm", action="store_true", help="Exécuter réellement (sinon dry-run)")
    args = parser.parse_args()
    configure_logging()
    asyncio.run(run(args.confirm))


if __name__ == "__main__":
    main()
