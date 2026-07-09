"""
Atlas - Opportunity Engine
===========================
Moteur de calcul du score d'opportunité.

Principe fondamental : le score n'est JAMAIS une boîte noire.
Chaque composant retourne sa valeur, son poids, et les facteurs — positifs
et négatifs — qui l'expliquent.

Le moteur est une classe pure : aucune dépendance à SQLAlchemy, à la base de
données ou à FastAPI. Il ne connaît que des structures de données simples
(dataclasses). Cela garantit :
- une testabilité unitaire totale, sans DB ni event loop ;
- un remplacement futur par un modèle de Machine Learning sans casser
  l'API ni le OpportunityScoreService qui l'appelle — seule cette classe
  serait remplacée, et OpportunityResult resterait le contrat de sortie.

Composants du score (pondération par défaut, scoring_version=1) :
- Events              35 % — signaux détectés (SEC, FDA, funding, brevets…)
- Theme Strength      20 % — maturité et alignement des thèmes de l'entreprise
- Company Quality     25 % — complétude et solidité du profil entreprise
- Discovery Signals   20 % — corroboration multi-sources et fraîcheur
- Market Signals       0 % — structure prête, volontairement non connecté

La somme des poids actifs fait toujours 100 %. Le jour où Market Signals sera
connecté à une vraie source de données de marché, les poids seront
rééquilibrés et SCORING_VERSION sera incrémenté — cela permettra de retraiter
tous les scores existants sans ambiguïté sur la méthode utilisée.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ConvictionLevel(StrEnum):
    """Niveau de conviction du score — traduction humaine du chiffre."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class OpportunityStage(StrEnum):
    """
    Stade de découverte du marché sur cette opportunité (cf. doc
    ATLAS_OPPORTUNITY_ENGINE.md — section "Types d'opportunités").

    EARLY        : entreprise encore peu suivie, signaux naissants.
    ACCELERATION : les signaux se multiplient sur une période récente.
    CONFIRMATION : la tendance est confirmée par un volume soutenu de signaux.
    MATURE       : le marché a déjà intégré l'information.
    """

    EARLY = "early"
    ACCELERATION = "acceleration"
    CONFIRMATION = "confirmation"
    MATURE = "mature"


# ─── Structures d'entrée (aucune dépendance ORM) ───────────────────────────────
#
# Le Service est responsable de traduire les modèles SQLAlchemy vers ces
# dataclasses avant d'appeler le moteur. Le moteur ne doit jamais recevoir
# un objet Company, Event, Theme ou DiscoverySource directement.

@dataclass
class EventSignal:
    """Vue simplifiée d'un Event, suffisante pour le calcul du score."""

    event_type: str
    importance: str
    occurred_at: datetime
    score_boost: float  # déjà calculé par EventService.get_score_boost()


@dataclass
class ThemeSignal:
    """Vue simplifiée d'un Theme associé à l'entreprise."""

    name: str
    maturity_level: str  # "emerging" | "growth" | "mature"


@dataclass
class CompanySignal:
    """Champs du profil Company pertinents pour la qualité du profil."""

    has_description: bool
    has_website: bool
    has_sector: bool
    has_industry: bool
    has_employees: bool
    has_revenue: bool
    has_market_cap: bool
    has_founded_year: bool
    has_logo: bool
    is_featured: bool
    status: str  # "active" | "inactive" | ...


@dataclass
class DiscoverySignal:
    """Vue simplifiée d'un DiscoverySource."""

    source: str
    discovered_at: datetime


@dataclass
class ScoreComponent:
    """
    Un composant du score — toujours explicable.

    value=None signifie explicitement "non connecté" (cas de Market Signals) :
    ce n'est pas un zéro déguisé, la distinction est structurelle et exposée
    telle quelle dans l'API.
    """

    name: str
    value: float | None
    weight: float
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    is_connected: bool = True

    @property
    def contribution(self) -> float:
        """Contribution pondérée au score global (0 si non connecté)."""
        if self.value is None:
            return 0.0
        return self.value * self.weight


@dataclass
class OpportunityResult:
    """Résultat complet et explicable d'un calcul de score."""

    score: int
    conviction: ConvictionLevel
    stage: OpportunityStage
    stage_rationale: str
    components: dict[str, ScoreComponent]
    positive_factors: list[str]
    negative_factors: list[str]
    calculated_at: datetime


# ─── Constantes de calcul ───────────────────────────────────────────────────────

WEIGHTS: dict[str, float] = {
    "events": 0.35,
    "theme_strength": 0.20,
    "company_quality": 0.25,
    "discovery_signals": 0.20,
    "market_signals": 0.0,  # structure prête, non connecté — voir docstring module
}

MATURITY_POTENTIAL: dict[str, float] = {
    "emerging": 90.0,
    "growth": 78.0,
    "mature": 55.0,
}

