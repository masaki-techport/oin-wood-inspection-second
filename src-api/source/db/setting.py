from datetime import datetime
from sqlalchemy import Integer, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import Session

if __package__ == "db":
    from .base import Base
else:
    from base import Base


class Setting(Base):
    __tablename__ = "t_setting"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="ID"
    )

    camera_exposure: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="カメラ露光"
    )

    lighting_intensity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="照明強度"
    )

    ai_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="AI閾値"
    )

    create_dt: Mapped[datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="作成日時"
    )

    update_dt: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
        comment="更新日時",
    )

    def __repr__(self) -> str:
        return f"<Setting(id={self.id}, camera_exposure={self.camera_exposure}, lighting_intensity={self.lighting_intensity}, ai_threshold={self.ai_threshold})>"


if __name__ == "__main__":
    from engine import engine

    with Session(engine) as session:
        # new object 
        new_setting = Setting(
            camera_exposure=100,
            lighting_intensity=200,
            ai_threshold=50
        )
        session.add(new_setting)
        session.commit()

        print(f"Inserted Setting with id={new_setting.id}")
