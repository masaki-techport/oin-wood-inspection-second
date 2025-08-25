from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app_config import DB
from db.base import Base

engine = create_engine(
    DB["driver"],
    connect_args={"check_same_thread": False},
    echo=DB.get("echo", False)
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def initialize_database():
    import models
    Base.metadata.create_all(engine)
