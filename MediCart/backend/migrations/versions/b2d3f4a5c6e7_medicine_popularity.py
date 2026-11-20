"""medicine popularity for ranking equivalent brands

Revision ID: b2d3f4a5c6e7
Revises: a1c2e3f4b5d6
Create Date: 2026-11-20 10:40:00+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2d3f4a5c6e7"
down_revision: Union[str, None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("medicines") as batch:
        batch.add_column(sa.Column("popularity", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_medicines_popularity", "medicines", ["popularity"])
    # Products per manufacturer is the best distribution proxy the dataset offers.
    op.execute(
        """
        UPDATE medicines SET popularity = counts.n
        FROM (SELECT manufacturer, COUNT(*) AS n FROM medicines WHERE manufacturer IS NOT NULL GROUP BY manufacturer) AS counts
        WHERE medicines.manufacturer = counts.manufacturer
        """
        if op.get_bind().dialect.name == "postgresql"
        else """
        UPDATE medicines SET popularity = (
            SELECT COUNT(*) FROM medicines AS m2 WHERE m2.manufacturer = medicines.manufacturer
        ) WHERE manufacturer IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_medicines_popularity", table_name="medicines")
    with op.batch_alter_table("medicines") as batch:
        batch.drop_column("popularity")
