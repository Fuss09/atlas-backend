"""
Atlas - SEC EDGAR Collector
============================
Collecte les entreprises cotées US via l'API publique SEC EDGAR.

API utilisée : https://data.sec.gov/submissions/
- Pas d'authentification requise
- Rate limit : 10 req/sec (on reste à 5 pour la marge)
- Source officielle pour toutes les entreprises déposant auprès de la SEC

Données récupérées :
- Nom légal, ticker, exchange, SIC code (→ sector/industry)
- CIK (Central Index Key) = external_id pour la déduplication
- État de constitution (→ headquarters_state)

Limitations connues :
- Pas de description textuelle dans EDGAR (enrichissement via d'autres sources)
- Market cap absent (nécessite yfinance ou Polygon — Module suivant)
- Uniquement les entreprises US déposant en 10-K/10-Q
"""

import asyncio

from app.collectors.base import BaseCollector, CollectorResult, CompanyData
from app.models.company import CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySourceName

# Mapping SIC code → (sector, industry)
# Source : https://www.sec.gov/info/edgar/siccodes.htm
SIC_MAP: dict[str, tuple[str, str]] = {
    "0100": ("Agriculture", "Crops"),
    "0200": ("Agriculture", "Livestock"),
    "1000": ("Materials", "Mining"),
    "1311": ("Energy", "Oil & Gas Exploration"),
    "1381": ("Energy", "Drilling Oil & Gas Wells"),
    "1400": ("Materials", "Mining & Quarrying"),
    "1521": ("Industrials", "General Building Contractors"),
    "2000": ("Consumer Staples", "Food & Kindred Products"),
    "2100": ("Consumer Staples", "Tobacco"),
    "2600": ("Materials", "Paper & Allied Products"),
    "2800": ("Materials", "Chemicals & Allied Products"),
    "2830": ("Healthcare", "Pharmaceuticals"),
    "2836": ("Healthcare", "Biologics & Pharmaceuticals"),
    "3310": ("Materials", "Steel & Iron"),
    "3559": ("Industrials", "Industrial Machinery"),
    "3571": ("Technology", "Electronic Computers"),
    "3572": ("Technology", "Computer Storage Devices"),
    "3576": ("Technology", "Computer Communications Equipment"),
    "3577": ("Technology", "Computer Peripheral Equipment"),
    "3600": ("Technology", "Electronic Components"),
    "3661": ("Communication Services", "Telephone & Telegraph Apparatus"),
    "3669": ("Technology", "Communications Equipment"),
    "3672": ("Technology", "Printed Circuit Boards"),
    "3674": ("Technology", "Semiconductors"),
    "3679": ("Technology", "Electronic Components"),
    "3690": ("Technology", "Electronic & Other Electrical Equipment"),
    "3711": ("Consumer Discretionary", "Motor Vehicles"),
    "3812": ("Industrials", "Defense Electronics"),
    "3825": ("Technology", "Instruments for Measuring"),
    "3841": ("Healthcare", "Surgical & Medical Instruments"),
    "4000": ("Industrials", "Railroad Transportation"),
    "4210": ("Industrials", "Trucking & Warehousing"),
    "4400": ("Industrials", "Water Transportation"),
    "4512": ("Industrials", "Air Transportation"),
    "4813": ("Communication Services", "Telephone Communications"),
    "4911": ("Utilities", "Electric Services"),
    "4924": ("Utilities", "Natural Gas Distribution"),
    "5000": ("Consumer Discretionary", "Wholesale Trade"),
    "5200": ("Consumer Discretionary", "Retail Trade"),
    "5945": ("Consumer Discretionary", "Hobby & Toy Stores"),
    "6020": ("Financials", "State Commercial Banks"),
    "6022": ("Financials", "National Commercial Banks"),
    "6035": ("Financials", "Savings Institutions"),
    "6141": ("Financials", "Personal Credit Institutions"),
    "6153": ("Financials", "Short-Term Business Credit"),
    "6159": ("Financials", "Federal-Sponsored Credit Agencies"),
    "6200": ("Financials", "Security & Commodity Brokers"),
    "6211": ("Financials", "Security Brokers & Dealers"),
    "6282": ("Financials", "Investment Advice"),
    "6311": ("Financials", "Life Insurance"),
    "6321": ("Financials", "Accident & Health Insurance"),
    "6331": ("Financials", "Fire, Marine & Casualty Insurance"),
    "6411": ("Financials", "Insurance Agents"),
    "6500": ("Real Estate", "Real Estate"),
    "6512": ("Real Estate", "Operators of Nonresidential Buildings"),
    "6726": ("Financials", "Investment Offices"),
    "7372": ("Technology", "Prepackaged Software"),
    "7374": ("Technology", "Computer Processing & Data Preparation"),
    "7379": ("Technology", "Computer Related Services"),
    "7389": ("Industrials", "Services-Equipment Rental & Leasing"),
    "7372": ("Technology", "Software"),
    "8000": ("Healthcare", "Health Services"),
    "8011": ("Healthcare", "Offices & Clinics of Doctors"),
    "8049": ("Healthcare", "Offices & Clinics of Other Health Practitioners"),
    "8062": ("Healthcare", "Hospitals"),
    "8071": ("Healthcare", "Medical Laboratories"),
    "8731": ("Technology", "Commercial Physical & Biological Research"),
    "8742": ("Industrials", "Management Consulting Services"),
}

