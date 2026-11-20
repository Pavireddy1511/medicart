"""catalogue search columns and trigram indexes

Revision ID: a1c2e3f4b5d6
Revises: 7fc4c3fc9427
Create Date: 2026-11-20 10:00:00+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, None] = "7fc4c3fc9427"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRIGRAM_INDEXES = {
    "ix_medicines_search_name_trgm": "search_name",
    "ix_medicines_composition_key_trgm": "composition_key",
    "ix_medicines_medicine_name_trgm": "medicine_name",
    "ix_medicines_brand_name_trgm": "brand_name",
    "ix_medicines_generic_name_trgm": "generic_name",
}


def upgrade() -> None:
    with op.batch_alter_table("medicines") as batch:
        batch.add_column(sa.Column("search_name", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("composition", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("composition_key", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("therapeutic_class", sa.String(length=80), nullable=True))
    op.create_index("ix_medicines_search_name", "medicines", ["search_name"])
    op.create_index("ix_medicines_composition_key", "medicines", ["composition_key"])

    # Backfill the normalised name for rows that already exist.
    from app.utils.text import normalise_name

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, medicine_name, generic_name FROM medicines")).all()
    for row_id, name, generic in rows:
        bind.execute(
            sa.text("UPDATE medicines SET search_name = :s, composition_key = :c WHERE id = :id"),
            {
                "s": normalise_name(name)[:150],
                "c": "|".join(normalise_name(p) for p in (generic or "").split("+") if p.strip())[:300]
                or None,
                "id": row_id,
            },
        )

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for index_name, column in TRIGRAM_INDEXES.items():
            op.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON medicines USING gin ({column} gin_trgm_ops)"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for index_name in TRIGRAM_INDEXES:
            op.execute(f"DROP INDEX IF EXISTS {index_name}")
    op.drop_index("ix_medicines_composition_key", table_name="medicines")
    op.drop_index("ix_medicines_search_name", table_name="medicines")
    with op.batch_alter_table("medicines") as batch:
        batch.drop_column("therapeutic_class")
        batch.drop_column("composition_key")
        batch.drop_column("composition")
        batch.drop_column("search_name")
