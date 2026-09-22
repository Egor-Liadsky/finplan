"""create currencies and users

Revision ID: fc2037cdf9d2
Revises:
Create Date: 2026-09-21 17:30:19.447253

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc2037cdf9d2"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Список — допущение, docs/architecture.md раздел 4.3, подраздел currencies:
# уточняется владельцем продукта. minor_unit=2 для всех перечисленных валют.
# Символ указан только там, где он общепринят и однозначен.
_CURRENCIES: list[dict[str, object]] = [
    {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "minor_unit": 2},
    {"code": "USD", "name": "Доллар США", "symbol": "$", "minor_unit": 2},
    {"code": "EUR", "name": "Евро", "symbol": "€", "minor_unit": 2},
    {"code": "CNY", "name": "Китайский юань", "symbol": "¥", "minor_unit": 2},
    {"code": "KZT", "name": "Казахстанский тенге", "symbol": "₸", "minor_unit": 2},
    {"code": "GEL", "name": "Грузинский лари", "symbol": "₾", "minor_unit": 2},
    {"code": "TRY", "name": "Турецкая лира", "symbol": "₺", "minor_unit": 2},
    {"code": "AED", "name": "Дирхам ОАЭ", "symbol": None, "minor_unit": 2},
    {"code": "RSD", "name": "Сербский динар", "symbol": None, "minor_unit": 2},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "currencies",
        sa.Column("code", sa.CHAR(3), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("minor_unit", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        # Имя — короткий токен, а не готовое "ck_currencies_...": naming_convention
        # из target_metadata (см. migrations/env.py) уже добавляет префикс
        # "ck_%(table_name)s_" сама, полное имя удвоилось бы.
        sa.CheckConstraint("minor_unit BETWEEN 0 AND 4", name="minor_unit_range"),
        sa.PrimaryKeyConstraint("code", name="pk_currencies"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("base_currency", sa.CHAR(3), server_default="RUB", nullable=False),
        sa.Column("timezone", sa.Text(), server_default="Europe/Moscow", nullable=False),
        sa.Column("locale", sa.Text(), server_default="ru", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["base_currency"], ["currencies.code"], name="fk_users_base_currency"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )

    currencies_table = sa.table(
        "currencies",
        sa.column("code", sa.CHAR(3)),
        sa.column("name", sa.Text()),
        sa.column("symbol", sa.Text()),
        sa.column("minor_unit", sa.SmallInteger()),
    )
    op.bulk_insert(currencies_table, _CURRENCIES)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users")
    op.drop_table("currencies")
