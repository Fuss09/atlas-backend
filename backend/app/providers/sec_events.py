"""
Atlas - SEC Filing Events Provider
==================================
Récupère les dépôts SEC récents d'une entreprise (via son CIK) et les
transforme en événements scorables. Réutilise l'endpoint submissions que le
collecteur de découverte interroge déjà. Source officielle, JSON, sans clé.

Mapping form → EventType (v1) :
    8-K → SEC_FILING (MEDIUM) ; 10-K → EARNINGS (HIGH) ; 10-Q → EARNINGS (MEDIUM)
    4   → SEC_FILING (LOW) — transaction d'initié, achat/vente NON distingué en
          v1 (INSIDER_SELL=-5 / INSIDER_BUY=+10 : tout étiqueter « achat »
          fausserait le score). Précision en v2.
Déduplication : source_id = numéro d'accession du dépôt.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

import httpx

from app.core.logging import get_logger
from app.models.event import EventType, ImportanceLevel

logger = get_logger(__name__)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

FORM_MAP: dict[str, tuple[EventType, ImportanceLevel, str]] = {
    "8-K": (EventType.SEC_FILING, ImportanceLevel.MEDIUM, "Material event (8-K)"),
    "10-K": (EventType.EARNINGS, ImportanceLevel.HIGH, "Annual report (10-K)"),
    "10-Q": (EventType.EARNINGS, ImportanceLevel.MEDIUM, "Quarterly report (10-Q)"),
    "4": (EventType.SEC_FILING, ImportanceLevel.LOW, "Insider transaction (Form 4)"),
}


@dataclass
class FilingEvent:
    accession: str
    form: str
    event_type: EventType
    importance: ImportanceLevel
    title: str
    occurred_at: datetime
    url: str


class SecEventsProvider(Protocol):
    name: str

    def fetch_filings(self, cik: str, since: date) -> list[FilingEvent]: ...


class EdgarEventsProvider:
    name = "sec_edgar"
    TIMEOUT = 20.0

    def _user_agent(self) -> str:
        from app.core.config import get_settings
        s = get_settings()
        return f"Atlas-Market-Intelligence/{s.app_version} (contact: {s.collector_contact_email})"

    def fetch_filings(self, cik: str, since: date) -> list[FilingEvent]:
        cik10 = str(cik).zfill(10)
        try:
            resp = httpx.get(
                SUBMISSIONS_URL.format(cik=cik10),
                headers={"User-Agent": self._user_agent(), "Accept": "application/json"},
                timeout=self.TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.warning("SEC filings fetch failed", cik=cik10, error=str(exc))
            return []
        recent = (payload.get("filings") or {}).get("recent") or {}
        return self._parse_recent(recent, cik10, since)

    @staticmethod
    def _parse_recent(recent: dict, cik10: str, since: date) -> list[FilingEvent]:
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        docs = recent.get("primaryDocument") or []
        out: list[FilingEvent] = []
        for i, form in enumerate(forms):
            mapping = FORM_MAP.get(form)
            if not mapping:
                continue
            try:
                filed = date.fromisoformat(dates[i])
            except (IndexError, ValueError):
                continue
            if filed < since:
                continue
            accession = accessions[i] if i < len(accessions) else None
            if not accession:
                continue
            event_type, importance, label = mapping
            doc = docs[i] if i < len(docs) else ""
            acc_nodash = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc_nodash}/{doc}"
            out.append(FilingEvent(accession, form, event_type, importance, label,
                                   datetime(filed.year, filed.month, filed.day, tzinfo=UTC), url))
        return out


class FakeSecEventsProvider:
    name = "fake"

    def fetch_filings(self, cik: str, since: date) -> list[FilingEvent]:
        recent = {
            "form": ["8-K", "10-Q", "4", "S-1", "10-K"],
            "filingDate": [(datetime.now(UTC).date() - timedelta(days=d)).isoformat()
                           for d in (5, 20, 12, 8, 400)],
            "accessionNumber": [f"{cik}-{i:04d}" for i in range(5)],
            "primaryDocument": ["a.htm", "b.htm", "c.xml", "d.htm", "e.htm"],
        }
        return EdgarEventsProvider._parse_recent(recent, str(cik).zfill(10), since)


def get_sec_events_provider(name: str) -> SecEventsProvider:
    providers: dict[str, SecEventsProvider] = {
        "sec_edgar": EdgarEventsProvider(),
        "fake": FakeSecEventsProvider(),
    }
    if name not in providers:
        raise ValueError(f"Unknown SEC events provider: {name!r} (expected {sorted(providers)})")
    return providers[name]
