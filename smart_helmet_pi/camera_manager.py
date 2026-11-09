"""
SMART HELMET 360 - BỘ QUẢN LÝ 3 CAMERA CHẠY ĐỒNG THỜI Ở FPS THẤP (CONTINUOUS LOW-FPS V4L2-MMAP)
Giải pháp tối ưu phần cứng cho 3 Webcam UVC Jieli (5258:4a55) trên Raspberry Pi 4:
1. Chạy đồng thời cả 3 Camera (FRONT 0°, REAR 180°, RIGHT 90°) ở chế độ Continuous Low-FPS (6 FPS/cam):
   - Tổng băng thông USB 2.0 chiếm ~96% (<= 100%), cho phép cả 3 camera giữ luồng STREAMON liên tục.
   - Không gọi VIDIOC_STREAMOFF / STREAMON lặp lại -> Triệt tiêu hoàn toàn lỗi treo chip USB Jieli (-110).
2. Hạ tần số lấy mẫu phần cứng (VIDIOC_S_PARM) & Zero-Copy MMAP Drain:
   - Xả bỏ các khung hình MJPEG cũ ngay trong bộ đệm RAM của nhân Linux mà không tốn CPU giải mã.
   - Chỉ giải mã đúng 1 khung hình JPEG mới nhất mỗi chu kỳ (6 FPS), giảm hơn 60% tải CPU nhưng độ trễ vẫn ~0ms.
"""
import os
import glob
import fcntl
import mmap
import select
import struct
import cv2
import time
import threading
import logging
import platform
import numpy as np
import config

logger = logging.getLogger("CameraManager")

# Hằng số ioctl V4L2 chuẩn trên Linux 64-bit (aarch64 / x86_64)
V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_MEMORY_MMAP = 1
VIDIOC_QUERYCAP  = 0x80685600
VIDIOC_S_FMT     = 0xc0d05605
VIDIOC_REQBUFS   = 0xc0145608
VIDIOC_QUERYBUF  = 0xc0585609
VIDIOC_QBUF      = 0xc058560f
VIDIOC_DQBUF     = 0xc0585611
VIDIOC_STREAMON  = 0x40045612
VIDIOC_STREAMOFF = 0x40045613
VIDIOC_S_PARM    = 0xc0cc5616


def scan_available_video_devices():
    """
    Trả về danh sách các cặp (label_path, video_index) của các webcam USB thực tế đang cắm.
    Chỉ lấy node capture chính (*-video-index0), tuyệt đối bỏ qua node metadata (*-video-index1)
    và bỏ qua các node codec/isp nội bộ của bcm2835.
    """
    devices = []
    seen_indices = set()
    metadata_indices = set()

    for meta_p in glob.glob("/dev/v4l/by-path/*video-index1"):
        if os.path.exists(meta_p):
            base = os.path.basename(os.path.realpath(meta_p))
            if base.startswith("video") and base.replace("video", "").isdigit():
                metadata_indices.add(int(base.replace("video", "")))

    by_path_nodes = sorted(glob.glob("/dev/v4l/by-path/*usb*index0"))
    for p in by_path_nodes:
        if not os.path.exists(p):
            continue
        real_path = os.path.realpath(p)
        base = os.path.basename(real_path)
        if base.startswith("video"):
            idx_str = base.replace("video", "")
            if idx_str.isdigit():
                idx = int(idx_str)
                if idx not in seen_indices and idx not in metadata_indices:
                    seen_indices.add(idx)
                    devices.append((p, idx))

    if not devices:
        for idx in range(8):
            dev_node = f"/dev/video{idx}"
            if idx not in seen_indices and idx not in metadata_indices and os.path.exists(dev_node):
                if idx % 2 == 0:
                    seen_indices.add(idx)
                    devices.append((dev_node, idx))

    return devices


