from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db.base import Base


class InspectionImage(Base):
    """Model for inspection images"""
    __tablename__ = 't_inspection_images'

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey('t_inspection.inspection_id', ondelete='CASCADE'), nullable=False)
    image_no = Column(Integer, nullable=False, default=0, comment='Image sequence number')
    image_path = Column(String(4096), nullable=False, comment='Path to the image file')
    image_type = Column(String(50), nullable=False, comment='Type of image (raw, processed, etc.)')
    capture_timestamp = Column(DateTime, default=func.now(), comment='When the image was captured')
    image_metadata = Column(JSON, nullable=True, comment='Additional image metadata')
    created_at = Column(DateTime, default=func.now())

    # Define relationship with Inspection table
    inspection = relationship("Inspection", back_populates="images")