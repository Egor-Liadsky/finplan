"""create accounts, categories and transactions

Revision ID: 2058c667ebfe
Revises: fc2037cdf9d2
Create Date: 2026-09-24 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2058c667ebfe"
down_revision: str | Sequence[str] | None = "fc2037cdf9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# docs/architecture.md, раздел 4.3, подраздел transactions: имя функции не
# задано документом, только имя триггера trg_transactions_immutable.
_IMMUTABLE_FUNCTION = "fn_transactions_guard_immutable"
_IMMUTABLE_TRIGGER = "trg_transactions_immutable"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("opening_balance", sa.Numeric(20, 4), server_default="0", nullable=False),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("is_valuated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("include_in_networth", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),
        sa.CheckConstraint(
            "type IN ('cash', 'bank_account', 'card', 'broker', 'real_estate', "
            "'deposit', 'other_asset', 'liability')",
            name="type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_accounts_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["currency"], ["currencies.code"], name="fk_accounts_currency"),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    # Частичный уникальный индекс: WHERE-условие недоступно UniqueConstraint,
    # только Index(unique=True, postgresql_where=...).
    op.create_index(
        "uq_accounts_user_id_name",
        "accounts",
        ["user_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("NOT is_archived"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "aliases",
            sa.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.CheckConstraint("id <> parent_id", name="no_self_parent"),
        sa.CheckConstraint("kind IN ('income', 'expense')", name="kind_allowed"),
        sa.CheckConstraint("depth BETWEEN 0 AND 2", name="depth_range"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_categories_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("user_id", "path", name="uq_categories_user_id_path"),
    )
    op.create_index("ix_categories_user_id_kind", "categories", ["user_id", "kind"])
    op.create_index(
        "ix_categories_user_id_path",
        "categories",
        ["user_id", "path"],
        postgresql_ops={"path": "text_pattern_ops"},
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("counter_account_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("base_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("base_currency", sa.CHAR(3), nullable=False),
        sa.Column("base_rate", sa.Numeric(18, 10), nullable=False),
        sa.Column("transfer_group_id", sa.Uuid(), nullable=True),
        # deposit_id, goal_id, recurring_rule_id: без FK, таблицы-цели
        # (deposits, savings_goals, recurring_rules) не входят в эту
        # подзадачу — см. docstring finplan.infrastructure.db.models.transactions.
        sa.Column("deposit_id", sa.Uuid(), nullable=True),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("recurring_rule_id", sa.Uuid(), nullable=True),
        sa.Column("reverses_id", sa.Uuid(), nullable=True),
        sa.Column("external_key", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('income', 'expense', 'transfer', 'adjustment', 'interest')",
            name="kind_allowed",
        ),
        sa.CheckConstraint("status IN ('posted', 'reversed', 'pending')", name="status_allowed"),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.CheckConstraint("comment IS NULL OR length(comment) <= 500", name="comment_length"),
        sa.CheckConstraint("base_rate > 0", name="base_rate_positive"),
        sa.CheckConstraint(
            "source IN ('bot', 'web', 'recurring', 'system', 'import')", name="source_allowed"
        ),
        sa.CheckConstraint(
            "(kind = 'transfer' AND counter_account_id IS NOT NULL "
            "AND counter_account_id <> account_id AND category_id IS NULL) "
            "OR (kind <> 'transfer' AND counter_account_id IS NULL)",
            name="transfer_shape",
        ),
        sa.CheckConstraint(
            "(kind IN ('income', 'expense') AND category_id IS NOT NULL) "
            "OR kind NOT IN ('income', 'expense')",
            name="category_required",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_transactions_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["currency"], ["currencies.code"], name="fk_transactions_currency"),
        sa.ForeignKeyConstraint(
            ["base_currency"], ["currencies.code"], name="fk_transactions_base_currency"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name="fk_transactions_account_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["counter_account_id"],
            ["accounts.id"],
            name="fk_transactions_counter_account_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transactions_category_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_id"], ["transactions.id"], name="fk_transactions_reverses_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
        sa.UniqueConstraint("user_id", "external_key", name="uq_transactions_user_id_external_key"),
        sa.UniqueConstraint("reverses_id", name="uq_transactions_reverses_id"),
    )
    op.create_index(
        "ix_transactions_user_id_occurred_at",
        "transactions",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_transactions_user_id_occurred_on_kind",
        "transactions",
        ["user_id", "occurred_on", "kind"],
    )
    op.create_index(
        "ix_transactions_account_id_occurred_at", "transactions", ["account_id", "occurred_at"]
    )
    op.create_index(
        "ix_transactions_category_id_occurred_on",
        "transactions",
        ["category_id", "occurred_on"],
        postgresql_where=sa.text("status = 'posted'"),
    )
    op.create_index(
        "ix_transactions_deposit_id_occurred_at",
        "transactions",
        ["deposit_id", "occurred_at"],
        postgresql_where=sa.text("deposit_id IS NOT NULL"),
    )
    op.create_index(
        "ix_transactions_goal_id",
        "transactions",
        ["goal_id"],
        postgresql_where=sa.text("goal_id IS NOT NULL"),
    )
    op.create_index(
        "ix_transactions_pending",
        "transactions",
        ["user_id", "occurred_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Иммутабельность журнала (раздел 4.2, 4.3): триггер на уровне БД —
    # страховка от ошибки в коде приложения, а не замена доменных проверок.
    # Разрешён только переход status posted -> reversed при UPDATE, все
    # прочие столбцы неизменны; DELETE запрещён всегда.
    op.execute(
        f"""
        CREATE FUNCTION {_IMMUTABLE_FUNCTION}() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION
                    'transactions is an append-only log: DELETE is not allowed (id=%)',
                    OLD.id;
            END IF;

            IF OLD.status <> 'posted' OR NEW.status <> 'reversed' THEN
                RAISE EXCEPTION
                    'transactions is an append-only log: only posted -> reversed is allowed (id=%)',
                    OLD.id;
            END IF;

            IF (NEW.id, NEW.user_id, NEW.kind, NEW.amount, NEW.currency, NEW.account_id,
                NEW.counter_account_id, NEW.category_id, NEW.occurred_at, NEW.occurred_on,
                NEW.comment, NEW.base_amount, NEW.base_currency, NEW.base_rate,
                NEW.transfer_group_id, NEW.deposit_id, NEW.goal_id, NEW.recurring_rule_id,
                NEW.reverses_id, NEW.external_key, NEW.source, NEW.created_at)
               IS DISTINCT FROM
               (OLD.id, OLD.user_id, OLD.kind, OLD.amount, OLD.currency, OLD.account_id,
                OLD.counter_account_id, OLD.category_id, OLD.occurred_at, OLD.occurred_on,
                OLD.comment, OLD.base_amount, OLD.base_currency, OLD.base_rate,
                OLD.transfer_group_id, OLD.deposit_id, OLD.goal_id, OLD.recurring_rule_id,
                OLD.reverses_id, OLD.external_key, OLD.source, OLD.created_at)
            THEN
                RAISE EXCEPTION
                    'transactions is an append-only log: only status may change (id=%)', OLD.id;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_IMMUTABLE_TRIGGER}
        BEFORE UPDATE OR DELETE ON transactions
        FOR EACH ROW EXECUTE FUNCTION {_IMMUTABLE_FUNCTION}();
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DROP TRIGGER IF EXISTS {_IMMUTABLE_TRIGGER} ON transactions")
    op.execute(f"DROP FUNCTION IF EXISTS {_IMMUTABLE_FUNCTION}()")
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("accounts")
