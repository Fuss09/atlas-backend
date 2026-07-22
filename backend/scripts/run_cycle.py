"""
Atlas - Run Cycle
=================
Le cœur battant : enchaîne les jobs d'enrichissement dans le bon ordre.
Découvrir → enrichir (events) → dater (catalyseurs) → coter (snapshots).
Chaque étape est ISOLÉE : une panne isolée n'arrête pas le cycle.

Usage :
    python -m scripts.run_cycle              # cycle réel (réseau)
    python -m scripts.run_cycle --mode fake  # validation sans réseau
"""
import argparse
import asyncio
import time

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from scripts.run_discovery import run as run_discovery
from scripts.sync_events import sync as sync_events
from scripts.sync_catalysts import sync as sync_catalysts
from scripts.capture_snapshots import capture as capture_snapshots

logger = get_logger(__name__)


async def _step(name: str, coro) -> bool:
    start = time.monotonic()
    logger.info("Cycle step starting", step=name)
    try:
        await coro
        logger.info("Cycle step done", step=name, seconds=round(time.monotonic() - start, 1))
        return True
    except Exception as exc:
        logger.error("Cycle step failed (continuing)", step=name, error=str(exc))
        return False


async def run_cycle(mode: str = "real") -> None:
    settings = get_settings()
    fake = mode == "fake"
    ev_provider = "fake" if fake else "sec_edgar"
    cat_provider = "fake" if fake else "clinicaltrials"
    price_provider = "fake" if fake else "yfinance"

    logger.info("Nightly cycle starting", mode=mode)
    start = time.monotonic()
    ok = 0
    total = 0

    # 1. Découverte — élargit l'univers (réel uniquement : pas de fake réseau)
    if not fake:
        total += 1
        ok += await _step("discovery", run_discovery("sec", settings.cycle_discovery_limit))

    # 2. Événements — dépôts SEC récents
    total += 1
    ok += await _step("events", sync_events(ev_provider, settings.cycle_events_limit, settings.cycle_events_days))

    # 3. Catalyseurs — essais cliniques (toutes les entreprises santé)
    total += 1
    ok += await _step("catalysts", sync_catalysts(cat_provider, None, None))

    # 4. Snapshots — cours + scores figés du jour
    total += 1
    ok += await _step("snapshots", capture_snapshots(price_provider))

    logger.info("Nightly cycle complete", mode=mode, steps_ok=ok, steps_total=total,
                seconds=round(time.monotonic() - start, 1))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full nightly enrichment cycle")
    parser.add_argument("--mode", default="real", choices=["real", "fake"])
    args = parser.parse_args()
    configure_logging()
    asyncio.run(run_cycle(args.mode))


if __name__ == "__main__":
    main()
