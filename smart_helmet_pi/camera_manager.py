"""
SMART HELMET 360 - BỘ QUẢN LÝ 4 CAMERA ĐA LUỒNG (ZERO-LATENCY THREADING)
Hỗ trợ tự động fallback sang khung hình giả lập nếu thiếu camera vật lý
"""
import cv2
import time
import threading
import numpy as np
import logging
import config

logger = logging.getLogger("CameraManager")


class CameraThread:
    """Luồng độc lập đọc liên tục từng mắt Camera để tránh ứ đọng buffer trễ hình"""
    def __init__(self, direction: str, index: int, width: int = 640, height: int = 480):
        self.direction = direction
        self.index = index
        self.width = width
        self.height = height
        self.cap = None
        self.is_connected = False
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        self.thread = None
        self.last_frame_time = 0
        self.sim_tick = 0

    def start(self):
        self.running = True
        self._init_camera()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _init_camera(self):
        try:
            # Khởi tạo camera với backend V4L2 trên Linux hoặc DSHOW/MSMF trên Windows
            self.cap = cv2.VideoCapture(self.index)
            if self.cap.isOpened():
                # Ép dùng codec MJPEG để tối ưu băng thông USB và tải CPU
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, config.CAM_FPS)
                # Giảm buffer size của OpenCV xuống 1 frame để lấy hình ảnh tức thì
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    self.is_connected = True
                    self.frame = test_frame
                    logger.info(f"Camera [{self.direction}] kết nối thành công tại cổng index {self.index}.")
                    return
            self.is_connected = False
            logger.warning(f"Không thể mở Camera [{self.direction}] tại index {self.index}. Sử dụng chế độ giả lập.")
        except Exception as e:
            logger.warning(f"Lỗi khởi tạo Camera [{self.direction}]: {e}")
            self.is_connected = False

    def _generate_synthetic_frame(self) -> np.ndarray:
        """Tạo khung hình giả lập khi chưa cắm camera, kèm mô phỏng vật cản di chuyển"""
        self.sim_tick += 1
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Nền gradient xanh công nghệ
        img[:, :] = (20, 25, 35)

        # Lưới tọa độ
        for x in range(0, self.width, 80):
            cv2.line(img, (x, 0), (x, self.height), (35, 45, 60), 1)
        for y in range(0, self.height, 60):
            cv2.line(img, (0, y), (self.width, y), (35, 45, 60), 1)

        # Text HUD thông tin camera
        status_text = f"CAM {self.direction} (MÔ PHỎNG SẴN SÀNG)"
        cv2.putText(img, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 240, 255), 2)
        cv2.putText(img, f"Port Index: {self.index} | 640x480 MJPEG", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 175, 190), 1)

        # Giả lập vật cản chuyển động để test AI khi không có camera thực
        cx = int(self.width / 2 + np.sin(self.sim_tick * 0.05 + self.index) * 160)
        cy = int(self.height / 2 + np.cos(self.sim_tick * 0.03 + self.index) * 80)
        cv2.circle(img, (cx, cy), 35, (0, 200, 100), -1)
        cv2.putText(img, "TEST OBSTACLE", (cx - 45, cy - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 200), 1)

        # Khung viền HUD
        cv2.rectangle(img, (5, 5), (self.width - 5, self.height - 5), (50, 70, 95), 1)
        return img

    def _capture_loop(self):
        while self.running:
            if self.is_connected and self.cap is not None:
                try:
                    # Dùng grab() & retrieve() để chỉ lấy frame mới nhất, bỏ qua buffer cũ
                    if self.cap.grab():
                        ret, raw_frame = self.cap.retrieve()
                        if ret and raw_frame is not None:
                            with self.lock:
                                self.frame = raw_frame
                            self.last_frame_time = time.time()
                        else:
                            self.is_connected = False
                    else:
                        self.is_connected = False
                except Exception:
                    self.is_connected = False
            else:
                # Nếu không có camera thực, tạo frame giả lập ở tần số 15 FPS
                synthetic = self._generate_synthetic_frame()
                with self.lock:
                    self.frame = synthetic
                time.sleep(1.0 / config.CAM_FPS)

            time.sleep(0.005)

    def get_frame(self) -> np.ndarray:
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return self._generate_synthetic_frame()

    def stop(self):
        self.running = False
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass


class CameraManager:
    """Quản lý đồng thời 4 camera và xuất luồng video ghép 360°"""
    def __init__(self):
        self.cams = {}
        for direction, idx in config.CAMERA_INDICES.items():
            self.cams[direction] = CameraThread(
                direction=direction,
                index=idx,
                width=config.CAM_WIDTH,
                height=config.CAM_HEIGHT
            )

    def start_all(self):
        logger.info("Đang khởi động toàn bộ 4 mắt Camera...")
        for cam in self.cams.values():
            cam.start()
        time.sleep(0.5)

    def get_frame(self, direction: str) -> np.ndarray:
        if direction in self.cams:
            return self.cams[direction].get_frame()
        return None

    def get_all_frames(self):
        return {direction: cam.get_frame() for direction, cam in self.cams.items()}

    def get_quad_view(self) -> np.ndarray:
        """
        Ghép 4 camera thành khung nhìn 2x2 chuyên nghiệp để quan sát toàn cảnh:
        [ TRƯỚC (Front) ]  [ PHẢI (Right) ]
        [ TRÁI (Left)   ]  [ SAU (Rear)   ]
        """
        f = self.get_frame('FRONT')
        r = self.get_frame('RIGHT')
        b = self.get_frame('REAR')
        l = self.get_frame('LEFT')

        # Thêm nhãn hướng lên từng góc
        def _stamp(img, title, color=(0, 240, 255)):
            if img is None:
                img = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
            out = img.copy()
            # Dải banner tiêu đề
            cv2.rectangle(out, (0, 0), (220, 36), (15, 23, 42), -1)
            cv2.putText(out, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            return out

        f_stamped = _stamp(f, "1. HUONG TRUOC", (0, 240, 255))
        r_stamped = _stamp(r, "2. HUONG PHAI", (0, 230, 118))
        l_stamped = _stamp(l, "4. HUONG TRAI", (255, 179, 0))
        b_stamped = _stamp(b, "3. HUONG SAU", (255, 51, 102))

        top_row = np.hstack([f_stamped, r_stamped])
        bottom_row = np.hstack([l_stamped, b_stamped])
        quad = np.vstack([top_row, bottom_row])
        return quad

    def stop_all(self):
        logger.info("Đang đóng toàn bộ các luồng camera...")
        for cam in self.cams.values():
            cam.stop()
