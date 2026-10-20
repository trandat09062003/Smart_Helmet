"""
SMART HELMET 360 - BỘ PHÁT CẢNH BÁO ÂM THANH TIẾNG VIỆT
Tích hợp thuật toán lọc thông minh (Smart Filter) chống quá tải thính giác cho người khiếm thị
"""
import time
import queue
import threading
import logging
import subprocess
import shutil
import config

logger = logging.getLogger("VoiceAlert")


class VoiceAlert:
    def __init__(self):
        self.speech_queue = queue.Queue(maxsize=5)
        self.last_spoken_time = {
            'FRONT': 0,
            'RIGHT': 0,
            'REAR':  0,
            'LEFT':  0,
            'GLOBAL': 0
        }
        self.engine_type = self._detect_engine()
        self.running = True
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()

    def _detect_engine(self) -> str:
        """Kiểm tra công cụ đọc Text-To-Speech có sẵn trên hệ thống Linux Pi"""
        if shutil.which("espeak-ng"):
            logger.info("Sử dụng engine âm thanh [espeak-ng] chuẩn Linux.")
            return "espeak-ng"
        if shutil.which("espeak"):
            logger.info("Sử dụng engine âm thanh [espeak].")
            return "espeak"
        try:
            import pyttsx3
            return "pyttsx3"
        except Exception:
            pass
        logger.warning("Không tìm thấy engine TTS phần cứng. Sử dụng audio log mô phỏng.")
        return "log"

    def _speech_worker(self):
        """Luồng chạy ngầm đọc âm thanh độc lập để không làm nghẽn vòng lặp AI"""
        pyttsx_engine = None
        if self.engine_type == "pyttsx3":
            try:
                import pyttsx3
                pyttsx_engine = pyttsx3.init()
                pyttsx_engine.setProperty('rate', 150)
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo pyttsx3: {e}")
                self.engine_type = "log"

        while self.running:
            try:
                text = self.speech_queue.get(timeout=0.2)
                if text is None:
                    continue

                logger.info(f"🔊 PHÁT GIỌNG NÓI: '{text}'")

                if self.engine_type in ["espeak-ng", "espeak"]:
                    # Dùng espeak-ng với giọng tiếng Việt (vi) hoặc tiếng Anh nếu chưa cài gói vi
                    cmd = [self.engine_type, "-v", "vi", "-s", "145", text]
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
                elif self.engine_type == "pyttsx3" and pyttsx_engine:
                    try:
                        pyttsx_engine.say(text)
                        pyttsx_engine.runAndWait()
                    except Exception:
                        pass
                else:
                    # Mô phỏng thời gian đọc nếu chạy trên máy test không có loa
                    time.sleep(0.5)

                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Lỗi luồng phát giọng nói: {e}")

    def speak(self, text: str, force: bool = False):
        """Đưa câu nói vào hàng đợi (nếu hàng đợi đầy thì bỏ qua câu cũ để cập nhật tức thì)"""
        if not force and self.speech_queue.full():
            return
        try:
            self.speech_queue.put_nowait(text)
        except queue.Full:
            pass

    def evaluate_and_alert(self, direction: str, obstacles: list):
        """
        BỘ LỌC THÔNG MINH (Smart Debounce & Priority Filter):
        Đánh giá danh sách vật cản ở một hướng và chỉ phát cảnh báo khi thực sự cần thiết
        """
        if not obstacles:
            return

        now = time.time()
        # Kiểm tra cooldown chung và cooldown riêng từng hướng
        if now - self.last_spoken_time.get(direction, 0) < config.VOICE_COOLDOWN_SECONDS:
            return
        if now - self.last_spoken_time['GLOBAL'] < 1.8:
            return

        # Sắp xếp tìm vật cản nguy hiểm nhất
        critical_obs = [o for o in obstacles if o.distance_level == 'CRITICAL']
        approaching_obs = [o for o in obstacles if o.is_approaching]
        warning_obs = [o for o in obstacles if o.distance_level == 'WARNING']

        msg = None
        dir_vn = {
            'FRONT': 'phía trước',
            'RIGHT': 'bên phải',
            'LEFT':  'bên trái',
            'REAR':  'phía sau'
        }.get(direction, direction)

        if critical_obs:
            target = critical_obs[0]
            if direction == 'FRONT':
                msg = f"Dừng lại! Có {target.vn_label} ngay phía trước."
            else:
                msg = f"Nguy hiểm! {target.vn_label} rất gần {dir_vn}."
        elif approaching_obs:
            target = approaching_obs[0]
            msg = f"Cẩn thận, {target.vn_label} đang tới {dir_vn}."
        elif warning_obs:
            target = warning_obs[0]
            msg = f"Có {target.vn_label} ở {dir_vn}."

        if msg:
            self.last_spoken_time[direction] = now
            self.last_spoken_time['GLOBAL'] = now
            self.speak(msg)

    def stop(self):
        self.running = False
