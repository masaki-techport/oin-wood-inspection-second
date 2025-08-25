"""
Database handler for Basler camera operations.
"""

import time
import concurrent.futures
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import sessionmaker
from db.engine import SessionLocal, engine
from db import Inspection, InspectionResult
from db.inspection_details import InspectionDetails
from db.inspection_presentation import InspectionPresentation

logger = logging.getLogger('BaslerCamera.Database')

class DatabaseHandler:
    """Optimized database operations with connection pooling"""
    
    def __init__(self):
        """Initialize database handler"""
        self.Session = SessionLocal
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
    def add_inspection_batch(self, inspection_data: Dict[str, Any]) -> Optional[int]:
        """Add inspection with batch operation pattern"""
        start_time = time.time()
        try:
            with self.Session() as session:
                # Create inspection record
                inspection = Inspection(
                    ai_threshold=inspection_data.get('ai_threshold', 50),
                    inspection_dt=datetime.now(),
                    file_path=inspection_data.get('file_path', ''),
                    status=inspection_data.get('status', False),
                    results=inspection_data.get('results', '無欠点')  # Default to no defects
                )
                session.add(inspection)
                session.flush()
                
                # Add all details at once if provided
                if 'details' in inspection_data and inspection_data['details']:
                    session.bulk_save_objects(inspection_data['details'])
                    
                session.commit()
                elapsed = time.time() - start_time
                logger.debug(f"Database operation completed in {elapsed:.3f}s")
                return inspection.inspection_id
        except Exception as e:
            logger.error(f"Database error: {e}")
            return None
            
    def submit_async(self, func, *args, **kwargs):
        """Submit database operation to run asynchronously"""
        return self._executor.submit(func, *args, **kwargs)