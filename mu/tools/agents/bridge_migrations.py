"""Ordered schema migrations for the bridge SQLite database.

Each migration is a function that receives a sqlite3.Connection and applies
one schema change.  Migrations are idempotent where practical (ADD COLUMN
is a no-op if the column already exists in SQLite).

The current schema version is tracked in a single-row ``schema_version``
table.  On startup, ``run_pending_migrations()`` compares the stored version
to ``len(MIGRATIONS)`` and runs any that haven't been applied yet.

Concurrency safety: the runner acquires an EXCLUSIVE transaction lock before
checking/applying migrations, so concurrent callers serialize correctly.
"""

from __future__ import annotations

import sqlite3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if *column* already exists on *table*."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Return True if *table* exists in the database."""
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row[0] > 0


def add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, col_type: str,
) -> None:
    if not column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


# ---------------------------------------------------------------------------
# Individual migrations — append-only list; NEVER reorder or delete.
# ---------------------------------------------------------------------------

def _migrate_v1_add_attempt_and_canonical(conn: sqlite3.Connection) -> None:
    """Add canonical-attempt tracking columns to turns."""
    add_column_if_missing(conn, "turns", "attempt_no", "INTEGER NOT NULL DEFAULT 1")
    add_column_if_missing(conn, "turns", "is_canonical", "INTEGER NOT NULL DEFAULT 1")


def _migrate_v2_add_reviewer_baseline(conn: sqlite3.Connection) -> None:
    """Add incremental re-review baseline columns to turns."""
    add_column_if_missing(
        conn, "turns", "reviewer_input_ref", "TEXT",
    )
    add_column_if_missing(
        conn, "turns", "reviewer_input_validation_sha", "TEXT",
    )
    add_column_if_missing(
        conn, "turns", "reviewer_input_prompt_sha", "TEXT",
    )


def _migrate_v3_add_job_actions_and_seq(conn: sqlite3.Connection) -> None:
    """Create the append-only job_actions table and add turns_modified_seq."""
    if not table_exists(conn, "job_actions"):
        conn.execute(
            """
            CREATE TABLE job_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id)
            )
            """,
        )
    # Triggers are created unconditionally (IF NOT EXISTS) so that
    # pre-existing job_actions tables without triggers get them backfilled.
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS job_actions_no_update
        BEFORE UPDATE ON job_actions
        BEGIN
            SELECT RAISE(ABORT, 'job_actions is append-only: UPDATE not allowed');
        END
        """,
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS job_actions_no_delete
        BEFORE DELETE ON job_actions
        BEGIN
            SELECT RAISE(ABORT, 'job_actions is append-only: DELETE not allowed');
        END
        """,
    )
    add_column_if_missing(
        conn, "jobs", "turns_modified_seq", "INTEGER NOT NULL DEFAULT 0",
    )


# ---------------------------------------------------------------------------
# Migration registry — order matters, append only.
# ---------------------------------------------------------------------------

MIGRATIONS: list[tuple[str, callable]] = [
    ("v1_add_attempt_and_canonical", _migrate_v1_add_attempt_and_canonical),
    ("v2_add_reviewer_baseline", _migrate_v2_add_reviewer_baseline),
    ("v3_add_job_actions_and_seq", _migrate_v3_add_job_actions_and_seq),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    """Create the schema_version table if it doesn't exist.

    Uses INSERT OR IGNORE so concurrent callers don't race on the seed row.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL DEFAULT 0
        )
        """,
    )
    conn.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 0)")


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if unversioned."""
    if not table_exists(conn, "schema_version"):
        return 0
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    return row[0] if row else 0


class MigrationVersionError(Exception):
    """Raised when the DB schema version is newer than the code supports."""


def run_pending_migrations(conn: sqlite3.Connection, *, verbose: bool = False) -> int:
    """Run any migrations that haven't been applied yet.

    Acquires an EXCLUSIVE lock to serialize concurrent callers.
    Raises MigrationVersionError if the DB is from a newer version.
    Returns the number of migrations applied.
    """
    # Acquire exclusive lock to prevent concurrent migration races.
    conn.execute("BEGIN EXCLUSIVE")
    try:
        ensure_schema_version_table(conn)
        current = get_schema_version(conn)

        if current > len(MIGRATIONS):
            conn.rollback()
            raise MigrationVersionError(
                f"Database schema version ({current}) is newer than this code "
                f"supports ({len(MIGRATIONS)}). Upgrade the bridge code."
            )

        applied = 0
        for idx, (name, fn) in enumerate(MIGRATIONS):
            version = idx + 1  # 1-indexed
            if version <= current:
                continue
            if verbose:
                print(f"  bridge migration {version}/{len(MIGRATIONS)}: {name}")
            fn(conn)
            conn.execute("UPDATE schema_version SET version = ? WHERE id = 1", (version,))
            applied += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return applied
