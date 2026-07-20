"""
Atlas - Price Providers
=======================
Abstraction d'accès aux données de marché.

Pourquoi une abstraction : yfinance (source actuelle) est non-officiel,
rate-limité agressivement par Yahoo (blocages d'IP temporaires) et fragile
aux changements de leur site. Il convient à notre usage — UN batch quotidien
sur un petit univers — mais pas au-delà. Le jour où Atlas passe à un
fournisseur payant (Polygon, EODHD...), seul ce module change.

Règles d'or appliquées à YFinanceProvider (issues des recommandations de
la communauté yfinance, vérifiées en 2026) :
- batcher les tickers en un seul appel plutôt que N appels ;
- throttle entre les lots + backoff exponentiel sur rate limit ;
- échec gracieux : ticker introuvable ou erreur réseau → None, on log,
  on n'interrompt jamais la capture des autres.
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PriceQuote:
    """Cotation minimale nécessaire aux snapshots."""

    symbol: str
    price: float
    currency: str
    volume: int | None
    market_cap: int | None
    as_of: datetime


class PriceProvider(Protocol):
    """Contrat commun à tous les fournisseurs de prix."""

    name: str

    def get_quotes(self, symbols: list[str]) -> dict[str, PriceQuote | None]:
        """
        Retourne une cotation par symbole demandé (None si introuvable).
        Ne lève jamais pour un symbole individuel — seule une panne totale
        du fournisseur peut lever.
        """
        ...


# ─── Mapping exchange -> suffixe de symbole yfinance ──────────────────────────
#
# yfinance identifie les places non-US par un suffixe. Couverture minimale
# pour l'univers actuel d'Atlas (US + Euronext) — à étendre au fil des besoins.
EXCHANGE_SUFFIX: dict[str, str] = {
    "NASDAQ": "",
    "NYSE": "",
    "AMEX": "",
    "EURONEXT": ".PA",       # Euronext Paris par défaut
    "EURONEXT PARIS": ".PA",
    "EPA": ".PA",
    "EURONEXT AMSTERDAM": ".AS",
    "EURONEXT BRUSSELS": ".BR",
    "LSE": ".L",
    "XETRA": ".DE",
}


def to_provider_symbol(ticker: str, exchange: str | None) -> str:
    """Traduit (ticker, exchange) Atlas vers un symbole yfinance."""
    suffix = EXCHANGE_SUFFIX.get((exchange or "").upper(), "")
    return f"{ticker}{suffix}"


class YFinanceProvider:
    """Fournisseur yfinance — batch, throttle, backoff, échecs gracieux."""

    name = "yfinance"

    BATCH_SIZE = 25
    THROTTLE_SECONDS = 2.0
    MAX_RETRIES = 3

    def get_quotes(self, symbols: list[str]) -> dict[str, PriceQuote | None]:
        # Import local : yfinance (et sa dépendance pandas) ne se charge que
        # si ce provider est réellement utilisé — les tests et le reste de
        # l'app n'en dépendent pas.
        import yfinance as yf

        results: dict[str, PriceQuote | None] = {s: None for s in symbols}

        for i in range(0, len(symbols), self.BATCH_SIZE):
            batch = symbols[i : i + self.BATCH_SIZE]
            if i > 0:
                time.sleep(self.THROTTLE_SECONDS)

            for attempt in range(self.MAX_RETRIES):
                try:
                    tickers = yf.Tickers(" ".join(batch))
                    for symbol in batch:
                        results[symbol] = self._extract_quote(tickers, symbol)
                    break
                except Exception as exc:  # rate limit ou panne réseau
                    wait = self.THROTTLE_SECONDS * (2**attempt)
                    logger.warning(
                        "Price batch failed — backing off",
                        attempt=attempt + 1,
                        wait_seconds=wait,
                        error=str(exc),
                    )
                    if attempt + 1 < self.MAX_RETRIES:
                        time.sleep(wait)
        return results

    @staticmethod
    def _extract_quote(tickers, symbol: str) -> PriceQuote | None:
        try:
            info = tickers.tickers[symbol].fast_info
            price = info.get("last_price") or info.get("lastPrice")
            if price is None:
                return None
            return PriceQuote(
                symbol=symbol,
                price=float(price),
                currency=str(info.get("currency") or "USD"),
                volume=int(v) if (v := info.get("last_volume")) else None,
                market_cap=int(m) if (m := info.get("market_cap")) else None,
                as_of=datetime.now(UTC),
            )
        except Exception as exc:
            logger.info("No quote for symbol", symbol=symbol, reason=str(exc))
            return None


class FakePriceProvider:
    """
    Fournisseur de test : prix déterministes dérivés du symbole.
    Sert à valider toute la chaîne de capture sans toucher au réseau —
    utilisé par les tests unitaires et le flag --provider fake du script.
    """

    name = "fake"

    def get_quotes(self, symbols: list[str]) -> dict[str, PriceQuote | None]:
        now = datetime.now(UTC)
        return {
            s: PriceQuote(
                symbol=s,
                price=round(10.0 + (sum(ord(c) for c in s) % 900) / 10.0, 2),
                currency="USD",
                volume=100_000,
                market_cap=1_000_000_000,
                as_of=now,
            )
            for s in symbols
        }


def get_provider(name: str) -> PriceProvider:
    """Fabrique de providers — point d'entrée unique du reste de l'app."""
    providers: dict[str, PriceProvider] = {
        "yfinance": YFinanceProvider(),
        "fake": FakePriceProvider(),
    }
    if name not in providers:
        raise ValueError(f"Unknown price provider: {name!r} (expected {sorted(providers)})")
    return providers[name]
