"""Bot-owned durable state. Successful turns are committed atomically."""

import asyncio
import fcntl
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

from src.domain import BotError, Message, Session


@dataclass(frozen=True)
class Scope:
    bot_id: int
    guild_id: int
    channel_id: int
    user_id: int
    private: bool = True

    @property
    def base(self) -> str:
        return f"{self.bot_id}:{self.guild_id}:{self.channel_id}:{self.user_id}"

    @property
    def key(self) -> str:
        return hashlib.sha256(f"{self.base}:{self.private}".encode()).hexdigest()


@dataclass
class Conversation:
    key: str
    model: str
    persona: str
    turns: list[Message]
    session: Session | None = None


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.db: aiosqlite.Connection
        self.lock = asyncio.Lock()
        self.lock_file: Any = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock_file = self.path.with_suffix(".lock").open("a")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock_file.close()
            raise BotError("Another bot process is already using this database.") from None
        try:
            self.db = await aiosqlite.connect(self.path, isolation_level=None)
            self.db.row_factory = aiosqlite.Row
            async with self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cursor:
                tables = {row[0] for row in await cursor.fetchall()}
            if tables:
                if "schema_version" not in tables:
                    raise BotError(
                        "Existing database has no supported bot schema; choose a new database path."
                    )
                async with self.db.execute("SELECT version FROM schema_version") as cursor:
                    versions = [row[0] for row in await cursor.fetchall()]
                if versions != [1]:
                    raise BotError(
                        "Unsupported conversation schema; back up data before migration."
                    )
            self.path.chmod(0o600)
            await self._initialize()
        except BaseException:
            if hasattr(self, "db"):
                await self.db.close()
            self.lock_file.close()
            raise

    async def _initialize(self) -> None:
        await self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            PRAGMA busy_timeout=5000;
            PRAGMA secure_delete=ON;
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL);
            INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM schema_version);
            CREATE TABLE IF NOT EXISTS conversations(
                key TEXT PRIMARY KEY, base TEXT NOT NULL, model TEXT NOT NULL,
                persona TEXT NOT NULL DEFAULT 'standard', turns TEXT NOT NULL DEFAULT '[]',
                session_id TEXT, fingerprint TEXT, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS conversation_expiry ON conversations(updated);
            CREATE TABLE IF NOT EXISTS preferences(base TEXT PRIMARY KEY, private INTEGER NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS channels(key TEXT PRIMARY KEY, enabled INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, scope TEXT NOT NULL, model TEXT NOT NULL,
                fingerprint TEXT NOT NULL, operation TEXT, state TEXT NOT NULL,
                created REAL NOT NULL, updated REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS job_expiry ON jobs(updated);
        """)
        await self.db.execute("UPDATE jobs SET state='unknown' WHERE state='submitting'")

    async def close(self) -> None:
        await self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await self.db.close()
        if self.lock_file:
            self.lock_file.close()

    async def reply_enabled(self, scope: Scope) -> bool:
        key = f"{scope.bot_id}:{scope.guild_id}:{scope.channel_id}"
        async with self.db.execute("SELECT enabled FROM channels WHERE key=?", (key,)) as cursor:
            row = await cursor.fetchone()
        return bool(row[0]) if row else True

    async def set_reply(self, scope: Scope, enabled: bool) -> None:
        key = f"{scope.bot_id}:{scope.guild_id}:{scope.channel_id}"
        await self.db.execute(
            "INSERT INTO channels VALUES(?,?) ON CONFLICT(key) DO UPDATE SET enabled=excluded.enabled",
            (key, enabled),
        )

    async def prune(self, retention_days: int) -> list[str]:
        cutoff = time.time() - retention_days * 86400
        async with self.lock:
            async with self.db.execute(
                "SELECT key FROM conversations WHERE updated < ?", (cutoff,)
            ) as cursor:
                expired = [row[0] for row in await cursor.fetchall()]
            for table in ("conversations", "preferences", "jobs"):
                await self.db.execute(f"DELETE FROM {table} WHERE updated < ?", (cutoff,))
        return expired

    async def private(self, scope: Scope) -> bool:
        async with self.db.execute(
            "SELECT private FROM preferences WHERE base=?", (scope.base,)
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row[0]) if row else True

    async def set_private(self, scope: Scope, private: bool) -> None:
        await self.db.execute(
            "INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(base) DO UPDATE SET private=excluded.private, updated=excluded.updated",
            (scope.base, private, time.time()),
        )

    async def get(
        self, scope: Scope, default_model: str, maximum: int, retention_days: int = 30
    ) -> Conversation:
        async with self.lock:
            async with self.db.execute(
                "SELECT * FROM conversations WHERE key=?", (scope.key,)
            ) as cursor:
                row = await cursor.fetchone()
            if row is not None and row["updated"] < time.time() - retention_days * 86400:
                await self.db.execute("DELETE FROM conversations WHERE key=?", (scope.key,))
                row = None
            if row is None:
                async with self.db.execute("SELECT count(*) FROM conversations") as cursor:
                    count = await cursor.fetchone()
                if count and count[0] >= maximum:
                    raise BotError("Conversation storage is full; contact the administrator.")
                await self.db.execute(
                    "INSERT INTO conversations(key,base,model,updated) VALUES(?,?,?,?)",
                    (scope.key, scope.base, default_model, time.time()),
                )
                return Conversation(scope.key, default_model, "standard", [])
            session = Session(row["session_id"], row["fingerprint"]) if row["session_id"] else None
            await self.db.execute(
                "UPDATE conversations SET updated=? WHERE key=?", (time.time(), scope.key)
            )
            return Conversation(
                scope.key,
                row["model"],
                row["persona"],
                [Message(**m) for m in json.loads(row["turns"])],
                session,
            )

    async def save(self, conversation: Conversation) -> None:
        session = conversation.session
        await self.db.execute(
            "UPDATE conversations SET model=?,persona=?,turns=?,session_id=?,fingerprint=?,updated=? WHERE key=?",
            (
                conversation.model,
                conversation.persona,
                json.dumps([m.__dict__ for m in conversation.turns]),
                session.id if session else None,
                session.fingerprint if session else None,
                time.time(),
                conversation.key,
            ),
        )

    async def invalidate_session(self, key: str) -> None:
        await self.db.execute(
            "UPDATE conversations SET session_id=NULL,fingerprint=NULL WHERE key=?", (key,)
        )

    async def delete(self, scope: Scope) -> None:
        async with self.lock:
            await self.db.execute("DELETE FROM conversations WHERE key=?", (scope.key,))
            await self.db.execute("DELETE FROM jobs WHERE scope=?", (scope.key,))

    async def create_job(
        self, job_id: str, scope: Scope, model: str, fingerprint: str, maximum: int = 1000
    ) -> bool:
        async with self.lock:
            async with self.db.execute("SELECT id FROM jobs WHERE id=?", (job_id,)) as cursor:
                if await cursor.fetchone():
                    return False
            async with self.db.execute("SELECT count(*) FROM jobs") as cursor:
                row = await cursor.fetchone()
            if row and row[0] >= maximum:
                raise BotError("Media job storage is full; contact the administrator.")
            await self.db.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,NULL,'submitting',?,?)",
                (job_id, scope.key, model, fingerprint, time.time(), time.time()),
            )
            return True

    async def conversation_keys(self) -> set[str]:
        async with self.db.execute("SELECT key FROM conversations") as cursor:
            return {row[0] for row in await cursor.fetchall()}

    async def job(self, job_id: str, scope: Scope) -> dict[str, Any]:
        async with self.db.execute(
            "SELECT * FROM jobs WHERE id=? AND scope=?", (job_id, scope.key)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise BotError("No media job with that ID belongs to this conversation.")
        return dict(row)

    async def update_job(self, job_id: str, state: str, operation: str | None = None) -> None:
        await self.db.execute(
            "UPDATE jobs SET state=?,operation=COALESCE(?,operation),updated=? WHERE id=?",
            (state, operation, time.time(), job_id),
        )
