"""
Atlas - Watchlist Service
=========================
Logique métier de la watchlist.

Règles :
- add() est idempotent : ajouter une entreprise déjà suivie renvoie l'entrée
  existante (200, pas d'erreur) — le bouton étoile peut être cliqué deux fois
  sans conséquence.
- remove() est un soft delete ; re-add() restaure l'entrée existante et
  préserve created_at (« suivie depuis » reste la première date).
- L'entreprise doit exister et ne pas être soft-deleted.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.watchlist import WatchlistItem
from app.repositories.company import CompanyRepository
from app.repositories.watchlist import WatchlistRepository
from app.schemas.watchlist import WatchlistItemResponse

logger = get_logger(__name__)


class WatchlistService:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WatchlistRepository(session)
        self.company_repo = CompanyRepository(session)

    # ─── Lecture ──────────────────────────────────────────────────────────────

    async def list_items(self) -> list[WatchlistItemResponse]:
        items = await self.repo.list_active()
        return [WatchlistItemResponse.model_validate(i) for i in items]

    async def list_company_ids(self) -> list[uuid.UUID]:
        items = await self.repo.list_active()
        return [i.company_id for i in items]

    # ─── Écriture ─────────────────────────────────────────────────────────────

    async def add(self, company_id: uuid.UUID, notes: str | None = None) -> WatchlistItemResponse:
        company = await self.company_repo.get_by_id(company_id)
        if not company:
            raise NotFoundError("Company", company_id)

        existing = await self.repo.get_by_company_id_any(company_id)
        if existing:
            if existing.is_deleted:
                existing.restore()
                if notes is not None:
                    existing.notes = notes
                await self.session.commit()
                await self.session.refresh(existing)
                logger.info("Watchlist item restored", company_id=str(company_id))
            # déjà actif → idempotent, on renvoie l'existant
            return WatchlistItemResponse.model_validate(existing)

        item = WatchlistItem(company_id=company_id, notes=notes)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        logger.info("Watchlist item added", company_id=str(company_id))
        return WatchlistItemResponse.model_validate(item)

    async def remove(self, company_id: uuid.UUID) -> None:
        item = await self.repo.get_by_company_id(company_id)
        if not item:
            raise NotFoundError("WatchlistItem", company_id)
        item.soft_delete()
        await self.session.commit()
        logger.info("Watchlist item removed", company_id=str(company_id))
