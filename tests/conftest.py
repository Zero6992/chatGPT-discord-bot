import asyncio
import os
import socket
from pathlib import Path

import pytest

from src.config import Backend, Model, Settings
from src.domain import Capability, Completion
from src.service import ConversationService
from src.storage import Store


@pytest.fixture
def assert_process_stopped():
    if not Path("/proc/self/stat").is_file():
        pytest.skip("Process-tree cleanup checks require Linux /proc")

    async def check(pid: int, timeout: float = 1) -> None:
        # SIGKILL delivery and parent wait() do not synchronously reap descendants.
        # Require the actual child to stop within a deadline, including under CI load.
        deadline = asyncio.get_running_loop().time() + timeout
        status = Path(f"/proc/{pid}/stat")
        while True:
            try:
                state = status.read_text().rsplit(")", 1)[1].split()[0]
            except FileNotFoundError:
                return
            if state == "Z":
                return
            assert asyncio.get_running_loop().time() < deadline, "Child process is still running"
            await asyncio.sleep(0.01)

    return check


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
