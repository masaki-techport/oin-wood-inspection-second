from datetime import datetime
from sqlalchemy import Integer
from sqlalchemy import String, text, LargeBinary, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

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
    file_path: Mapped[str] = mapped_column(
        String, nullable=True, comment="画像ファイルパス"
    )
    status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="ステータス (0: Active, 1: 削除済)"
    )
    results: Mapped[str] = mapped_column(
        String(20), nullable=True, comment="検査結果（無欠点、こぶし、節あり）"
    )

    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
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

        file_path = "data/images/test_inspection_image.png"

        # select
        results = Inspection.add(
            session,
            ai_threshold=75,
            inspection_dt=datetime.now(),
            file_path=file_path,
            status=True)
        print("insert record: ", results)

        # rollback
        session.rollback()
