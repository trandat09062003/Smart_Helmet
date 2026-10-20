"""
SMART HELMET 360 - BỘ PHÂN TÍCH THỊ GIÁC AI ĐA HƯỚNG
Nhận diện vật thể, ước lượng khoảng cách và đánh giá nguy cơ va chạm tiệm cận
"""
import time
import logging
import cv2
import numpy as np
import config

logger = logging.getLogger("AIDetector")

# Thử nạp thư viện Ultralytics YOLO
YOLO_AVAILABLE = False
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception as e:
    logger.warning(f"Chưa có thư viện Ultralytics YOLO ({e}). Sẽ sử dụng bộ nhận diện dự phòng OpenCV.")


class DetectedObstacle:
    """Đối tượng chướng ngại vật đã qua phân tích tình huống"""
    def __init__(self, direction: str, class_name: str, confidence: float, bbox, distance_level: str, is_approaching: bool):
        self.direction = direction             # 'FRONT', 'RIGHT', 'REAR', 'LEFT'
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
                # Nạp mô hình nhẹ YOLOv8n (nếu chưa có file thì Ultralytics tự tải)
                model_name = "yolov8n.pt"
                logger.info(f"Đang nạp mô hình AI [{model_name}]...")
                self.model = YOLO(model_name)
                logger.info("Đã nạp mô hình YOLOv8n thành công.")
                return
            except Exception as e:
                logger.warning(f"Không thể nạp YOLOv8n ({e}). Chuyển sang detector dự phòng.")
                self.model = None

    def detect_direction(self, direction: str, frame: np.ndarray):
        """
        Xử lý 1 khung hình từ một camera chỉ định:
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
                    imgsz=320  # Tối ưu kích thước 320x320 để đạt FPS cao trên Raspberry Pi
                )

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        cls_name = self.model.names[cls_id]

                        # Lọc các lớp vật cản quan trọng đối với người khiếm thị
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

                        # Đánh giá tốc độ tiệm cận (Optical Expansion Rate)
                        prev_ratio = self.history[direction].get(cls_name, ratio)
                        expansion = ratio - prev_ratio
                        self.history[direction][cls_name] = ratio
                        is_approaching = expansion > 0.03  # Diện tích tăng nhanh -> đang lao tới

                        obs = DetectedObstacle(
                            direction=direction,
                            class_name=cls_name,
                            confidence=conf,
                            bbox=(x1, y1, x2, y2),
                            distance_level=dist_level,
                            is_approaching=is_approaching
                        )
                        obstacles.append(obs)

                        # Vẽ Bounding Box & HUD
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)
                        tag = f"{obs.vn_label} [{dist_level}]"
                        if is_approaching:
                            tag += " (!TIEM CAN)"
                        cv2.putText(annotated_frame, tag, (x1, max(20, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, box_color, 2)

            except Exception as e:
                logger.error(f"Lỗi suy luận AI trên camera [{direction}]: {e}")

        else:
            # 2. BỘ PHÁT HIỆN DỰ PHÒNG (NẾU CHƯA CÀI ULTRALYTICS TRÊN MÁY DEV)
            # Phát hiện khối vật thể dựa trên chuyển động hoặc vùng nổi bật
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
                    obs = DetectedObstacle(
                        direction=direction,
                        class_name='chair',
                        confidence=0.85,
                        bbox=(x, y, x + bw, y + bh),
                        distance_level=dist_level,
                        is_approaching=False
                    )
                    obstacles.append(obs)
                    color = (0, 0, 255) if dist_level == 'CRITICAL' else (0, 200, 255)
                    cv2.rectangle(annotated_frame, (x, y), (x + bw, y + bh), color, 2)
                    cv2.putText(annotated_frame, f"Vat can [{dist_level}]", (x, max(20, y - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        return annotated_frame, obstacles
