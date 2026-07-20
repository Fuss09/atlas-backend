"""
Atlas - Capture Snapshots
=========================
Le geste quotidien de la boucle de calibration : photographier les scores
et les prix du jour dans les tables d'historique immuable.

Usage :
    python -m scripts.capture_snapshots                  # yfinance (défaut)
    python -m scripts.capture_snapshots --provider fake  # sans réseau (validation)

Idempotent par jour : si une entreprise a déjà un snapshot (score ou prix)
capturé aujourd'hui (UTC), elle est sautée pour ce type — relancer le script
ne duplique rien.

Les entreprises sans ticker n'ont pas de snapshot de prix (normal : sociétés
privées). Les tickers introuvables chez le fournisseur sont sautés et
comptés — jamais bloquants.
"""

import argparse
import asyncio
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
# Importer l'ensemble des modèles pour que le registre SQLAlchemy résolve
# toutes les relations déclarées par chaîne (ex: Company -> company_themes).
from app.models import discovery, event, graph, theme, user, watchlist  # noqa: F401
from app.models.company import Company
from app.models.opportunity import OpportunityScore
from app.models.snapshot import PriceSnapshot, ScoreSnapshot
from app.providers.prices import get_provider, to_provider_symbol

logger = get_logger(__name__)


def _today_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


async def capture(provider_name: str) -> None:
    now = datetime.now(UTC)
    day_start, _ = _today_bounds(now)
    provider = get_provider(provider_name)

    async with AsyncSessionFactory() as session:
        companies = (
            (
                await session.execute(
                    select(Company).where(Company.is_deleted == False)  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        # ── 1. Score snapshots ────────────────────────────────────────────────
        already_scored = set(
            (
                await session.execute(
                    select(ScoreSnapshot.company_id).where(
                        ScoreSnapshot.captured_at >= day_start
                    )
                )
            )
            .scalars()
            .all()
        )

        scores = (
            (
                await session.execute(
                    select(OpportunityScore).where(
                        OpportunityScore.is_deleted == False  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        score_by_company = {s.company_id: s for s in scores}

        scores_captured = 0
        for company in companies:
            if company.id in already_scored:
                continue
            live = score_by_company.get(company.id)
            if not live:
                continue
            session.add(
                ScoreSnapshot(
                    company_id=company.id,
                    score=live.score,
                    conviction=str(live.conviction),
                    stage=str(live.stage),
                    scoring_version=live.scoring_version,
                    components=live.components or {},
                    captured_at=now,
                )
            )
            scores_captured += 1

        # ── 2. Price snapshots ────────────────────────────────────────────────
        already_priced = set(
            (
                await session.execute(
                    select(PriceSnapshot.company_id).where(
                        PriceSnapshot.captured_at >= day_start
                    )
                )
            )
            .scalars()
            .all()
        )

        with_ticker = [
            c
            for c in companies
            if c.ticker and c.id not in already_priced
        ]
        symbol_by_company = {
            c.id: to_provider_symbol(c.ticker, c.exchange) for c in with_ticker
        }

        prices_captured = 0
        prices_missing = 0
        if symbol_by_company:
            # Le provider est synchrone (yfinance) — exécuté hors event loop.
            quotes = await asyncio.to_thread(
                provider.get_quotes, sorted(set(symbol_by_company.values()))
            )
            for company in with_ticker:
                quote = quotes.get(symbol_by_company[company.id])
                if quote is None:
                    prices_missing += 1
                    continue
                session.add(
                    PriceSnapshot(
                        company_id=company.id,
                        price=quote.price,
                        currency=quote.currency,
                        volume=quote.volume,
                        market_cap=quote.market_cap,
                        source=provider.name,
                        captured_at=now,
                    )
                )
                prices_captured += 1

        await session.commit()

        logger.info(
            "Snapshot capture complete",
            provider=provider.name,
            companies=len(companies),
            scores_captured=scores_captured,
            scores_already_done=len(already_scored),
            prices_captured=prices_captured,
            prices_missing=prices_missing,
            prices_already_done=len(already_priced),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture daily score & price snapshots")
    parser.add_argument(
        "--provider",
        default="yfinance",
        choices=["yfinance", "fake"],
        help="Price data provider (fake = deterministic, no network)",
    )
    args = parser.parse_args()
    configure_logging()
    asyncio.run(capture(args.provider))


if __name__ == "__main__":
    main()
