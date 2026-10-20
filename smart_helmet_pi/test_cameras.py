#!/usr/bin/env python3
"""
SMART HELMET 360 - CÔNG CỤ KIỂM TRA ĐỒNG THỜI 4 WEBCAM QUA USB HUB
Dùng để chẩn đoán cổng USB1, USB2, USB3, USB4 và đo tốc độ khung hình (FPS) trên Ubuntu 22.04
"""
import sys
import os
import time
import glob
import cv2
import numpy as np

# Đảm bảo in tiếng Việt chuẩn trên mọi terminal
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def scan_all_video_nodes():
    print("=" * 65)
    print(" 🔍 [BƯỚC 1] QUÉT CÁC THIẾT BỊ CAMERA V4L2 TRÊN HỆ THỐNG")
    print("=" * 65)
    
    # 1. Kiểm tra /dev/v4l/by-path/
    by_paths = sorted(glob.glob("/dev/v4l/by-path/*index0"))
    if by_paths:
        print(f"✅ Tìm thấy {len(by_paths)} camera qua cổng vật lý USB (/dev/v4l/by-path/):")
        for i, p in enumerate(by_paths):
            print(f"   [Cổng {i+1}] -> {p}")
    else:
        print("ℹ️ Không tìm thấy /dev/v4l/by-path/, chuyển sang quét /dev/video*")

    # 2. Kiểm tra các node /dev/video*
    nodes = sorted(glob.glob("/dev/video[0-9]*"), key=lambda x: int(x.replace("/dev/video", "")))
    print(f"\nDanh sách các node /dev/video tìm thấy: {[os.path.basename(n) for n in nodes]}")
    
    valid_caps = []
    for node in nodes:
        idx = int(node.replace("/dev/video", ""))
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            # Thử đọc 1 frame
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                valid_caps.append(idx)
                print(f"   ✓ /dev/video{idx}: Khả dụng (Đọc thành công frame {frame.shape[1]}x{frame.shape[0]})")
            else:
                print(f"   - /dev/video{idx}: Bỏ qua (Node metadata hoặc không có stream)")
        else:
            print(f"   x /dev/video{idx}: Không mở được")

    print(f"\n=> TỔNG CỘNG CÓ {len(valid_caps)} MẮT CAMERA THỰC SỰ HOẠT ĐỘNG: {valid_caps}")
    return valid_caps


def test_concurrent_4_cameras(valid_caps):
    print("\n" + "=" * 65)
    print(" 📹 [BƯỚC 2] KIỂM TRA MỞ ĐỒNG THỜI 4 CAMERA QUA 1 USB HUB")
    print("=" * 65)

    if len(valid_caps) == 0:
        print("❌ LỖI: Không tìm thấy camera nào! Vui lòng kiểm tra cáp USB cắm vào Pi.")
        return

    # Gán 4 hướng
    directions = ['1. TRƯỚC (USB1)', '2. PHẢI (USB2)', '3. SAU (USB3)', '4. TRÁI (USB4)']
    caps = {}

    for i in range(4):
        dir_name = directions[i]
        if i < len(valid_caps):
            idx = valid_caps[i]
            cap = cv2.VideoCapture(idx)
            # Bắt buộc MJPEG để tránh lỗi "No space left on device" trên USB 2.0/3.0
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 15)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if cap.isOpened():
                caps[dir_name] = cap
                print(f"✅ Đã mở [{dir_name}] tại /dev/video{idx} (640x480 MJPEG)")
            else:
                caps[dir_name] = None
                print(f"⚠️ Không mở được [{dir_name}] tại /dev/video{idx}")
        else:
            caps[dir_name] = None
            print(f"ℹ️ [{dir_name}]: Chưa cắm (Đang chờ cắm vào Hub)")

    print("\n🚀 Đang tiến hành đọc liên tục 30 frame đồng thời từ 4 camera...")
    frames_recorded = {k: 0 for k in caps.keys()}
    t_start = time.time()

    latest_frames = {}
    for step in range(30):
        for name, cap in caps.items():
            if cap is not None:
                ret, frame = cap.read()
                if ret and frame is not None:
                    frames_recorded[name] += 1
                    latest_frames[name] = frame
            else:
                # Tạo ảnh mẫu giả lập
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, f"{name}: CHUA KET NOI", (40, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                latest_frames[name] = blank
        time.sleep(0.02)

    t_elapsed = time.time() - t_start
    print(f"\n📊 KẾT QUẢ ĐO TỐC ĐỘ (Thời gian đo: {t_elapsed:.2f}s):")
    for name, cnt in frames_recorded.items():
        fps = cnt / t_elapsed if t_elapsed > 0 else 0
        status = "OK (MƯỢT MÀ)" if cnt > 15 else ("CHƯA CẮM" if caps[name] is None else "BỊ NGHẼN/GIẬT")
        print(f"   • {name}: Đọc được {cnt} frame -> FPS: {fps:.1f} [{status}]")

    # Ghép 4 frame thành ảnh 2x2 lưu file
    def _prep_frame(img, label):
        out = img.copy()
        cv2.rectangle(out, (0, 0), (220, 35), (10, 15, 28), -1)
        cv2.putText(out, label, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 240, 255), 2)
        return out

    f1 = _prep_frame(latest_frames[directions[0]], directions[0])
    f2 = _prep_frame(latest_frames[directions[1]], directions[1])
    f3 = _prep_frame(latest_frames[directions[2]], directions[2])
    f4 = _prep_frame(latest_frames[directions[3]], directions[3])

    top = np.hstack([f1, f2])
    bot = np.hstack([f4, f3])
    grid = np.vstack([top, bot])

    output_path = "test_4cam_grid.jpg"
    cv2.imwrite(output_path, grid)
    print(f"\n🎉 ĐÃ LƯU ẢNH CHỤP ĐỒNG THỜI 4 MẮT CAMERA VÀO: {os.path.abspath(output_path)}")
    print("   Bạn có thể xem ảnh này để căn chỉnh góc nghiêng của 4 mắt camera trên mũ bảo hiểm.")

    # Đóng camera
    for cap in caps.values():
        if cap is not None:
            cap.release()
    print("=" * 65)


if __name__ == '__main__':
    valid = scan_all_video_nodes()
    test_concurrent_4_cameras(valid)
