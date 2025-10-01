import os
import cv2
import numpy as np
import yaml
from typing import List, Dict, Any
import logging
from .yolo_seg import YOLOSeg
from .read_jpimage import imread
from .yolo_utils import draw_detections
import base64


class WoodKnotInferenceService:
    def __init__(self, model_path: str = None, config_path: str = None):
        # Get the root directory of the src-api project
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from source/inference/
        
        # Set default paths relative to project root
        if model_path is None:
            model_path = os.path.join(project_root, "model", "best.onnx")
        if config_path is None:
            config_path = os.path.join(project_root, "config", "calc_param.yaml")
            
        self.model_path = model_path
        self.config_path = config_path
        self.model = None
        self.initialization_error = None
        self.config = self._load_config()
        
        logger = logging.getLogger(__name__)
        logger.info("Initializing WoodKnotInferenceService")
        logger.debug(f"Model path: {self.model_path}, exists={os.path.exists(self.model_path)}")
        logger.debug(f"Config path: {self.config_path}, exists={os.path.exists(self.config_path)}")
        
        self._initialize_model()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        default_config = {
            "resolution": 1.0,
            "thresh": 0.5
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    config = yaml.safe_load(file)
                    return {**default_config, **config}
            except Exception as e:
                logging.getLogger(__name__).exception(f"Error loading config: {e}")
                return default_config
        return default_config

    def _initialize_model(self):
        """Initialize the YOLO model with comprehensive error handling"""
        if not os.path.exists(self.model_path):
            error_msg = f"Model file not found: {self.model_path}"
            logging.getLogger(__name__).error(error_msg)
            logging.getLogger(__name__).warning("Please ensure the AI model file exists at the specified location")
            self.model = None
            self.initialization_error = error_msg
            return
            
        try:
            logging.getLogger(__name__).info(f"Loading YOLO model from: {self.model_path}")
            
            # Check if onnxruntime is available
            try:
                import onnxruntime
                logging.getLogger(__name__).info(f"onnxruntime version: {onnxruntime.__version__}")
            except ImportError as e:
                error_msg = f"onnxruntime not available: {e}"
                logging.getLogger(__name__).error(error_msg)
                self.model = None
                self.initialization_error = error_msg
                return
            
            self.model = YOLOSeg(
                path=self.model_path,
                conf_thres=self.config.get("thresh", 0.5),
                iou_thres=0.5
            )
            logging.getLogger(__name__).info(f"Model loaded successfully from {self.model_path}")
            self.initialization_error = None
        except ImportError as e:
            error_msg = f"Missing dependencies for YOLO model: {e}"
            logging.getLogger(__name__).error(error_msg)
            logging.getLogger(__name__).warning("Please ensure all required packages are installed (onnxruntime, etc.)")
            self.model = None
            self.initialization_error = error_msg
        except Exception as e:
            error_msg = f"Error loading model: {e}"
            logging.getLogger(__name__).error(error_msg)
            logging.getLogger(__name__).warning("The model file may be corrupted or incompatible")
            self.model = None
            self.initialization_error = error_msg

    def is_model_available(self) -> bool:
        """Check if model is available for inference"""
        return self.model is not None

    def _predict_on_image_array(self, image: np.ndarray) -> Dict[str, Any]:
        """Core prediction on an RGB ndarray without any file I/O."""
        if not self.is_model_available():
            return {
                "success": False,
                "error": "Model not available"
            }

        try:
            # Get image dimensions
            height, width, _ = image.shape

            # Step 1: Prepare input and get raw outputs
            # The model expects RGB input
            input_tensor = self.model.prepare_input(image)
            outputs = self.model.inference(input_tensor)

            # Step 2: Process outputs to get detection results
            boxes, scores, class_ids, mask_pred = self.model.process_box_output(
                outputs[0], width, height
            )
            
            # Step 3: Process mask outputs  
            mask_maps = self.model.process_mask_output(
                mask_predictions=mask_pred, 
                boxes=boxes, 
                mask_output=outputs[1], 
                img_width=width, 
                img_height=height
            )

            # Count detections by class
            knot_counts = self._count_detections(class_ids)

            # Generate result image with annotations using the draw_detections function
            result_image = draw_detections(
                image=image.copy(),
                boxes=boxes,
                scores=scores,
                class_ids=class_ids,
                mask_alpha=0.4,
                mask_maps=mask_maps
            )
            
            # Convert result image to base64
            _, buffer = cv2.imencode('.jpg', result_image)
            result_image_base64 = base64.b64encode(buffer).decode('utf-8')

            # Add debug class mapping information (same as original app)
            model_class_mapping = {
                0: 'discoloration',
                1: 'hole', 
                2: 'knot_dead',
                3: 'flow_dead',
                4: 'flow_live',
                5: 'knot_live',
            }
            
            app_class_mapping = {
                0: 'knot_live',
                1: 'knot_dead',
                2: 'flow_live',
                3: 'flow_dead',
                4: 'hole',
                5: 'discoloration',
            }

            return {
                "success": True,
                "results": {
                    "total_detections": len(boxes),
                    "knot_counts": knot_counts,
                    "detections": [
                        {
                            "class_id": int(class_id),
                            "class_name": self._get_class_name(class_id),
                            "confidence": float(score),
                            "bbox": [float(x) for x in box]
                        }
                        for box, score, class_id in zip(boxes, scores, class_ids)
                    ],
                    "result_image": result_image_base64,
                    "config": self.config,
                    "debug": {
                        "model_class_mapping": model_class_mapping,
                        "app_class_mapping": app_class_mapping,
                        "mapping_note": "Model class IDs (0-5) map to model labels, then to app class IDs (0-5) for display"
                    }
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Inference failed: {str(e)}"
            }

    def predict_image(self, image_path: str) -> Dict[str, Any]:
        """
        Perform inference on a single image from file path.
        """
        if not self.is_model_available():
            return {
                "success": False,
                "error": "Model not available"
            }

        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": "Image file not found"
            }

        try:
            image = imread(image_path, cv2.IMREAD_COLOR)
            if image is None:
                return {"success": False, "error": "Failed to load image"}
            # imread returns BGR; convert to RGB for the model
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            return self._predict_on_image_array(image_rgb)
        except Exception as e:
            return {
                "success": False,
                "error": f"Inference failed: {str(e)}"
            }

    def predict_array(self, image: np.ndarray) -> Dict[str, Any]:
        """Public API: perform inference directly on an RGB ndarray without saving to disk."""
        if image is None or not isinstance(image, np.ndarray) or image.ndim != 3:
            return {"success": False, "error": "Invalid image array"}
        return self._predict_on_image_array(image)

    def _count_detections(self, class_ids: np.ndarray) -> Dict[str, int]:
        """Count detections by class"""
        knot_counts = {
            "生き節": 0,
            "死に節": 0,
            "流れ節(生)": 0,
            "流れ節(死)": 0,
            "穴": 0,
            "変色": 0
        }

        unique_ids, counts = np.unique(class_ids, return_counts=True)
        for class_id, count in zip(unique_ids, counts):
            class_name = self._get_class_name(class_id)
            if class_name in knot_counts:
                knot_counts[class_name] = int(count)

        return knot_counts

    def _get_class_name(self, class_id: int) -> str:
        """Get class name from class ID - direct mapping to Japanese labels"""
        japanese_labels = {
            0: '変色',      # discoloration  
            1: '穴',        # hole
            2: '死に節',     # knot_dead
            3: '流れ節(死)', # flow_dead
            4: '流れ節(生)', # flow_live
            5: '生き節',     # knot_live
        }
        
        return japanese_labels.get(class_id, f"Unknown class {class_id}")

    def update_threshold(self, new_thresh: float):
        """Update detection threshold"""
        self.config["thresh"] = new_thresh
        if self.model:
            self.model.update_thresholds(new_thresh)

    def get_status(self) -> Dict[str, Any]:
        """Get service status with detailed diagnostics"""
        model_available = self.is_model_available()
        model_path_exists = os.path.exists(self.model_path)
        config_path_exists = os.path.exists(self.config_path)
        
        status = {
            "model_available": model_available,
            "model_path": self.model_path,
            "model_path_exists": model_path_exists,
            "config_path": self.config_path,
            "config_path_exists": config_path_exists,
            "config": self.config,
            "initialization_error": self.initialization_error
        }
        
        # Add diagnostic information
        if not model_available:
            if self.initialization_error:
                status["issue"] = "initialization_failed"
                status["message"] = self.initialization_error
            elif not model_path_exists:
                status["issue"] = "model_file_missing"
                status["message"] = f"Model file not found at: {self.model_path}"
            else:
                status["issue"] = "model_load_failed"
                status["message"] = "Model file exists but failed to load"
        else:
            status["message"] = "Inference service ready"
            
        return status 