"""
Audit Logger — Immutable Log Writer
=====================================
Ghi log bat bien cho moi lenh dieu khien hardware.

Dac diem:
- SQLite WAL mode (write-ahead log — concurrent reads)
- Trigger ABORT khi UPDATE hoac DELETE (bat bien)
- Checksum SHA-256 cho moi record (chong tampering)
- Async non-blocking writes
- Tự dong tao DB va table khi khoi dong

Schema:
  audit_log(
    id, request_id, user_id, ip_address, session_id,
    entity_id, action, params, decision, deny_reason,
    safety_level, ha_result, ha_response_ms,
    timestamp, checksum
  )
"""

from __future__ import annotations

import json
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path

import aiosqlite

from src.config import get_settings

logger = logging.getLogger(__name__)

# ── Data Model ─────────────────────────────────────────────

@dataclass
class AuditRecord:
    """Mot dong trong audit log."""
    request_id: str
    user_id: str
    ip_address: str
    session_id: str
    entity_id: str
    action: str
    params: str          # JSON string
    decision: str        # APPROVED | DENIED | RATE_LIMITED
    deny_reason: str | None
    safety_level: str
    ha_result: str | None       # SUCCESS | FAILED | TIMEOUT | None
    ha_response_ms: int | None
    timestamp: str       # ISO format UTC
    checksum: str = ""   # SHA-256 (se tinh sau)

    def compute_checksum(self) -> str:
        """Tinh SHA-256 checksum cua record (tru field checksum)."""
        data = (
            f"{self.request_id}|{self.user_id}|{self.entity_id}|"
            f"{self.action}|{self.params}|{self.decision}|"
            f"{self.deny_reason}|{self.timestamp}"
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ── SQL Statements ─────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    ip_address      TEXT DEFAULT '',
    session_id      TEXT DEFAULT '',
    entity_id       TEXT NOT NULL,
    action          TEXT NOT NULL,
    params          TEXT DEFAULT '{}',
    decision        TEXT NOT NULL,
    deny_reason     TEXT,
    safety_level    TEXT DEFAULT '',
    ha_result       TEXT,
    ha_response_ms  INTEGER,
    timestamp       TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision);
"""

# Trigger chong UPDATE (bat bien)
PREVENT_UPDATE_SQL = """
CREATE TRIGGER IF NOT EXISTS prevent_audit_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log is immutable — UPDATE not allowed');
END;
"""

# Trigger chong DELETE (bat bien)
PREVENT_DELETE_SQL = """
CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log is immutable — DELETE not allowed');
END;
"""

INSERT_SQL = """
INSERT INTO audit_log (
    request_id, user_id, ip_address, session_id,
    entity_id, action, params, decision, deny_reason,
    safety_level, ha_result, ha_response_ms,
    timestamp, checksum
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


# ── Audit Logger Class ────────────────────────────────────

class AuditLogger:
    """
    Async audit logger voi SQLite WAL mode.
    Singleton pattern — chi co 1 instance.
    """

    _instance: AuditLogger | None = None
    _initialized: bool = False

    def __new__(cls) -> AuditLogger:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def init(self) -> None:
        """Khoi tao DB, tao table va triggers."""
        if self._initialized:
            return

        settings = get_settings()
        db_path = Path(settings.sqlite_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._db_path = str(db_path)

        async with aiosqlite.connect(self._db_path) as db:
            # Bat WAL mode
            await db.execute("PRAGMA journal_mode=WAL;")
            # Tao table
            await db.execute(CREATE_TABLE_SQL)
            # Tao indexes
            await db.executescript(CREATE_INDEX_SQL)
            # Tao immutable triggers
            await db.execute(PREVENT_UPDATE_SQL)
            await db.execute(PREVENT_DELETE_SQL)
            await db.commit()

        self._initialized = True
        logger.info("[AUDIT] Database initialized at %s", self._db_path)

    async def log(self, record: AuditRecord) -> None:
        """
        Ghi 1 audit record vao DB.
        Non-blocking async.
        """
        if not self._initialized:
            await self.init()

        # Tinh checksum
        record.checksum = record.compute_checksum()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(INSERT_SQL, (
                    record.request_id,
                    record.user_id,
                    record.ip_address,
                    record.session_id,
                    record.entity_id,
                    record.action,
                    record.params,
                    record.decision,
                    record.deny_reason,
                    record.safety_level,
                    record.ha_result,
                    record.ha_response_ms,
                    record.timestamp,
                    record.checksum,
                ))
                await db.commit()

            logger.info(
                "[AUDIT] Logged: req=%s entity=%s action=%s decision=%s",
                record.request_id[:8],
                record.entity_id,
                record.action,
                record.decision,
            )
        except Exception as e:
            # Audit log KHONG duoc lam crash he thong
            logger.error("[AUDIT] Failed to write log: %s", e)

    async def query(
        self,
        user_id: str | None = None,
        entity_id: str | None = None,
        decision: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query audit log voi filters."""
        if not self._initialized:
            await self.init()

        conditions = []
        params = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if entity_id:
            conditions.append("entity_id = ?")
            params.append(entity_id)
        if decision:
            conditions.append("decision = ?")
            params.append(decision)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM audit_log {where_clause} ORDER BY id DESC LIMIT ?"
        params.append(limit)

        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error("[AUDIT] Query failed: %s", e)
            return []

    async def verify_integrity(self, request_id: str) -> bool:
        """Kiem tra checksum cua 1 record de phat hien tampering."""
        if not self._initialized:
            await self.init()

        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM audit_log WHERE request_id = ?",
                    (request_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return False

                    record = AuditRecord(
                        request_id=row["request_id"],
                        user_id=row["user_id"],
                        ip_address=row["ip_address"],
                        session_id=row["session_id"],
                        entity_id=row["entity_id"],
                        action=row["action"],
                        params=row["params"],
                        decision=row["decision"],
                        deny_reason=row["deny_reason"],
                        safety_level=row["safety_level"],
                        ha_result=row["ha_result"],
                        ha_response_ms=row["ha_response_ms"],
                        timestamp=row["timestamp"],
                    )
                    expected = record.compute_checksum()
                    actual = row["checksum"]

                    if expected != actual:
                        logger.error(
                            "[AUDIT] INTEGRITY VIOLATION: req=%s expected=%s actual=%s",
                            request_id[:8], expected[:16], actual[:16],
                        )
                        return False
                    return True
        except Exception as e:
            logger.error("[AUDIT] Integrity check failed: %s", e)
            return False


# ── Singleton accessor ────────────────────────────────────

def get_audit_logger() -> AuditLogger:
    """Tra ve singleton AuditLogger instance."""
    return AuditLogger()
