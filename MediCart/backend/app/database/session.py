from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None, echo: bool | None = None):
    settings = get_settings()
    url = database_url or settings.database_url
    echo = settings.db_echo if echo is None else echo

    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
        sqlite_engine = create_engine(url, echo=echo, **kwargs)

        @event.listens_for(sqlite_engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return sqlite_engine

    # Neon pooled endpoints sit behind PgBouncer. Pre-ping plus a short recycle keeps
    # idle serverless connections from surfacing as errors on the next request.
    return create_engine(
        url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
        pool_timeout=30,
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
