from typing import Generator
from contextlib import contextmanager

from db import SessionLocal


# Dependency
def get_session() -> Generator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope():
    return get_session()
