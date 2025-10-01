from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class InspectionImage(Base):
    """Model for inspection images"""
    __tablename__ = 't_inspection_images'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(Integer, ForeignKey('t_inspection.inspection_id', ondelete='CASCADE'), nullable=False)
    image_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Image sequence number')
    image_path: Mapped[str] = mapped_column(String(4096), nullable=False, comment='Path to the image file')
    image_type: Mapped[str] = mapped_column(String(50), nullable=False, comment='Type of image (raw, processed, etc.)')
    capture_timestamp: Mapped[datetime] = mapped_column(
        default=datetime.now,
        comment='When the image was captured'
    )
    image_metadata: Mapped[str] = mapped_column(JSON, nullable=True, comment='Additional image metadata')
    
    # create_dt / update_dt (use local system time)
    create_dt: Mapped[datetime] = mapped_column(
        default=datetime.now
    )
    update_dt: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )

    # Define relationship with Inspection table
    inspection = relationship("Inspection", back_populates="images")