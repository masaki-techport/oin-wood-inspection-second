from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app_config import DB
from db.base import Base

# SQLAlchemyエンジンの作成
engine = create_engine(
    DB["driver"],
    connect_args={"check_same_thread": False},
    echo=DB.get("echo", False),
)

# セッション生成用クラス
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# データベース初期化関数
def initialize_database():
    # Base.metadata.create_all() で全テーブルを作成
    Base.metadata.create_all(engine)


# サーバ起動時にDB初期化
initialize_database()
