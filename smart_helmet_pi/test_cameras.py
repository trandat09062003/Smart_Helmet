#!/usr/bin/env python3
"""
SMART HELMET 360 - CÔNG CỤ KIỂM TRA ĐỒNG THỜI 3 WEBCAM (TRƯỚC • SAU • PHẢI) Ở FPS THẤP
Kiểm tra và hiển thị đồng thời cả 3 mắt camera (FRONT 0°, REAR 180°, RIGHT 90°) trên khung nhìn ba 1x3
với tốc độ lấy mẫu 6 FPS (Continuous Low-FPS V4L2-MMAP) ổn định trên Raspberry Pi 4.
"""
import sys
import os
import time
import cv2
import numpy as np
from camera_manager import FastV4L2Device, scan_available_video_devices

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def scan_all_video_nodes():
    print("=" * 72)
    print(" [BƯỚC 1] QUÉT CÁC THIẾT BỊ CAMERA V4L2 TRÊN HỆ THỐNG (3 CAMERA)")
    print("=" * 72)

    available = scan_available_video_devices()
    roles = [
        "CAM 1: TRƯỚC (FRONT 0°)",
        "CAM 2: SAU (REAR 180°)",
        "CAM 3: PHẢI (RIGHT 90°)"
    ]
    if available:
        print(f"[OK] Tìm thấy {len(available)} node camera USB (/dev/v4l/by-path/):")
        for i, (path_label, idx) in enumerate(available[:3]):
            role = roles[i] if i < len(roles) else f"CAM {i+1}"
            print(f"   [{role}] -> /dev/video{idx} ({os.path.basename(path_label)})")
    else:
        print("[ERR] Không tìm thấy node camera USB nào!")
        return []

    valid_caps = [idx for _, idx in available[:3]]
    return valid_caps


def test_concurrent_3_cameras(valid_caps):
    print("\n" + "=" * 72)
    print(" [BƯỚC 2] CHẠY ĐỒNG THỜI 3 CAMERA Ở FPS THẤP (6 FPS V4L2-MMAP)")
    print("=" * 72)

    if len(valid_caps) == 0:
        print("[ERR] LỖI: Chưa có camera nào được cắm vào cổng USB của Raspberry Pi!")
        return

    directions = ['1. CAM TRUOC (0°)', '2. CAM SAU (180°)', '3. CAM PHAI (90°)']
    devs = {}

    for i in range(3):
        dir_name = directions[i]
        if i < len(valid_caps):
            idx = valid_caps[i]
            dev = FastV4L2Device(idx, 352, 240, fps=6)
            if dev.open() and dev.start_stream():
                devs[dir_name] = dev
                print(f"[OK] Đã mở luồng liên tục [{dir_name}] tại /dev/video{idx} (352x240 @ 6 FPS)")
                time.sleep(0.40)
            else:
                dev.close()
                devs[dir_name] = None
                print(f"[WARN] Không mở được [{dir_name}] tại /dev/video{idx}")
        else:
            devs[dir_name] = None
            print(f"[INFO] [{dir_name}]: Chưa cắm (Đang chờ cắm thêm)")

    print("\nĐang thu nhận đồng thời 15 chu kỳ ở tốc độ thấp (6 FPS) từ cả 3 mắt camera...")
    frames_recorded = {k: 0 for k in devs.keys()}
    latest_frames = {}
    t_start = time.time()

    for step in range(15):
        t0 = time.time()
        for name, dev in devs.items():
            if dev is not None:
                timeout = 1.80 if step == 0 else 0.60
                frame = dev.read_latest_frame(timeout=timeout, keep_streaming=True)
                if frame is not None:
                    frames_recorded[name] += 1
                    latest_frames[name] = frame
            if name not in latest_frames:
                blank = np.zeros((240, 352, 3), dtype=np.uint8)
                cv2.putText(blank, f"{name}: CHO KET NOI", (20, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
                latest_frames[name] = blank
        elapsed = time.time() - t0
        if elapsed < (1.0 / 6.0):
            time.sleep((1.0 / 6.0) - elapsed)

    t_elapsed = time.time() - t_start
    print(f"\nKẾT QUẢ ĐO 3 CAMERA ĐỒNG THỜI LOW-FPS (Thời gian đo: {t_elapsed:.2f}s):")
    for name, cnt in frames_recorded.items():
        fps = cnt / t_elapsed if t_elapsed > 0 else 0
        status = "OK (STREAM ĐỒNG THỜI MƯỢT MÀ 100%)" if cnt >= 12 else ("CHƯA CẮM" if devs[name] is None else "CHẬM")
        print(f"   • {name}: Đọc được {cnt}/15 chu kỳ -> Tốc độ: {fps:.1f} FPS [{status}]")

    for dev in devs.values():
        if dev is not None:
            dev.close()
    print("=" * 72)


if __name__ == '__main__':
    valid = scan_all_video_nodes()
    test_concurrent_3_cameras(valid)
