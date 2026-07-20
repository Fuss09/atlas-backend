"""
Atlas - Watchlist Repository
============================
Accès aux données pour la watchlist.

Particularité : la réactivation. Retirer une entreprise de la watchlist est un
soft delete ; la remettre restaure l'entrée existante (préserve created_at =
« suivie depuis »). Le repository expose donc get_by_company_id_any() qui voit
aussi les soft-deleted, réservé à ce cas d'usage.
"""

import uuid

from sqlalchemy import select

from app.models.watchlist import WatchlistItem
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[WatchlistItem]):

    model = WatchlistItem

    async def get_by_company_id(self, company_id: uuid.UUID) -> WatchlistItem | None:
        """Entrée active pour cette entreprise, None sinon."""
        result = await self.session.execute(
            select(WatchlistItem).where(
                WatchlistItem.company_id == company_id,
                WatchlistItem.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_company_id_any(self, company_id: uuid.UUID) -> WatchlistItem | None:
        """
        Entrée pour cette entreprise, y compris soft-deleted.
        Utilisé uniquement pour la réactivation (add après remove).
        """
        result = await self.session.execute(
            select(WatchlistItem).where(WatchlistItem.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[WatchlistItem]:
        """
        Toutes les entrées actives, plus récentes d'abord.
        La relation company est chargée en jointure (lazy="joined" sur le
        modèle) — une seule requête, pas de N+1.
        """
        result = await self.session.execute(
            select(WatchlistItem)
            .where(WatchlistItem.is_deleted == False)  # noqa: E712
            .order_by(WatchlistItem.created_at.desc())
        )
        return list(result.scalars().all())
