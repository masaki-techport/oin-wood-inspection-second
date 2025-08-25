import os
import base64
import logging
import sys
import tempfile
import time
import random
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import shutil
from inference.inference_service import WoodKnotInferenceService
from app_config import APP_CONFIG

# Import the BaslerCamera analysis modules for direct usage
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    # First try the direct import path
    try:
        from camera.basler.analysis.image_analyzer import ImageAnalyzer
        from camera.basler.analysis.presentation_processor import PresentationProcessor
        from camera.basler.camera import BaslerCamera
        logger = logging.getLogger(__name__)
        logger.info("Successfully imported BaslerCamera analysis modules")
    except ImportError:
        # If that fails, try the alternative import path
        logger.info("Trying alternative import path for BaslerCamera modules")
        from source.camera.basler.analysis.image_analyzer import ImageAnalyzer
        from source.camera.basler.analysis.presentation_processor import PresentationProcessor
        from source.camera.basler.camera import BaslerCamera
        logger.info("Successfully imported BaslerCamera analysis modules using alternative path")
    
    # Create a temporary instance of BaslerCamera for analysis
    try:
        analyzer_camera = BaslerCamera()
        logger.info("Successfully created BaslerCamera instance")
    except Exception as camera_error:
        logger.error(f"Failed to create BaslerCamera instance: {camera_error}")
        analyzer_camera = None
except ImportError as e:
    logger.error(f"Failed to import BaslerCamera modules: {e}")
    analyzer_camera = None

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference")

# Initialize inference service with error handling
try:
    inference_service = WoodKnotInferenceService()
    logger.info("Inference service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize inference service: {e}")
    inference_service = None


@router.get("/status")
def get_inference_status():
    """Get inference service status"""
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service failed to initialize")
    return inference_service.get_status()


@router.post("/predict")
async def predict_wood_knots(file: UploadFile = File(...)):
    """
    Analyze wood image for knot detection
    
    Args:
        file: Image file to analyze
        
    Returns:
        Inference results with detected knots
    """
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service failed to initialize")
    if not inference_service.is_model_available():
        raise HTTPException(status_code=503, detail="Inference model not available")
    
    # Validate file type
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    try:
        # Save uploaded file temporarily
        upload_dir = APP_CONFIG['upload_folder_inspection']
        os.makedirs(upload_dir, exist_ok=True)
        
        temp_file_path = os.path.join(upload_dir, f"temp_{file.filename}")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Perform inference
        result = inference_service.predict_image(temp_file_path)
        
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if result["success"]:
            return JSONResponse(content={
                "result": True,
                "message": "推論完了",
                "data": result["results"]
            })
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        # Clean up on error
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"推論処理中にエラーが発生しました: {str(e)}")


