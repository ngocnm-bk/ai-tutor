import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from ai_tutor.tutor.bot import echo_handler


def test_echo_handler_replies_with_prefix():
    sent = AsyncMock()
    update = SimpleNamespace(message=SimpleNamespace(text="2+2?", reply_text=sent))
    asyncio.run(echo_handler(update, context=SimpleNamespace()))
    sent.assert_awaited_once_with("Bot: 2+2?")
