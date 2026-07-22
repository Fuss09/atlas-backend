"""Module 11 — Fix users.auth_provider enum type

La colonne auth_provider a été créée dans 001_initial avec le mauvais type
Postgres (user_role_enum au lieu de auth_provider_enum) — copié-collé de la
colonne role juste en dessous. Le type auth_provider_enum existe en base
depuis 001 mais n'était utilisé par aucune colonne. Bloquait tout INSERT
dans users (register, create_user) via un DatatypeMismatchError.

Revision ID: 011_fix_auth_provider_enum
Revises: 010_catalysts
Create Date: 2026-07-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "011_fix_auth_provider_enum"
down_revision: str | None = "010_catalysts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN auth_provider TYPE auth_provider_enum "
        "USING auth_provider::text::auth_provider_enum"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN auth_provider TYPE user_role_enum "
        "USING auth_provider::text::user_role_enum"
    )
