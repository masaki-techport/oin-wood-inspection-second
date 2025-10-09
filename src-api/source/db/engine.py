import sys
import os

import sqlalchemy

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import app_config

config = app_config.DB

sys.path.append(os.path.join(os.path.dirname(__file__)))
from base import Base

# create connection url
connection_url = sqlalchemy.engine.URL.create(
    drivername=config["driver"],
    username=config["user"],
    password=config["password"],
    host=config["host"],
    database=config["database"],
)

# create database engine
engine = sqlalchemy.create_engine(
    connection_url,
    echo=config["echo"],
    pool_size=20,
    max_overflow=0,
)

# create tables
Base.metadata.create_all(engine)

# create session
SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


if __name__ == "__main__":
    print("connection_url", connection_url)
    print("engine", engine)
    print("SessionLocal", SessionLocal)
