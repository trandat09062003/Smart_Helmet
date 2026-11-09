"""
================================================================================
SMART HELMET 360° - CHƯƠNG TRÌNH ĐIỀU KHIỂN CHÍNH TRÊN RASPBERRY PI
Đề tài Nghiên cứu Khoa học Kỹ thuật 2026
Kiến trúc Triple-Camera 360° (Chạy đồng thời 3 Camera ở FPS thấp + Phân Vùng 4 Hướng Haptic)
================================================================================
"""
import sys
import os

# Giới hạn cứng số luồng OpenMP / OpenBLAS / MKL ngay từ đầu để tránh chiếm CPU cao trên Pi 4
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import time
import signal
import threading
import logging
import cv2
import numpy as np

# Thiết lập ghi log hệ thống
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SmartHelmetMain")

import config
from haptic_controller import HapticController
from camera_manager import CameraManager
from ai_detector import AIDetector
from voice_alert import VoiceAlert
from sos_manager import SOSManager
import web_server


class SmartHelmetSystem:
    def __init__(self):
        logger.info("==================================================")
        logger.info("   ĐANG KHỞI ĐỘNG HỆ THỐNG SMART HELMET 360°      ")
        logger.info("   (CHẾ ĐỘ 3 CAMERA ĐỒNG THỜI LOW-FPS TRÊN PI 4)  ")
        logger.info("==================================================")

        self.running = True
        self.active_cams = list(getattr(config, 'ACTIVE_CAMERAS', ['FRONT', 'REAR', 'RIGHT']))
        self.state_holder = {
            'quad_frame': None,
            'quad_jpeg': None,
            'fps': float(config.CAM_FPS),
            'cpu_usage': '22',
            'latest_log': f'Khởi tạo hệ thống {len(self.active_cams)} Camera ({", ".join(self.active_cams)}) ở {config.CAM_FPS} FPS...'
        }

        # 1. Khởi tạo khối điều khiển Rung Haptic (4 hướng) & Còi Buzzer
        self.haptic = HapticController()

        # 2. Khởi tạo khối Cảnh báo Giọng nói tiếng Việt
        self.voice = VoiceAlert()

        # 3. Khởi tạo khối Quản lý SOS & Định vị GPS
        self.sos = SOSManager(self.haptic, self.voice)

        # 4. Khởi tạo khối Thu nhận hình ảnh 3 Camera đồng thời (FRONT, REAR, RIGHT)
        self.camera_mgr = CameraManager()

        # 5. Khởi tạo khối Thị giác AI (YOLOv8-Nano + Phân vùng Không gian 4 hướng)
        self.detector = AIDetector()

        # Lưu kết quả nhận diện mới nhất theo từng camera vật lý
        self.latest_obstacles = {d: [] for d in self.active_cams}
        self.obs_lock = threading.Lock()

    def start(self):
        # Khởi động đồng thời 3 camera
        self.camera_mgr.start_all()

        # Chào mừng khởi động: Rung nhẹ motor và phát âm thanh chào
        self.haptic.buzz(duration=0.15, count=1)
        self.voice.speak("Hệ thống Mũ thông minh ba camera đã sẵn sàng hoạt động.", force=True)

        # Khởi động luồng ghép video 3 camera thời gian thực (độc lập với AI)
        stream_thread = threading.Thread(target=self._stream_composer_loop, daemon=True)
        stream_thread.start()

        # Khởi động Web Server Dashboard trên luồng nền
        self._start_web_server()

        # Bắt đầu vòng lặp thị giác AI chính
        self._main_ai_loop()

    def _draw_obstacles(self, frame: np.ndarray, obstacles: list) -> np.ndarray:
        if frame is None:
            return None
        out = frame.copy()
        for obs in obstacles:
            x1, y1, x2, y2 = obs.bbox
            if obs.distance_level == 'CRITICAL':
                box_color = (0, 0, 255)
            elif obs.distance_level == 'WARNING':
                box_color = (0, 165, 255)
            else:
                box_color = (0, 255, 0)
            cv2.rectangle(out, (x1, y1), (x2, y2), box_color, 2)
            dir_badge = {'LEFT': 'TRAI', 'FRONT': 'TRUOC', 'RIGHT': 'PHAI', 'REAR': 'SAU'}.get(obs.direction, obs.direction)
            tag = f"{obs.class_name.upper()} [{dir_badge}:{obs.distance_level}]"
            if obs.is_approaching:
                tag += " (!)"
            cv2.putText(out, tag, (x1, max(38, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, box_color, 2)
        return out

    def _stream_composer_loop(self):
        """Luồng ghép 3 luồng Camera (TRƯỚC, SAU, PHẢI) ở FPS thấp và nén sẵn JPEG nhẹ tải cho Web Server"""
        frame_count = 0
        fps_start_time = time.time()
        target_interval = 1.0 / float(max(1, config.CAM_FPS))
        jpeg_quality = getattr(config, 'JPEG_QUALITY', 58)

        while self.running:
            t0 = time.time()
            frames_raw = self.camera_mgr.get_all_frames()
            with self.obs_lock:
                obs_snapshot = {k: list(v) for k, v in self.latest_obstacles.items()}

            annotated = {}
            for d in self.active_cams:
                obs_list = obs_snapshot.get(d, [])
                raw_f = frames_raw.get(d)
                annotated[d] = self._draw_obstacles(raw_f, obs_list) if obs_list else raw_f

            triple_img = self._compose_multi_view(annotated)
            self.state_holder['quad_frame'] = triple_img

            ret, jpeg = cv2.imencode('.jpg', triple_img, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            if ret:
                self.state_holder['quad_jpeg'] = jpeg.tobytes()

            frame_count += 1
            if frame_count >= 10:
                now = time.time()
                elapsed = now - fps_start_time
                if elapsed > 0:
                    self.state_holder['fps'] = frame_count / elapsed
                try:
                    with open("/proc/loadavg", "r") as f:
                        load1 = float(f.read().split()[0])
                        cpu_pct = min(99, int((load1 / 4.0) * 100))
                        self.state_holder['cpu_usage'] = str(cpu_pct)
                except Exception:
                    pass
                frame_count = 0
                fps_start_time = now

            elapsed_step = time.time() - t0
            sleep_time = max(0.025, target_interval - elapsed_step)
            time.sleep(sleep_time)

    def _start_web_server(self):
        def _run_server():
            app = web_server.create_app(
                camera_mgr=self.camera_mgr,
                haptic_ctrl=self.haptic,
                sos_mgr=self.sos,
                ai_detector=self.detector,
                state_holder=self.state_holder
            )
            import logging as py_logging
            py_logging.getLogger('werkzeug').setLevel(py_logging.ERROR)
            logger.info(f"Web Dashboard giám sát đang mở tại: http://{config.WEB_HOST}:{config.WEB_PORT}")
            app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False, use_reloader=False, threaded=True)

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

    def _main_ai_loop(self):
        """
        VÒNG LẶP XỬ LÝ AI LUÂN PHIÊN 3 CAMERA (Tần suất Cam Trước được kiểm tra gấp đôi):
        - Ưu tiên tần suất kiểm tra phía trước (FRONT) gấp đôi vì người dùng di chuyển tiến tới.
        - Kết hợp phân vùng không gian để kích hoạt chính xác cả 4 motor Haptic (TRƯỚC, PHẢI, SAU, TRÁI).
        """
        logger.info(f"Bắt đầu vòng lặp xử lý thị giác 3 Camera ({', '.join(self.active_cams)}) ở FPS thấp...")
        if len(self.active_cams) >= 3:
            schedule = [self.active_cams[0], self.active_cams[1], self.active_cams[0], self.active_cams[2]]
        elif len(self.active_cams) == 2:
            schedule = [self.active_cams[0], self.active_cams[1]]
        else:
            schedule = list(self.active_cams)
        sched_idx = 0

        while self.running:
            # Xóa vật cản cũ của camera nếu bị rút cáp
            for cam_dir in self.active_cams:
                if not self.camera_mgr.is_camera_connected(cam_dir):
                    with self.obs_lock:
                        self.latest_obstacles[cam_dir] = []

            target_cam = None
            for _ in range(len(schedule)):
                cand = schedule[sched_idx % len(schedule)]
                sched_idx += 1
                if cand in self.active_cams and self.camera_mgr.is_camera_connected(cand):
                    target_cam = cand
                    break

            if target_cam is not None:
                frame = self.camera_mgr.get_frame(target_cam)
                _, obs_list = self.detector.detect_direction(target_cam, frame)
                with self.obs_lock:
                    self.latest_obstacles[target_cam] = obs_list
                self._handle_feedback(obs_list)
                # Nghỉ 0.28s giữa mỗi lần suy luận YOLO để CPU Raspberry Pi 4 luôn mát (< 35%)
                time.sleep(0.28)
            else:
                time.sleep(0.35)

    def _handle_feedback(self, obstacles: list):
        """
        Kích hoạt motor rung (4 hướng: FRONT, RIGHT, REAR, LEFT) và giọng nói tiếng Việt
        dựa trên hướng không gian thực tế của từng vật cản.
        """
        if not obstacles:
            return

        by_dir = {}
        for obs in obstacles:
            by_dir.setdefault(obs.direction, []).append(obs)

        for spatial_dir, dir_obs in by_dir.items():
            has_critical = any(o.distance_level == 'CRITICAL' for o in dir_obs)
            has_warning = any(o.distance_level == 'WARNING' for o in dir_obs)
            has_approaching = any(o.is_approaching for o in dir_obs)

            # 1. Phản hồi xúc giác Haptic (4 kênh Motor rung)
            if has_critical or has_approaching:
                self.haptic.vibrate(spatial_dir, pattern="danger")
                log_txt = f"[{spatial_dir}] NGUY HIỂM: {dir_obs[0].vn_label} rất gần/tiệm cận! Rung mạnh."
                self.state_holder['latest_log'] = log_txt
            elif has_warning:
                self.haptic.vibrate(spatial_dir, pattern="warning")
                log_txt = f"[{spatial_dir}] CẢNH BÁO: Phát hiện {dir_obs[0].vn_label}. Rung vừa."
                self.state_holder['latest_log'] = log_txt

            # 2. Phản hồi âm thanh tiếng Việt
            self.voice.evaluate_and_alert(spatial_dir, dir_obs)

    def _compose_multi_view(self, annotated_dict: dict) -> np.ndarray:
        """
        Tạo ảnh ghép ngang 1x3 (1056x240) hiển thị đồng thời cả 3 mắt camera (TRƯỚC, SAU, PHẢI)
        kèm vạch chia phân vùng không gian (TRÁI | CHÍNH DIỆN | PHẢI) trên Camera Trước.
        """
        w = config.CAM_WIDTH
        h = config.CAM_HEIGHT
        meta = {
            'FRONT': ("1. CAM TRUOC (0°)", (0, 240, 255)),
            'REAR':  ("2. CAM SAU (180°)", (255, 51, 102)),
            'RIGHT': ("3. CAM PHAI (90°)", (0, 230, 118)),
            'LEFT':  ("4. CAM TRAI (270°)", (255, 190, 0))
        }

        def _prep(img, direction):
            title, color = meta.get(direction, (direction, (0, 240, 255)))
            if img is None:
                img = np.zeros((h, w, 3), dtype=np.uint8)
            res = img.copy()
            cam = self.camera_mgr.cams.get(direction)

            # Vẽ vạch chia phân vùng không gian Trái - Giữa - Phải cho Camera Trước
            if direction == 'FRONT' and cam and cam.is_connected:
                x_left = int(w * getattr(config, 'ZONE_LEFT_RATIO', 0.35))
                x_right = int(w * getattr(config, 'ZONE_RIGHT_RATIO', 0.67))
                cv2.line(res, (x_left, 26), (x_left, h), (100, 180, 200), 1)
                cv2.line(res, (x_right, 26), (x_right, h), (100, 180, 200), 1)
                cv2.putText(res, "TRAI", (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 190, 0), 1)
                cv2.putText(res, "TRUOC", (x_left + 26, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 240, 255), 1)
                cv2.putText(res, "PHAI", (x_right + 18, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 230, 118), 1)

            if cam and cam.is_connected and cam.video_index is not None:
                dev_tag = f"LIVE video{cam.video_index} #{cam.frame_count}"
                dot_color = (0, 230, 118) if (cam.frame_count % 2 == 0) else (0, 180, 90)
            else:
                dev_tag = "CHO USB"
                dot_color = (0, 140, 255)
            label = f"{title} [{dev_tag}]"
            cv2.rectangle(res, (0, 0), (w, 26), (15, 23, 42), -1)
            cv2.circle(res, (12, 13), 5, dot_color, -1)
            cv2.putText(res, label, (22, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.40, color, 1)
            cv2.rectangle(res, (0, 0), (w - 1, h - 1), (40, 55, 80), 1)
            return res

        tiles = [_prep(annotated_dict.get(d), d) for d in self.active_cams]
        return np.hstack(tiles)

    def stop(self):
        """Tắt hệ thống và dọn dẹp tài nguyên an toàn"""
        logger.info("Đang dừng toàn bộ hệ thống Smart Helmet 360...")
        self.running = False
        self.camera_mgr.stop_all()
        self.voice.stop()
        self.sos.stop()
        self.haptic.cleanup()
        logger.info("Đã tắt an toàn.")


def main():
    system = SmartHelmetSystem()

    def sig_handler(sig, frame):
        logger.info("Nhận tín hiệu dừng từ người dùng.")
        system.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        system.start()
    except Exception as e:
        logger.error(f"Lỗi ngoại lệ trong chương trình: {e}", exc_info=True)
        system.stop()


if __name__ == '__main__':
    main()
