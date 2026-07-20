"""
Atlas - Catalyst Providers
==========================
Sources de catalyseurs futurs (rendez-vous datés à venir).

Source actuelle : ClinicalTrials.gov API v2 — officielle, JSON, sans clé.
La « primary completion date » estimée d'un essai de phase 2/3 est le
catalyseur type d'une biotech : la lecture des résultats suit cette date,
et c'est l'événement binaire qui fait bouger le cours (le cas Abivax).

CTIS (registre européen) n'a PAS d'API publique officielle à ce jour (accès
machine réservé aux États membres) — noté comme collector futur si le portail
s'ouvre. En attendant, ClinicalTrials.gov couvre une large part des essais
européens (les sponsors internationaux y enregistrent aussi).

Particularité documentée de l'API : les dates sont à précision variable
(« 2026-09-15 », « 2026-09 », « September 2026 »). Le parseur normalise et
CONSERVE la précision — afficher un jour précis quand la source ne donnait
qu'un mois serait une fausse précision.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

# Statuts d'essais dont la lecture de résultats est encore à venir
ACTIVE_STATUSES = "RECRUITING|ACTIVE_NOT_RECRUITING|NOT_YET_RECRUITING|ENROLLING_BY_INVITATION"

# Phases retenues : les lectures de phase 2/3 sont les événements binaires
# à fort impact ; la phase 1 (sécurité) bouge rarement un cours.
RELEVANT_PHASES = {"PHASE2", "PHASE3"}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


@dataclass
class TrialCatalyst:
    """Un catalyseur issu d'un essai clinique."""

    external_id: str          # "NCT12345678:pcd" — clé de déduplication
    title: str
    expected_date: date
    date_precision: str       # "day" | "month"
    source_url: str
    phase: str
    trial_status: str


def parse_partial_date(raw: str) -> tuple[date, str] | None:
    """
    Normalise les formats de date de ClinicalTrials.gov.
    Retourne (date, précision) ou None si illisible.
    Une date à précision mois est ancrée au 1er du mois.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    # "2026-09-15"
    try:
        return date.fromisoformat(raw), "day"
    except ValueError:
        pass
    # "2026-09"
    parts = raw.split("-")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return date(int(parts[0]), int(parts[1]), 1), "month"
    # "September 2026" / "September 15, 2026"
    tokens = raw.replace(",", "").split()
    if len(tokens) == 2 and tokens[0].lower() in MONTHS and tokens[1].isdigit():
        return date(int(tokens[1]), MONTHS[tokens[0].lower()], 1), "month"
    if (
        len(tokens) == 3
        and tokens[0].lower() in MONTHS
        and tokens[1].isdigit()
        and tokens[2].isdigit()
    ):
        return date(int(tokens[2]), MONTHS[tokens[0].lower()], int(tokens[1])), "day"
    logger.info("Unparseable trial date", raw=raw)
    return None


class CatalystProvider(Protocol):
    name: str

    def fetch_for_sponsor(self, sponsor_name: str) -> list[TrialCatalyst]:
        """Catalyseurs à venir pour un sponsor. Liste vide si aucun/introuvable."""
        ...


class ClinicalTrialsProvider:
    """ClinicalTrials.gov API v2 — parsing défensif, échec gracieux."""

    name = "clinicaltrials"
    TIMEOUT = 20.0

    def fetch_for_sponsor(self, sponsor_name: str) -> list[TrialCatalyst]:
        params = {
            "query.spons": sponsor_name,
            "filter.overallStatus": ACTIVE_STATUSES,
            "pageSize": 50,
            "fields": (
                "protocolSection.identificationModule.nctId,"
                "protocolSection.identificationModule.briefTitle,"
                "protocolSection.statusModule.overallStatus,"
                "protocolSection.statusModule.primaryCompletionDateStruct,"
                "protocolSection.designModule.phases"
            ),
        }
        try:
            resp = httpx.get(CLINICALTRIALS_API, params=params, timeout=self.TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.warning(
                "ClinicalTrials fetch failed", sponsor=sponsor_name, error=str(exc)
            )
            return []
        return self._parse_studies(payload.get("studies") or [])

    def _parse_studies(self, studies: list[dict]) -> list[TrialCatalyst]:
        today = datetime.now(UTC).date()
        catalysts: list[TrialCatalyst] = []
        for study in studies:
            proto = study.get("protocolSection") or {}
            ident = proto.get("identificationModule") or {}
            status_mod = proto.get("statusModule") or {}
            design = proto.get("designModule") or {}

            nct_id = ident.get("nctId")
            if not nct_id:
                continue

            phases = set(design.get("phases") or [])
            if not (phases & RELEVANT_PHASES):
                continue

            pcd = status_mod.get("primaryCompletionDateStruct") or {}
            parsed = parse_partial_date(pcd.get("date") or "")
            if parsed is None:
                continue
            expected, precision = parsed
            if expected < today:
                continue  # lecture déjà passée — pas un catalyseur futur

            phase_label = "Phase 3" if "PHASE3" in phases else "Phase 2"
            title = ident.get("briefTitle") or nct_id
            catalysts.append(
                TrialCatalyst(
                    external_id=f"{nct_id}:pcd",
                    title=f"{phase_label} primary completion — {title[:200]}",
                    expected_date=expected,
                    date_precision=precision,
                    source_url=f"https://clinicaltrials.gov/study/{nct_id}",
                    phase=phase_label,
                    trial_status=str(status_mod.get("overallStatus") or ""),
                )
            )
        return catalysts


class FakeCatalystProvider:
    """
    Provider de test : deux essais déterministes, dont un à date partielle —
    valide toute la chaîne (parsing, précision, dédup) sans réseau.
    """

    name = "fake"

    def fetch_for_sponsor(self, sponsor_name: str) -> list[TrialCatalyst]:
        today = datetime.now(UTC).date()
        y, m = (today.year + (1 if today.month >= 10 else 0), (today.month + 3 - 1) % 12 + 1)
        payload = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": f"NCT9{sum(ord(c) * (i + 1) for i, c in enumerate(sponsor_name)) % 10**7:07d}",
                            "briefTitle": f"Pivotal study of {sponsor_name} lead candidate",
                        },
                        "statusModule": {
                            "overallStatus": "RECRUITING",
                            "primaryCompletionDateStruct": {
                                "date": f"{y}-{m:02d}-15",
                                "type": "ESTIMATED",
                            },
                        },
                        "designModule": {"phases": ["PHASE3"]},
                    }
                },
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": f"NCT8{sum(ord(c) * (i + 1) for i, c in enumerate(sponsor_name)) % 10**7:07d}",
                            "briefTitle": f"Dose-expansion study of {sponsor_name}",
                        },
                        "statusModule": {
                            "overallStatus": "ACTIVE_NOT_RECRUITING",
                            "primaryCompletionDateStruct": {
                                # date à précision mois — teste le parseur partiel
                                "date": f"{'January' if m == 1 else list(MONTHS)[m - 1].capitalize()} {y + 1}",
                                "type": "ESTIMATED",
                            },
                        },
                        "designModule": {"phases": ["PHASE2"]},
                    }
                },
            ]
        }
        return ClinicalTrialsProvider()._parse_studies(payload["studies"])


def get_catalyst_provider(name: str) -> CatalystProvider:
    providers: dict[str, CatalystProvider] = {
        "clinicaltrials": ClinicalTrialsProvider(),
        "fake": FakeCatalystProvider(),
    }
    if name not in providers:
        raise ValueError(f"Unknown catalyst provider: {name!r} (expected {sorted(providers)})")
    return providers[name]
