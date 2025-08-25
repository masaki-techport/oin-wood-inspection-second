from datetime import datetime
from sqlalchemy import Integer
from sqlalchemy import String, text, LargeBinary, ForeignKey, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

if __package__ == "db":
    from .base import Base
else:
    from base import Base

class InspectionResult(Base):
    __tablename__ = "t_inspection_result"

    inspection_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("t_inspection.inspection_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
        comment="検査ID（外部キー）"
    )
    discoloration: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="変色 (0)"
    )
    hole: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="穴 (1)"
    )
    knot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="節 (2)"
    )
    dead_knot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="流れ節_死 (3)"
    )
    live_knot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="流れ節_生 (4)"
    )
    tight_knot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"), comment="生き節 (5)"
    )
    length: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="欠点の長さ（mm）"
    )
    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    def __repr__(self) -> str:
        return f""
