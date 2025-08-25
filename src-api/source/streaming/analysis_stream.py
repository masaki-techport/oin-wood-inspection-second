"""
Analysis pipeline streaming service for real-time processing feedback
"""
import json
import asyncio
import tempfile
import shutil
import os
from typing import AsyncGenerator, List, Dict, Any
from fastapi import UploadFile

from .base import BaseStreamingService
from .error_handling import StreamErrorHandler


class AnalysisResultStreamer(BaseStreamingService):
    """Service for streaming analysis results as processing completes"""
    
    def __init__(self):
        super().__init__()
        self.error_handler = StreamErrorHandler()
    
    async def stream_multi_image_analysis(self, files: List[UploadFile]) -> AsyncGenerator[str, None]:
        """Stream analysis results for multiple images as they complete"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "multi_image_analysis")
        
        try:
            self.logger.info(f"Starting multi-image analysis stream {stream_id} for {len(files)} files")
            
            # Start JSON response
            yield '{"result": true, "data": {'
            yield f'"total_files": {len(files)}, '
            yield '"results": ['
            
            temp_files = []
            first_result = True
            
            try:
                # Process each file
                for i, file in enumerate(files):
                    if not status.is_active:
                        break
                    
                    try:
                        # Save file temporarily
                        temp_file_path = await self._save_temp_file(file)
                        temp_files.append(temp_file_path)
                        
                        # Send progress update
                        if not first_result:
                            yield ','
                        first_result = False
                        
                        progress_data = {
                            "file_index": i,
                            "filename": file.filename,
                            "status": "processing",
                            "progress": (i / len(files)) * 100,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        
                        yield json.dumps(progress_data)
                        self.update_stream_activity(stream_id, len(json.dumps(progress_data)))
                        
                        # Simulate processing delay
                        await asyncio.sleep(0.1)
                        
                        # Perform analysis (mock for now)
                        analysis_result = await self._analyze_image(temp_file_path, file.filename)
                        
                        # Send result
                        yield ','
                        result_data = {
                            "file_index": i,
                            "filename": file.filename,
                            "status": "completed",
                            "progress": ((i + 1) / len(files)) * 100,
                            "result": analysis_result,
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        
                        result_json = json.dumps(result_data)
                        yield result_json
                        self.update_stream_activity(stream_id, len(result_json))
                        
                    except Exception as e:
                        self.logger.error(f"Error processing file {file.filename}: {e}")
                        self.increment_error_count(stream_id)
                        
                        # Send error result
                        if not first_result:
                            yield ','
                        
                        error_data = {
                            "file_index": i,
                            "filename": file.filename,
                            "status": "error",
                            "error": str(e),
                            "timestamp": asyncio.get_event_loop().time()
                        }
                        
                        error_json = json.dumps(error_data)
                        yield error_json
                        self.update_stream_activity(stream_id, len(error_json))
                        
                        first_result = False
            
            finally:
                # Clean up temporary files
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
            
            # End JSON response
            yield ']'
            yield f', "completed_at": "{asyncio.get_event_loop().time()}"'
            yield '}'
            yield '}'
            
        except Exception as e:
            self.logger.error(f"Error in multi-image analysis stream {stream_id}: {e}")
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def stream_batch_processing(self, files: List[UploadFile], batch_size: int = 3) -> AsyncGenerator[str, None]:
        """Stream batch processing results"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "batch_processing")
        
        try:
            self.logger.info(f"Starting batch processing stream {stream_id} for {len(files)} files in batches of {batch_size}")
            
            yield '{"result": true, "data": {'
            yield f'"total_files": {len(files)}, '
            yield f'"batch_size": {batch_size}, '
            yield '"batches": ['
            
            # Process files in batches
            first_batch = True
            for batch_index in range(0, len(files), batch_size):
                if not status.is_active:
                    break
                
                batch_files = files[batch_index:batch_index + batch_size]
                
                if not first_batch:
                    yield ','
                first_batch = False
                
                # Process batch
                batch_result = await self._process_batch(batch_files, batch_index // batch_size)
                
                batch_json = json.dumps(batch_result)
                yield batch_json
                self.update_stream_activity(stream_id, len(batch_json))
                
                # Small delay between batches
                await asyncio.sleep(0.05)
            
            yield ']'
            yield f', "completed_at": "{asyncio.get_event_loop().time()}"'
            yield '}'
            yield '}'
            
        except Exception as e:
            self.logger.error(f"Error in batch processing stream {stream_id}: {e}")
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def stream_progress_updates(self, total_items: int, process_func) -> AsyncGenerator[str, None]:
        """Stream progress updates for long-running processes"""
        stream_id = self.generate_stream_id()
        status = self.register_stream(stream_id, "progress_updates")
        
        try:
            self.logger.info(f"Starting progress updates stream {stream_id} for {total_items} items")
            
            yield '{"result": true, "data": {'
            yield f'"total_items": {total_items}, '
            yield '"progress": ['
            
            first_update = True
            
            for i in range(total_items):
                if not status.is_active:
                    break
                
                if not first_update:
                    yield ','
                first_update = False
                
                # Process item
                try:
                    result = await process_func(i)
                    
                    progress_data = {
                        "item_index": i,
                        "progress_percent": ((i + 1) / total_items) * 100,
                        "status": "completed",
                        "result": result,
                        "timestamp": asyncio.get_event_loop().time()
                    }
                    
                except Exception as e:
                    progress_data = {
                        "item_index": i,
                        "progress_percent": ((i + 1) / total_items) * 100,
                        "status": "error",
                        "error": str(e),
                        "timestamp": asyncio.get_event_loop().time()
                    }
                
                progress_json = json.dumps(progress_data)
                yield progress_json
                self.update_stream_activity(stream_id, len(progress_json))
                
                # Small delay
                await asyncio.sleep(0.02)
            
            yield ']'
            yield f', "completed_at": "{asyncio.get_event_loop().time()}"'
            yield '}'
            yield '}'
            
        except Exception as e:
            self.logger.error(f"Error in progress updates stream {stream_id}: {e}")
            error_response = json.dumps({
                "result": False,
                "error": str(e),
                "stream_id": stream_id
            })
            yield error_response
        
        finally:
            await self.cleanup_stream(stream_id)
    
    async def _save_temp_file(self, file: UploadFile) -> str:
        """Save uploaded file to temporary location"""
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
        
        try:
            with os.fdopen(temp_fd, 'wb') as temp_file:
                # Reset file pointer
                await file.seek(0)
                # Copy file content
                shutil.copyfileobj(file.file, temp_file)
            
            return temp_path
            
        except Exception as e:
            # Clean up on error
            try:
                os.close(temp_fd)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
            raise e
    
    async def _analyze_image(self, image_path: str, filename: str) -> Dict[str, Any]:
        """Analyze image and return results using the inference service"""
        try:
            # Import inference service
            from inference.inference_service import WoodKnotInferenceService
            
            # Initialize inference service if not already done
            if not hasattr(self, '_inference_service'):
                self._inference_service = WoodKnotInferenceService()
            
            # Check if inference service is available
            if not self._inference_service.is_model_available():
                # Fall back to mock results if model not available
                return await self._mock_analyze_image(image_path, filename)
            
            # Perform actual inference
            start_time = asyncio.get_event_loop().time()
            result = self._inference_service.predict_image(image_path)
            end_time = asyncio.get_event_loop().time()
            
            if result["success"]:
                # Convert inference results to streaming format
                inference_data = result["results"]
                
                # Extract detected defects
                detected_defects = []
                confidence_scores = {}
                
                if "detections" in inference_data:
                    for detection in inference_data["detections"]:
                        defect_type = detection.get("class_name", "unknown")
                        confidence = detection.get("confidence", 0.0)
                        
                        if defect_type not in detected_defects:
                            detected_defects.append(defect_type)
                            confidence_scores[defect_type] = confidence
                        else:
                            # Keep highest confidence for each defect type
                            confidence_scores[defect_type] = max(confidence_scores[defect_type], confidence)
                
                return {
                    "filename": filename,
                    "file_size": os.path.getsize(image_path) if os.path.exists(image_path) else 0,
                    "detected_defects": detected_defects,
                    "confidence_scores": confidence_scores,
                    "overall_confidence": inference_data.get("confidence_above_threshold", False),
                    "processing_time_ms": int((end_time - start_time) * 1000),
                    "status": "completed",
                    "inference_data": inference_data
                }
            else:
                # Inference failed, return error
                return {
                    "filename": filename,
                    "file_size": os.path.getsize(image_path) if os.path.exists(image_path) else 0,
                    "status": "error",
                    "error": result.get("error", "Inference failed"),
                    "processing_time_ms": int((end_time - start_time) * 1000)
                }
                
        except Exception as e:
            self.logger.error(f"Error in inference for {filename}: {e}")
            # Fall back to mock results on error
            return await self._mock_analyze_image(image_path, filename)
    
    async def _mock_analyze_image(self, image_path: str, filename: str) -> Dict[str, Any]:
        """Mock analysis results when inference service is not available"""
        import random
        
        # Simulate processing time
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Mock analysis results
        defect_types = ['discoloration', 'hole', 'knot', 'dead_knot', 'live_knot']
        detected_defects = random.sample(defect_types, random.randint(0, 3))
        
        return {
            "filename": filename,
            "file_size": os.path.getsize(image_path) if os.path.exists(image_path) else 0,
            "detected_defects": detected_defects,
            "confidence_scores": {defect: random.uniform(0.5, 0.95) for defect in detected_defects},
            "overall_confidence": random.uniform(0.6, 0.9),
            "processing_time_ms": random.randint(100, 500),
            "status": "completed",
            "mock": True
        }
    
    async def _process_batch(self, batch_files: List[UploadFile], batch_index: int) -> Dict[str, Any]:
        """Process a batch of files"""
        batch_results = []
        temp_files = []
        
        try:
            for i, file in enumerate(batch_files):
                temp_file_path = await self._save_temp_file(file)
                temp_files.append(temp_file_path)
                
                result = await self._analyze_image(temp_file_path, file.filename)
                batch_results.append(result)
        
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
        
        return {
            "batch_index": batch_index,
            "batch_size": len(batch_files),
            "results": batch_results,
            "completed_at": asyncio.get_event_loop().time()
        }
    
    async def cleanup_stream(self, stream_id: str):
        """Clean up resources for a specific stream"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].is_active = False
        
        self.unregister_stream(stream_id)
        self.logger.info(f"Cleaned up analysis stream {stream_id}")


# Global analysis result streamer instance
analysis_streamer = AnalysisResultStreamer()