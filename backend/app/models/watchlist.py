"""
Atlas - Watchlist Model
=======================
Une entrée de watchlist marque une entreprise comme « suivie » par l'utilisateur.

Décisions de conception :
- Mono-utilisateur assumé (cohérent avec le reste de l'app : lectures publiques,
  pas de session active). Pas de user_id pour l'instant — le jour où l'auth
  multi-utilisateurs sera branchée, une migration ajoutera user_id et la
  contrainte d'unicité deviendra (user_id, company_id).
- Soft delete hérité d'AtlasBase : retirer une entreprise de la watchlist ne
  détruit pas l'historique (« depuis quand je suivais X » a de la valeur pour
  la future boucle de calibration).
- L'unicité porte sur company_id : une entreprise est suivie ou ne l'est pas.
  La réactivation d'une entrée soft-deleted est gérée par le service (restore)
  plutôt que par une nouvelle ligne, pour préserver la date de première mise
  en watchlist dans created_at.
- notes : champ libre optionnel — pourquoi je suis cette valeur. Affiché sur
  la page /watchlist, jamais obligatoire.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AtlasBase


class WatchlistItem(AtlasBase):
    """Entreprise suivie dans la watchlist."""

    __tablename__ = "watchlist_items"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relation vers Company (lecture seule côté watchlist)
    company = relationship("Company", lazy="joined")
