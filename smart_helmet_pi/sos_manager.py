"""
SMART HELMET 360 - BỘ QUẢN LÝ TÍN HIỆU CỨU HỘ KHẨN CẤP (SOS) & ĐỊNH VỊ GPS
Theo dõi nút bấm khẩn cấp trên mũ (đã bỏ tụ lọc, dùng PULL_UP nội), kích hoạt còi báo và gửi vị trí tới người thân
"""
import time
import os
import threading
import logging
import requests
import config

logger = logging.getLogger("SOSManager")


class SOSManager:
    def __init__(self, haptic_ctrl, voice_alert):
        self.haptic_ctrl = haptic_ctrl
        self.voice_alert = voice_alert
        self.is_sos_active = False
        self.last_sos_time = 0
        self.gps_coords = {'lat': config.DEFAULT_LAT, 'lon': config.DEFAULT_LON}
        self.running = True

        self._init_gpio_button()
        self._start_gps_listener()

    def _init_gpio_button(self):
        """Khởi tạo nút bấm khẩn cấp trên chân GPIO 25 với điện trở kéo lên Pull-Up (Đã bỏ tụ lọc)"""
        if self.haptic_ctrl.is_hardware:
            try:
                import RPi.GPIO as GPIO
                GPIO.setup(config.PIN_BUTTON_SOS, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                # Chạy luồng riêng kiểm tra nhấn giữ nút (> 0.8s để chống bấm nhầm)
                t = threading.Thread(target=self._button_poll_loop, daemon=True)
                t.start()
                logger.info(f"Nút bấm SOS đã gắn vào GPIO {config.PIN_BUTTON_SOS} (PULL_UP nội, chống rung) thành công.")
            except Exception as e:
                logger.warning(f"Lỗi khởi tạo nút bấm SOS: {e}")

    def _button_poll_loop(self):
        """Lắng nghe sự kiện bấm giữ nút SOS (ĐÃ BỎ TỤ LỌC, dùng debounce phần mềm)"""
        import RPi.GPIO as GPIO
        press_start = 0
        while self.running:
            try:
                # Nút nhấn nối GND -> Khi nhấn chân GPIO về mức LOW (0)
                if GPIO.input(config.PIN_BUTTON_SOS) == GPIO.LOW:
                    if press_start == 0:
                        press_start = time.time()
                    elif time.time() - press_start >= 0.8:
                        # Đã giữ nút đủ 0.8 giây -> Kích hoạt SOS!
                        self.trigger_sos(source="NUT_BAM_VAT_LY")
                        press_start = 0
                        time.sleep(2.5)  # Chờ nhả nút
                else:
                    press_start = 0
            except Exception:
                pass
            time.sleep(0.04)

    def _start_gps_listener(self):
        """Đọc tọa độ NMEA từ module GPS NEO-6M qua UART phần cứng (/dev/serial0 hoặc /dev/ttyAMA0)"""
        def _gps_worker():
            # Thử các cổng serial theo thứ tự ưu tiên
            ports_to_try = [config.GPS_SERIAL_PORT, "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyUSB0", "/dev/ttyS0"]
            ser = None
            for p in ports_to_try:
                if os.path.exists(p):
                    try:
                        import serial
                        ser = serial.Serial(p, baudrate=config.GPS_BAUDRATE, timeout=1)
                        logger.info(f"Đã kết nối module GPS NEO-6M trên cổng {p} thành công.")
                        break
                    except Exception:
                        ser = None

            if not ser:
                logger.info("Chưa phát hiện GPS trên cổng Serial. Sử dụng tọa độ GPS mẫu.")
                return

            try:
                while self.running:
                    line = ser.readline().decode('ascii', errors='replace').strip()
                    if line.startswith('$GPRMC') or line.startswith('$GNRMC'):
                        parts = line.split(',')
                        if len(parts) > 6 and parts[2] == 'A':
                            # Parse GPS fix
                            raw_lat, lat_dir = parts[3], parts[4]
                            raw_lon, lon_dir = parts[5], parts[6]
                            if raw_lat and raw_lon:
                                lat_deg = float(raw_lat[:2]) + float(raw_lat[2:]) / 60.0
                                lon_deg = float(raw_lon[:3]) + float(raw_lon[2:]) / 60.0
                                if lat_dir == 'S': lat_deg = -lat_deg
                                if lon_dir == 'W': lon_deg = -lon_deg
                                self.gps_coords = {'lat': round(lat_deg, 6), 'lon': round(lon_deg, 6)}
            except Exception as e:
                logger.warning(f"Lỗi đọc dữ liệu GPS: {e}")
            finally:
                if ser:
                    ser.close()

        t = threading.Thread(target=_gps_worker, daemon=True)
        t.start()

    def trigger_sos(self, source: str = "THU_CONG"):
        """Kích hoạt chuỗi hành động khẩn cấp SOS"""
        now = time.time()
        if now - self.last_sos_time < 5.0:
            return  # Tránh spam kích hoạt liên tiếp

        self.last_sos_time = now
        self.is_sos_active = True
        logger.warning(f"[CẢNH BÁO SOS ĐƯỢC KÍCH HOẠT TỪ: {source}] 🚨")

        # 1. Bật còi báo động khẩn cấp (4 tiếng bíp dồn dập)
        self.haptic_ctrl.buzz(duration=0.3, count=4)

        # 2. Rung toàn bộ cụm 4 motor để báo cho người dùng biết hệ thống đã kích hoạt cứu hộ
        self.haptic_ctrl.vibrate_all(duration=1.2)

        # 3. Đọc giọng nói xác nhận
        self.voice_alert.speak("Đã kích hoạt chế độ cứu hộ SOS, đang gửi vị trí tới người thân.", force=True)

        # 4. Gửi tin nhắn khẩn cấp qua Telegram Bot (nếu có cấu hình)
        threading.Thread(target=self._send_telegram_alert, daemon=True).start()

    def _send_telegram_alert(self):
        """Gửi tọa độ GPS và đường dẫn Google Maps tới điện thoại người thân qua Telegram"""
        lat = self.gps_coords['lat']
        lon = self.gps_coords['lon']
        maps_link = f"https://www.google.com/maps?q={lat},{lon}"

        msg = (
            "*CẢNH BÁO KHẨN CẤP TỪ MŨ THÔNG MINH SMART HELMET* 🚨\n\n"
            "Người dùng vừa nhấn nút SOS khẩn cấp trên mũ!\n"
            f"*Tọa độ hiện tại:* `{lat}, {lon}`\n"
            f"*Xem vị trí trên Google Maps:* {maps_link}\n"
            f"*Thời gian:* {time.strftime('%H:%M:%S %d/%m/%Y')}\n\n"
            "Vui lòng liên lạc hoặc kiểm tra an toàn ngay!"
        )

        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            try:
                url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "text": msg,
                    "parse_mode": "Markdown"
                }
                requests.post(url, json=payload, timeout=5)
                logger.info("Đã gửi tin nhắn SOS tới Telegram người thân thành công.")
            except Exception as e:
                logger.error(f"Lỗi gửi tin nhắn Telegram: {e}")
        else:
            logger.info(f"Mô phỏng tin nhắn SOS: {msg}")

    def reset_sos(self):
        self.is_sos_active = False

    def stop(self):
        self.running = False