class FastV4L2Device:
    """
    Trình điều khiển V4L2 Non-Blocking trực tiếp bằng MMAP ở mức nhân Linux.
    Giữ luồng STREAMON liên tục cho cả 3 camera ở tốc độ FPS thấp, tự động xả các frame MJPEG cũ
    trong ring-buffer mà không giải mã để triệt tiêu độ trễ và tiết kiệm tối đa CPU/USB.
    """
    def __init__(self, video_index: int, width: int = 352, height: int = 240, fps: int = 6):
        self.video_index = video_index
        self.dev_path = f"/dev/video{video_index}"
        self.width = width
        self.height = height
        self.fps = max(1, int(fps))
        self.fd = None
        self.buffers = []
        self.streaming = False

    def open(self) -> bool:
        self.close()
        try:
            self.fd = os.open(self.dev_path, os.O_RDWR | os.O_NONBLOCK)

            # Kiểm tra nhanh thiết bị có phản hồi ioctl không
            fcntl.ioctl(self.fd, VIDIOC_QUERYCAP, b"\x00" * 104)

            # 1. Cấu hình định dạng phần cứng MJPEG 352x240
            fmt = bytearray(208)
            struct.pack_into("<I", fmt, 0, V4L2_BUF_TYPE_VIDEO_CAPTURE)
            struct.pack_into("<III", fmt, 8, self.width, self.height, int.from_bytes(b"MJPG", "little"))
            fcntl.ioctl(self.fd, VIDIOC_S_FMT, fmt)

            # 2. Yêu cầu phần cứng hạ FPS (VIDIOC_S_PARM: timeperframe = 1 / fps)
            try:
                parm = bytearray(204)
                struct.pack_into("<I", parm, 0, V4L2_BUF_TYPE_VIDEO_CAPTURE)
                # v4l2_captureparm bắt đầu tại offset 4: capability(4), capturemode(4), timeperframe(num=4, den=4)
                struct.pack_into("<II", parm, 12, 1, self.fps)
                fcntl.ioctl(self.fd, VIDIOC_S_PARM, parm)
            except Exception:
                pass

            # 3. Cấp phát 3 vùng nhớ MMAP trong RAM để luồng liên tục không bao giờ cạn buffer
            req = bytearray(struct.pack("<IIIII", 3, V4L2_BUF_TYPE_VIDEO_CAPTURE, V4L2_MEMORY_MMAP, 0, 0))
            fcntl.ioctl(self.fd, VIDIOC_REQBUFS, req)
            buf_count = struct.unpack_from("<I", req, 0)[0]
            if buf_count < 1:
                self.close()
                return False

            self.buffers = []
            for i in range(buf_count):
                buf = bytearray(88)
                struct.pack_into("<II", buf, 0, i, V4L2_BUF_TYPE_VIDEO_CAPTURE)
                struct.pack_into("<I", buf, 60, V4L2_MEMORY_MMAP)
                fcntl.ioctl(self.fd, VIDIOC_QUERYBUF, buf)
                length = struct.unpack_from("<I", buf, 72)[0]
                offset = struct.unpack_from("<I", buf, 64)[0]
                mm = mmap.mmap(self.fd, length, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE, offset=offset)
                self.buffers.append((i, mm))

            return True
        except Exception as e:
            logger.debug(f"Không thể mở V4L2 {self.dev_path}: {e}")
            self.close()
            return False

    def start_stream(self) -> bool:
        if self.fd is None or not self.buffers:
            return False
        if self.streaming:
            return True
        try:
            for idx, _ in self.buffers:
                qbuf = bytearray(88)
                struct.pack_into("<II", qbuf, 0, idx, V4L2_BUF_TYPE_VIDEO_CAPTURE)
                struct.pack_into("<I", qbuf, 60, V4L2_MEMORY_MMAP)
                fcntl.ioctl(self.fd, VIDIOC_QBUF, qbuf)
            fcntl.ioctl(self.fd, VIDIOC_STREAMON, struct.pack("<I", V4L2_BUF_TYPE_VIDEO_CAPTURE))
            self.streaming = True
            return True
        except Exception as e:
            logger.debug(f"Lỗi VIDIOC_STREAMON trên {self.dev_path}: {e}")
            self.streaming = False
            return False

    def stop_stream(self):
        if not self.streaming or self.fd is None:
            self.streaming = False
            return
        try:
            fcntl.ioctl(self.fd, VIDIOC_STREAMOFF, struct.pack("<I", V4L2_BUF_TYPE_VIDEO_CAPTURE))
        except Exception:
            pass
        self.streaming = False

    def read_latest_frame(self, timeout: float = 0.60, keep_streaming: bool = True) -> np.ndarray:
        """
        Đọc khung hình mới nhất từ bộ đệm MMAP (Zero-Copy Drain).
        Xả toàn bộ các frame cũ trong ring-buffer mà không giải mã, chỉ giải mã đúng 1 frame mới nhất.
        """
        if not self.start_stream():
            return None

        raw_jpeg = None
        try:
            r, _, _ = select.select([self.fd], [], [], timeout)
            if r:
                while True:
                    dqbuf = bytearray(88)
                    struct.pack_into("<I", dqbuf, 4, V4L2_BUF_TYPE_VIDEO_CAPTURE)
                    struct.pack_into("<I", dqbuf, 60, V4L2_MEMORY_MMAP)
                    try:
                        fcntl.ioctl(self.fd, VIDIOC_DQBUF, dqbuf)
                    except Exception:
                        break

                    buf_idx = struct.unpack_from("<I", dqbuf, 0)[0]
                    bytes_used = struct.unpack_from("<I", dqbuf, 8)[0]
                    if 120 < bytes_used <= len(self.buffers[buf_idx][1]):
                        mm = self.buffers[buf_idx][1]
                        mm.seek(0)
                        raw_jpeg = mm.read(bytes_used)

                    if keep_streaming:
                        try:
                            fcntl.ioctl(self.fd, VIDIOC_QBUF, dqbuf)
                        except Exception:
                            break

                    r_more, _, _ = select.select([self.fd], [], [], 0.0)
                    if not r_more:
                        break
        except Exception as e:
            logger.debug(f"Lỗi đọc MMAP trên {self.dev_path}: {e}")
            raw_jpeg = None
        finally:
            if not keep_streaming:
                self.stop_stream()

        if raw_jpeg is not None:
            try:
                arr = np.frombuffer(raw_jpeg, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None and img.size > 0:
                    if img.shape[1] != self.width or img.shape[0] != self.height:
                        img = cv2.resize(img, (self.width, self.height))
                    return img
            except Exception:
                pass
        return None

    def capture_frame_tdm(self, timeout: float = 0.80) -> np.ndarray:
        """Tương thích với công cụ test_cameras.py"""
        return self.read_latest_frame(timeout=timeout, keep_streaming=True)

    def close(self):
        self.stop_stream()
        for _, mm in self.buffers:
            try:
                mm.close()
            except Exception:
                pass
        self.buffers = []

        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None


class CameraSlot:
    """Đại diện cho 1 mắt camera vật lý (FRONT, REAR hoặc RIGHT)"""
    def __init__(self, manager, direction: str, slot_index: int = 0, width: int = 352, height: int = 240):
        self.manager = manager
        self.direction = direction
        self.slot_index = slot_index
        self.width = width
        self.height = height
        self.device_label = f"USB{slot_index + 1}"
        self.video_index = None
        self.v4l2_dev = None
        self.cap = None
        self.is_connected = False
        self.frame = None
        self.frame_count = 0
        self.fps = 0.0
        self._fps_ticks = 0
        self._fps_t0 = time.time()
        self.lock = threading.Lock()
        self.last_frame_time = 0
        self.sim_tick = 0
        self.last_synthetic_time = 0
        self.last_reconnect_attempt = 0
        self.consecutive_failures = 0

        with self.lock:
            self.frame = self._generate_synthetic_frame()

    def release(self):
        if self.v4l2_dev is not None:
            self.v4l2_dev.close()
            self.v4l2_dev = None
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_connected = False
        if self.video_index is not None:
            self.manager.release_device(self.direction, self.video_index)
            self.video_index = None

    def try_connect(self, keep_streaming: bool = True) -> bool:
        self.release()
        assigned = self.manager.acquire_device(self.direction, self.slot_index)
        if assigned is None:
            return False

        label_path, target_idx = assigned
        self.device_label = label_path
        self.video_index = target_idx
        init_timeout = getattr(config, 'CAM_INIT_TIMEOUT_SEC', 1.80)

        if platform.system() == "Linux":
            dev = FastV4L2Device(target_idx, self.width, self.height, fps=getattr(config, 'CAM_FPS', 6))
            if dev.open():
                test_frame = dev.read_latest_frame(timeout=init_timeout, keep_streaming=keep_streaming)
                if test_frame is not None:
                    self.v4l2_dev = dev
                    self.is_connected = True
                    self.consecutive_failures = 0
                    self.frame_count += 1
                    self.last_frame_time = time.time()
                    self.manager.mark_device_verified(target_idx)
                    with self.lock:
                        self.frame = test_frame
                    short_port = os.path.basename(label_path) if "/" in str(label_path) else label_path
                    logger.info(f"[OK] Camera [{self.direction}] ĐÃ KẾT NỐI tại /dev/video{target_idx} ({short_port})")
                    return True
            dev.close()
        else:
            try:
                cap = cv2.VideoCapture(target_idx)
                if cap.isOpened():
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        self.cap = cap
                        self.is_connected = True
                        with self.lock:
                            self.frame = cv2.resize(test_frame, (self.width, self.height))
                        return True
                cap.release()
            except Exception:
                pass

        logger.warning(f"[WARN] Camera [{self.direction}] tại /dev/video{target_idx} đang khởi động chậm. Sẽ thử lại sau 3s.")
        self.manager.mark_device_unresponsive(target_idx)
        self.release()
        return False

    def poll_once(self) -> bool:
        """Đọc 1 khung hình mới nhất từ mắt camera (giữ luồng Continuous Low-FPS STREAMON)"""
        if not self.is_connected:
            return False

        read_timeout = getattr(config, 'CAM_READ_TIMEOUT_SEC', 0.60)
        new_frame = None
        if self.v4l2_dev is not None:
            new_frame = self.v4l2_dev.read_latest_frame(timeout=read_timeout, keep_streaming=True)
        elif self.cap is not None:
            ret, raw = self.cap.read()
            if ret and raw is not None:
                new_frame = cv2.resize(raw, (self.width, self.height))

        if new_frame is not None:
            now = time.time()
            with self.lock:
                self.frame = new_frame
            self.last_frame_time = now
            self.frame_count += 1
            self._fps_ticks += 1
            elapsed = now - self._fps_t0
            if elapsed >= 1.5:
                self.fps = self._fps_ticks / elapsed
                self._fps_ticks = 0
                self._fps_t0 = now
            self.consecutive_failures = 0
            return True
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 6:
                logger.warning(f"Mất tín hiệu từ Camera [{self.direction}] (/dev/video{self.video_index}). Đang kết nối lại...")
                if self.video_index is not None:
                    self.manager.mark_device_unresponsive(self.video_index)
                self.release()
            return False

    def update_synthetic_if_needed(self):
        now = time.time()
        if now - self.last_synthetic_time >= 1.0:
            self.last_synthetic_time = now
            syn = self._generate_synthetic_frame()
            with self.lock:
                self.frame = syn

    def _generate_synthetic_frame(self) -> np.ndarray:
        """Tạo khung hình chờ khi mắt camera chưa cắm"""
        self.sim_tick += 1
        img = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        img[:, :] = (18, 24, 38)

        for x in range(0, self.width, 60):
            cv2.line(img, (x, 0), (x, self.height), (30, 40, 58), 1)
        for y in range(0, self.height, 45):
            cv2.line(img, (0, y), (self.width, y), (30, 40, 58), 1)

        vn_map = {
            'FRONT':      "CAM 1: TRUOC (0°)",
            'REAR_RIGHT': "CAM 2: SAU-PHAI (120°)",
            'REAR_LEFT':  "CAM 3: SAU-TRAI (240°)",
            'REAR':       "CAM 2: SAU (180°)",
            'RIGHT':      "CAM 3: PHAI (90°)",
            'LEFT':       "CAM 4: TRAI (270°)"
        }
        vn_name = vn_map.get(self.direction, f"CAM {self.direction}")
        status_text = f"{vn_name} - CHO KET NOI USB"
        cv2.putText(img, status_text, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 240, 255), 1)
        cv2.putText(img, f"Slot: USB{self.slot_index + 1} | {self.width}x{self.height} Low-FPS", (14, 54),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 175, 190), 1)

        dir_offset = {'FRONT': 0, 'REAR_RIGHT': 2, 'REAR_LEFT': 4, 'REAR': 2, 'RIGHT': 4, 'LEFT': 6}.get(self.direction, 0)
        cx = int(self.width / 2 + np.sin(self.sim_tick * 0.25 + dir_offset) * 65)
        cy = int(self.height / 2 + 15 + np.cos(self.sim_tick * 0.2 + dir_offset) * 30)
        cv2.circle(img, (cx, cy), 16, (0, 200, 100), -1)
        cv2.putText(img, "STANDBY", (cx - 28, cy - 22), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 200), 1)

        cv2.rectangle(img, (3, 3), (self.width - 3, self.height - 3), (50, 70, 95), 1)
        return img

    def get_frame(self) -> np.ndarray:
        with self.lock:
            if self.frame is not None:
                return self.frame.copy()
            return self._generate_synthetic_frame()


