import math
import cv2
import numpy as np
import onnxruntime

from .yolo_utils import xywh2xyxy, nms, draw_detections, sigmoid


class YOLOSeg:
    def __init__(self, path, conf_thres=0.7, iou_thres=0.5, num_masks=32):
        self.conf_threshold = conf_thres
        self.iou_threshold = iou_thres
        self.num_masks = num_masks

        # Initialize model
        self.initialize_model(path)

    def initialize_model(self, path):
        # Try to use CUDA GPU provider if available, fallback to CPU
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        try:
            self.session = onnxruntime.InferenceSession(path, providers=providers)
            # Check which provider is actually being used
            used_provider = self.session.get_providers()[0]
            print(f"Using ONNX Runtime with provider: {used_provider}")
        except Exception as e:
            print(f"Failed to initialize with CUDA, falling back to CPU: {e}")
            self.session = onnxruntime.InferenceSession(path, providers=['CPUExecutionProvider'])
            print("Using ONNX Runtime with CPU provider only")
            
        # Get model info
        self.get_input_details()
        self.get_output_details()
        # Run inference on dummy data for JIT optimization
        self.dummydata_prediction()

    def segment_objects(self, image):
        input_tensor = self.prepare_input(image)

        # Perform inference on the image
        outputs = self.inference(input_tensor)
        img_width, img_height, _ = image.shape

        self.boxes, self.scores, self.class_ids, mask_pred = self.process_box_output(outputs[0], img_width, img_height)
        self.mask_maps = self.process_mask_output(mask_predictions=mask_pred, boxes=self.boxes, mask_output=outputs[1], img_width=img_width, img_height=img_height)

        return self.boxes, self.scores, self.class_ids, self.mask_maps

    def thresh_segment_objects(self, outputs, img_height, img_width):
        boxes, scores, class_ids, mask_pred = self.process_box_output(outputs[0], img_height, img_width)
        mask_maps = self.process_mask_output(mask_predictions=mask_pred, boxes=boxes, mask_output=outputs[1], img_width=img_width, img_height=img_height)
        return boxes, scores, class_ids, mask_maps
    
    def prepare_input(self, image):
        self.img_height, self.img_width = image.shape[:2]

        input_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Resize input image
        input_img = cv2.resize(input_img, (self.input_width, self.input_height))

        # Scale input pixel values to 0 to 1
        input_img = input_img / 255.0
        input_img = input_img.transpose(2, 0, 1)
        input_tensor = input_img[np.newaxis, :, :, :].astype(np.float32)

        return input_tensor

    def inference(self, input_tensor):
        outputs = self.session.run(self.output_names, {self.input_names[0]: input_tensor})
        return outputs

    def process_box_output(self, box_output, img_width, img_height):

        predictions = np.squeeze(box_output).T
        num_classes = box_output.shape[1] - self.num_masks - 4

        # Filter out object confidence scores below threshold
        scores = np.max(predictions[:, 4:4+num_classes], axis=1)
        predictions = predictions[scores > self.conf_threshold, :]
        scores = scores[scores > self.conf_threshold]

        if len(scores) == 0:
            return [], [], [], np.array([])

        box_predictions = predictions[..., :num_classes+4]
        mask_predictions = predictions[..., num_classes+4:]

        # Get the class with the highest confidence
        class_ids = np.argmax(box_predictions[:, 4:], axis=1)

        # Get bounding boxes for each object
        boxes = self.extract_boxes(box_predictions, img_height, img_width)

        # Apply non-maxima suppression to suppress weak, overlapping bounding boxes
        indices = nms(boxes, scores, self.iou_threshold)

        return boxes[indices], scores[indices], class_ids[indices], mask_predictions[indices]

    def process_mask_output(self, mask_predictions, boxes, mask_output, img_width, img_height):
        if mask_predictions.shape[0] == 0:
            return []

        mask_output = np.squeeze(mask_output)

        # Calculate the mask maps for each box
        num_mask, mask_height, mask_width = mask_output.shape  # CHW
        masks = sigmoid(mask_predictions @ mask_output.reshape((num_mask, -1)))
        masks = masks.reshape((-1, mask_height, mask_width))

        scale_boxes = self.rescale_boxes(boxes,
                                   (img_height, img_width),
                                   (mask_height, mask_width))

        # For every box/mask pair, get the mask map
        mask_maps = np.zeros((len(scale_boxes), img_height, img_width))
        blur_size = (int(img_width / mask_width), int(img_height / mask_height))
        for i in range(len(scale_boxes)):

            scale_x1 = int(math.floor(scale_boxes[i][0]))
            scale_y1 = int(math.floor(scale_boxes[i][1]))
            scale_x2 = int(math.ceil(scale_boxes[i][2]))
            scale_y2 = int(math.ceil(scale_boxes[i][3]))

            x1 = int(math.floor(boxes[i][0]))
            y1 = int(math.floor(boxes[i][1]))
            x2 = int(math.ceil(boxes[i][2]))
            y2 = int(math.ceil(boxes[i][3]))

            scale_crop_mask = masks[i][scale_y1:scale_y2, scale_x1:scale_x2]
            crop_mask = cv2.resize(scale_crop_mask,
                              (x2 - x1, y2 - y1),
                              interpolation=cv2.INTER_CUBIC)

            crop_mask = cv2.blur(crop_mask, blur_size)

            crop_mask = (crop_mask > 0.5).astype(np.uint8)
            mask_maps[i, y1:y2, x1:x2] = crop_mask

        return mask_maps

    def extract_boxes(self, box_predictions, img_height, img_width):
        # Extract boxes from predictions
        boxes = box_predictions[:, :4]

        # Scale boxes to original image dimensions
        boxes = self.rescale_boxes(boxes,
                                   (self.input_height, self.input_width),
                                   (img_height, img_width))

        # Convert boxes to xyxy format
        boxes = xywh2xyxy(boxes)

        # Check the boxes are within the image
        boxes[:, 0] = np.clip(boxes[:, 0], 0, img_width)
        boxes[:, 1] = np.clip(boxes[:, 1], 0, img_height)
        boxes[:, 2] = np.clip(boxes[:, 2], 0, img_width)
        boxes[:, 3] = np.clip(boxes[:, 3], 0, img_height)

        return boxes

    def draw_detections(self, image, draw_scores=True, mask_alpha=0.4):
        return draw_detections(image, self.boxes, self.scores,
                               self.class_ids, mask_alpha)

    def draw_masks(self, image, draw_scores=True, mask_alpha=0.5):
        return draw_detections(image, self.boxes, self.scores,
                               self.class_ids, mask_alpha, mask_maps=self.mask_maps)

    def get_input_details(self):
        model_inputs = self.session.get_inputs()
        self.input_names = [model_inputs[i].name for i in range(len(model_inputs))]

        self.input_shape = model_inputs[0].shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

    def get_output_details(self):
        model_outputs = self.session.get_outputs()
        self.output_names = [model_outputs[i].name for i in range(len(model_outputs))]

    @staticmethod
    def rescale_boxes(boxes, input_shape, image_shape):
        # Rescale boxes to original image dimensions
        input_shape = np.array([input_shape[1], input_shape[0], input_shape[1], input_shape[0]])
        boxes = np.divide(boxes, input_shape, dtype=np.float32)
        boxes *= np.array([image_shape[1], image_shape[0], image_shape[1], image_shape[0]])

        return boxes
    
    def update_thresholds(self, new_conf_thres, new_iou_thres=None):
        self.conf_threshold = new_conf_thres
        if new_iou_thres is not None:
            self.iou_threshold = new_iou_thres
            
    def dummydata_prediction(self):
        dst_img = np.random.randint(256, size=(self.input_height, self.input_width, 3)).astype(np.uint8)
        dst_img = self.prepare_input(dst_img)
        for i in range(5):
            self.inference(dst_img) 