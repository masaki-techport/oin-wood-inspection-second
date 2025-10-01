"""
Final Length Consolidator for inspection results.

This module provides functionality to update inspection_result.length with the
maximum length from inspection_details after all processing is complete.
"""

import logging
from typing import Optional
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from db.engine import SessionLocal
from db import InspectionResult
from db.inspection_details import InspectionDetails

logger = logging.getLogger('BaslerCamera.FinalLengthConsolidator')

class FinalLengthConsolidator:
    """
    Handles the final consolidation of length values from inspection_details to inspection_result.
    
    This ensures that the inspection_result.length field always contains the maximum length
    from all corresponding inspection_details records.
    """
    
    @staticmethod
    def update_length_from_details(inspection_id: int) -> bool:
        """
        Update the inspection_result.length with the maximum length from inspection_details.
        
        Args:
            inspection_id: The inspection ID to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            session = SessionLocal()
            
            try:
                # Query the maximum length from inspection_details for this inspection
                # Only consider knot-related defects (error_type 2,3,4,5) for max_length
                max_length_query = session.query(
                    func.max(InspectionDetails.length)
                ).filter(
                    InspectionDetails.inspection_id == inspection_id,
                    InspectionDetails.length.isnot(None),  # Exclude NULL values
                    InspectionDetails.error_type.in_([2, 3, 4, 5])  # Only knot types
                )
                
                max_length = max_length_query.scalar()
                
                if max_length is None:
                    logger.warning(f"No valid length found in inspection_details for inspection_id {inspection_id}")
                    return False
                
                # Update the inspection_result record with the maximum length
                result = session.query(InspectionResult).filter_by(
                    inspection_id=inspection_id
                ).first()
                
                if not result:
                    logger.error(f"No inspection_result found for inspection_id {inspection_id}")
                    return False
                
                # Only update if the new length is greater than the current one or current is 0
                if result.length is None or result.length == 0 or max_length > result.length:
                    old_length = result.length
                    result.length = max_length
                    session.commit()
                    logger.info(f"Updated inspection_result.length from {old_length} to {max_length} mm for inspection_id {inspection_id}")
                    return True
                else:
                    logger.debug(f"No update needed: current length {result.length} >= max_details_length {max_length}")
                    return True
                
            except SQLAlchemyError as e:
                logger.error(f"Database error updating length for inspection_id {inspection_id}: {e}")
                session.rollback()
                return False
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error in update_length_from_details for inspection_id {inspection_id}: {e}")
            return False
    
    @staticmethod
    def update_all_inspection_results() -> int:
        """
        Update all inspection_result records with maximum lengths from inspection_details.
        
        Returns:
            int: Number of records updated
        """
        try:
            session = SessionLocal()
            updated_count = 0
            
            try:
                # Find all inspection_result records with length = 0 or NULL
                results = session.query(InspectionResult).filter(
                    (InspectionResult.length == 0) | 
                    (InspectionResult.length.is_(None))
                ).all()
                
                logger.info(f"Found {len(results)} inspection_result records with length = 0 or NULL")
                
                # Update each record
                for result in results:
                    inspection_id = result.inspection_id
                    
                    # Get max length from details (only knot types)
                    max_length = session.query(
                        func.max(InspectionDetails.length)
                    ).filter(
                        InspectionDetails.inspection_id == inspection_id,
                        InspectionDetails.length.isnot(None),
                        InspectionDetails.error_type.in_([2, 3, 4, 5])  # Only knot types
                    ).scalar()
                    
                    if max_length is not None and max_length > 0:
                        result.length = max_length
                        updated_count += 1
                        logger.info(f"Updated inspection_id {inspection_id} length to {max_length} mm")
                    else:
                        logger.debug(f"No valid length found in details for inspection_id {inspection_id}")
                
                if updated_count > 0:
                    session.commit()
                    logger.info(f"Successfully updated {updated_count} inspection_result records")
                
                return updated_count
                
            except SQLAlchemyError as e:
                logger.error(f"Database error in update_all_inspection_results: {e}")
                session.rollback()
                return 0
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Error in update_all_inspection_results: {e}")
            return 0
