"""
================================================================================
SMART HELMET 360° - CHƯƠNG TRÌNH ĐIỀU KHIỂN CHÍNH TRÊN RASPBERRY PI
Đề tài Nghiên cứu Khoa học Kỹ thuật 2026
Mũ bảo hiểm thông minh 4 camera 360 độ hỗ trợ người khiếm thị
================================================================================
"""
import sys
import os
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
        logger.info("==================================================")

        self.running = True
        self.state_holder = {
            'quad_frame': None,
            'fps': 15.0,
            'cpu_usage': '25',
            'latest_log': 'Khởi tạo hệ thống...'
        }

        # 1. Khởi tạo khối điều khiển Rung Haptic & Còi Buzzer
        self.haptic = HapticController()

        # 2. Khởi tạo khối Cảnh báo Giọng nói tiếng Việt
        self.voice = VoiceAlert()

        # 3. Khởi tạo khối Quản lý SOS & Định vị GPS
        self.sos = SOSManager(self.haptic, self.voice)

        # 4. Khởi tạo khối Thu nhận hình ảnh 4 Camera đa luồng
        self.camera_mgr = CameraManager()

        # 5. Khởi tạo khối Thị giác AI (YOLOv8-Nano)
        self.detector = AIDetector()

        # Biến điều phối lập lịch AI so le để tối ưu tải CPU trên Pi
        self.peripheral_directions = ['RIGHT', 'REAR', 'LEFT']
        self.peripheral_turn = 0

    def start(self):
        # Khởi động camera
        self.camera_mgr.start_all()

        # Chào mừng khởi động: Rung nhẹ 4 motor và phát âm thanh chào
        self.haptic.buzz(duration=0.15, count=1)
        self.voice.speak("Hệ thống Mũ thông minh 360 độ đã sẵn sàng hoạt động.", force=True)

        # Khởi động Web Server Dashboard trên luồng nền
        self._start_web_server()

        # Bắt đầu vòng lặp thị giác AI chính
        self._main_ai_loop()

    def _start_web_server(self):
        def _run_server():
            app = web_server.create_app(
                camera_mgr=self.camera_mgr,
                haptic_ctrl=self.haptic,
                sos_mgr=self.sos,
                ai_detector=self.detector,
                state_holder=self.state_holder
            )
            # Tắt logging mặc định của werkzeug để tránh spam màn hình console
            import logging as py_logging
            py_logging.getLogger('werkzeug').setLevel(py_logging.ERROR)
            logger.info(f"🌐 Web Dashboard giám sát đang mở tại: http://{config.WEB_HOST}:{config.WEB_PORT}")
            app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False, use_reloader=False)

        server_thread = threading.Thread(target=_run_server, daemon=True)
        server_thread.start()

    def _main_ai_loop(self):
        """
        VÒNG LẶP XỬ LÝ AI LẬP LỊCH THÔNG MINH (INTELLIGENT INTERLEAVED SCHEDULER):
        - Hướng TRƯỚC (Front) là hướng di chuyển chính: Quét AI ở mọi chu kỳ.
        - 3 Hướng còn lại (PHẢI, SAU, TRÁI): Quét luân phiên so le từng chu kỳ.
        Cách lập lịch này giúp Pi 4/5 đạt tốc độ mượt mà 15-20 FPS mà không bị quá nhiệt!
        """
        frame_count = 0
        fps_start_time = time.time()

        logger.info("🚀 Bắt đầu vòng lặp xử lý thị giác 360° thời gian thực...")

        while self.running:
            loop_start = time.time()

            # 1. Lấy khung hình mới nhất từ 4 camera
            frames_raw = self.camera_mgr.get_all_frames()

            # 2. Xử lý AI hướng TRƯỚC (Ưu tiên số 1)
            f_frame, f_obs = self.detector.detect_direction('FRONT', frames_raw.get('FRONT'))

            # 3. Xử lý AI hướng ngoại vi luân phiên (RIGHT -> REAR -> LEFT)
            active_dir = self.peripheral_directions[self.peripheral_turn]
            self.peripheral_turn = (self.peripheral_turn + 1) % len(self.peripheral_directions)

            other_frames_annotated = {}
            for d in self.peripheral_directions:
                if d == active_dir:
                    ann_frame, obs_list = self.detector.detect_direction(d, frames_raw.get(d))
                    other_frames_annotated[d] = ann_frame
                    # Kích hoạt phản hồi cho hướng ngoại vi đang quét
                    self._handle_feedback(d, obs_list)
                else:
                    # Giữ nguyên khung hình hiện tại không chạy AI để tiết kiệm CPU
                    other_frames_annotated[d] = frames_raw.get(d)

            # 4. Kích hoạt phản hồi xúc giác & âm thanh cho hướng TRƯỚC
            self._handle_feedback('FRONT', f_obs)

            # 5. Ghép 4 khung hình đã vẽ Bounding Box để truyền lên Web Dashboard
            quad = self._compose_quad_view(
                f_frame,
                other_frames_annotated.get('RIGHT'),
                other_frames_annotated.get('REAR'),
                other_frames_annotated.get('LEFT')
            )
            self.state_holder['quad_frame'] = quad

            # 6. Đo lường tốc độ khung hình FPS
            frame_count += 1
            if frame_count >= 15:
                now = time.time()
                elapsed = now - fps_start_time
                if elapsed > 0:
                    current_fps = frame_count / elapsed
                    self.state_holder['fps'] = current_fps
                frame_count = 0
                fps_start_time = now

            # Nghỉ ngắn giữa các chu kỳ
            time.sleep(0.01)

    def _handle_feedback(self, direction: str, obstacles: list):
        """Kích hoạt motor rung và giọng nói khi phát hiện chướng ngại vật"""
        if not obstacles:
            return

        has_critical = any(o.distance_level == 'CRITICAL' for o in obstacles)
        has_warning = any(o.distance_level == 'WARNING' for o in obstacles)
        has_approaching = any(o.is_approaching for o in obstacles)

        # 1. Phản hồi xúc giác Haptic (Motor rung)
        if has_critical or has_approaching:
            self.haptic.vibrate(direction, pattern="danger")
            log_txt = f"[{direction}] NGUY HIỂM: Vật cản rất gần/tiệm cận! Rung mạnh."
            self.state_holder['latest_log'] = log_txt
        elif has_warning:
            self.haptic.vibrate(direction, pattern="warning")
            log_txt = f"[{direction}] CẢNH BÁO: Phát hiện vật cản. Rung vừa."
            self.state_holder['latest_log'] = log_txt

        # 2. Phản hồi âm thanh tiếng Việt (Qua bộ lọc Debounce thông minh)
        self.voice.evaluate_and_alert(direction, obstacles)

    def _compose_quad_view(self, f, r, b, l):
        """Tạo ảnh ghép 2x2 chuyên nghiệp phục vụ trình chiếu"""
        def _prep(img, label, color):
            if img is None:
                img = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
            res = img.copy()
            cv2.rectangle(res, (0, 0), (200, 32), (15, 23, 42), -1)
            cv2.putText(res, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            return res

        f_img = _prep(f, "TRUOC (Front 0°)", (0, 240, 255))
        r_img = _prep(r, "PHAI (Right 90°)", (0, 230, 118))
        l_img = _prep(l, "TRAI (Left 270°)", (255, 179, 0))
        b_img = _prep(b, "SAU (Rear 180°)", (255, 51, 102))

        top = np.hstack([f_img, r_img])
        bot = np.hstack([l_img, b_img])
        return np.vstack([top, bot])

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

    # Bắt tín hiệu ngắt (Ctrl+C hoặc lệnh tắt dịch vụ Linux)
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
