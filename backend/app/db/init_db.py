from __future__ import annotations

from sqlalchemy import bindparam, text

from app.db.session import Base, engine

# Stable 64-bit advisory lock id for Artifact Hub schema initialization.
# This prevents the API process and worker process from running create_all()
# at the same time against the same Postgres database.
SCHEMA_INIT_LOCK_ID = 77192348011235813


def _is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


def _cleanup_orphan_composite_types() -> None:
    """Repair an interrupted/racy PostgreSQL CREATE TABLE attempt.

    PostgreSQL creates a composite type with the same name as every table. If a
    CREATE TABLE was interrupted during a race, the type can remain even though
    the table was not created, which later raises:
      duplicate key value violates unique constraint pg_type_typname_nsp_index
    This cleanup only drops the orphan type when the table itself is absent.
    """

    table_names = [table.name for table in Base.metadata.sorted_tables]
    if not table_names:
        return

    with engine.begin() as conn:
        orphan_type_stmt = text(
            """
            SELECT t.typname
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            LEFT JOIN information_schema.tables it
              ON it.table_schema = n.nspname
             AND it.table_name = t.typname
            WHERE n.nspname = 'public'
              AND t.typname IN :table_names
              AND it.table_name IS NULL
            """
        ).bindparams(bindparam("table_names", expanding=True))

        orphan_type_names = conn.execute(
            orphan_type_stmt,
            {"table_names": table_names},
        ).scalars().all()

        for type_name in orphan_type_names:
            # Type names come from SQLAlchemy model metadata, but quote defensively.
            safe_type_name = str(type_name).replace('"', '""')
            conn.execute(text(f'DROP TYPE IF EXISTS public."{safe_type_name}" CASCADE'))



def _column_exists_sqlite(conn, table_name: str, column_name: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def _run_lightweight_migrations(conn) -> None:
    """Small demo migrations for fields added after create_all().

    This keeps existing local/Railway databases usable without introducing a full
    Alembic setup in the challenge project. For production, replace this with
    versioned Alembic migrations.
    """

    if engine.dialect.name == "postgresql":
        conn.execute(text("ALTER TABLE artifacts ADD COLUMN IF NOT EXISTS feedback_summary TEXT"))
        return

    if engine.dialect.name == "sqlite":
        if not _column_exists_sqlite(conn, "artifacts", "feedback_summary"):
            conn.execute(text("ALTER TABLE artifacts ADD COLUMN feedback_summary TEXT"))

def init_db() -> None:
    """Initialize database tables safely for local dev and Railway startup.

    This challenge project intentionally avoids a full Alembic migration setup.
    For dev/demo reliability, we serialize create_all() with a Postgres advisory
    lock so the web process and background worker cannot initialize the schema
    concurrently.
    """

    if not _is_postgres():
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
            _run_lightweight_migrations(conn)
        return

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": SCHEMA_INIT_LOCK_ID})
        try:
            _cleanup_orphan_composite_types()
            Base.metadata.create_all(bind=conn)
            _run_lightweight_migrations(conn)
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": SCHEMA_INIT_LOCK_ID})


if __name__ == "__main__":
    init_db()
    print("Database schema is ready.")
