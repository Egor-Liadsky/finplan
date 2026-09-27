"""ORM-модели SQLAlchemy 2.x, по файлу на таблицу.

Импорт модуля собирает все модели в общую `Base.metadata`
(`finplan.infrastructure.db.base.Base`) — нужен для `target_metadata` в
`migrations/env.py` и для `alembic check`.
"""

from __future__ import annotations

from finplan.infrastructure.db.models.accounts import Account
from finplan.infrastructure.db.models.categories import Category
from finplan.infrastructure.db.models.currencies import Currency
from finplan.infrastructure.db.models.transactions import Transaction
from finplan.infrastructure.db.models.users import User

__all__ = ["Account", "Category", "Currency", "Transaction", "User"]
