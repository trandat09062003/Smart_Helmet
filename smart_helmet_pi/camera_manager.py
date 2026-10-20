"""
SMART HELMET 360 - BỘ QUẢN LÝ 4 CAMERA ĐA LUỒNG (ZERO-LATENCY THREADING)
Tối ưu hóa băng thông USB Hub cho 4 Webcam UVC, tự động dò cổng /dev/v4l/by-path/ và tự kết nối lại
"""
import os
import glob
import cv2
import time
import threading
import numpy as np
import logging
import platform
import config

logger = logging.getLogger("CameraManager")


def discover_usb_cameras():
    """
    Tự động quét và nhận diện 4 mắt camera USB cắm qua USB Hub trên Linux / Ubuntu 22.04.
    Sử dụng đường dẫn vật lý /dev/v4l/by-path/ để cố định thứ tự cổng USB1, USB2, USB3, USB4 trên Hub.
    """
    detected_devices = []

    # 1. Thử quét qua /dev/v4l/by-path/ (chuẩn trên Ubuntu/Debian Linux)
    by_path_nodes = sorted(glob.glob("/dev/v4l/by-path/*index0"))
    if by_path_nodes:
        logger.info(f"Phát hiện {len(by_path_nodes)} thiết bị camera qua /dev/v4l/by-path/:")
        for p in by_path_nodes:
            logger.info(f"  -> {p}")
            detected_devices.append(p)
        return detected_devices

    # 2. Nếu không có by-path, quét lần lượt các node /dev/video* (chỉ lấy node video thực, bỏ qua metadata)
    video_nodes = sorted(glob.glob("/dev/video[0-9]*"), key=lambda x: int(x.replace("/dev/video", "")))
    for node in video_nodes:
        idx = int(node.replace("/dev/video", ""))
        # Thử mở nhanh xem có phải node video capture hợp lệ không
        cap = cv2.VideoCapture(idx, cv2.CAP_V4L2 if platform.system() == "Linux" else cv2.CAP_ANY)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                detected_devices.append(idx)
                if len(detected_devices) >= 4:
                    break

    logger.info(f"Kết quả quét thiết bị Camera khả dụng: {detected_devices}")
    return detected_devices


class CameraThread:
    """Luồng độc lập đọc liên tục từng mắt Camera để tránh ứ đọng buffer trễ hình"""
    def __init__(self, direction: str, device_target, width: int = 640, height: int = 480):
        self.direction = direction
        self.device_target = device_target  # Có thể là index (0, 2, 4...) hoặc đường dẫn (/dev/videoX, by-path)
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
        self.last_reconnect_attempt = 0

    def start(self):
        self.running = True
        self._init_camera()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _init_camera(self):
        try:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

            # Trên Linux, ép dùng backend V4L2 để kiểm soát chính xác FOURCC và Buffer
            backend = cv2.CAP_V4L2 if platform.system() == "Linux" else cv2.CAP_ANY

            # Khởi tạo VideoCapture với device_target
            if isinstance(self.device_target, str) and self.device_target.isdigit():
                target = int(self.device_target)
            else:
                target = self.device_target

            self.cap = cv2.VideoCapture(target, backend)
            if self.cap.isOpened():
                # QUAN TRỌNG: Bắt buộc ép codec MJPEG để 4 camera không bị nghẽn băng thông trên 1 Hub USB
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, config.CAM_FPS)
                # Giảm buffer size của OpenCV xuống 1 frame để lấy hình ảnh tức thì không độ trễ
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                ret, test_frame = self.cap.read()
                if ret and test_frame is not None:
                    self.is_connected = True
                    self.frame = test_frame
                    logger.info(f"Camera [{self.direction}] kết nối thành công tại cổng: {self.device_target}")
                    return

            self.is_connected = False
            logger.warning(f"Chưa nhận tín hiệu Camera [{self.direction}] tại {self.device_target}. Chạy chế độ chờ kết nối.")
        except Exception as e:
            logger.warning(f"Lỗi khởi tạo Camera [{self.direction}]: {e}")
            self.is_connected = False

    def _generate_synthetic_frame(self) -> np.ndarray:
        """Tạo khung hình đồ họa khi chưa cắm camera, kèm mô phỏng vật cản di chuyển"""
        self.sim_tick += 1
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:, :] = (18, 24, 38)

        # Lưới tọa độ
        for x in range(0, self.width, 80):
            cv2.line(img, (x, 0), (x, self.height), (30, 40, 58), 1)
        for y in range(0, self.height, 60):
            cv2.line(img, (0, y), (self.width, y), (30, 40, 58), 1)

        # Text HUD thông tin camera
        status_text = f"CAM {self.direction} (DANG CHO KET NOI HUB)"
        cv2.putText(img, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 240, 255), 2)
        cv2.putText(img, f"Port: {self.device_target} | 640x480 MJPEG", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 175, 190), 1)

        # Giả lập vật cản chuyển động để test AI khi chưa cắm đủ 4 cam
        dir_offset = {'FRONT': 0, 'RIGHT': 1, 'REAR': 2, 'LEFT': 3}.get(self.direction, 0)
        cx = int(self.width / 2 + np.sin(self.sim_tick * 0.05 + dir_offset) * 160)
        cy = int(self.height / 2 + np.cos(self.sim_tick * 0.03 + dir_offset) * 80)
        cv2.circle(img, (cx, cy), 32, (0, 200, 100), -1)
        cv2.putText(img, "TEST TARGET", (cx - 45, cy - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 200), 1)

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
                # Nếu mất kết nối, hiển thị frame chờ và tự động thử kết nối lại sau mỗi 4 giây
                synthetic = self._generate_synthetic_frame()
                with self.lock:
                    self.frame = synthetic

                now = time.time()
                if now - self.last_reconnect_attempt > 4.0:
                    self.last_reconnect_attempt = now
                    self._init_camera()

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
        directions = ['FRONT', 'RIGHT', 'REAR', 'LEFT']

        # Dò tìm tự động các mắt camera trên cổng USB
        discovered = discover_usb_cameras()

        for idx, direction in enumerate(directions):
            # Nếu tìm thấy thiết bị thực qua auto-discovery thì dùng, nếu không dùng cấu hình config.py
            if idx < len(discovered):
                dev_target = discovered[idx]
            else:
                dev_target = config.CAMERA_INDICES.get(direction, idx * 2)

            self.cams[direction] = CameraThread(
                direction=direction,
                device_target=dev_target,
                width=config.CAM_WIDTH,
                height=config.CAM_HEIGHT
            )

    def start_all(self):
        logger.info("Đang khởi động toàn bộ 4 mắt Camera USB...")
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

        def _stamp(img, title, color=(0, 240, 255)):
            if img is None:
                img = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
            out = img.copy()
            cv2.rectangle(out, (0, 0), (220, 36), (15, 23, 42), -1)
            cv2.putText(out, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            return out

        f_stamped = _stamp(f, "1. TRUOC (USB1)", (0, 240, 255))
        r_stamped = _stamp(r, "2. PHAI (USB2)", (0, 230, 118))
        l_stamped = _stamp(l, "4. TRAI (USB4)", (255, 179, 0))
        b_stamped = _stamp(b, "3. SAU (USB3)", (255, 51, 102))

        top_row = np.hstack([f_stamped, r_stamped])
        bottom_row = np.hstack([l_stamped, b_stamped])
        quad = np.vstack([top_row, bottom_row])
        return quad

    def stop_all(self):
        logger.info("Đang đóng toàn bộ các luồng camera...")
        for cam in self.cams.values():
            cam.stop()
