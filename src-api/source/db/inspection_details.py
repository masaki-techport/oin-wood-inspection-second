from datetime import datetime
from sqlalchemy import Integer, Float
from sqlalchemy import String, text, ForeignKey
from sqlalchemy.orm import Session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

if __package__ == "db":
    from .base import Base
else:
    from base import Base

class InspectionDetails(Base):
    """
    Database model for storing detailed inspection information 
    including error position, confidence and type for each detected error in an image
    """
    __tablename__ = "t_inspection_details"

    error_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="エラー検出ID"
    )
    inspection_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("t_inspection.inspection_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        comment="検査ID（外部キー）"
    )
    error_type: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="エラータイプ (0:変色, 1:穴, 2:死に節, 3:流れ節_死, 4:流れ節_生, 5:生き節)"
    )
    error_type_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="エラータイプ名"
    )
    x_position: Mapped[float] = mapped_column(
        Float, nullable=False, comment="X座標"
    )
    y_position: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Y座標"
    )
    width: Mapped[float] = mapped_column(
        Float, nullable=False, comment="幅"
    )
    height: Mapped[float] = mapped_column(
        Float, nullable=False, comment="高さ"
    )
    length: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("0"), comment="長さ (幅と高さの最大値)"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, comment="信頼度"
    )
    image_path: Mapped[str] = mapped_column(
        String(255), nullable=True, comment="エラー画像のパス"
    )
    image_no: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="画像番号"
    )
    
    # create_dt / update_dt
    create_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP")
    )
    update_dt: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    @classmethod
    def add(cls, session: Session, **kwargs):
        """Add a new inspection detail record"""
        try:
            new_item = cls(**kwargs)
            session.add(new_item)
            session.commit()
            return {"result": True, "message": "Success!!", "new_item": new_item}
        except Exception as ex:
            session.rollback()
            return {"result": False, "message": f"Failed to add inspection detail: {ex}"}
            
    @classmethod
    def get_by_inspection_id(cls, session: Session, inspection_id: int):
        """Get all inspection details for a specific inspection"""
        try:
            results = session.query(cls).filter(cls.inspection_id == inspection_id).all()
            return {"result": True, "message": "Success!!", "data": results}
        except Exception as ex:
            return {"result": False, "message": f"Failed to get inspection details: {ex}"} 