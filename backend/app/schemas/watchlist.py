"""
Atlas - Watchlist Schemas
=========================
Contrats d'entrée/sortie des endpoints watchlist.

WatchlistItemResponse embarque la CompanyListItem complète : la page
/watchlist affiche des cartes entreprise, autant réutiliser le schéma
existant plutôt que d'en inventer un presque identique.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.company import CompanyListItem


class WatchlistAdd(BaseModel):
    """Corps de POST /watchlist."""

    company_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=500)


class WatchlistItemResponse(BaseModel):
    """Une entrée de watchlist, avec l'entreprise embarquée."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    notes: str | None
    created_at: datetime
    company: CompanyListItem


class WatchlistIdsResponse(BaseModel):
    """
    Liste légère des company_id suivis.
    Sert aux boutons étoile : un seul fetch, mis en cache côté client,
    pour connaître l'état de toutes les étoiles de la page.
    """

    company_ids: list[uuid.UUID]
