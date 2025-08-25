"""
Inspection data streaming service for progressive data loading
"""
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional, Tuple
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from .base import BaseStreamingService
from .error_handling import StreamErrorHandler
from dependencies import get_session
from db import Inspection, InspectionResult, InspectionDetails


class InspectionDataStreamer(BaseStreamingService):
    """Service for streaming inspection data progressively"""
    
    def __init__(self, session_factory=get_session):
        super().__init__()
        self.session_factory = session_factory
        self.error_handler = StreamErrorHandler()
    
    async def stream_inspections(self, filters: Dict[str, Any] = None, limit: Optional[int] = None) -> AsyncGenerator[str, None]:
        """Stream inspection data as JSON"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "inspection_stream")
        
        try:
            self.logger.info(f"Starting inspection data stream {stream_id}")
            
            # Start JSON response
            yield '{"result": true, "data": ['
            
            with next(self.session_factory()) as session:
                # Build query
                query = session.query(Inspection).order_by(desc(Inspection.inspection_dt))
                
                # Apply filters if provided
                if filters:
                    if 'date_from' in filters and filters['date_from']:
                        query = query.filter(Inspection.inspection_dt >= filters['date_from'])
                    if 'date_to' in filters and filters['date_to']:
                        query = query.filter(Inspection.inspection_dt <= filters['date_to'])
                
                # Apply limit
                if limit:
                    query = query.limit(limit)
                
                # Stream results in batches
                batch_size = self.config.data.batch_size
                offset = 0
                first_item = True
                
                while status.is_active:
                    batch = query.offset(offset).limit(batch_size).all()
                    
                    if not batch:
                        break
                    
                    for inspection in batch:
                        if not first_item:
                            yield ','
                        first_item = False
                        
                        # Convert to dict
                        inspection_dict = {
                            'inspection_id': inspection.inspection_id,
                            'inspection_dt': inspection.inspection_dt.isoformat() if inspection.inspection_dt else None,
                            'results': inspection.results,
                            'confidence_above_threshold': inspection.confidence_above_threshold,
                            'ai_threshold': inspection.ai_threshold,
                            'presentation_ready': inspection.presentation_ready
                        }
                        
                        json_data = json.dumps(inspection_dict)
                        yield json_data
                        
                        self.update_stream_activity(stream_id, len(json_data))
                    
                    offset += batch_size
                    
                    # Small delay to prevent overwhelming the client
                    await asyncio.sleep(0.01)
            
            # End JSON response
            yield ']}'
            
        except Exception as e:
            self.logger.error(f"Error in inspection stream {stream_id}: {e}")
            # Send error in JSON format
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def stream_inspection_history(self, date_range: Tuple[date, date]) -> AsyncGenerator[str, None]:
        """Stream historical inspection data for date range"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "inspection_history_stream")
        
        try:
            start_date, end_date = date_range
            self.logger.info(f"Starting inspection history stream {stream_id} for {start_date} to {end_date}")
            
            yield '{"result": true, "data": {'
            yield f'"date_range": {{"start": "{start_date.isoformat()}", "end": "{end_date.isoformat()}"}}, '
            yield '"inspections": ['
            
            with next(self.session_factory()) as session:
                # Query inspections in date range
                query = session.query(Inspection).filter(
                    func.date(Inspection.inspection_dt) >= start_date,
                    func.date(Inspection.inspection_dt) <= end_date
                ).order_by(desc(Inspection.inspection_dt))
                
                batch_size = self.config.data.batch_size
                offset = 0
                first_item = True
                
                while status.is_active:
                    batch = query.offset(offset).limit(batch_size).all()
                    
                    if not batch:
                        break
                    
                    for inspection in batch:
                        if not first_item:
                            yield ','
                        first_item = False
                        
                        # Get detailed inspection data
                        inspection_dict = await self._get_detailed_inspection_data(session, inspection)
                        
                        json_data = json.dumps(inspection_dict)
                        yield json_data
                        
                        self.update_stream_activity(stream_id, len(json_data))
                    
                    offset += batch_size
                    await asyncio.sleep(0.01)
            
            yield ']}'
            yield '}'
            
        except Exception as e:
            self.logger.error(f"Error in inspection history stream {stream_id}: {e}")
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def stream_analysis_results(self, inspection_ids: List[int]) -> AsyncGenerator[str, None]:
        """Stream analysis results for multiple inspections"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "analysis_results_stream")
        
        try:
            self.logger.info(f"Starting analysis results stream {stream_id} for {len(inspection_ids)} inspections")
            
            yield '{"result": true, "data": ['
            
            with next(self.session_factory()) as session:
                first_item = True
                
                for inspection_id in inspection_ids:
                    if not status.is_active:
                        break
                    
                    try:
                        # Get inspection with results
                        inspection = session.query(Inspection).filter(
                            Inspection.inspection_id == inspection_id
                        ).first()
                        
                        if inspection:
                            if not first_item:
                                yield ','
                            first_item = False
                            
                            # Get comprehensive analysis data
                            analysis_data = await self._get_analysis_data(session, inspection)
                            
                            json_data = json.dumps(analysis_data)
                            yield json_data
                            
                            self.update_stream_activity(stream_id, len(json_data))
                        
                        # Small delay between inspections
                        await asyncio.sleep(0.005)
                        
                    except Exception as e:
                        self.logger.warning(f"Error processing inspection {inspection_id}: {e}")
                        # Continue with next inspection
                        continue
            
            yield ']}'
            
        except Exception as e:
            self.logger.error(f"Error in analysis results stream {stream_id}: {e}")
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def _get_detailed_inspection_data(self, session: Session, inspection: Inspection) -> Dict[str, Any]:
        """Get detailed inspection data including results and details"""
        inspection_dict = {
            'inspection_id': inspection.inspection_id,
            'inspection_dt': inspection.inspection_dt.isoformat() if inspection.inspection_dt else None,
            'results': inspection.results,
            'confidence_above_threshold': inspection.confidence_above_threshold,
            'ai_threshold': inspection.ai_threshold,
            'presentation_ready': inspection.presentation_ready
        }
        
        # Use a single JOIN query to fetch both inspection results and details in one database call
        try:
            # First get inspection results with a direct query
            inspection_result = session.query(InspectionResult).filter(
                InspectionResult.inspection_id == inspection.inspection_id
            ).first()
            
            if inspection_result:
                inspection_dict['inspection_results'] = {
                    'discoloration': inspection_result.discoloration,
                    'hole': inspection_result.hole,
                    'knot': inspection_result.knot,
                    'dead_knot': inspection_result.dead_knot,
                    'live_knot': inspection_result.live_knot,
                    'tight_knot': inspection_result.tight_knot,
                    'length': inspection_result.length
                }
                
            # Then get inspection details in the same transaction
            # Create a covering index query with all fields we need to avoid a second lookup
            inspection_details_query = session.query(
                InspectionDetails.id,
                InspectionDetails.error_type,
                InspectionDetails.error_type_name,
                InspectionDetails.x_position,
                InspectionDetails.y_position,
                InspectionDetails.width,
                InspectionDetails.height,
                InspectionDetails.length,
                InspectionDetails.confidence,
                InspectionDetails.image_path
            ).filter(
                InspectionDetails.inspection_id == inspection.inspection_id
            )
            
            # Execute the query and transform the results into dictionaries
            inspection_details = inspection_details_query.all()
            
            if inspection_details:
                inspection_dict['inspection_details'] = [
                    {
                        'id': detail.id,
                        'error_type': detail.error_type,
                        'error_type_name': detail.error_type_name,
                        'x_position': detail.x_position,
                        'y_position': detail.y_position,
                        'width': detail.width,
                        'height': detail.height,
                        'length': detail.length,
                        'confidence': detail.confidence,
                        'image_path': detail.image_path
                    }
                    for detail in inspection_details
                ]
        except Exception as e:
            self.logger.warning(f"Error getting inspection data for {inspection.inspection_id}: {e}")
        
        return inspection_dict
    
    async def _get_analysis_data(self, session: Session, inspection: Inspection) -> Dict[str, Any]:
        """Get comprehensive analysis data for an inspection"""
        return await self._get_detailed_inspection_data(session, inspection)
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].is_active = False
        
        self.unregister_stream(stream_id)
        self.logger.info(f"Cleaned up inspection stream {stream_id}")


# Global inspection data streamer instance
inspection_streamer = InspectionDataStreamer()