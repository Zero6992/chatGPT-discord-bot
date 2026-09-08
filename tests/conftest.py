import os
import socket

import pytest

from src.config import Backend, Model, Settings
from src.domain import Capability, Completion
from src.service import ConversationService
from src.storage import Store


@pytest.fixture(autouse=True)
def offline(monkeypatch, request):
    if request.node.get_closest_marker("live"):
        return
    for key in list(os.environ):
        if key.endswith(("_KEY", "_TOKEN", "_COOKIE", "_PSID")) or key.startswith(
            ("G4F_", "DEFAULT_")
        ):
            monkeypatch.delenv(key, raising=False)

    def blocked(*args, **kwargs):
        raise AssertionError("Default tests may not access external services")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def model():
    return Model(
        "local",
        Backend("local", "compatible", "http://127.0.0.1:11434/v1", auth="none"),
        "fixture-model",
        frozenset({Capability.CHAT}),
        {"max_output_tokens": 512},
    )


@pytest.fixture
def settings(tmp_path, model):
    return Settings(
        {model.name: model}, model.name, database=tmp_path / "state.sqlite3", poll_interval=0.01
    )


class RecordingProvider:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.session = None

    async def complete(self, messages, session=None, *, conversation_id=""):
        self.calls.append((list(messages), session, conversation_id))
        if self.fail:
            raise RuntimeError("secret diagnostic")
        return Completion("reply to " + messages[-1].content, self.session)

    async def close(self):
        pass


@pytest.fixture
async def service(settings):
    store = Store(settings.database)
    await store.open()
    provider = RecordingProvider()
    value = ConversationService(settings, store, {"local": provider})
    yield value
    await value.close()
    await store.close()
