"""
Atlas - Discovery Service
==========================
Orchestre l'exécution des collecteurs et la persistance des résultats.

Responsabilités :
1. Créer le DiscoveryJob en base
2. Instancier le bon collecteur via le registry
3. Exécuter la collecte
4. Pour chaque CompanyData retournée :
   - Détecter les doublons (ticker, ISIN, nom exact)
   - Créer ou mettre à jour la Company
   - Créer le DiscoverySource (traçabilité)
5. Mettre à jour le job avec les statistiques finales

Stratégie de déduplication :
  Priorité : ticker > ISIN > nom exact (case-insensitive)
  Si aucun match : création d'une nouvelle Company
  Si match : mise à jour uniquement des champs non renseignés (pas d'écrasement)
  → Principe Atlas : une donnée existante ne recule jamais
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CompanyData
from app.collectors.registry import get_collector
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.company import Company
from app.models.discovery import DiscoveryJob, DiscoverySourceName, JobStatus
from app.models.event import EventType, ImportanceLevel
from app.repositories.company import CompanyRepository
from app.repositories.discovery import DiscoveryJobRepository, DiscoverySourceRepository
from app.schemas.company import CompanyCreate, _generate_slug
from app.schemas.discovery import DiscoveryJobResponse, DiscoveryJobSummary

logger = get_logger(__name__)


class DiscoveryService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = DiscoveryJobRepository(session)
        self.source_repo = DiscoverySourceRepository(session)
        self.company_repo = CompanyRepository(session)

    # ─── Lecture ──────────────────────────────────────────────────────────────

    async def get_job(self, job_id: uuid.UUID) -> DiscoveryJob:
        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("DiscoveryJob", job_id)
        return job

    async def list_jobs(
        self,
        source: str | None = None,
        limit: int = 50,
    ) -> list[DiscoveryJob]:
        return await self.job_repo.list_recent(source=source, limit=limit)

    # ─── Exécution ────────────────────────────────────────────────────────────

    async def trigger_job(
        self,
        source: DiscoverySourceName,
        params: dict | None = None,
        triggered_by: uuid.UUID | None = None,
    ) -> DiscoveryJob:
        """
        Crée un job et lance la collecte en arrière-plan (fire-and-forget).

        Le job est créé en base immédiatement (statut PENDING).
        La collecte tourne en tâche asyncio — l'API répond sans attendre la fin.
        """
        # Valider que le collecteur existe avant de créer le job
        try:
            get_collector(source, params)
        except ValueError as e:
            raise ValidationError(str(e))

        job = await self.job_repo.create(
            source=source.value,
            triggered_by=triggered_by,
            params=params,
        )
        await self.session.commit()

        # Lancer la collecte en arrière-plan
        asyncio.create_task(
            self._run_job_background(job.id, source, params)
        )

        logger.info(
            "Discovery job triggered",
            job_id=str(job.id),
            source=source.value,
            triggered_by=str(triggered_by) if triggered_by else "system",
        )
        return job

    async def run_job_sync(
        self,
        source: DiscoverySourceName,
        params: dict | None = None,
        triggered_by: uuid.UUID | None = None,
    ) -> DiscoveryJob:
        """
        Exécute un job de façon synchrone (attend la fin).
        Utilisé pour les tests et les runs manuels en CLI.
        """
        job = await self.job_repo.create(
            source=source.value,
            triggered_by=triggered_by,
            params=params,
        )
        await self.session.commit()
        await self._execute_job(job.id, source, params)
        return await self.job_repo.get_by_id(job.id)

    async def _run_job_background(
        self,
        job_id: uuid.UUID,
        source: DiscoverySourceName,
        params: dict | None,
    ) -> None:
        """
        Wrapper pour l'exécution en arrière-plan.
        Crée une nouvelle session DB pour éviter les conflits avec la session principale.
        """
        from app.db.database import AsyncSessionFactory
        async with AsyncSessionFactory() as session:
            service = DiscoveryService(session)
            try:
                await service._execute_job(job_id, source, params)
            except Exception as e:
                logger.error(
                    "Background job failed",
                    job_id=str(job_id),
                    error=str(e),
                    exc_info=e,
                )

    async def _execute_job(
        self,
        job_id: uuid.UUID,
        source: DiscoverySourceName,
        params: dict | None,
    ) -> None:
        """
        Exécution principale du job :
        1. Marquer comme RUNNING
        2. Collecter les données
        3. Persister chaque CompanyData
        4. Marquer comme SUCCESS/PARTIAL/FAILED
        """
        await self.job_repo.mark_running(job_id)
        await self.session.commit()

        job = await self.job_repo.get_by_id(job_id)
        stats = {"created": 0, "updated": 0, "skipped": 0}
        final_status = JobStatus.SUCCESS

        try:
            collector = get_collector(source, params)
            async with collector:
                result = await collector.collect(job)

            # Persister les entreprises
            for company_data in result.companies:
                try:
                    action = await self._upsert_company(company_data, job_id, source)
                    stats[action] += 1
                except Exception as e:
                    result.add_error(f"persist:{company_data.name}", str(e))
                    stats["skipped"] += 1

            if result.errors:
                final_status = JobStatus.PARTIAL

            await self.job_repo.mark_finished(
                job_id=job_id,
                status=final_status,
                companies_found=len(result.companies),
                companies_created=stats["created"],
                companies_updated=stats["updated"],
                companies_skipped=stats["skipped"],
                errors=result.errors[:100],  # Cap à 100 erreurs
                meta=result.meta,
            )

        except Exception as e:
            logger.error("Job execution failed", job_id=str(job_id), error=str(e))
            await self.job_repo.mark_finished(
                job_id=job_id,
                status=JobStatus.FAILED,
                errors=[{"context": "fatal", "error": str(e)}],
            )
        finally:
            await self.session.commit()

        logger.info(
            "Discovery job finished",
            job_id=str(job_id),
            source=source.value,
            status=final_status.value,
            **stats,
        )

    # ─── Déduplication et persistance ─────────────────────────────────────────

    async def _upsert_company(
        self,
        data: CompanyData,
        job_id: uuid.UUID,
        source: DiscoverySourceName,
    ) -> str:
        """
        Crée ou met à jour une Company depuis un CompanyData.

        Retourne : "created", "updated", ou "skipped"

        Stratégie de déduplication (ordre de priorité) :
        1. Ticker (identifiant de marché fiable pour les entreprises publiques)
        2. ISIN (identifiant international normalisé)
        3. Nom exact (case-insensitive, dernière chance)

        Règle de mise à jour :
        On ne remplace jamais une valeur existante par None.
        On ne remplace jamais une valeur existante par une valeur identique.
        On enrichit : si le champ est vide, on le remplit.
        """
        existing = await self._find_existing(data)

        if existing:
            updated = await self._enrich_company(existing, data)
            action = "updated" if updated else "skipped"
            await self.source_repo.create(
                company_id=existing.id,
                job_id=job_id,
                source=source.value,
                action=action,
                external_id=data.external_id,
                external_url=data.external_url,
                raw_data=data.raw_data,
            )
            return action

        # Création
        company = await self._create_company(data)
        await self.source_repo.create(
            company_id=company.id,
            job_id=job_id,
            source=source.value,
            action="created",
            external_id=data.external_id,
            external_url=data.external_url,
            raw_data=data.raw_data,
        )
        # Création automatique d'un event de découverte
        await self._create_discovery_event(company, data, source)
        return "created"

    async def _find_existing(self, data: CompanyData) -> Company | None:
        """Cherche une Company existante via ticker, ISIN, puis nom."""
        if data.ticker:
            found = await self.company_repo.get_by_ticker(data.ticker)
            if found:
                return found
        if data.isin:
            found = await self.company_repo.get_by_isin(data.isin)
            if found:
                return found
        # Recherche par nom exact (dernière chance)
        from sqlalchemy import func, select
        from app.models.company import Company as CompanyModel
        result = await self.session.execute(
            select(CompanyModel).where(
                func.lower(CompanyModel.name) == data.name.lower(),
                CompanyModel.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def _enrich_company(self, company: Company, data: CompanyData) -> bool:
        """
        Enrichit une Company existante avec les données du collecteur.
        Principe : ne jamais écraser une valeur existante non-nulle.
        Retourne True si au moins un champ a été mis à jour.
        """
        updates: dict = {}

        # Champs enrichissables (ne pas écraser si déjà renseigné)
        field_map = {
            "ticker": data.ticker,
            "isin": data.isin,
            "exchange": data.exchange,
            "sector": data.sector,
            "industry": data.industry,
            "description": data.description,
            "description_short": data.description_short,
            "website": data.website,
            "logo_url": data.logo_url,
            "founded_year": data.founded_year,
            "market_cap_usd": data.market_cap_usd,
            "employees": data.employees,
            "revenue_usd": data.revenue_usd,
            "headquarters_city": data.headquarters_city,
            "headquarters_state": data.headquarters_state,
            "country_name": data.country_name,
        }

        for field, new_value in field_map.items():
            if new_value is not None and getattr(company, field) is None:
                updates[field] = new_value

        # Tags : fusion (union sans doublons)
        if data.tags:
            existing_tags = list(company.tags or [])
            new_tags = [t for t in data.tags if t not in existing_tags]
            if new_tags:
                updates["tags"] = existing_tags + new_tags

        # data_sources : enrichissement du dict
        existing_sources = dict(company.data_sources or {})
        existing_sources[data.external_id or "unknown"] = {
            "url": data.external_url,
            "last_updated": datetime.now(UTC).isoformat(),
        }
        updates["data_sources"] = existing_sources
        updates["last_enriched_at"] = datetime.now(UTC)

        if updates:
            await self.company_repo.update(company.id, **updates)
            return True
        return False

    async def _create_company(self, data: CompanyData) -> Company:
        """Crée une nouvelle Company depuis un CompanyData."""
        base_slug = _generate_slug(data.name)
        slug = await self.company_repo.generate_unique_slug(base_slug)

        data_sources = {}
        if data.external_id:
            data_sources[data.external_id] = {
                "url": data.external_url,
                "last_updated": datetime.now(UTC).isoformat(),
            }

        return await self.company_repo.create(
            name=data.name,
            slug=slug,
            ticker=data.ticker,
            isin=data.isin,
            exchange=data.exchange,
            company_type=data.company_type,
            sector=data.sector,
            industry=data.industry,
            country=data.country,
            country_name=data.country_name,
            headquarters_city=data.headquarters_city,
            headquarters_state=data.headquarters_state,
            description=data.description,
            description_short=data.description_short,
            website=data.website,
            logo_url=data.logo_url,
            founded_year=data.founded_year,
            ipo_date=data.ipo_date,
            market_cap_usd=data.market_cap_usd,
            employees=data.employees,
            revenue_usd=data.revenue_usd,
            tags=data.tags or [],
            data_sources=data_sources,
            last_enriched_at=datetime.now(UTC),
        )

    async def _create_discovery_event(
        self,
        company: Company,
        data: CompanyData,
        source: DiscoverySourceName,
    ) -> None:
        """
        Crée automatiquement un event de découverte lors de l'ajout d'une entreprise.
        Appelé uniquement à la création (pas lors des mises à jour).
        Importation locale pour éviter la circularité discovery ↔ event.
        """
        try:
            from app.services.event import EventService

            event_type_map = {
                DiscoverySourceName.YCOMBINATOR: EventType.YC_DISCOVERY,
                DiscoverySourceName.CRUNCHBASE: EventType.CRUNCHBASE_FUNDING,
                DiscoverySourceName.GITHUB: EventType.GITHUB_ACTIVITY,
                DiscoverySourceName.SEC: EventType.SEC_FILING,
            }
            event_type = event_type_map.get(source, EventType.NEWS)

            importance_map = {
                DiscoverySourceName.YCOMBINATOR: ImportanceLevel.HIGH,
                DiscoverySourceName.CRUNCHBASE: ImportanceLevel.HIGH,
                DiscoverySourceName.GITHUB: ImportanceLevel.MEDIUM,
                DiscoverySourceName.SEC: ImportanceLevel.MEDIUM,
            }
            importance = importance_map.get(source, ImportanceLevel.LOW)

            event_service = EventService(self.session)
            await event_service.create_from_discovery(
                company_id=company.id,
                event_type=event_type,
                title=f"New company discovered via {source.value.upper()}: {company.name}",
                source=source.value,
                source_url=data.external_url,
                source_id=f"{source.value}_{data.external_id}" if data.external_id else None,
                importance=importance,
                confidence_score=0.85,
                raw_data={"discovery_source": source.value, "external_id": data.external_id},
            )
        except Exception as exc:
            # L'event est non-critique — on ne fait pas planter le job pour ça
            self.logger.warning(
                "Failed to create discovery event",
                company_id=str(company.id),
                source=source.value,
                error=str(exc),
            )
