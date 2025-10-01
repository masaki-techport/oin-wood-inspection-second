from datetime import datetime
from sqlalchemy import Integer
from sqlalchemy import String, text, LargeBinary, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
import os

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Inspection(Base):
    __tablename__ = "t_inspection"

    inspection_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="検査トランザクションID"
    )
    ai_threshold: Mapped[int] = mapped_column(
        Integer, nullable=True, comment="AI閾値"
    )
    inspection_dt: Mapped[datetime] = mapped_column(
        nullable=False, comment="更新日時"
    )
    folder_path: Mapped[str] = mapped_column(
        String, nullable=True, comment="画像フォルダパス"
    )
    status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="検査ステータス (0: 削除済み, 1: 検査完了)"
    )
    results: Mapped[str] = mapped_column(
        String(20), nullable=True, comment="検査結果（無欠点、こぶし、節あり）"
    )

    # create_dt / update_dt (use local system time)
    create_dt: Mapped[datetime] = mapped_column(
        default=datetime.now
    )
    update_dt: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )
    
    # Relationship with presentation images
    presentation_images = relationship("InspectionPresentation", back_populates="inspection", cascade="all, delete-orphan")
    
    # Relationship with inspection images
    images = relationship("InspectionImage", back_populates="inspection", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f""


if __name__ == "__main__":
    from engine import engine

    with Session(engine) as session:
        import random
        import string

        from __init__ import ROOT_DIR
        folder_path = os.path.join(ROOT_DIR, "data", "images", "test_inspection_image.png")

        # select
        results = Inspection.add(
            session,
            ai_threshold=75,
            inspection_dt=datetime.now(),
            folder_path=folder_path,
            status=True)
        import logging
        logging.getLogger(__name__).info("insert record: %s", results)

        # rollback
        session.rollback()