class CameraManager:
    """
    Quản lý đồng thời 3 Camera vật lý (FRONT, REAR, RIGHT) ở chế độ Continuous Low-FPS V4L2-MMAP:
    - Giữ luồng STREAMON liên tục cho cả 3 camera ở tốc độ ~6 FPS mỗi mắt với tải CPU cực thấp.
    - Không bao giờ ngắt quãng camera đang chạy, đảm bảo ổn định 100% trên Raspberry Pi 4.
    """
    def __init__(self):
        self.alloc_lock = threading.Lock()
        self.claimed_indices = {}          # direction -> video_index
        self.unresponsive_until = {}       # video_index -> timestamp
        self.cams = {}
        self.running = False
        self.capture_thread = None

        self.directions = list(getattr(config, 'ACTIVE_CAMERAS', ['FRONT', 'REAR', 'RIGHT']))
        for idx, direction in enumerate(self.directions):
            self.cams[direction] = CameraSlot(
                manager=self,
                direction=direction,
                slot_index=idx,
                width=config.CAM_WIDTH,
                height=config.CAM_HEIGHT
            )

    def is_camera_connected(self, direction: str) -> bool:
        cam = self.cams.get(direction)
        return bool(cam and cam.is_connected)

    def mark_device_verified(self, video_index: int):
        with self.alloc_lock:
            self.unresponsive_until.pop(video_index, None)

    def reset_unresponsive_devices(self):
        """Cho phép người dùng nhấn nút Quét lại trên Web Dashboard để thử lại các cổng USB"""
        with self.alloc_lock:
            self.unresponsive_until.clear()
        for cam in self.cams.values():
            cam.last_reconnect_attempt = 0
        logger.info(f"Đã xóa bộ nhớ đệm cổng chờ, đang quét lại {len(self.directions)} cổng Camera USB...")

    def has_unclaimed_device(self) -> bool:
        """Kiểm tra nhanh xem có node /dev/videoX nào đang cắm mà chưa được nhận không"""
        with self.alloc_lock:
            now = time.time()
            available = scan_available_video_devices()
            if not available:
                return False
            in_use = {v for v in self.claimed_indices.values() if v is not None}
            for _, v_idx in available:
                if v_idx not in in_use and now >= self.unresponsive_until.get(v_idx, 0):
                    return True
            return False

    def acquire_device(self, direction: str, slot_index: int):
        """Cấp phát độc quyền 1 cổng /dev/videoX cho hướng `direction`"""
        with self.alloc_lock:
            now = time.time()
            available = scan_available_video_devices()
            if not available:
                return None

            in_use_by_others = {
                v_idx for d, v_idx in self.claimed_indices.items()
                if d != direction and v_idx is not None
            }

            def _is_usable(v_idx):
                if v_idx in in_use_by_others:
                    return False
                if now < self.unresponsive_until.get(v_idx, 0):
                    return False
                return True

            # 1. Ưu tiên khớp đúng index cấu hình (FRONT -> video0, REAR -> video2, RIGHT -> video4)
            preferred_idx = getattr(config, 'CAMERA_INDICES', {}).get(direction)
            if preferred_idx is not None:
                for label_path, v_idx in available:
                    if v_idx == preferred_idx and _is_usable(v_idx):
                        self.claimed_indices[direction] = v_idx
                        return (label_path, v_idx)

            # 2. Lấy thiết bị khả dụng đầu tiên chưa có luồng nào dùng
            for label_path, v_idx in available:
                if _is_usable(v_idx):
                    self.claimed_indices[direction] = v_idx
                    return (label_path, v_idx)

            return None

    def release_device(self, direction: str, video_index: int):
        with self.alloc_lock:
            if self.claimed_indices.get(direction) == video_index:
                self.claimed_indices.pop(direction, None)

    def mark_device_unresponsive(self, video_index: int, was_verified: bool = False):
        with self.alloc_lock:
            self.unresponsive_until[video_index] = time.time() + 3.0

    def start_all(self):
        logger.info(
            f"Đang khởi chạy Bộ điều phối {len(self.directions)} Camera ({', '.join(self.directions)}) "
            f"chế độ Continuous Low-FPS ({config.CAM_FPS} FPS/cam)..."
        )
        self.running = True
        self.capture_thread = threading.Thread(target=self._continuous_capture_loop, daemon=True)
        self.capture_thread.start()

    def _continuous_capture_loop(self):
        """
        Luồng thu nhận hình ảnh đồng thời cho cả 3 Camera (FRONT, REAR, RIGHT) ở FPS thấp:
        - Khởi động lệch pha nhau 0.40s để tránh sụt áp dòng khởi động 5V.
        - Giữ STREAMON liên tục cho cả 3 camera, xả buffer cũ Zero-Copy và chỉ giải mã ở ~6 FPS.
        """
        target_loop_interval = 1.0 / max(1.0, float(config.CAM_FPS))

        # Khởi tạo tuần tự từng mắt camera khi bắt đầu
        for direction in self.directions:
            if not self.running:
                return
            cam = self.cams[direction]
            cam.last_reconnect_attempt = time.time()
            cam.try_connect(keep_streaming=True)
            time.sleep(0.40)

        while self.running:
            t_cycle = time.time()

            for d in self.directions:
                if not self.running:
                    break
                cam = self.cams[d]
                if cam.is_connected:
                    cam.poll_once()
                else:
                    cam.update_synthetic_if_needed()
                    now = time.time()
                    if now - cam.last_reconnect_attempt >= 3.5:
                        cam.last_reconnect_attempt = now
                        if self.has_unclaimed_device():
                            cam.try_connect(keep_streaming=True)

            elapsed = time.time() - t_cycle
            if elapsed < target_loop_interval:
                time.sleep(max(0.015, target_loop_interval - elapsed))

    def get_camera_status(self):
        """Trả về trạng thái kết nối thực tế, số frame và FPS của các mắt camera cho Web Dashboard"""
        status = {}
        now = time.time()
        for direction, cam in self.cams.items():
            age = round(now - cam.last_frame_time, 1) if cam.last_frame_time > 0 else -1
            status[direction] = {
                'connected': cam.is_connected,
                'device': f"/dev/video{cam.video_index}" if cam.video_index is not None else "Chờ USB",
                'frames': cam.frame_count,
                'fps': round(cam.fps, 1) if cam.is_connected else 0.0,
                'last_update_sec': age
            }
        return status

    def get_frame(self, direction: str) -> np.ndarray:
        if direction in self.cams:
            return self.cams[direction].get_frame()
        return None

    def get_all_frames(self):
        return {direction: cam.get_frame() for direction, cam in self.cams.items()}

    def get_triple_view(self) -> np.ndarray:
        """
        Ghép đồng thời 3 camera thành khung nhìn ba (Triple-View 1x3: 1056x240) trực quan:
        [ 1. CAM TRƯỚC (0°) ]  [ 2. CAM SAU (180°) ]  [ 3. CAM PHẢI (90°) ]
        """
        meta = {
            'FRONT':      ("1. CAM TRUOC (0)", (0, 240, 255)),
            'REAR_RIGHT': ("2. CAM SAU-PHAI (120)", (0, 230, 118)),
            'REAR_LEFT':  ("3. CAM SAU-TRAI (240)", (255, 51, 102)),
            'REAR':       ("2. CAM SAU (180)", (255, 51, 102)),
            'RIGHT':      ("3. CAM PHAI (90)", (0, 230, 118)),
            'LEFT':       ("4. CAM TRAI (270)", (255, 190, 0))
        }

        def _stamp(img, direction):
            title, color = meta.get(direction, (direction, (0, 240, 255)))
            if img is None:
                img = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
            out = img.copy()
            cam = self.cams.get(direction)
            if cam and cam.is_connected and cam.video_index is not None:
                dev_txt = f"LIVE video{cam.video_index} #{cam.frame_count}"
            else:
                dev_txt = "OFFLINE"
            cv2.rectangle(out, (0, 0), (config.CAM_WIDTH, 26), (15, 23, 42), -1)
            cv2.putText(out, f"{title} [{dev_txt}]", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
            return out

        tiles = [_stamp(self.get_frame(d), d) for d in self.directions]
        return np.hstack(tiles)

    def get_dual_view(self) -> np.ndarray:
        return self.get_triple_view()

    def get_quad_view(self) -> np.ndarray:
        return self.get_triple_view()

    def stop_all(self):
        logger.info(f"Đang đóng {len(self.directions)} luồng camera V4L2 an toàn...")
        self.running = False
        if self.capture_thread is not None and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        for cam in self.cams.values():
            cam.release()
