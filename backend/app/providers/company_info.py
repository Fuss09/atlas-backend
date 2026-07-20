"""
Atlas - Company Info Providers
==============================
Récupération des métadonnées d'une entreprise réelle par son ticker —
le point d'entrée de l'univers réel d'Atlas.

Source actuelle : yfinance (mêmes précautions qu'au Sprint 9 : non-officiel,
rate-limité — un import est un geste ponctuel, pas un batch, donc largement
dans les clous). Même abstraction : remplaçable sans toucher au reste.

Honnêteté des données :
- market_cap_usd n'est renseigné QUE si la devise de cotation est l'USD.
  Stocker une capitalisation en euros dans une colonne « _usd » serait un
  mensonge silencieux (une conversion FX propre viendra plus tard).
- Le pays est mappé vers ISO-2 pour les marchés couverts ; sinon on garde
  le nom brut en country_name et « US » par défaut en code (loggé) — le
  champ est requis par le modèle, le nom affiché reste exact.
"""

from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger(__name__)

COUNTRY_ISO2: dict[str, str] = {
    "united states": "US", "france": "FR", "germany": "DE",
    "united kingdom": "GB", "netherlands": "NL", "belgium": "BE",
    "switzerland": "CH", "sweden": "SE", "denmark": "DK", "norway": "NO",
    "finland": "FI", "spain": "ES", "italy": "IT", "ireland": "IE",
    "portugal": "PT", "austria": "AT", "canada": "CA", "japan": "JP",
    "china": "CN", "israel": "IL", "australia": "AU", "luxembourg": "LU",
}

# Codes de place yfinance -> libellés Atlas (alignés sur EXCHANGE_SUFFIX de prices.py)
EXCHANGE_LABELS: dict[str, str] = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
    "NYQ": "NYSE", "ASE": "AMEX",
    "PAR": "EURONEXT PARIS", "AMS": "EURONEXT AMSTERDAM", "BRU": "EURONEXT BRUSSELS",
    "LSE": "LSE", "GER": "XETRA", "FRA": "XETRA",
}


@dataclass
class CompanyInfo:
    name: str
    legal_name: str | None
    sector: str | None
    industry: str | None
    exchange: str | None
    country: str            # ISO-2
    country_name: str | None
    website: str | None
    description: str | None
    market_cap_usd: int | None
    employees: int | None
    currency: str | None


class CompanyInfoProvider(Protocol):
    name: str

    def fetch(self, symbol: str) -> CompanyInfo | None:
        """Métadonnées pour un symbole. None si introuvable."""
        ...


class YFinanceCompanyInfoProvider:

    name = "yfinance"

    def fetch(self, symbol: str) -> CompanyInfo | None:
        import yfinance as yf

        try:
            info: dict = yf.Ticker(symbol).info or {}
        except Exception as exc:
            logger.warning("Company info fetch failed", symbol=symbol, error=str(exc))
            return None

        name = info.get("shortName") or info.get("longName")
        if not name:
            logger.info("No company found for symbol", symbol=symbol)
            return None

        raw_country = (info.get("country") or "").strip()
        iso2 = COUNTRY_ISO2.get(raw_country.lower())
        if raw_country and iso2 is None:
            logger.warning("Unmapped country, defaulting code to US", country=raw_country)

        currency = info.get("currency")
        market_cap = info.get("marketCap")
        market_cap_usd = int(market_cap) if (market_cap and currency == "USD") else None

        summary = info.get("longBusinessSummary")
        return CompanyInfo(
            name=str(name)[:255],
            legal_name=(str(info["longName"])[:500] if info.get("longName") else None),
            sector=(str(info["sector"])[:100] if info.get("sector") else None),
            industry=(str(info["industry"])[:150] if info.get("industry") else None),
            exchange=EXCHANGE_LABELS.get(str(info.get("exchange") or ""), str(info.get("exchange") or "") or None),
            country=iso2 or "US",
            country_name=raw_country or None,
            website=(str(info["website"])[:512] if info.get("website") else None),
            description=(str(summary) if summary else None),
            market_cap_usd=market_cap_usd,
            employees=(int(info["fullTimeEmployees"]) if info.get("fullTimeEmployees") else None),
            currency=(str(currency) if currency else None),
        )


class FakeCompanyInfoProvider:
    """Métadonnées déterministes pour valider la chaîne sans réseau."""

    name = "fake"

    def fetch(self, symbol: str) -> CompanyInfo | None:
        if symbol.upper().startswith("NOPE"):
            return None  # permet de tester le 404
        base = symbol.split(".")[0].upper()
        is_paris = symbol.upper().endswith(".PA")
        return CompanyInfo(
            name=f"{base.capitalize()} SA" if is_paris else f"{base.capitalize()} Inc",
            legal_name=None,
            sector="Healthcare",
            industry="Biotechnology",
            exchange="EURONEXT PARIS" if is_paris else "NASDAQ",
            country="FR" if is_paris else "US",
            country_name="France" if is_paris else "United States",
            website=f"https://www.{base.lower()}.example.com",
            description=f"Deterministic fake profile for {base}.",
            market_cap_usd=None if is_paris else 500_000_000,
            employees=120,
            currency="EUR" if is_paris else "USD",
        )


def get_company_info_provider(name: str) -> CompanyInfoProvider:
    providers: dict[str, CompanyInfoProvider] = {
        "yfinance": YFinanceCompanyInfoProvider(),
        "fake": FakeCompanyInfoProvider(),
    }
    if name not in providers:
        raise ValueError(f"Unknown company info provider: {name!r} (expected {sorted(providers)})")
    return providers[name]
