from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class InspectionPresentation(Base):
    """Model for representative presentation images for each inspection group (A-E)"""
    __tablename__ = 't_inspection_presentation'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(Integer, ForeignKey('t_inspection.inspection_id', ondelete='CASCADE'), nullable=False)
    group_name: Mapped[str] = mapped_column(String(1), nullable=False, comment='Group name (A, B, C, D, or E)')
    image_path: Mapped[str] = mapped_column(String(255), nullable=True, comment='Path to the presentation image file')
    
    # create_dt / update_dt (use local system time)
    create_dt: Mapped[datetime] = mapped_column(
        default=datetime.now
    )
    update_dt: Mapped[datetime] = mapped_column(
        default=datetime.now,
        onupdate=datetime.now,
    )

    # Define relationship with Inspection table
    inspection = relationship("Inspection", back_populates="presentation_images") 