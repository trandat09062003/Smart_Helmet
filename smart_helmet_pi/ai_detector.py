"""
SMART HELMET 360 - BỘ PHÂN TÍCH THỊ GIÁC AI ĐA HƯỚNG (TRIPLE-CAMERA SPATIAL 360°)
Nhận diện vật thể từ 3 Camera chạy đồng thời (Trước 0°, Sau 180°, Phải 90°),
kết hợp phân vùng không gian trên Camera Trước để bao quát cả góc Trái (LEFT)
và điều khiển chính xác cả 4 kênh Motor rung Haptic (FRONT, RIGHT, REAR, LEFT) + giọng nói.
"""
import os
import time
import logging
import cv2
import numpy as np
import config

logger = logging.getLogger("AIDetector")

# Giới hạn số luồng CPU của OpenCV & PyTorch để tránh treo giao diện/USB trên Raspberry Pi 4
try:
    cv2.setNumThreads(1)
except Exception:
    pass

# Thử nạp thư viện Ultralytics YOLO
YOLO_AVAILABLE = False
try:
    import torch
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except Exception:
        pass
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception as e:
    logger.warning(f"Chưa có thư viện Ultralytics YOLO ({e}). Sẽ sử dụng bộ nhận diện dự phòng OpenCV.")


class DetectedObstacle:
    """Đối tượng chướng ngại vật đã qua phân tích tình huống và phân vùng không gian"""
    def __init__(self, direction: str, class_name: str, confidence: float, bbox,
                 distance_level: str, is_approaching: bool, cam_source: str = None):
        self.direction = direction             # Hướng kích hoạt Haptic/Voice: 'FRONT', 'RIGHT', 'REAR', 'LEFT'
        self.cam_source = cam_source or direction  # Camera vật lý gốc: 'FRONT', 'REAR', 'RIGHT'
        self.class_name = class_name           # 'person', 'car', 'motorcycle', ...
        self.vn_label = config.VIETNAMESE_LABELS.get(class_name, class_name)
        self.confidence = confidence           # 0.0 - 1.0
        self.bbox = bbox                       # (x1, y1, x2, y2)
        self.distance_level = distance_level   # 'CRITICAL' (<1m), 'WARNING' (1-2m), 'FAR' (>2m)
        self.is_approaching = is_approaching   # True nếu đang lao về phía người dùng


