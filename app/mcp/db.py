from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


@contextmanager
def mcp_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