EXCHANGE_MAP = {
    "Nasdaq": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE MKT": "NYSE American",
    "NYSE Arca": "NYSE Arca",
    "CBOE": "CBOE",
    "OTC": "OTC",
}


class SecCollector(BaseCollector):
    """
    Collecteur SEC EDGAR.

    Utilise deux endpoints :
    1. https://www.sec.gov/files/company_tickers_exchange.json
       → Liste complète des entreprises cotées avec ticker et exchange
    2. https://data.sec.gov/submissions/CIK{cik}.json
       → Détail d'une entreprise (SIC, état, nb d'employés)

    Stratégie :
    - Phase 1 : télécharger la liste complète (~10k entreprises, 1 seul appel)
    - Phase 2 : enrichir chaque entrée via le endpoint submissions (paginé, avec sleep)
    - Le paramètre `limit` contrôle le nombre d'entreprises à traiter (défaut 500)
    """

    SOURCE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    # Délai entre les appels EDGAR pour respecter le rate limit
    REQUEST_DELAY = 0.2  # secondes

    @property
    def source_name(self) -> DiscoverySourceName:
        return DiscoverySourceName.SEC

    def _build_client(self):
        import httpx
        return httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )

    async def collect(self, job: DiscoveryJob) -> CollectorResult:
        result = CollectorResult()
        limit = self.params.get("limit", 500)

        self.logger.info("Starting SEC collection", limit=limit)

        # Phase 1 : liste des entreprises cotées
        try:
            response = await self._get(self.SOURCE_URL)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            result.add_error("fetch_ticker_list", str(e))
            raise

        # Format columnar (actuel) : {"fields": ["cik","name","ticker","exchange"], "data": [[320193,"Apple Inc.","AAPL","Nasdaq"], ...]}
        fields = data["fields"]
        rows = data["data"]
        entries = [dict(zip(fields, row)) for row in rows[:limit]]
        for entry in entries:
            entry["cik_str"] = entry.pop("cik", None)
            entry["title"] = entry.pop("name", "")
        self.logger.info("SEC tickers fetched", count=len(entries))

        # Phase 2 : enrichissement par lots de 10 (avec pause)
        batch_size = 10
        for i in range(0, len(entries), batch_size):
            batch = entries[i : i + batch_size]
            tasks = [self._enrich_company(entry, result) for entry in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            # Pause entre les batches pour respecter le rate limit SEC
            if i + batch_size < len(entries):
                await asyncio.sleep(self.REQUEST_DELAY * batch_size)

        result.meta["total_tickers"] = len(rows)
        result.meta["processed"] = len(entries)
        self.logger.info(
            "SEC collection complete",
            companies=len(result.companies),
            errors=len(result.errors),
        )
        return result

    async def _enrich_company(self, entry: dict, result: CollectorResult) -> None:
        """Récupère les détails d'une entreprise SEC et la normalise."""
        cik_raw = entry.get("cik_str", entry.get("cik", ""))
        ticker = entry.get("ticker", "")
        name = entry.get("title", "").strip()

        if not name or not cik_raw:
            return

        cik = str(cik_raw).zfill(10)

        # Enrichissement via submissions endpoint
        sic_code = None
        state_of_inc = None
        employees = None

        try:
            resp = await self._get(self.SUBMISSIONS_URL.format(cik=cik))
            if resp.status_code == 200:
                sub = resp.json()
                sic_code = str(sub.get("sic", "")).zfill(4) if sub.get("sic") else None
                state_of_inc = sub.get("stateOfIncorporation")
                employees = sub.get("employeeCount")
                await asyncio.sleep(self.REQUEST_DELAY)
        except Exception as e:
            result.add_error(f"enrichment:{ticker}", str(e))

        sector, industry = None, None
        if sic_code and sic_code in SIC_MAP:
            sector, industry = SIC_MAP[sic_code]

        exchange_raw = entry.get("exchange", "")
        exchange = EXCHANGE_MAP.get(exchange_raw, exchange_raw or None)

        company = CompanyData(
            name=name,
            country="US",
            country_name="United States",
            ticker=ticker.upper() if ticker else None,
            exchange=exchange,
            company_type=CompanyType.PUBLIC,
            sector=sector,
            industry=industry,
            headquarters_state=state_of_inc,
            employees=employees,
            external_id=cik,
            external_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
            tags=["sec-listed"],
            raw_data={
                "cik": cik,
                "ticker": ticker,
                "exchange": exchange_raw,
                "sic": sic_code,
            },
        )
        result.companies.append(company)
