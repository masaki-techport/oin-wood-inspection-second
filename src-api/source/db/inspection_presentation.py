from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.base import Base


class InspectionPresentation(Base):
    """Model for representative presentation images for each inspection group (A-E)"""
    __tablename__ = 't_inspection_presentation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey('t_inspection.inspection_id', ondelete='CASCADE'), nullable=False)
    group_name = Column(String(1), nullable=False, comment='Group name (A, B, C, D, or E)')
    image_path = Column(String(255), comment='Path to the presentation image file')
    created_at = Column(DateTime, default=func.now())

    # Define relationship with Inspection table
    inspection = relationship("Inspection", back_populates="presentation_images") 