import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from src.domains.execution_result import ExecutionResult
from src.domains.platform import Platform
from src.models.account import Account
from src.services.credential_cipher import CredentialCipher
from src.services.csv_account_parser import ParsedAccount


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BatchRecord:
    id: str
    name: str
    platform: str
    filename: str
    account_count: int
    created_at: str


@dataclass(frozen=True)
class JobRecord:
    id: str
    batch_id: str
    batch_name: str
    platform: str
    action: str
    target_url: str
    params: dict
    status: str
    total: int
    completed: int
    succeeded: int
    failed: int
    error: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


class JobStore:
    def __init__(self, database_path: str, cipher: CredentialCipher) -> None:
        self.database_path = database_path
        self.cipher = cipher
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_batches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    account_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL REFERENCES account_batches(id) ON DELETE CASCADE,
                    username TEXT NOT NULL,
                    password_ciphertext TEXT NOT NULL,
                    UNIQUE(batch_id, username)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES account_batches(id),
                    platform TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total INTEGER NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    succeeded INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_status_created_idx ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS job_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    username TEXT NOT NULL,
                    code TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error = failed || ' of ' || total || ' account tasks failed'
                WHERE status = 'completed' AND failed > 0
                """
            )
            connection.commit()

    def create_batch(
        self,
        platform: Platform,
        name: str,
        filename: str,
        accounts: list[ParsedAccount],
    ) -> BatchRecord:
        batch = BatchRecord(
            id=uuid.uuid4().hex,
            name=name.strip()[:80],
            platform=platform.value,
            filename=filename[:255],
            account_count=len(accounts),
            created_at=utc_now(),
        )
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO account_batches VALUES (?, ?, ?, ?, ?, ?)",
                tuple(asdict(batch).values()),
            )
            connection.executemany(
                "INSERT INTO accounts(batch_id, username, password_ciphertext) VALUES (?, ?, ?)",
                [
                    (batch.id, account.username, self.cipher.encrypt(account.password))
                    for account in accounts
                ],
            )
            connection.commit()
        return batch

    def list_batches(self, platform: Platform | None = None) -> list[BatchRecord]:
        query = "SELECT * FROM account_batches"
        params = ()
        if platform:
            query += " WHERE platform = ?"
            params = (platform.value,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            return [BatchRecord(**dict(row)) for row in connection.execute(query, params)]

    def get_batch(self, batch_id: str) -> BatchRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM account_batches WHERE id = ?", (batch_id,)
            ).fetchone()
        return BatchRecord(**dict(row)) if row else None

    def delete_batch(self, batch_id: str) -> bool:
        with self._connect() as connection:
            has_jobs = connection.execute(
                "SELECT 1 FROM jobs WHERE batch_id = ? LIMIT 1", (batch_id,)
            ).fetchone()
            if has_jobs:
                raise ValueError("A batch with job history cannot be deleted")
            cursor = connection.execute("DELETE FROM account_batches WHERE id = ?", (batch_id,))
            connection.commit()
            return cursor.rowcount > 0

    def load_accounts(self, batch_id: str) -> list[Account]:
        batch = self.get_batch(batch_id)
        if batch is None:
            raise LookupError("Account batch no longer exists")
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT username, password_ciphertext FROM accounts WHERE batch_id = ? ORDER BY id",
                (batch_id,),
            ).fetchall()
        return [
            Account(
                username=row["username"],
                password=self.cipher.decrypt(row["password_ciphertext"]),
                platform=batch.platform,
            )
            for row in rows
        ]

    def create_job(self, batch: BatchRecord, action: str, target_url: str, params: dict) -> JobRecord:
        job_id = uuid.uuid4().hex
        created_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    id, batch_id, platform, action, target_url, params_json,
                    status, total, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    job_id,
                    batch.id,
                    batch.platform,
                    action,
                    target_url,
                    json.dumps(params),
                    batch.account_count,
                    created_at,
                ),
            )
            connection.commit()
        return self.get_job(job_id)

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                self._job_query() + " ORDER BY j.created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                self._job_query() + " WHERE j.id = ?", (job_id,)
            ).fetchone()
        return self._job_from_row(row) if row else None

    def claim_next_job(self) -> JobRecord | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?",
                (utc_now(), row["id"]),
            )
            connection.commit()
        return self.get_job(row["id"])

    def record_result(self, job_id: str, result: ExecutionResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_results(job_id, username, code, attempts, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    result.task.account.username,
                    result.code.value,
                    result.attempts,
                    (result.error or "")[:2000] or None,
                    utc_now(),
                ),
            )
            connection.execute(
                """
                UPDATE jobs SET completed = completed + 1,
                    succeeded = succeeded + ?, failed = failed + ?
                WHERE id = ?
                """,
                (int(result.success), int(not result.success), job_id),
            )
            connection.commit()

    def complete_job(self, job_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = CASE WHEN failed > 0 THEN 'failed' ELSE 'completed' END,
                    error = CASE
                        WHEN failed > 0 THEN failed || ' of ' || total || ' account tasks failed'
                        ELSE NULL
                    END,
                    completed_at = ?
                WHERE id = ?
                """,
                (utc_now(), job_id),
            )
            connection.commit()

    def fail_job(self, job_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
                (error[:2000], utc_now(), job_id),
            )
            connection.commit()

    def fail_interrupted_jobs(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs SET status = 'failed', completed_at = ?,
                    error = 'Interrupted by service restart; not retried automatically'
                WHERE status = 'running'
                """,
                (utc_now(),),
            )
            connection.commit()

    def list_results(self, job_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT username, code, attempts, error, created_at
                FROM job_results WHERE job_id = ? ORDER BY id
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict:
        with self._connect() as connection:
            batches = connection.execute("SELECT COUNT(*) FROM account_batches").fetchone()[0]
            accounts = connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            job_rows = connection.execute(
                "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
            ).fetchall()
        jobs = {row["status"]: row["count"] for row in job_rows}
        return {
            "batches": batches,
            "accounts": accounts,
            "queued": jobs.get("queued", 0),
            "running": jobs.get("running", 0),
            "completed": jobs.get("completed", 0),
            "failed": jobs.get("failed", 0),
        }

    @staticmethod
    def _job_query() -> str:
        return """
            SELECT j.*, b.name AS batch_name
            FROM jobs j JOIN account_batches b ON b.id = j.batch_id
        """

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> JobRecord:
        data = dict(row)
        data["params"] = json.loads(data.pop("params_json"))
        return JobRecord(**data)
