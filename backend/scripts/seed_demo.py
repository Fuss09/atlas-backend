"""
Atlas - Demo Dataset Seed
==========================
Populates Atlas with a small, realistic demo dataset so the product can
be explored end-to-end without any external data source connected —
no live SEC/GitHub/YCombinator collector required.

Coverage (per Sprint 6 brief):
  - 10 companies across 4 domains: AI, Quantum Computing, Biotech, Energy
  - Associated to the real seeded themes (Module 03 migration) — this
    script does NOT create themes, it links companies to the themes
    that already exist in the database
  - A realistic spread of events per company (funding, partnerships,
    FDA/SEC/GitHub signals, acquisitions...) dated across the last
    ~90 days, so the unified Timeline (Sprint 5) has something to group
    into "This week" / "This month" / "Earlier" on first load
  - A discovery job + discovery source per company, so the Sources tab
    (Sprint 3) and the Discovery Signals score component aren't empty
  - A handful of graph relations between the demo companies (competes
    with, supplies, partners with, invests in) so the Knowledge Graph
    (Sprint 5) has a real connected structure to render, not a lone
    node with zero edges
  - Opportunity scores are NOT inserted directly — deliberately. Atlas's
    real OpportunityScoreService.get_or_compute() computes them from the
    events/themes/discoveries this script inserts, which is the most
    honest possible demonstration of "never a black box": the demo
    score is a real computed score, not a hand-picked number. This
    script calls recompute() once at the end so the first Dashboard
    load is already fast (scores precomputed), but the numbers
    themselves come from the real engine.

Idempotent: safe to run multiple times. Every entity is looked up by
its natural key (company slug, theme slug) before insertion — re-running
updates nothing and creates nothing new if the data already exists.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.db.database import AsyncSessionFactory
from app.models.company import Company, CompanyStatus, CompanyType
from app.models.discovery import DiscoveryJob, DiscoverySource, JobStatus
from app.models.event import Event, EventType, ImportanceLevel
from app.models.graph import EntityType, GraphRelation, RelationType
from app.models.theme import Theme, company_themes
from app.services.opportunity import OpportunityScoreService

configure_logging()
logger = get_logger("seed_demo")


def days_ago(n: int, hour: int = 10) -> datetime:
    return (datetime.now(UTC) - timedelta(days=n)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demo companies — 10 total, spanning the 4 domains called out in the brief.
# Each entry: (slug is derived from name), theme_slugs links to the real
# themes seeded by Module 03's migration.
# ─────────────────────────────────────────────────────────────────────────────

DEMO_COMPANIES: list[dict] = [
    # ── Artificial Intelligence ─────────────────────────────────────────────
    {
        "name": "Nexora AI",
        "ticker": "NXRA",
        "exchange": "NASDAQ",
        "company_type": CompanyType.PUBLIC,
        "sector": "Technology",
        "industry": "Artificial Intelligence Software",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "San Francisco",
        "headquarters_state": "California",
        "description": (
            "Nexora AI builds foundation models for enterprise document understanding, "
            "used by law firms and insurers to automate contract review at scale. "
            "The company has shipped three major model releases since its Series B."
        ),
        "description_short": "Foundation models for enterprise document understanding.",
        "website": "https://nexora.example.com",
        "founded_year": 2019,
        "market_cap_usd": 4_200_000,
        "employees": 340,
        "is_featured": True,
        "tags": ["AI", "enterprise-software", "foundation-models"],
        "theme_slugs": ["artificial-intelligence"],
    },
    {
        "name": "Verdant Robotics Labs",
        "ticker": None,
        "exchange": None,
        "company_type": CompanyType.PRIVATE,
        "sector": "Technology",
        "industry": "Robotics & AI",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "Boston",
        "headquarters_state": "Massachusetts",
        "description": (
            "Verdant Robotics Labs develops autonomous perception systems for warehouse "
            "robotics, combining computer vision models with low-latency edge inference "
            "hardware. Currently deployed in twelve fulfillment centers."
        ),
        "description_short": "Autonomous perception systems for warehouse robotics.",
        "website": "https://verdantrobotics.example.com",
        "founded_year": 2021,
        "market_cap_usd": None,
        "employees": 85,
        "is_featured": False,
        "tags": ["AI", "robotics", "computer-vision"],
        "theme_slugs": ["artificial-intelligence", "robotics-automation"],
    },
    {
        "name": "Halcyon Semantics",
        "ticker": "HLCY",
        "exchange": "NASDAQ",
        "company_type": CompanyType.PUBLIC,
        "sector": "Technology",
        "industry": "AI Infrastructure",
        "country": "GB",
        "country_name": "United Kingdom",
        "headquarters_city": "London",
        "headquarters_state": None,
        "description": (
            "Halcyon Semantics provides retrieval infrastructure for large language "
            "model applications, indexing structured and unstructured enterprise data "
            "for low-latency semantic search."
        ),
        "description_short": "Retrieval infrastructure for enterprise LLM applications.",
        "website": "https://halcyonsemantics.example.com",
        "founded_year": 2020,
        "market_cap_usd": 1_800_000,
        "employees": 210,
        "is_featured": False,
        "tags": ["AI", "infrastructure", "search"],
        "theme_slugs": ["artificial-intelligence", "cloud-computing"],
    },
    # ── Quantum Computing ────────────────────────────────────────────────────
    {
        "name": "Solstice Quantum",
        "ticker": "SQBT",
        "exchange": "NASDAQ",
        "company_type": CompanyType.PUBLIC,
        "sector": "Technology",
        "industry": "Quantum Computing Hardware",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "Boulder",
        "headquarters_state": "Colorado",
        "description": (
            "Solstice Quantum designs superconducting qubit processors, and has "
            "published peer-reviewed results demonstrating error correction thresholds "
            "competitive with the field's leading labs."
        ),
        "description_short": "Superconducting qubit processors with published error correction results.",
        "website": "https://solsticequantum.example.com",
        "founded_year": 2017,
        "market_cap_usd": 2_600_000,
        "employees": 165,
        "is_featured": True,
        "tags": ["quantum", "hardware", "deep-tech"],
        "theme_slugs": ["quantum-computing"],
    },
    {
        "name": "Argent Q Systems",
        "ticker": None,
        "exchange": None,
        "company_type": CompanyType.PRIVATE,
        "sector": "Technology",
        "industry": "Quantum Software",
        "country": "CA",
        "country_name": "Canada",
        "headquarters_city": "Waterloo",
        "headquarters_state": "Ontario",
        "description": (
            "Argent Q Systems builds a quantum circuit optimization compiler used by "
            "pharmaceutical and materials science research teams to reduce gate count "
            "on near-term quantum hardware."
        ),
        "description_short": "Quantum circuit optimization compiler for near-term hardware.",
        "website": "https://argentq.example.com",
        "founded_year": 2022,
        "market_cap_usd": None,
        "employees": 28,
        "is_featured": False,
        "tags": ["quantum", "software", "compiler"],
        "theme_slugs": ["quantum-computing"],
    },
    # ── Biotechnology ────────────────────────────────────────────────────────
    {
        "name": "Meridian Genomics",
        "ticker": "MRDG",
        "exchange": "NASDAQ",
        "company_type": CompanyType.PUBLIC,
        "sector": "Healthcare",
        "industry": "Gene Therapy",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "Cambridge",
        "headquarters_state": "Massachusetts",
        "description": (
            "Meridian Genomics develops AAV-based gene therapies for rare inherited "
            "retinal diseases. Its lead candidate is in Phase 2 trials following a "
            "positive Phase 1 safety readout."
        ),
        "description_short": "AAV-based gene therapies for rare inherited retinal diseases.",
        "website": "https://meridiangenomics.example.com",
        "founded_year": 2016,
        "market_cap_usd": 3_100_000,
        "employees": 190,
        "is_featured": True,
        "tags": ["biotech", "gene-therapy", "clinical-stage"],
        "theme_slugs": ["biotechnology"],
    },
    {
        "name": "Cascade Bio Diagnostics",
        "ticker": "CSBD",
        "exchange": "NYSE",
        "company_type": CompanyType.PUBLIC,
        "sector": "Healthcare",
        "industry": "Molecular Diagnostics",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "San Diego",
        "headquarters_state": "California",
        "description": (
            "Cascade Bio Diagnostics manufactures point-of-care molecular diagnostic "
            "panels for infectious disease detection, with FDA clearance for its "
            "flagship respiratory panel."
        ),
        "description_short": "Point-of-care molecular diagnostics for infectious disease.",
        "website": "https://cascadebio.example.com",
        "founded_year": 2014,
        "market_cap_usd": 980_000,
        "employees": 410,
        "is_featured": False,
        "tags": ["biotech", "diagnostics", "medtech"],
        "theme_slugs": ["biotechnology"],
    },
    {
        "name": "Orinthal Therapeutics",
        "ticker": None,
        "exchange": None,
        "company_type": CompanyType.PRIVATE,
        "sector": "Healthcare",
        "industry": "Biopharmaceuticals",
        "country": "CH",
        "country_name": "Switzerland",
        "headquarters_city": "Basel",
        "headquarters_state": None,
        "description": (
            "Orinthal Therapeutics is developing a small-molecule pipeline targeting "
            "fibrotic disease, spun out of university research and backed by a Series A "
            "led by a specialist life sciences fund."
        ),
        "description_short": "Small-molecule pipeline targeting fibrotic disease.",
        "website": "https://orinthal.example.com",
        "founded_year": 2023,
        "market_cap_usd": None,
        "employees": 22,
        "is_featured": False,
        "tags": ["biotech", "pharma", "early-stage"],
        "theme_slugs": ["biotechnology"],
    },
    # ── Energy ───────────────────────────────────────────────────────────────
    {
        "name": "Solvane Energy",
        "ticker": "SLVN",
        "exchange": "NYSE",
        "company_type": CompanyType.PUBLIC,
        "sector": "Energy",
        "industry": "Grid-Scale Battery Storage",
        "country": "US",
        "country_name": "United States",
        "headquarters_city": "Austin",
        "headquarters_state": "Texas",
        "description": (
            "Solvane Energy manufactures grid-scale lithium iron phosphate battery "
            "systems, with three utility-scale storage projects commissioned in the "
            "past eighteen months."
        ),
        "description_short": "Grid-scale lithium iron phosphate battery storage systems.",
        "website": "https://solvaneenergy.example.com",
        "founded_year": 2015,
        "market_cap_usd": 2_950_000,
        "employees": 520,
        "is_featured": True,
        "tags": ["energy", "storage", "grid"],
        "theme_slugs": ["energy-transition"],
    },
    {
        "name": "Fenwick Hydrogen",
        "ticker": None,
        "exchange": None,
        "company_type": CompanyType.PRIVATE,
        "sector": "Energy",
        "industry": "Green Hydrogen",
        "country": "DE",
        "country_name": "Germany",
        "headquarters_city": "Hamburg",
        "headquarters_state": None,
        "description": (
            "Fenwick Hydrogen operates electrolysis facilities producing green hydrogen "
            "for industrial customers, with a second production site under construction "
            "backed by an EU green infrastructure grant."
        ),
        "description_short": "Green hydrogen production for industrial customers.",
        "website": "https://fenwickhydrogen.example.com",
        "founded_year": 2020,
        "market_cap_usd": None,
        "employees": 140,
        "is_featured": False,
        "tags": ["energy", "hydrogen", "industrial"],
        "theme_slugs": ["energy-transition"],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Demo events — a realistic spread per company, dated across the last ~90
# days. Not every company gets every event type; the mix is deliberately
# uneven so the Timeline and Opportunity Score read as organic rather than
# templated. (company_name, event_type, importance, title, summary, days_ago,
# source, confidence_score)
# ─────────────────────────────────────────────────────────────────────────────

DEMO_EVENTS: list[dict] = [
    # Nexora AI
    {"company": "Nexora AI", "type": EventType.FUNDING, "importance": ImportanceLevel.CRITICAL,
     "title": "Nexora AI raises $85M Series C led by Sequoia",
     "summary": "The round values the company at $650M and will fund expansion into the European market.",
     "days_ago": 4, "source": "crunchbase", "confidence": 0.95},
    {"company": "Nexora AI", "type": EventType.PARTNERSHIP, "importance": ImportanceLevel.HIGH,
     "title": "Nexora AI announces strategic partnership with a Fortune 500 insurer",
     "summary": "The multi-year agreement integrates Nexora's document models into the insurer's claims pipeline.",
     "days_ago": 12, "source": "news", "confidence": 0.85},
    {"company": "Nexora AI", "type": EventType.GITHUB_ACTIVITY, "importance": ImportanceLevel.MEDIUM,
     "title": "Nexora AI open-sources its evaluation harness",
     "summary": "The repository crossed 2,000 stars within a week of release.",
     "days_ago": 25, "source": "github", "confidence": 0.9},
    {"company": "Nexora AI", "type": EventType.PRODUCT_LAUNCH, "importance": ImportanceLevel.MEDIUM,
     "title": "Nexora AI ships v3 of its document understanding model",
     "summary": "Benchmarks show a 14-point improvement on long-context contract clauses.",
     "days_ago": 48, "source": "news", "confidence": 0.8},
    {"company": "Nexora AI", "type": EventType.EARNINGS, "importance": ImportanceLevel.LOW,
     "title": "Nexora AI Q3 investor update",
     "summary": "ARR grew 40% quarter over quarter, per the company's investor letter.",
     "days_ago": 70, "source": "sec", "confidence": 0.75},

    # Verdant Robotics Labs
    {"company": "Verdant Robotics Labs", "type": EventType.YC_DISCOVERY, "importance": ImportanceLevel.HIGH,
     "title": "Verdant Robotics Labs discovered via Y Combinator batch tracking",
     "summary": "Flagged as a fast-growing graduate with strong warehouse automation traction.",
     "days_ago": 55, "source": "ycombinator", "confidence": 0.85},
    {"company": "Verdant Robotics Labs", "type": EventType.PARTNERSHIP, "importance": ImportanceLevel.HIGH,
     "title": "Verdant Robotics Labs signs pilot agreement with a national logistics operator",
     "summary": "The pilot covers three fulfillment centers over a six-month evaluation period.",
     "days_ago": 18, "source": "news", "confidence": 0.8},
    {"company": "Verdant Robotics Labs", "type": EventType.GITHUB_ACTIVITY, "importance": ImportanceLevel.LOW,
     "title": "Verdant Robotics Labs publishes a technical blog on edge inference latency",
     "summary": "The post details a 3x latency reduction on their perception stack.",
     "days_ago": 8, "source": "github", "confidence": 0.7},

    # Halcyon Semantics
    {"company": "Halcyon Semantics", "type": EventType.FUNDING, "importance": ImportanceLevel.HIGH,
     "title": "Halcyon Semantics closes $32M Series B",
     "summary": "The round was led by a London-based growth fund with participation from existing investors.",
     "days_ago": 33, "source": "crunchbase", "confidence": 0.9},
    {"company": "Halcyon Semantics", "type": EventType.PRODUCT_LAUNCH, "importance": ImportanceLevel.MEDIUM,
     "title": "Halcyon Semantics launches a managed retrieval API",
     "summary": "The new offering targets teams without in-house vector database expertise.",
     "days_ago": 15, "source": "news", "confidence": 0.75},
    {"company": "Halcyon Semantics", "type": EventType.NEWS, "importance": ImportanceLevel.LOW,
     "title": "Halcyon Semantics featured in an enterprise AI infrastructure roundup",
     "summary": "Coverage highlighted the company's low-latency indexing benchmarks.",
     "days_ago": 60, "source": "news", "confidence": 0.6},

    # Solstice Quantum
    {"company": "Solstice Quantum", "type": EventType.PATENT, "importance": ImportanceLevel.HIGH,
     "title": "Solstice Quantum granted patent for a novel qubit coupling architecture",
     "summary": "The USPTO grant covers a coupling method the company says reduces crosstalk error.",
     "days_ago": 6, "source": "uspto", "confidence": 0.9},
    {"company": "Solstice Quantum", "type": EventType.SEC_FILING, "importance": ImportanceLevel.MEDIUM,
     "title": "Solstice Quantum files 10-Q for the latest fiscal quarter",
     "summary": "R&D spend increased 22% year over year, per the filing.",
     "days_ago": 22, "source": "sec", "confidence": 0.95},
    {"company": "Solstice Quantum", "type": EventType.PARTNERSHIP, "importance": ImportanceLevel.CRITICAL,
     "title": "Solstice Quantum partners with a national research lab on error correction",
     "summary": "The multi-year collaboration grants joint access to a next-generation testbed.",
     "days_ago": 40, "source": "news", "confidence": 0.85},
    {"company": "Solstice Quantum", "type": EventType.INSIDER_BUY, "importance": ImportanceLevel.MEDIUM,
     "title": "Solstice Quantum CEO discloses open-market share purchase",
     "summary": "Form 4 filing shows a purchase of 15,000 shares at prevailing market price.",
     "days_ago": 3, "source": "sec", "confidence": 1.0},

    # Argent Q Systems
    {"company": "Argent Q Systems", "type": EventType.FUNDING, "importance": ImportanceLevel.HIGH,
     "title": "Argent Q Systems raises seed extension",
     "summary": "The extension brings total seed funding to $6.2M ahead of a planned Series A.",
     "days_ago": 28, "source": "crunchbase", "confidence": 0.85},
    {"company": "Argent Q Systems", "type": EventType.GITHUB_ACTIVITY, "importance": ImportanceLevel.MEDIUM,
     "title": "Argent Q Systems' compiler crosses 1,000 GitHub stars",
     "summary": "Adoption accelerated after a conference talk on gate-count reduction results.",
     "days_ago": 11, "source": "github", "confidence": 0.8},

    # Meridian Genomics
    {"company": "Meridian Genomics", "type": EventType.CLINICAL_TRIAL, "importance": ImportanceLevel.CRITICAL,
     "title": "Meridian Genomics advances lead candidate to Phase 2",
     "summary": "The advancement follows a positive Phase 1 safety and tolerability readout.",
     "days_ago": 9, "source": "news", "confidence": 0.9},
    {"company": "Meridian Genomics", "type": EventType.FDA_APPROVAL, "importance": ImportanceLevel.HIGH,
     "title": "Meridian Genomics receives Orphan Drug Designation",
     "summary": "The FDA designation applies to its lead gene therapy candidate.",
     "days_ago": 35, "source": "fda", "confidence": 0.95},
    {"company": "Meridian Genomics", "type": EventType.FUNDING, "importance": ImportanceLevel.HIGH,
     "title": "Meridian Genomics completes $60M follow-on offering",
     "summary": "Proceeds will fund the Phase 2 trial and expand manufacturing capacity.",
     "days_ago": 50, "source": "sec", "confidence": 0.9},
    {"company": "Meridian Genomics", "type": EventType.PATENT, "importance": ImportanceLevel.MEDIUM,
     "title": "Meridian Genomics granted patent on its AAV capsid delivery method",
     "summary": "The patent strengthens the company's position ahead of Phase 2 data readout.",
     "days_ago": 65, "source": "uspto", "confidence": 0.85},

    # Cascade Bio Diagnostics
    {"company": "Cascade Bio Diagnostics", "type": EventType.FDA_APPROVAL, "importance": ImportanceLevel.CRITICAL,
     "title": "Cascade Bio Diagnostics receives FDA clearance for expanded respiratory panel",
     "summary": "The clearance extends detection to four additional pathogens.",
     "days_ago": 14, "source": "fda", "confidence": 0.95},
    {"company": "Cascade Bio Diagnostics", "type": EventType.EARNINGS, "importance": ImportanceLevel.MEDIUM,
     "title": "Cascade Bio Diagnostics reports quarterly revenue above consensus",
     "summary": "Diagnostic panel volume grew 18% year over year.",
     "days_ago": 30, "source": "sec", "confidence": 0.9},
    {"company": "Cascade Bio Diagnostics", "type": EventType.INSIDER_SELL, "importance": ImportanceLevel.LOW,
     "title": "Cascade Bio Diagnostics director discloses a scheduled share sale",
     "summary": "Form 4 filing indicates a pre-scheduled 10b5-1 trading plan sale.",
     "days_ago": 5, "source": "sec", "confidence": 1.0},

    # Orinthal Therapeutics
    {"company": "Orinthal Therapeutics", "type": EventType.FUNDING, "importance": ImportanceLevel.HIGH,
     "title": "Orinthal Therapeutics closes CHF 18M Series A",
     "summary": "The round was led by a specialist life sciences fund with a board seat.",
     "days_ago": 20, "source": "crunchbase", "confidence": 0.85},
    {"company": "Orinthal Therapeutics", "type": EventType.NEWS, "importance": ImportanceLevel.LOW,
     "title": "Orinthal Therapeutics presents preclinical data at a fibrosis research conference",
     "summary": "The poster session drew attention from several potential pharma partners.",
     "days_ago": 45, "source": "news", "confidence": 0.65},

    # Solvane Energy
    {"company": "Solvane Energy", "type": EventType.ACQUISITION, "importance": ImportanceLevel.CRITICAL,
     "title": "Solvane Energy acquires a battery recycling startup",
     "summary": "The acquisition secures upstream material supply and closes a circularity gap in the value chain.",
     "days_ago": 7, "source": "news", "confidence": 0.9},
    {"company": "Solvane Energy", "type": EventType.PARTNERSHIP, "importance": ImportanceLevel.HIGH,
     "title": "Solvane Energy signs a utility-scale storage agreement",
     "summary": "The agreement covers a 400 MWh installation to be commissioned over eighteen months.",
     "days_ago": 24, "source": "news", "confidence": 0.85},
    {"company": "Solvane Energy", "type": EventType.EARNINGS, "importance": ImportanceLevel.MEDIUM,
     "title": "Solvane Energy Q2 revenue beats guidance",
     "summary": "Storage deployment revenue exceeded the company's own quarterly guidance range.",
     "days_ago": 42, "source": "sec", "confidence": 0.9},
    {"company": "Solvane Energy", "type": EventType.SEC_FILING, "importance": ImportanceLevel.LOW,
     "title": "Solvane Energy files annual report",
     "summary": "The 10-K outlines expansion plans for two additional manufacturing lines.",
     "days_ago": 75, "source": "sec", "confidence": 0.95},

    # Fenwick Hydrogen
    {"company": "Fenwick Hydrogen", "type": EventType.FUNDING, "importance": ImportanceLevel.HIGH,
     "title": "Fenwick Hydrogen secures EU green infrastructure grant",
     "summary": "The grant co-funds construction of the company's second electrolysis facility.",
     "days_ago": 17, "source": "news", "confidence": 0.85},
    {"company": "Fenwick Hydrogen", "type": EventType.PARTNERSHIP, "importance": ImportanceLevel.MEDIUM,
     "title": "Fenwick Hydrogen signs offtake agreement with an industrial gas distributor",
     "summary": "The multi-year agreement provides committed volume for the new facility's output.",
     "days_ago": 38, "source": "news", "confidence": 0.8},
]


# ─────────────────────────────────────────────────────────────────────────────
# Demo graph relations between the seeded companies — enough for the
# Knowledge Graph to render a real connected structure rather than a
# lone node. Weight/confidence are illustrative but plausible.
# ─────────────────────────────────────────────────────────────────────────────

DEMO_RELATIONS: list[dict] = [
    {"source": "Nexora AI", "target": "Halcyon Semantics", "type": RelationType.USES,
     "weight": 0.75, "confidence": 0.8,
     "source_tag": "manual", "inferred": False},
    {"source": "Nexora AI", "target": "Verdant Robotics Labs", "type": RelationType.COMPETES_WITH,
     "weight": 0.4, "confidence": 0.6,
     "source_tag": "discovery", "inferred": True},
    {"source": "Solstice Quantum", "target": "Argent Q Systems", "type": RelationType.PARTNERS_WITH,
     "weight": 0.85, "confidence": 0.9,
     "source_tag": "manual", "inferred": False},
    {"source": "Meridian Genomics", "target": "Cascade Bio Diagnostics", "type": RelationType.PARTNERS_WITH,
     "weight": 0.6, "confidence": 0.7,
     "source_tag": "discovery", "inferred": True},
    {"source": "Meridian Genomics", "target": "Orinthal Therapeutics", "type": RelationType.COMPETES_WITH,
     "weight": 0.5, "confidence": 0.65,
     "source_tag": "discovery", "inferred": True},
    {"source": "Solvane Energy", "target": "Fenwick Hydrogen", "type": RelationType.COMPETES_WITH,
     "weight": 0.45, "confidence": 0.6,
     "source_tag": "discovery", "inferred": True},
    {"source": "Solvane Energy", "target": "Nexora AI", "type": RelationType.INVESTS_IN,
     "weight": 0.3, "confidence": 0.55,
     "source_tag": "manual", "inferred": False},
    {"source": "Halcyon Semantics", "target": "Argent Q Systems", "type": RelationType.SUPPLIES,
     "weight": 0.35, "confidence": 0.5,
     "source_tag": "discovery", "inferred": True},
]


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "")


async def seed() -> None:
    async with AsyncSessionFactory() as session:
        # ── Companies ────────────────────────────────────────────────────────
        companies_by_name: dict[str, Company] = {}
        created_count = 0

        for spec in DEMO_COMPANIES:
            slug = _slugify(spec["name"])
            result = await session.execute(select(Company).where(Company.slug == slug))
            existing = result.scalar_one_or_none()
            if existing:
                companies_by_name[spec["name"]] = existing
                continue

            company = Company(
                id=uuid.uuid4(),
                name=spec["name"],
                slug=slug,
                ticker=spec["ticker"],
                exchange=spec["exchange"],
                company_type=spec["company_type"],
                status=CompanyStatus.ACTIVE,
                sector=spec["sector"],
                industry=spec["industry"],
                country=spec["country"],
                country_name=spec["country_name"],
                headquarters_city=spec["headquarters_city"],
                headquarters_state=spec["headquarters_state"],
                description=spec["description"],
                description_short=spec["description_short"],
                website=spec["website"],
                founded_year=spec["founded_year"],
                market_cap_usd=spec["market_cap_usd"],
                employees=spec["employees"],
                is_featured=spec["is_featured"],
                tags=spec["tags"],
                data_sources={"seed": "demo_dataset"},
            )
            session.add(company)
            companies_by_name[spec["name"]] = company
            created_count += 1

        await session.flush()
        logger.info("Companies seeded", created=created_count, total=len(DEMO_COMPANIES))

        # ── Theme associations ──────────────────────────────────────────────
        theme_links_created = 0
        for spec in DEMO_COMPANIES:
            company = companies_by_name[spec["name"]]
            for theme_slug in spec["theme_slugs"]:
                result = await session.execute(select(Theme).where(Theme.slug == theme_slug))
                theme = result.scalar_one_or_none()
                if not theme:
                    logger.warning(
                        "Theme not found — skipping association. Has Module 03's "
                        "migration (003_themes) been applied?",
                        theme_slug=theme_slug,
                    )
                    continue

                existing = await session.execute(
                    select(company_themes).where(
                        company_themes.c.company_id == company.id,
                        company_themes.c.theme_id == theme.id,
                    )
                )
                if existing.first():
                    continue

                await session.execute(
                    company_themes.insert().values(company_id=company.id, theme_id=theme.id)
                )
                theme_links_created += 1

        await session.flush()
        logger.info("Theme associations seeded", created=theme_links_created)

        # ── Discovery job + sources ─────────────────────────────────────────
        # One shared demo job per source, so the Discovery page and each
        # company's Sources tab have something real to show.
        jobs_by_source: dict[str, DiscoveryJob] = {}
        for source_name in ("crunchbase", "ycombinator", "sec", "github"):
            result = await session.execute(
                select(DiscoveryJob)
                .where(
                    DiscoveryJob.source == source_name,
                    DiscoveryJob.params.op("->>")("seed") == "demo_dataset",
                )
                .limit(1)
            )
            existing_job = result.scalars().first()
            if existing_job:
                jobs_by_source[source_name] = existing_job
                continue

            job = DiscoveryJob(
                id=uuid.uuid4(),
                source=source_name,
                status=JobStatus.SUCCESS,
                started_at=days_ago(90),
                finished_at=days_ago(90) + timedelta(minutes=4),
                companies_found=len(DEMO_COMPANIES),
                companies_created=len(DEMO_COMPANIES),
                companies_updated=0,
                companies_skipped=0,
                params={"seed": "demo_dataset"},
                meta={"note": "Synthetic job backing the Sprint 6 demo dataset"},
            )
            session.add(job)
            jobs_by_source[source_name] = job

        await session.flush()

        sources_created = 0
        for spec in DEMO_COMPANIES:
            company = companies_by_name[spec["name"]]
            source_name = "crunchbase" if spec["company_type"] == CompanyType.PRIVATE else "sec"
            job = jobs_by_source[source_name]

            existing = await session.execute(
                select(DiscoverySource)
                .where(
                    DiscoverySource.company_id == company.id,
                    DiscoverySource.job_id == job.id,
                )
                .limit(1)
            )
            if existing.scalars().first():
                continue

            session.add(
                DiscoverySource(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    job_id=job.id,
                    source=source_name,
                    external_id=f"demo-{_slugify(spec['name'])}",
                    external_url=spec["website"],
                    raw_data={"seed": "demo_dataset"},
                    action="created",
                )
            )
            sources_created += 1

        await session.flush()
        logger.info("Discovery sources seeded", created=sources_created)

        # ── Events ───────────────────────────────────────────────────────────
        events_created = 0
        for spec in DEMO_EVENTS:
            company = companies_by_name.get(spec["company"])
            if not company:
                continue

            occurred_at = days_ago(spec["days_ago"], hour=random.randint(8, 18))
            source_id = f"demo-{_slugify(spec['company'])}-{spec['type'].value}-{spec['days_ago']}"

            existing = await session.execute(
                select(Event)
                .where(
                    Event.source == spec["source"],
                    Event.source_id == source_id,
                )
                .limit(1)
            )
            if existing.scalars().first():
                continue

            session.add(
                Event(
                    id=uuid.uuid4(),
                    company_id=company.id,
                    event_type=spec["type"],
                    importance=spec["importance"],
                    title=spec["title"],
                    summary=spec["summary"],
                    occurred_at=occurred_at,
                    source=spec["source"],
                    source_id=source_id,
                    source_url=company.website,
                    confidence_score=spec["confidence"],
                    raw_data={"seed": "demo_dataset"},
                )
            )
            events_created += 1

        await session.flush()
        logger.info("Events seeded", created=events_created, total=len(DEMO_EVENTS))

        # ── Graph relations ─────────────────────────────────────────────────
        relations_created = 0
        for spec in DEMO_RELATIONS:
            source_company = companies_by_name.get(spec["source"])
            target_company = companies_by_name.get(spec["target"])
            if not source_company or not target_company:
                continue

            existing = await session.execute(
                select(GraphRelation).where(
                    GraphRelation.source_type == EntityType.COMPANY,
                    GraphRelation.source_id == source_company.id,
                    GraphRelation.target_type == EntityType.COMPANY,
                    GraphRelation.target_id == target_company.id,
                    GraphRelation.relation_type == spec["type"],
                )
            )
            if existing.scalar_one_or_none():
                continue

            session.add(
                GraphRelation(
                    id=uuid.uuid4(),
                    source_type=EntityType.COMPANY,
                    source_id=source_company.id,
                    source_label=source_company.name,
                    target_type=EntityType.COMPANY,
                    target_id=target_company.id,
                    target_label=target_company.name,
                    relation_type=spec["type"],
                    weight=spec["weight"],
                    confidence_score=spec["confidence"],
                    relation_source=spec["source_tag"],
                    is_inferred=spec["inferred"],
                )
            )
            relations_created += 1

        await session.flush()
        logger.info("Graph relations seeded", created=relations_created, total=len(DEMO_RELATIONS))

        await session.commit()

        # ── Compute real Opportunity Scores ─────────────────────────────────
        # Deliberately done last, after commit, using the real scoring
        # engine against the data just inserted — never a hand-picked
        # number. See module docstring.
        opportunity_service = OpportunityScoreService(session)
        scored = 0
        for company in companies_by_name.values():
            try:
                await opportunity_service.recompute(company.id)
                scored += 1
            except Exception as exc:  # noqa: BLE001 — a scoring failure shouldn't abort the seed
                logger.warning("Could not compute score", company=company.name, error=str(exc))
        await session.commit()
        logger.info("Opportunity scores computed", scored=scored, total=len(companies_by_name))

    logger.info(
        "Demo dataset seed complete",
        companies=len(DEMO_COMPANIES),
        events=len(DEMO_EVENTS),
        relations=len(DEMO_RELATIONS),
    )


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception:
        logger.error("Seed failed", exc_info=True)
        sys.exit(1)
