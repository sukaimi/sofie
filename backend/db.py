"""SQLite engine tuning shared by the API and the Celery worker.

The 'database is locked' errors came from SQLite running in its default
rollback-journal mode, which locks the whole file on every write. WAL
mode allows concurrent readers with a single writer and, together with a
generous busy_timeout, lets the FastAPI handlers and the Celery worker
share one SQLite file without colliding.
"""

from sqlalchemy import event


def apply_sqlite_pragmas(engine) -> None:
    """Enable WAL + busy_timeout on every new SQLite connection.

    Must run OUTSIDE a transaction — a ``PRAGMA journal_mode=WAL`` issued
    inside ``engine.begin()`` is silently ignored by SQLite. Attaching to
    the connection pool's 'connect' event guarantees it runs once per raw
    connection, before any transaction starts.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()
