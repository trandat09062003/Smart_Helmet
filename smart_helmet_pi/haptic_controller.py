"""
SMART HELMET 360 - BỘ ĐIỀU KHIỂN RUNG XÚC GIÁC (HAPTIC) & BUZZER
Hỗ trợ cả chế độ:
  1. PARALLEL: 4 Motor rung mắc song song điều khiển bằng 1 chân GPIO 17 (Pin 11) qua 1 Transistor 2N2222
  2. DISCRETE: 4 Motor rung độc lập (Trước, Phải, Sau, Trái)
"""
import time
import threading
import logging
import config

logger = logging.getLogger("HapticController")

# Kiểm tra thư viện GPIO (RPi.GPIO hoặc Mock trên PC)
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO_AVAILABLE = True
    logger.info("Đã kết nối thư viện RPi.GPIO phần cứng thành công.")
except Exception as e:
    logger.warning(f"Không có phần cứng RPi.GPIO ({e}). Kích hoạt chế độ mô phỏng (Mock Mode).")


class HapticController:
    def __init__(self):
        self.is_hardware = GPIO_AVAILABLE
        self.active_status = {
            'FRONT': False,
            'RIGHT': False,
            'REAR':  False,
            'LEFT':  False,
            'BUZZER': False
        }
        self._lock = threading.Lock()

        if self.is_hardware:
            try:
                # Khởi tạo các chân GPIO motor duy nhất (tránh setup trùng chân khi chạy song song)
                unique_pins = set(config.MOTOR_PINS.values())
                for pin in unique_pins:
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                
                # Khởi tạo chân Còi Buzzer
                GPIO.setup(config.PIN_BUZZER, GPIO.OUT, initial=GPIO.LOW)
                
                mode_str = "4 Motor Rung Mắc Song Song (1x 2N2222 tại GPIO 17)" if config.MOTOR_MODE == 'PARALLEL' else "4 Motor Rung Độc Lập"
                logger.info(f"Khởi tạo GPIO thành công. Chế độ: {mode_str}.")
            except Exception as e:
                logger.error(f"Lỗi cấu hình GPIO: {e}. Chuyển sang mô phỏng.")
                self.is_hardware = False

    def _set_pin(self, target, state: bool):
        with self._lock:
            self.active_status[target] = state
            
            if self.is_hardware:
                try:
                    if target == 'BUZZER':
                        GPIO.output(config.PIN_BUZZER, GPIO.HIGH if state else GPIO.LOW)
                    else:
                        if config.MOTOR_MODE == 'PARALLEL':
                            # Nếu bất kỳ hướng nào bật -> Bật GPIO 17
                            any_motor_on = any(self.active_status[d] for d in ['FRONT', 'RIGHT', 'REAR', 'LEFT'])
                            GPIO.output(config.PIN_MOTOR_PARALLEL, GPIO.HIGH if any_motor_on else GPIO.LOW)
                        else:
                            pin = config.MOTOR_PINS.get(target)
                            if pin is not None:
                                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
                except Exception as e:
                    logger.error(f"Lỗi điều khiển GPIO {target}: {e}")

    def vibrate(self, direction: str, pattern: str = "warning", duration: float = 0.3):
        """
        Kích hoạt rung haptic theo hướng và mẫu rung (Chạy trên luồng nền để không nghẽn AI)
        - direction: 'FRONT', 'RIGHT', 'REAR', 'LEFT'
        - pattern: 'notice' (rung nhẹ 1 nhịp), 'warning' (rung 2 nhịp), 'danger' (rung dồn dập 3 nhịp)
        """
        if direction not in config.MOTOR_PINS:
            return

        def _vibe_worker():
            try:
                if pattern == "notice":
                    self._set_pin(direction, True)
                    time.sleep(0.15)
                    self._set_pin(direction, False)

                elif pattern == "warning":
                    # Rung 2 nhịp ngắt quãng
                    for _ in range(2):
                        self._set_pin(direction, True)
                        time.sleep(0.18)
                        self._set_pin(direction, False)
                        time.sleep(0.10)

                elif pattern == "danger":
                    # Rung dồn dập 3 nhịp mạnh
                    for _ in range(3):
                        self._set_pin(direction, True)
                        time.sleep(0.22)
                        self._set_pin(direction, False)
                        time.sleep(0.08)
                else:
                    self._set_pin(direction, True)
                    time.sleep(duration)
                    self._set_pin(direction, False)
            finally:
                self._set_pin(direction, False)

        t = threading.Thread(target=_vibe_worker, daemon=True)
        t.start()

    def buzz(self, duration: float = 0.2, count: int = 1):
        """Kích hoạt còi Buzzer cảnh báo hoặc SOS"""
        def _buzz_worker():
            try:
                for _ in range(count):
                    self._set_pin('BUZZER', True)
                    time.sleep(duration)
                    self._set_pin('BUZZER', False)
                    time.sleep(0.10)
            finally:
                self._set_pin('BUZZER', False)

        t = threading.Thread(target=_buzz_worker, daemon=True)
        t.start()

    def vibrate_all(self, duration: float = 0.5):
        """Rung toàn bộ cụm motor (Dùng khi cảnh báo khẩn cấp hoặc khởi động hệ thống)"""
        self.vibrate('FRONT', pattern="danger", duration=duration)

    def get_status(self):
        """Lấy trạng thái hiện tại của các motor để hiển thị lên Web Dashboard"""
        with self._lock:
            return self.active_status.copy()

    def cleanup(self):
        """Dọn dẹp GPIO khi dừng chương trình"""
        for direction in config.MOTOR_PINS.keys():
            self._set_pin(direction, False)
        self._set_pin('BUZZER', False)
        if self.is_hardware:
            try:
                GPIO.cleanup()
                logger.info("Đã giải phóng an toàn tài nguyên GPIO.")
            except Exception as e:
                logger.error(f"Lỗi khi cleanup GPIO: {e}")
