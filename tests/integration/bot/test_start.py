"""Хендлер `/start` — раздел `docs/architecture.md`, 13 «Этап 0» и 11.3.

Раздел 11.3 называет `aiogram.test_utils.mocked_bot.MockedBot` как
инструмент. Установленная в проекте версия `aiogram` (3.31.0) этот модуль не
поставляет — пакета `aiogram.test_utils` в дистрибутиве нет вообще, что
расхождение с документом (см. «Вопросы диспетчеру» в разделе результата).
Тест использует второй способ, прямо разрешённый текстом задания:
`Dispatcher.feed_update` на настоящем апдейте против настоящего роутера
`start_router`, а сеть подменяется на уровне `BaseSession` — том месте,
где aiogram сам ожидает подмену транспорта для тестов, а не на уровне
хендлера или доменного объекта. Маршрутизация (`CommandStart`), сам хендлер
и `Dispatcher` — настоящие; подменена только HTTP-транспортная часть,
которой в тестовом окружении просто неоткуда взяться.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message, TelegramObject, Update, User

from finplan.entrypoints.bot.routers.start import router as start_router


class FakeSession(BaseSession):
    """`BaseSession`, которая ничего не отправляет в сеть.

    Перехватывает вызовы Bot API (здесь — только `SendMessage`) и строит
    правдоподобный ответ прямо из аргументов запроса, не обращаясь к
    `api.telegram.org`. Список отправленных методов доступен через
    `self.requests` — по нему тест проверяет, что хендлер действительно
    вызвал `message.answer(...)`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []

    async def close(self) -> None:
        return None

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None
    ) -> Any:
        self.requests.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=len(self.requests),
                date=datetime.now(tz=UTC),
                chat=Chat(id=method.chat_id, type="private"),  # type: ignore[arg-type]
                text=method.text,
            )
        raise NotImplementedError(f"FakeSession не умеет отвечать на {type(method).__name__}")

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> Any:
        yield b""


def _make_start_update(bot: Bot, chat_id: int = 100500) -> Update:
    """Апдейт с сообщением `/start` от приватного чата, привязанный к `bot`."""
    chat = Chat(id=chat_id, type="private")
    sender = User(id=chat_id, is_bot=False, first_name="Тестовый пользователь")
    message: TelegramObject = Message(
        message_id=1,
        date=datetime.now(tz=UTC),
        chat=chat,
        from_user=sender,
        text="/start",
    ).as_(bot)
    return Update(update_id=1, message=message)  # type: ignore[arg-type]


@pytest.fixture
def fake_bot() -> Bot:
    """`Bot` без обращений к сети — валидация токена в aiogram локальная."""
    return Bot(token="123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", session=FakeSession())


@pytest.fixture(scope="module")
def dispatcher() -> Dispatcher:
    """Модульный, а не функциональный scope: `start_router` — модульный
    объект-одиночка `finplan.entrypoints.bot.routers.start`, и повторный
    `include_router` того же объекта в другой `Dispatcher` — ошибка aiogram
    (`RuntimeError: Router is already attached to ...`). Тесты этого файла
    не мутируют состояние `Dispatcher`/`Router`, которое могло бы утечь
    между ними, поэтому общий диспетчер безопасен.
    """
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router)
    return dp


async def test_start_router_is_registered(dispatcher: Dispatcher) -> None:
    assert [router.name for router in dispatcher.sub_routers] == ["start"]


async def test_start_command_sends_non_empty_reply(dispatcher: Dispatcher, fake_bot: Bot) -> None:
    update = _make_start_update(fake_bot)

    await dispatcher.feed_update(fake_bot, update)

    session = fake_bot.session
    assert isinstance(session, FakeSession)
    sent_messages = [request for request in session.requests if isinstance(request, SendMessage)]
    assert len(sent_messages) == 1, "хендлер /start обязан отправить ровно один ответ"
    assert sent_messages[0].text.strip() != ""
    assert sent_messages[0].chat_id == 100500
