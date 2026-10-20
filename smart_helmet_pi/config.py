"""
SMART HELMET 360 - CẤU HÌNH HỆ THỐNG TRÊN RASPBERRY PI
Đề tài Nghiên Cứu Khoa Học Kỹ Thuật 2026
"""
import os

# ==============================================================================
# 1. CẤU HÌNH GPIO (CHÂN BCM TRÊN RASPBERRY PI 4 / 5)
# ==============================================================================
# 4 Motor rung định hướng haptic (qua mạch đệm Transistor / MOSFET)
PIN_MOTOR_FRONT = 17   # Chân kích motor Trước trán (Front)
PIN_MOTOR_RIGHT = 27   # Chân kích motor Thái dương phải (Right)
PIN_MOTOR_REAR  = 22   # Chân kích motor Gáy sau (Rear)
PIN_MOTOR_LEFT  = 23   # Chân kích motor Thái dương trái (Left)

# Còi Buzzer cảnh báo âm lượng lớn
PIN_BUZZER      = 24   # Chân còi báo động chủ động (Active Buzzer)

# Nút nhấn khẩn cấp SOS (Pull-up nội bộ, nhấn nối đất GND)
PIN_BUTTON_SOS  = 25   # Chân nút SOS khẩn cấp

# Map các hướng tới chân GPIO
MOTOR_PINS = {
    'FRONT': PIN_MOTOR_FRONT,
    'RIGHT': PIN_MOTOR_RIGHT,
    'REAR':  PIN_MOTOR_REAR,
    'LEFT':  PIN_MOTOR_LEFT
}

# ==============================================================================
# 2. CẤU HÌNH 4 CAMERA USB CẮM QUA USB HUB (CHUẨN UVC)
# ==============================================================================
# Thứ tự cắm dây trên Hub 4 Cổng (USB 3.0 SuperSpeed 4 Ports Hub):
# - Cổng USB1 trên Hub: Camera TRƯỚC (Front) - Hướng nhìn chính
# - Cổng USB2 trên Hub: Camera PHẢI (Right)   - Quan sát bên phải
# - Cổng USB3 trên Hub: Camera SAU (Rear)     - Quan sát gáy sau lưng
# - Cổng USB4 trên Hub: Camera TRÁI (Left)    - Quan sát bên trái
AUTO_DISCOVER_CAMERAS = True

# Fallback index thủ công nếu không dùng auto-discovery:
# (Lưu ý: Trên Linux mỗi webcam tạo 2 node, ví dụ video0 là hình, video1 là metadata)
CAMERA_INDICES = {
    'FRONT': 0,    # Thường là /dev/video0 hoặc USB1
    'RIGHT': 2,    # Thường là /dev/video2 hoặc USB2
    'REAR':  4,    # Thường là /dev/video4 hoặc USB3
    'LEFT':  6     # Thường là /dev/video6 hoặc USB4
}

CAM_WIDTH  = 640
CAM_HEIGHT = 480
CAM_FPS    = 15

# ==============================================================================
# 3. CẤU HÌNH MÔ HÌNH AI NHẬN DIỆN VẬT THỂ
# ==============================================================================
# Mô hình nhẹ tối ưu cho Pi: yolov8n.pt (Nano) hoặc yolov8n.onnx
AI_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'yolov8n.pt')
CONFIDENCE_THRESHOLD = 0.40  # Ngưỡng tin cậy nhận diện

# Các lớp vật cản quan trọng đối với người khiếm thị (theo bộ COCO)
TARGET_CLASSES = [
    'person',        # Người đi bộ
    'bicycle',       # Xe đạp
    'car',           # Ô tô
    'motorcycle',    # Xe máy
    'bus',           # Xe buýt
    'truck',         # Xe tải
    'dog',           # Chó
    'cat',           # Mèo
    'chair',         # Ghế / bàn chướng ngại vật
    'potted plant',  # Chậu cây trên vỉa hè
    'stop sign'      # Biển báo
]

# Dịch tên vật thể sang tiếng Việt để phát âm thanh
VIETNAMESE_LABELS = {
    'person': 'Người',
    'bicycle': 'Xe đạp',
    'car': 'Ô tô',
    'motorcycle': 'Xe máy',
    'bus': 'Xe buýt',
    'truck': 'Xe tải',
    'dog': 'Chó',
    'cat': 'Mèo',
    'chair': 'Vật cản',
    'potted plant': 'Chậu cây',
    'stop sign': 'Biển báo'
}

# ==============================================================================
# 4. CẤU HÌNH KHOẢNG CÁCH & BỘ LỌC CẢNH BÁO THÔNG MINH
# ==============================================================================
# Ước lượng khoảng cách dựa vào tỉ lệ diện tích Bounding Box so với toàn khung hình
BBOX_RATIO_CRITICAL = 0.28   # >28% khung hình: Rất gần (< 1m) -> Báo động mức ĐỎ
BBOX_RATIO_WARNING  = 0.12   # >12% khung hình: Gần (1m - 2m) -> Báo động mức VÀNG

# Thời gian cooldown (giây) giữa 2 lần nhắc giọng nói cùng 1 hướng (tránh nói liên tục)
VOICE_COOLDOWN_SECONDS = 3.5

# ==============================================================================
# 5. CẤU HÌNH WEB DASHBOARD CHO GIÁM KHẢO / NGƯỜI THÂN
# ==============================================================================
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000

# ==============================================================================
# 6. CẤU HÌNH SOS & TELEGRAM BOT (TÙY CHỌN)
# ==============================================================================
# Để trống nếu không dùng gửi tin nhắn qua mạng
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID   = ""

# Tọa độ GPS mặc định (Dùng khi chưa có module GPS vật lý)
DEFAULT_LAT = 10.7769
DEFAULT_LON = 106.7009
GPS_SERIAL_PORT = "/dev/ttyUSB0"  # Cổng Serial nếu cắm module GPS NEO-6M
