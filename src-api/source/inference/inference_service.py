import os
import cv2
import numpy as np
import yaml
from typing import List, Dict, Any
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
        self.config = self._load_config()
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
                print(f"Error loading config: {e}")
                return default_config
        return default_config

    def _initialize_model(self):
        """Initialize the YOLO model"""
        if os.path.exists(self.model_path):
            try:
                self.model = YOLOSeg(
                    path=self.model_path,
                    conf_thres=self.config.get("thresh", 0.5),
                    iou_thres=0.5
                )
                print(f"Model loaded successfully from {self.model_path}")
            except Exception as e:
                print(f"Error loading model: {e}")
                self.model = None
        else:
            print(f"Model file not found: {self.model_path}")
            self.model = None

    def is_model_available(self) -> bool:
        """Check if model is available for inference"""
        return self.model is not None

    def predict_image(self, image_path: str) -> Dict[str, Any]:
        """
        Perform inference on a single image
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary containing inference results
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
            # Load image using the special imread function for Japanese filenames
            image = imread(image_path, cv2.IMREAD_COLOR)
            if image is None:
                return {
                    "success": False,
                    "error": "Failed to load image"
                }

            # Get image dimensions
            height, width, _ = image.shape

            # Step 1: Prepare input and get raw outputs
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
        """Get service status"""
        return {
            "model_available": self.is_model_available(),
            "model_path": self.model_path,
            "config": self.config
        } 