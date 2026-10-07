"""
Atlas - Remove Discovery Events
================================
Retire les events "New company discovered via ..." générés automatiquement
par le Discovery Engine (app/services/discovery.py — _create_discovery_event,
retiré : la découverte d'une entreprise ne crée plus d'event). La provenance
reste intacte dans discovery_sources ; seuls ces events bruiteurs disparaissent.

Sécurité (suppression irréversible) :
- DRY-RUN par défaut : liste le nombre concerné + 5 exemples, ne supprime rien.
  Ajouter --confirm pour exécuter réellement.
- Ciblage strict par préfixe de titre ("New company discovered via") — ne
  touche JAMAIS aux events de scripts.sync_events (source=sec_edgar, titres
  type "Material event (8-K)", "Quarterly report (10-Q)", "Annual report
  (10-K)", "Insider transaction (Form 4)").
- Aucune table ne référence events par clé étrangère (vérifié) : un DELETE
  direct est sûr, pas de cascade à gérer.

Usage :
    python -m scripts.remove_discovery_events              # dry-run (liste)
    python -m scripts.remove_discovery_events --confirm     # supprime
"""

import argparse
import asyncio

from sqlalchemy import delete, select

from app.models import catalyst, company, discovery, graph, opportunity, snapshot, theme, user, watchlist  # noqa: F401
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.event import Event

logger = get_logger(__name__)

TITLE_PREFIX = "New company discovered via"


async def run(confirm: bool) -> None:
    async with AsyncSessionFactory() as session:
        rows = (
            (
                await session.execute(
                    select(Event).where(Event.title.like(f"{TITLE_PREFIX}%"))
                )
            )
            .scalars()
            .all()
        )

        logger.info("Discovery events scan", matched=len(rows))
        for e in rows[:5]:
            logger.info("  example", title=e.title, source=e.source, event_type=e.event_type)

        if not confirm:
            logger.info("DRY-RUN — rien supprimé. Ajoute --confirm pour exécuter.")
            return

        if not rows:
            logger.info("Aucun event de découverte à supprimer.")
            return

        ids = [e.id for e in rows]
        result = await session.execute(delete(Event).where(Event.id.in_(ids)))
        await session.commit()
        logger.info("Discovery events removed", deleted=result.rowcount)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove auto-generated discovery events")
    parser.add_argument("--confirm", action="store_true", help="Exécuter réellement (sinon dry-run)")
    args = parser.parse_args()
    configure_logging()
    asyncio.run(run(args.confirm))


if __name__ == "__main__":
    main()