class AIDetector:
    def __init__(self):
        self.model = None
        self.history = {'FRONT': {}, 'RIGHT': {}, 'REAR': {}, 'LEFT': {}}
        self._init_model()

    def _init_model(self):
        if YOLO_AVAILABLE:
            try:
                model_path = config.AI_MODEL_PATH if os.path.exists(config.AI_MODEL_PATH) else "yolov8n.pt"
                logger.info(f"Đang nạp mô hình AI [{model_path}]...")
                self.model = YOLO(model_path)
                logger.info("Đã nạp mô hình YOLOv8n thành công.")
                return
            except Exception as e:
                logger.warning(f"Không thể nạp YOLOv8n ({e}). Chuyển sang detector dự phòng.")
                self.model = None

    def _resolve_spatial_direction(self, cam_source: str, x1: int, x2: int, frame_width: int) -> str:
        """
        Ánh xạ từ 3 Camera vật lý sang 4 hướng Motor Haptic (LEFT, FRONT, RIGHT, REAR).
        Hỗ trợ cả 2 kiến trúc:
        1. 'TRI_120' (Tam giác đều 120°: Trước 0°, Sau-Phải 120°, Sau-Trái 240°):
           - Cam TRƯỚC (0°):
             + Tâm < 28%: hướng chếch TRÁI -> Kích motor LEFT
             + Tâm > 72%: hướng chếch PHẢI -> Kích motor RIGHT
             + 28% <= Tâm <= 72%: hướng CHÍNH DIỆN -> Kích motor FRONT
           - Cam SAU-PHẢI (120°):
             + Tâm < 48%: hướng sườn PHẢI (90°) -> Kích motor RIGHT
             + Tâm >= 48%: hướng sau gáy (180°) -> Kích motor REAR
           - Cam SAU-TRÁI (240°):
             + Tâm > 52%: hướng sườn TRÁI (270°) -> Kích motor LEFT
             + Tâm <= 52%: hướng sau gáy (180°) -> Kích motor REAR

        2. 'ORTHO_90' (Trước 0°, Sau 180°, Phải 90°):
           - Phân vùng mép trái trên Cam Trước để bù góc Trái.
        """
        if frame_width <= 0:
            return cam_source

        cx_ratio = ((x1 + x2) * 0.5) / float(frame_width)
        layout = getattr(config, 'CAMERA_LAYOUT', 'TRI_120')

        if layout == 'TRI_120':
            if cam_source == 'FRONT':
                left_thr = getattr(config, 'ZONE_FRONT_LEFT_RATIO', 0.28)
                right_thr = getattr(config, 'ZONE_FRONT_RIGHT_RATIO', 0.72)
                if cx_ratio < left_thr:
                    return 'LEFT'
                elif cx_ratio > right_thr:
                    return 'RIGHT'
                return 'FRONT'

            elif cam_source in ['REAR_RIGHT', 'RIGHT']:
                split_thr = getattr(config, 'ZONE_REAR_SPLIT_RATIO', 0.50)
                if cx_ratio < split_thr:
                    return 'RIGHT'
                return 'REAR'

            elif cam_source in ['REAR_LEFT', 'LEFT']:
                split_thr = getattr(config, 'ZONE_REAR_SPLIT_RATIO', 0.50)
                if cx_ratio > split_thr:
                    return 'LEFT'
                return 'REAR'

        else:
            if cam_source == 'FRONT':
                left_thr = getattr(config, 'ZONE_LEFT_RATIO', 0.35)
                right_thr = getattr(config, 'ZONE_RIGHT_RATIO', 0.67)
                if cx_ratio < left_thr:
                    return 'LEFT'
                elif cx_ratio > right_thr:
                    return 'RIGHT'
                return 'FRONT'
            elif cam_source in ['REAR_RIGHT', 'REAR']:
                return 'REAR'
            elif cam_source in ['RIGHT']:
                return 'RIGHT'
            elif cam_source in ['LEFT']:
                return 'LEFT'

        return cam_source

    def detect_direction(self, cam_source: str, frame: np.ndarray):
        """
        Xử lý 1 khung hình từ một camera vật lý ('FRONT', 'REAR' hoặc 'RIGHT'):
        Trả về: (annotated_frame, list_of_obstacles)
        """
        if frame is None:
            return frame, []

        h, w = frame.shape[:2]
        frame_area = w * h
        obstacles = []
        annotated_frame = frame.copy()

        # 1. NHẬN DIỆN VẬT THỂ BẰNG YOLOV8
        if self.model is not None:
            try:
                results = self.model.predict(
                    source=frame,
                    conf=config.CONFIDENCE_THRESHOLD,
                    classes=None,
                    verbose=False,
                    imgsz=getattr(config, 'AI_IMG_SIZE', 256)
                )

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names[cls_id]

                        if cls_name not in config.TARGET_CLASSES:
                            continue

                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        bbox_area = (x2 - x1) * (y2 - y1)
                        ratio = bbox_area / float(frame_area)

                        # Phân tích mức độ khoảng cách
                        if ratio >= config.BBOX_RATIO_CRITICAL:
                            dist_level = 'CRITICAL'
                            box_color = (0, 0, 255)      # Đỏ
                        elif ratio >= config.BBOX_RATIO_WARNING:
                            dist_level = 'WARNING'
                            box_color = (0, 165, 255)    # Cam/Vàng
                        else:
                            dist_level = 'FAR'
                            box_color = (0, 255, 0)      # Xanh lá

                        # Xác định hướng không gian thực tế (LEFT / FRONT / RIGHT / REAR)
                        spatial_dir = self._resolve_spatial_direction(cam_source, x1, x2, w)

                        # Đánh giá tốc độ tiệm cận (Optical Expansion Rate)
                        prev_ratio = self.history.get(spatial_dir, {}).get(cls_name, ratio)
                        expansion = ratio - prev_ratio
                        if spatial_dir not in self.history:
                            self.history[spatial_dir] = {}
                        self.history[spatial_dir][cls_name] = ratio
                        is_approaching = expansion > 0.03

                        obs = DetectedObstacle(
                            direction=spatial_dir,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=(x1, y1, x2, y2),
                            distance_level=dist_level,
                            is_approaching=is_approaching,
                            cam_source=cam_source
                        )
                        obstacles.append(obs)

                        # Vẽ Bounding Box & HUD
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                        dir_badge = {'LEFT': 'TRAI', 'FRONT': 'TRUOC', 'RIGHT': 'PHAI', 'REAR': 'SAU'}.get(spatial_dir, spatial_dir)
                        tag = f"{obs.vn_label} [{dir_badge}-{dist_level}]"
                        if is_approaching:
                            tag += " (!)"
                        cv2.putText(annotated_frame, tag, (x1, max(20, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, box_color, 2)

            except Exception as e:
                logger.error(f"Lỗi suy luận AI trên camera [{cam_source}]: {e}")

        else:
            # 2. BỘ PHÁT HIỆN DỰ PHÒNG (NẾU CHƯA CÀI ULTRALYTICS)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (15, 15), 0)
            _, thresh = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                ratio = area / float(frame_area)
                if ratio > 0.08:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    dist_level = 'CRITICAL' if ratio >= config.BBOX_RATIO_CRITICAL else 'WARNING'
                    spatial_dir = self._resolve_spatial_direction(cam_source, x, x + bw, w)
                    obs = DetectedObstacle(
                        direction=spatial_dir,
                        class_name='chair',
                        confidence=0.85,
                        bbox=(x, y, x + bw, y + bh),
                        distance_level=dist_level,
                        is_approaching=False,
                        cam_source=cam_source
                    )
                    obstacles.append(obs)
                    color = (0, 0, 255) if dist_level == 'CRITICAL' else (0, 200, 255)
                    cv2.rectangle(annotated_frame, (x, y), (x + bw, y + bh), color, 2)
                    cv2.putText(annotated_frame, f"Vat can [{spatial_dir}]", (x, max(20, y - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)

        return annotated_frame, obstacles