@router.post("/predict-inspection/{inspection_id}")
def predict_inspection_image(inspection_id: str):
    """
    Analyze inspection image for knot detection
    
    Args:
        inspection_id: ID of the inspection image
        
    Returns:
        Inference results with detected knots
    """
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service failed to initialize")
    if not inference_service.is_model_available():
        raise HTTPException(status_code=503, detail="Inference model not available")
    
    # Look for inspection image
    inspection_dir = APP_CONFIG['upload_folder_inspection']
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    
    image_path = None
    for ext in image_extensions:
        potential_path = os.path.join(inspection_dir, f"{inspection_id}{ext}")
        if os.path.exists(potential_path):
            image_path = potential_path
            break
    
    if not image_path:
        raise HTTPException(status_code=404, detail="検査画像が見つかりません")
    
    try:
        result = inference_service.predict_image(image_path)
        
        if result["success"]:
            return JSONResponse(content={
                "result": True,
                "message": "推論完了",
                "data": result["results"]
            })
        else:
            raise HTTPException(status_code=500, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推論処理中にエラーが発生しました: {str(e)}")


@router.put("/threshold")
def update_threshold(threshold: float = Query(..., ge=0.0, le=1.0)):
    """
    Update detection threshold
    
    Args:
        threshold: New detection threshold (0.0 - 1.0)
    """
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service failed to initialize")
    try:
        inference_service.update_threshold(threshold)
        return {
            "result": True,
            "message": "しきい値を更新しました",
            "data": {"threshold": threshold}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"しきい値の更新に失敗しました: {str(e)}")


@router.get("/config")
def get_inference_config():
    """Get current inference configuration"""
    if inference_service is None:
        raise HTTPException(status_code=503, detail="Inference service failed to initialize")
    return {
        "result": True,
        "message": "設定取得完了",
        "data": inference_service.config
    }


@router.post("/analyze-with-basler")
async def analyze_with_basler_analyzer(file: UploadFile = File(...)):
    """
    Analyze wood image using the BaslerCamera ImageAnalyzer
    
    Args:
        file: Image file to analyze
        
    Returns:
        Analysis results with detected defects
    """
    global analyzer_camera
    
    # Create analyzer if needed
    if analyzer_camera is None:
        try:
            # Initialize a temporary BaslerCamera for analysis
            from camera.basler.camera import BaslerCamera
            analyzer_camera = BaslerCamera()
            logger.info("Created BaslerCamera for analysis")
        except Exception as e:
            logger.error(f"Failed to create BaslerCamera: {e}")
            raise HTTPException(status_code=503, detail=f"Failed to initialize analyzer: {str(e)}")
    
    # Validate file type
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    try:
        # Save uploaded file temporarily
        upload_dir = APP_CONFIG['upload_folder_inspection']
        os.makedirs(upload_dir, exist_ok=True)
        
        temp_file_path = os.path.join(upload_dir, f"temp_{file.filename}")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Use the ImageAnalyzer directly
        logger.info(f"Analyzing image using BaslerCamera's ImageAnalyzer: {temp_file_path}")
        analyzer = ImageAnalyzer(analyzer_camera)
        
        # Use the analyze_image method
        analysis_result = analyzer.analyze_image(temp_file_path)
        
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        if analysis_result:
            return JSONResponse(content={
                "result": True,
                "message": "Analysis completed",
                "data": analysis_result
            })
        else:
            raise HTTPException(status_code=500, detail="Analysis failed")
            
    except Exception as e:
        logger.error(f"Error analyzing image: {e}")
        # Clean up on error
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/test-basler-workflow")
async def test_basler_workflow(files: List[UploadFile] = File(...)):
    """
    Simplified test of BaslerCamera workflow for debugging purposes
    
    Args:
        files: List of image files to analyze (batch processing)
        
    Returns:
        Simulated analysis results including presentation images
    """
    # Check if we have files
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided for analysis")
    
    try:
        # Create a temporary directory for the batch
        with tempfile.TemporaryDirectory() as temp_dir:
            # Process and save all uploaded images
            temp_file_paths = []
            
            logger.info(f"Processing {len(files)} uploaded images for BaslerCamera workflow test")
            
            # Save all uploaded files
            for i, file in enumerate(files):
                # Validate file type
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
                file_extension = os.path.splitext(file.filename)[1].lower()
                if file_extension not in allowed_extensions:
                    continue  # Skip unsupported formats
                
                # Save with sequential filename pattern
                save_name = f"image_{i:04d}{file_extension}"
                temp_file_path = os.path.join(temp_dir, save_name)
                
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                    
                temp_file_paths.append(temp_file_path)
            
            if not temp_file_paths:
                raise HTTPException(status_code=400, detail="No valid image files provided")
            
            # Create a simulated inspection ID
            inspection_id = int(time.time() * 1000)
            logger.info(f"Created simulated inspection ID: {inspection_id}")
            
            # Create simulated analysis results
            all_results = []
            for i, path in enumerate(temp_file_paths):
                # Generate random detections for simulation
                detections = []
                total_detections = random.randint(0, 5)
                
                for j in range(total_detections):
                    class_id = random.randint(0, 5)
                    class_name = [
                        '変色',      # discoloration  
                        '穴',        # hole
                        '死に節',     # knot_dead
                        '流れ節(死)', # flow_dead
                        '流れ節(生)', # flow_live
                        '生き節',     # knot_live
                    ][class_id]
                    
                    detections.append({
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": 0.5 + random.random() * 0.5,  # 0.5-1.0
                        "bbox": [
                            random.random() * 300,  # x
                            random.random() * 200,  # y
                            50 + random.random() * 100,  # width
                            50 + random.random() * 100   # height
                        ]
                    })
                
                # Create a simulated analysis result
                result = {
                    "inspection_id": inspection_id,
                    "detections": detections,
                    "confidence_above_threshold": len(detections) > 0,
                    "ai_threshold": 50,
                    "results": "節あり" if len(detections) > 0 else "無欠点",
                    "inspection_details": [
                        {
                            "id": j + 1,
                            "error_type": detection["class_id"],
                            "error_type_name": detection["class_name"],
                            "x_position": detection["bbox"][0],
                            "y_position": detection["bbox"][1],
                            "width": detection["bbox"][2],
                            "height": detection["bbox"][3],
                            "length": max(detection["bbox"][2], detection["bbox"][3]) / 100,
                            "confidence": detection["confidence"],
                            "image_path": path
                        }
                        for j, detection in enumerate(detections)
                    ]
                }
                
                all_results.append(result)
            
            # Create simulated presentation images
            presentation_images = []
            for i, path in enumerate(temp_file_paths):
                group_name = chr(65 + min(i, 4))  # A, B, C, D, E
                
                # Save the image to a location accessible by the frontend
                save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images", "inspection")
                os.makedirs(save_dir, exist_ok=True)
                
                # Create a unique filename
                timestamp = int(time.time() * 1000)
                filename = f"test_{timestamp}_{i}.jpg"
                save_path = os.path.join(save_dir, filename)
                
                # Copy the image
                shutil.copy(path, save_path)
                
                # Create a relative path for the frontend
                relative_path = f"inspection/{filename}"
                
                presentation_images.append({
                    "inspection_id": inspection_id,
                    "group_name": group_name,
                    "image_path": relative_path
                })
            
            # Create simulated presentation results
            presentation_results = {
                "inspection_id": inspection_id,
                "presentation_images": presentation_images,
                "inspection_dt": datetime.now().isoformat(),
                "presentation_ready": True
            }
            
            # Prepare response with simulated data
            response_data = {
                "result": True,
                "message": f"Successfully analyzed {len(temp_file_paths)} images with BaslerCamera workflow (simulated)",
                "data": {
                    "inspection_id": inspection_id,
                    "analysis_results": all_results,
                    "presentation_results": presentation_results,
                    "image_count": len(temp_file_paths),
                    "processed_count": len(all_results)
                }
            }
            
            return JSONResponse(content=response_data)
    
    except Exception as e:
        logger.error(f"Error in BaslerCamera workflow test: {e}")
        # Include stack trace for debugging
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Trace: {trace}")
        raise HTTPException(status_code=500, detail=f"BaslerCamera workflow test failed: {str(e)}")


@router.post("/presentation-test")
async def presentation_test(files: List[UploadFile] = File(...)):
    """
    Simplified test of presentation processor functionality for debugging purposes
    
    Args:
        files: List of image files to process for presentation
        
    Returns:
        Simulated presentation processing results
    """
    # Check if we have files
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided for presentation processing")
    
    try:
        # Create a temporary directory for the files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Process and save all uploaded images
            temp_file_paths = []
            
            logger.info(f"Processing {len(files)} uploaded images for presentation test")
            
            # Save all uploaded files
            for i, file in enumerate(files):
                # Validate file type
                allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
                file_extension = os.path.splitext(file.filename)[1].lower()
                if file_extension not in allowed_extensions:
                    continue  # Skip unsupported formats
                
                # Save with sequential filename pattern
                save_name = f"image_{i:04d}{file_extension}"
                temp_file_path = os.path.join(temp_dir, save_name)
                
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                    
                temp_file_paths.append(temp_file_path)
            
            if not temp_file_paths:
                raise HTTPException(status_code=400, detail="No valid image files provided")
            
            # Create a simulated inspection ID
            inspection_id = int(time.time() * 1000)
            logger.info(f"Created simulated inspection ID: {inspection_id} for presentation test")
            
            # Create simulated presentation images
            presentation_images = []
            for i, path in enumerate(temp_file_paths):
                group_name = chr(65 + min(i, 4))  # A, B, C, D, E
                
                # Save the image to a location accessible by the frontend
                save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images", "inspection")
                os.makedirs(save_dir, exist_ok=True)
                
                # Create a unique filename
                timestamp = int(time.time() * 1000)
                filename = f"presentation_{timestamp}_{i}.jpg"
                save_path = os.path.join(save_dir, filename)
                
                # Copy the image
                shutil.copy(path, save_path)
                
                # Create a relative path for the frontend
                relative_path = f"inspection/{filename}"
                
                presentation_images.append({
                    "inspection_id": inspection_id,
                    "group_name": group_name,
                    "image_path": relative_path
                })
            
            # Create simulated presentation results
            presentation_results = {
                "inspection_id": inspection_id,
                "presentation_images": presentation_images,
                "inspection_dt": datetime.now().isoformat(),
                "presentation_ready": True
            }
            
            # Prepare response
            response_data = {
                "result": True,
                "message": "Presentation processing completed (simulated)",
                "data": {
                    "inspection_id": inspection_id,
                    "presentation_results": presentation_results,
                    "image_count": len(temp_file_paths)
                }
            }
            
            return JSONResponse(content=response_data)
    
    except Exception as e:
        logger.error(f"Error in presentation test: {e}")
        # Include stack trace for debugging
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Trace: {trace}")
        raise HTTPException(status_code=500, detail=f"Presentation test failed: {str(e)}")
