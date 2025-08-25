import cv2
import numpy as np


# Define specific colors for each defect type
defect_colors = {
    0: (128, 0, 128),     # 変色 (Discoloration) - Purple
    1: (0, 0, 255),       # 穴 (Hole) - Red  
    2: (0, 165, 255),     # 死に節 (Dead Knot) - Orange
    3: (0, 255, 255),     # 流れ節(死) (Dead Flow) - Yellow
    4: (0, 255, 0),       # 流れ節(生) (Live Flow) - Green
    5: (255, 0, 0),       # 生き節 (Live Knot) - Blue
}

# Convert to numpy array for compatibility
colors = np.array([defect_colors[i] for i in range(6)])


def draw_detections(image, boxes, scores, class_ids, mask_alpha=0.3, mask_maps=None):
    mask_img = image.copy()
    det_img = image.copy()

    img_height, img_width = image.shape[:2]
    font_scale = max(0.8, min([img_height, img_width]) * 0.0012)  # Better scaling
    thickness = max(2, int(min([img_height, img_width]) * 0.003))

    # Draw bounding boxes without text labels
    for box, score, class_id in zip(boxes, scores, class_ids):
        color = tuple(map(int, colors[class_id]))

        x1, y1, x2, y2 = box.astype(int)

        # Draw rectangle with specific color for each defect type
        cv2.rectangle(det_img, (x1, y1), (x2, y2), color, 3)

    # Draw masks
    if mask_maps is not None:
        for i, (box, class_id) in enumerate(zip(boxes, class_ids)):
            color = colors[class_id]
            x1, y1, x2, y2 = box.astype(int)

            # Draw fill mask image
            mask_img[mask_maps[i] == 1] = mask_img[mask_maps[i] == 1] * 0.5 + np.array(color) * 0.5

        # Combine with alpha blending
        return cv2.addWeighted(mask_img, mask_alpha, det_img, 1 - mask_alpha, 0)

    return det_img


def get_label(class_id):
    # Simplified mapping - directly map model class_id to Japanese labels
    # Based on the debug information showing model outputs class IDs 0-5
    
    japanese_labels = {
        0: '変色',      # discoloration
        1: '穴',        # hole  
        2: '死に節',     # knot_dead
        3: '流れ節(死)', # flow_dead
        4: '流れ節(生)', # flow_live  
        5: '生き節',     # knot_live
    }
    
    # Also provide English fallback
    english_labels = {
        0: 'Discolor',
        1: 'Hole',
        2: 'DeadKnot', 
        3: 'DeadFlow',
        4: 'LiveFlow',
        5: 'LiveKnot',
    }
    
    # Try Japanese first, fallback to English
    japanese_label = japanese_labels.get(class_id)
    if japanese_label:
        return japanese_label
    else:
        return english_labels.get(class_id, f'Class{class_id}')


def nms(boxes, scores, iou_threshold):
    # Sort by score
    sorted_indices = np.argsort(scores)[::-1]

    keep_boxes = []
    while sorted_indices.size > 0:
        # Pick the last box
        box_id = sorted_indices[0]
        keep_boxes.append(box_id)

        # Compute IoU of the picked box with the rest
        ious = compute_iou(boxes[box_id, :], boxes[sorted_indices[1:], :])

        # Remove boxes with IoU over the threshold
        keep_indices = np.where(ious < iou_threshold)[0]

        # print(keep_indices.shape, sorted_indices.shape)
        sorted_indices = sorted_indices[keep_indices + 1]

    return keep_boxes


def compute_iou(box, boxes):
    # Compute xmin, ymin, xmax, ymax for both boxes
    xmin = np.maximum(box[0], boxes[:, 0])
    ymin = np.maximum(box[1], boxes[:, 1])
    xmax = np.minimum(box[2], boxes[:, 2])
    ymax = np.minimum(box[3], boxes[:, 3])

    # Compute intersection area
    intersection_area = np.maximum(0, xmax - xmin) * np.maximum(0, ymax - ymin)

    # Compute union area
    box_area = (box[2] - box[0]) * (box[3] - box[1])
    boxes_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union_area = box_area + boxes_area - intersection_area

    # Compute IoU
    iou = intersection_area / union_area

    return iou


def xywh2xyxy(x):
    # Convert bounding box (x, y, w, h) to bounding box (x1, y1, x2, y2)
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2
    y[..., 1] = x[..., 1] - x[..., 3] / 2
    y[..., 2] = x[..., 0] + x[..., 2] / 2
    y[..., 3] = x[..., 1] + x[..., 3] / 2
    return y


def sigmoid(x):
    return 1 / (1 + np.exp(-x)) 