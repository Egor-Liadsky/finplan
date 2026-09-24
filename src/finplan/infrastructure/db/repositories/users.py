"""`SqlAlchemyUserRepository`: доступ к пользователям.

`docs/architecture.md`, раздел 4.3, таблица `users`, и раздел 4.5: поиск по
`telegram_id` идёт только через функцию БД `find_user_by_telegram_id`,
потому что до её вызова `app.user_id` не установлен и обычный `SELECT` под
RLS не увидит ни одной строки.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from finplan.application.ports.repositories import DuplicateError, UserRepository
from finplan.domain.common.currency import Currency
from finplan.domain.entities.user import User
from finplan.infrastructure.db.models.currencies import Currency as CurrencyModel
from finplan.infrastructure.db.models.users import User as UserModel

# Код ошибки PostgreSQL `unique_violation` (раздел 12.3): используется вместо
# проверки конкретного класса исключения asyncpg, потому что SQLAlchemy сам
# копирует `sqlstate` в обёрнутое исключение при трансляции ошибок asyncpg.
_UNIQUE_VIOLATION = "23505"


class SqlAlchemyUserRepository:
    """Репозиторий пользователей поверх `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        stmt = (
            select(UserModel, CurrencyModel.minor_unit)
            .join(CurrencyModel, UserModel.base_currency == CurrencyModel.code)
            .where(UserModel.id == user_id)
        )
        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        model, minor_unit = row
        return _to_domain(model, minor_unit)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        # Раздел 4.5: функция `SECURITY DEFINER` — единственный способ найти
        # пользователя до того, как известен его `id` и выставлен
        # `app.user_id`. Прямой `SELECT ... WHERE telegram_id = ...` под RLS
        # без `app.user_id` не вернул бы ни одной строки.
        stmt = select(UserModel).from_statement(
            text("SELECT * FROM find_user_by_telegram_id(:telegram_id)")
        )
        result = await self._session.execute(stmt, {"telegram_id": telegram_id})
        model = result.scalar_one_or_none()
        if model is None:
            return None
        minor_unit = await self._minor_unit(model.base_currency)
        return _to_domain(model, minor_unit)

    async def add(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=None,
            photo_url=None,
            base_currency=user.base_currency.code,
            timezone=user.timezone,
            locale=user.locale,
            is_active=user.is_active,
            created_at=user.created_at,
            # Раздел 4.3: `updated_at` обязателен и без DEFAULT в БД, а
            # `User` его не хранит — при создании он совпадает с `created_at`.
            updated_at=user.created_at,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise DuplicateError(f"telegram_id {user.telegram_id} уже занят") from exc
            raise

    async def _minor_unit(self, currency_code: str) -> int:
        stmt = select(CurrencyModel.minor_unit).where(CurrencyModel.code == currency_code)
        return (await self._session.execute(stmt)).scalar_one()


def _to_domain(model: UserModel, minor_unit: int) -> User:
    return User(
        id=model.id,
        telegram_id=model.telegram_id,
        username=model.username,
        first_name=model.first_name,
        created_at=model.created_at,
        base_currency=Currency(code=model.base_currency, minor_unit=minor_unit),
        timezone=model.timezone,
        locale=model.locale,
        is_active=model.is_active,
    )


if TYPE_CHECKING:
    _check: type[UserRepository] = SqlAlchemyUserRepository
