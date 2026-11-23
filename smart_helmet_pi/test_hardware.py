#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SMART HELMET 360° - KỊCH BẢN KIỂM TRA PHẦN CỨNG TOÀN DIỆN (HARDWARE DIAGNOSTIC)
Chạy trực tiếp trên Raspberry Pi 4 để test nhanh các chân nối:
  1. PIN 11 (GPIO 17): Cụm 4 Động cơ rung mắc song song (Transistor 2N2222)
  2. PIN 18 (GPIO 24): Còi Buzzer Active 5V (Transistor S8050)
  3. PIN 22 (GPIO 25): Nút bấm khẩn cấp SOS (Đã bỏ tụ lọc, PULL_UP nội)
  4. PIN 8 & 10 (UART0): Module GPS NEO-6M (/dev/serial0 hoặc /dev/ttyAMA0)
================================================================================
"""
import sys
import os
import time

# Chuyển thư mục hiện tại để import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

print("=" * 70)
print("     CÔNG CỤ KIỂM TRA PHẦN CỨNG MŨ BẢO HIỂM THÔNG MINH (PI 4)     ")
print("=" * 70)

# 1. Thử nạp thư viện RPi.GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_OK = True
except ImportError:
    GPIO_OK = False
    print(" [CẢNH BÁO] Không tìm thấy thư viện RPi.GPIO. Bạn đang chạy trên PC?")
    print("            Hãy chạy script này trực tiếp trên Raspberry Pi 4.")

def setup_gpio():
    if not GPIO_OK:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.PIN_MOTOR_PARALLEL, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(config.PIN_BUZZER, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(config.PIN_BUTTON_SOS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def test_motor():
    print("\n>>> [1/4] ĐANG TEST CỤM 4 MOTOR RUNG SONG SONG (PIN 11 / GPIO 17)...")
    if not GPIO_OK:
        print("    [MÔ PHỎNG] Bật GPIO 17 -> Rung 4 motor trong 1.5 giây...")
        time.sleep(1.5)
        print("    [MÔ PHỎNG] Tắt GPIO 17.")
        return

    print("    -> Kích hoạt mức HIGH trong 1.2 giây (Cả 4 motor phải rung mạnh)...")
    GPIO.output(config.PIN_MOTOR_PARALLEL, GPIO.HIGH)
    time.sleep(1.2)
    GPIO.output(config.PIN_MOTOR_PARALLEL, GPIO.LOW)
    print("    -> Hoàn tất test motor.")

def test_buzzer():
    print("\n>>> [2/4] ĐANG TEST CÒI ACTIVE BUZZER 5V (PIN 18 / GPIO 24)...")
    if not GPIO_OK:
        print("    [MÔ PHỎNG] Kêu 3 tiếng bíp ngắn...")
        time.sleep(1.0)
        return

    print("    -> Kích còi kêu 3 tiếng bíp ngắn...")
    for i in range(3):
        GPIO.output(config.PIN_BUZZER, GPIO.HIGH)
        time.sleep(0.18)
        GPIO.output(config.PIN_BUZZER, GPIO.LOW)
        time.sleep(0.12)
    print("    -> Hoàn tất test còi.")

def test_sos():
    print("\n>>> [3/4] ĐANG TEST NÚT BẤM KHẨN CẤP SOS (PIN 22 / GPIO 25)...")
    print("    -> Hãy BẤM THỬ NÚT SOS trên mũ trong vòng 10 giây tới...")
    start_t = time.time()
    pressed = False

    while time.time() - start_t < 10.0:
        if GPIO_OK:
            state = GPIO.input(config.PIN_BUTTON_SOS)
            if state == GPIO.LOW:  # Nhấn dập xuống GND Pin 20
                pressed = True
                print("\n    [THÀNH CÔNG] -> ĐÃ PHÁT HIỆN BẤM NÚT SOS (Mức 0/LOW)!")
                # Rung nhẹ và kêu bíp xác nhận
                GPIO.output(config.PIN_MOTOR_PARALLEL, GPIO.HIGH)
                GPIO.output(config.PIN_BUZZER, GPIO.HIGH)
                time.sleep(0.3)
                GPIO.output(config.PIN_MOTOR_PARALLEL, GPIO.LOW)
                GPIO.output(config.PIN_BUZZER, GPIO.LOW)
                break
        time.sleep(0.05)
        sys.stdout.write(".")
        sys.stdout.flush()

    if not pressed:
        print("\n    [HẾT GIỜ] Không phát hiện bấm nút SOS trong 10 giây.")

def test_gps():
    print("\n>>> [4/4] ĐANG TEST MODULE GPS NEO-6M (PIN 8 & 10 UART0)...")
    ports = [config.GPS_SERIAL_PORT, "/dev/serial0", "/dev/ttyAMA0", "/dev/ttyUSB0"]
    found_port = None
    for p in ports:
        if os.path.exists(p):
            found_port = p
            break

    if not found_port:
        print("    [CẢNH BÁO] Không tìm thấy cổng UART (/dev/serial0 hoặc /dev/ttyAMA0).")
        print("               Hãy kiểm tra xem đã bật UART bằng `sudo raspi-config` chưa.")
        return

    print(f"    -> Đang mở cổng {found_port} ở tốc độ 9600 baud (chờ 5 giây đọc dữ liệu)...")
    try:
        import serial
        with serial.Serial(found_port, baudrate=config.GPS_BAUDRATE, timeout=1.0) as ser:
            t0 = time.time()
            got_data = False
            while time.time() - t0 < 5.0:
                line = ser.readline().decode('ascii', errors='replace').strip()
                if line.startswith('$GP') or line.startswith('$GN'):
                    print(f"       Nhận được: {line[:60]}...")
                    got_data = True
                    break
            if got_data:
                print("    [THÀNH CÔNG] Module GPS đang truyền bản tin NMEA bình thường!")
            else:
                print("    [LƯU Ý] Không nhận được bản tin NMEA. Kiểm tra dây RX/TX (đấu chéo).")
    except Exception as e:
        print(f"    [LỖI] Không thể đọc serial: {e}")

def main():
    if GPIO_OK:
        setup_gpio()

    while True:
        print("\n" + "-" * 50)
        print("CHỌN MỤC CẦN KIỂM TRA:")
        print("  1. Test Cụm 4 Động cơ rung // (GPIO 17 / Pin 11)")
        print("  2. Test Còi Buzzer (GPIO 24 / Pin 18)")
        print("  3. Test Nút bấm SOS (GPIO 25 / Pin 22)")
        print("  4. Test Module GPS NEO-6M (UART Pins 8 & 10)")
        print("  5. Chạy toàn bộ bài test tự động (1 -> 4)")
        print("  0. Thoát chương trình")
        print("-" * 50)

        choice = input("Nhập lựa chọn của bạn (0-5): ").strip()

        if choice == '1':
            test_motor()
        elif choice == '2':
            test_buzzer()
        elif choice == '3':
            test_sos()
        elif choice == '4':
            test_gps()
        elif choice == '5':
            test_motor()
            time.sleep(0.5)
            test_buzzer()
            time.sleep(0.5)
            test_sos()
            time.sleep(0.5)
            test_gps()
        elif choice == '0':
            print("Đang thoát...")
            break
        else:
            print("Lựa chọn không hợp lệ!")

    if GPIO_OK:
        GPIO.cleanup()
        print("[OK] Đã dọn dẹp GPIO.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã hủy bởi người dùng.")
        if GPIO_OK:
            GPIO.cleanup()