# Demi-vie (en jours) de la pertinence d'un event dans le score.
# Un event garde 50% de son poids initial après ce nombre de jours.
EVENT_RECENCY_HALF_LIFE_DAYS = 90.0

# Demi-vie (en jours) de la fraîcheur d'une découverte.
DISCOVERY_FRESHNESS_HALF_LIFE_DAYS = 180.0


class OpportunityEngine:
    """
    Moteur de calcul du score d'opportunité Atlas.

    Usage :
        engine = OpportunityEngine()
        result = engine.compute(
            events=[...], themes=[...], company=company_signal, discoveries=[...],
        )
    """

    SCORING_VERSION = 1

    def compute(
        self,
        events: list[EventSignal],
        themes: list[ThemeSignal],
        company: CompanySignal,
        discoveries: list[DiscoverySignal],
        now: datetime | None = None,
    ) -> OpportunityResult:
        now = now or datetime.now(UTC)

        components: dict[str, ScoreComponent] = {
            "events": self._score_events(events, now),
            "theme_strength": self._score_themes(themes),
            "company_quality": self._score_company_quality(company),
            "discovery_signals": self._score_discovery(discoveries, now),
            "market_signals": self._score_market_signals(),
        }

        raw_score = sum(c.contribution for c in components.values())
        global_score = round(max(0.0, min(100.0, raw_score)))

        positive, negative = self._collect_factors(components)
        conviction = self._conviction_from_score(global_score)
        stage, rationale = self._determine_stage(events, themes, global_score, now)

        return OpportunityResult(
            score=global_score,
            conviction=conviction,
            stage=stage,
            stage_rationale=rationale,
            components=components,
            positive_factors=positive,
            negative_factors=negative,
            calculated_at=now,
        )

    # ── Events ────────────────────────────────────────────────────────────────

    def _score_events(self, events: list[EventSignal], now: datetime) -> ScoreComponent:
        weight = WEIGHTS["events"]
        if not events:
            return ScoreComponent(
                name="events",
                value=0.0,
                weight=weight,
                negative_factors=["Aucun événement détecté sur cette entreprise"],
            )

        total = 0.0
        positive: list[str] = []
        negative: list[str] = []

        recent_first = sorted(events, key=lambda e: e.occurred_at, reverse=True)
        for e in recent_first[:20]:
            age_days = max((now - e.occurred_at).total_seconds() / 86400, 0.0)
            decay = 0.5 ** (age_days / EVENT_RECENCY_HALF_LIFE_DAYS)
            contribution = e.score_boost * decay
            total += contribution

            label = f"{e.event_type.replace('_', ' ').title()} ({e.importance}) — il y a {int(age_days)}j"
            if contribution >= 0:
                if len(positive) < 5:
                    positive.append(label)
            elif len(negative) < 5:
                negative.append(label)

        value = max(0.0, min(100.0, total))
        return ScoreComponent(
            name="events",
            value=round(value, 2),
            weight=weight,
            positive_factors=positive,
            negative_factors=negative,
        )

    # ── Theme Strength ───────────────────────────────────────────────────────

    def _score_themes(self, themes: list[ThemeSignal]) -> ScoreComponent:
        weight = WEIGHTS["theme_strength"]
        if not themes:
            return ScoreComponent(
                name="theme_strength",
                value=30.0,  # neutre-bas : pas de contexte thématique disponible
                weight=weight,
                negative_factors=["Aucun thème d'investissement associé"],
            )

        potentials = [MATURITY_POTENTIAL.get(t.maturity_level, 60.0) for t in themes]
        base = sum(potentials) / len(potentials)

        # Bonus de convergence : plusieurs thèmes pertinents renforcent le signal,
        # plafonné pour éviter qu'un simple tag-spam gonfle artificiellement le score.
        diversification_bonus = min(len(themes) - 1, 3) * 3.0
        value = min(100.0, base + diversification_bonus)

        positive = [f"Thème « {t.name} » ({t.maturity_level})" for t in themes[:5]]
        negative = []
        if all(t.maturity_level == "mature" for t in themes):
            negative.append(
                "Tous les thèmes associés sont matures — potentiel de découverte réduit"
            )

        return ScoreComponent(
            name="theme_strength",
            value=round(value, 2),
            weight=weight,
            positive_factors=positive,
            negative_factors=negative,
        )

    # ── Company Quality ──────────────────────────────────────────────────────

    def _score_company_quality(self, company: CompanySignal) -> ScoreComponent:
        weight = WEIGHTS["company_quality"]
        checks = {
            "Description renseignée": company.has_description,
            "Site web renseigné": company.has_website,
            "Secteur classifié": company.has_sector,
            "Industrie classifiée": company.has_industry,
            "Effectif connu": company.has_employees,
            "Chiffre d'affaires connu": company.has_revenue,
            "Capitalisation connue": company.has_market_cap,
            "Année de création connue": company.has_founded_year,
            "Logo disponible": company.has_logo,
        }
        filled = sum(1 for ok in checks.values() if ok)
        value = (filled / len(checks)) * 100.0

        positive = [label for label, ok in checks.items() if ok][:5]
        negative = [label for label, ok in checks.items() if not ok][:5]

        if company.is_featured:
            value = min(100.0, value + 5.0)
            positive.insert(0, "Entreprise mise en avant par Atlas")

        if company.status != "active":
            value *= 0.5
            negative.insert(0, f"Statut de l'entreprise : {company.status}")

        return ScoreComponent(
            name="company_quality",
            value=round(value, 2),
            weight=weight,
            positive_factors=positive,
            negative_factors=negative,
        )

    # ── Discovery Signals ────────────────────────────────────────────────────

    def _score_discovery(
        self, discoveries: list[DiscoverySignal], now: datetime
    ) -> ScoreComponent:
        weight = WEIGHTS["discovery_signals"]
        if not discoveries:
            return ScoreComponent(
                name="discovery_signals",
                value=20.0,
                weight=weight,
                negative_factors=["Aucune source de découverte enregistrée"],
            )

        distinct_sources = sorted({d.source for d in discoveries})
        corroboration_score = min(len(distinct_sources), 4) * 20.0  # jusqu'à 80

        most_recent = max(d.discovered_at for d in discoveries)
        age_days = max((now - most_recent).total_seconds() / 86400, 0.0)
        freshness_score = 20.0 * (0.5 ** (age_days / DISCOVERY_FRESHNESS_HALF_LIFE_DAYS))

        value = min(100.0, corroboration_score + freshness_score)

        positive = [
            f"Détectée via {len(distinct_sources)} source(s) : {', '.join(distinct_sources)}"
        ]
        negative: list[str] = []
        if age_days <= 30:
            positive.append("Dernière détection récente (< 30 jours)")
        else:
            negative.append(f"Dernière détection il y a {int(age_days)} jours")

        return ScoreComponent(
            name="discovery_signals",
            value=round(value, 2),
            weight=weight,
            positive_factors=positive,
            negative_factors=negative,
        )

    # ── Market Signals (structure uniquement) ───────────────────────────────

    def _score_market_signals(self) -> ScoreComponent:
        """
        Toujours présent dans la sortie pour que l'API n'ait jamais à changer
        de forme le jour où ce composant sera branché sur une vraie source
        de données de marché (cours, volume, volatilité...).
        """
        return ScoreComponent(
            name="market_signals",
            value=None,
            weight=WEIGHTS["market_signals"],
            is_connected=False,
            negative_factors=["Signaux de marché non connectés — prévu dans un module futur"],
        )

    # ── Agrégation ───────────────────────────────────────────────────────────

    def _collect_factors(
        self, components: dict[str, ScoreComponent]
    ) -> tuple[list[str], list[str]]:
        positive: list[str] = []
        negative: list[str] = []
        for component in components.values():
            positive.extend(component.positive_factors)
            negative.extend(component.negative_factors)
        return positive, negative

    def _conviction_from_score(self, score: int) -> ConvictionLevel:
        if score >= 80:
            return ConvictionLevel.VERY_HIGH
        if score >= 60:
            return ConvictionLevel.HIGH
        if score >= 40:
            return ConvictionLevel.MODERATE
        return ConvictionLevel.LOW

    def _determine_stage(
        self,
        events: list[EventSignal],
        themes: list[ThemeSignal],
        score: int,
        now: datetime,
    ) -> tuple[OpportunityStage, str]:
        if not events:
            return (
                OpportunityStage.EARLY,
                "Aucun événement détecté — entreprise tout juste repérée par Atlas",
            )

        recent_events = [e for e in events if (now - e.occurred_at).days <= 30]

        if len(recent_events) >= 3 and score >= 60:
            return (
                OpportunityStage.ACCELERATION,
                f"{len(recent_events)} événements détectés dans les 30 derniers jours "
                "— les signaux se multiplient",
            )

        if score >= 70 and len(events) >= 5:
            return (
                OpportunityStage.CONFIRMATION,
                "Tendance confirmée par un volume soutenu de signaux positifs",
            )

        if (
            themes
            and all(t.maturity_level == "mature" for t in themes)
            and not recent_events
        ):
            return (
                OpportunityStage.MATURE,
                "Thème(s) mature(s) et absence de signal récent — le marché a "
                "probablement déjà intégré l'information",
            )

        return (
            OpportunityStage.EARLY,
            "Peu de signaux à ce stade — entreprise encore peu suivie",
        )
