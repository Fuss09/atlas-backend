"""
Atlas - Run Discovery
=====================
Lance un collecteur de découverte : Atlas va chercher de vraies entreprises
tout seul, depuis des sources publiques (SEC EDGAR, GitHub, YCombinator…).

C'est le passage de « j'ajoute les entreprises à la main » à « Atlas les
découvre pour moi ».

Usage :
    python -m scripts.run_discovery --source sec --limit 200
    python -m scripts.run_discovery --source github --limit 100

Le collecteur télécharge, normalise, DÉDUPLIQUE (ne recrée pas ce qui existe),
crée ou enrichit chaque entreprise, et trace la provenance. Idempotent :
relancer n'ajoute que le nouveau.

⚠️ AVANT un run SEC réel : mets un vrai email dans COLLECTOR_CONTACT_EMAIL
(.env). SEC bloque les requêtes sans contact valide.
"""

import argparse
import asyncio

# Résolution du registre SQLAlchemy
from app.models import (  # noqa: F401
    catalyst, company, discovery, event, graph, opportunity, snapshot, theme, user, watchlist,
)
from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.discovery import DiscoverySourceName
from app.services.discovery import DiscoveryService

logger = get_logger(__name__)


async def run(source_name: str, limit: int) -> None:
    try:
        source = DiscoverySourceName(source_name)
    except ValueError:
        valid = [s.value for s in DiscoverySourceName]
        logger.error("Unknown source", source=source_name, valid=valid)
        return

    async with AsyncSessionFactory() as session:
        service = DiscoveryService(session)
        job = await service.run_job_sync(source=source, params={"limit": limit})

        logger.info(
            "Discovery run finished",
            source=source.value,
            status=str(job.status),
            found=job.companies_found,
            created=job.companies_created,
            updated=job.companies_updated,
            skipped=job.companies_skipped,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a discovery collector")
    parser.add_argument(
        "--source",
        required=True,
        help="Source: sec, github, ycombinator…",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Nombre max d'entreprises à traiter (défaut 200)",
    )
    args = parser.parse_args()
    configure_logging()
    asyncio.run(run(args.source, args.limit))


if __name__ == "__main__":
    main()
