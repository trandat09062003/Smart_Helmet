"""
SMART HELMET 360 - CẤU HÌNH HỆ THỐNG TRÊN RASPBERRY PI
Đề tài Nghiên Cứu Khoa Học Kỹ Thuật 2026
Kiến trúc Triple-Camera 360° (Chạy đồng thời 3 Camera ở FPS thấp + Phân Vùng Không Gian 4 Hướng Haptic)
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

# Map các hướng tới chân GPIO (Đầy đủ 4 hướng rung xúc giác trên mũ)
MOTOR_PINS = {
    'FRONT': PIN_MOTOR_FRONT,
    'RIGHT': PIN_MOTOR_RIGHT,
    'REAR':  PIN_MOTOR_REAR,
    'LEFT':  PIN_MOTOR_LEFT
}

# ==============================================================================
# 2. CẤU HÌNH 3 CAMERA USB CHẠY ĐỒNG THỜI Ở FPS THẤP (CONTINUOUS LOW-FPS)
# ==============================================================================
# Danh sách các mắt camera kích hoạt:
# - Chế độ 3 Camera đồng thời (Mặc định): ['FRONT', 'REAR', 'RIGHT']
# - Nếu muốn quay về chế độ 2 Camera: đổi thành ['FRONT', 'REAR']
ACTIVE_CAMERAS = ['FRONT', 'REAR', 'RIGHT']
AUTO_DISCOVER_CAMERAS = True

# Fallback index ưu tiên theo thứ tự cổng USB:
# (Trên Linux mỗi webcam tạo 2 node, ví dụ video0 là hình, video1 là metadata)
CAMERA_INDICES = {
    'FRONT': 0,    # /dev/video0 (Cổng USB 1 - Cam Chính Phía Trước 0°)
    'REAR':  2,    # /dev/video2 (Cổng USB 2 - Cam Phía Sau 180°)
    'RIGHT': 4     # /dev/video4 (Cổng USB 3 - Cam Bên Phải 90°)
}

# Độ phân giải gốc CIF (352x240) MJPEG V4L2-MMAP với tốc độ lấy mẫu FPS thấp (6 FPS/cam)
# Giúp cả 3 camera giữ luồng STREAMON đồng thời liên tục mà CPU vẫn mát (< 30%) và không nghẽn USB
CAM_WIDTH    = 352
CAM_HEIGHT   = 240
CAM_FPS      = 6
JPEG_QUALITY = 58
AI_IMG_SIZE  = 256

# Thời gian chờ V4L2 non-blocking (giây):
# - Khi mới bật cảm biến CMOS (cold-start) chờ tối đa 1.8s để có frame đầu tiên
# - Khi đang đọc luồng liên tục chờ tối đa 0.6s
CAM_INIT_TIMEOUT_SEC = 1.80
CAM_READ_TIMEOUT_SEC = 0.60

# Phân vùng không gian ngang (Spatial Zone Splitting) trên khung hình Camera Trước:
# Giúp bao quát luôn cả góc Trái (LEFT) để điều khiển đủ 4 Motor Haptic với 3 Camera vật lý
ZONE_LEFT_RATIO  = 0.35   # Tâm vật thể < 35% chiều ngang Cam Trước -> Lệch TRÁI (Kích motor LEFT)
ZONE_RIGHT_RATIO = 0.67   # Tâm vật thể > 67% chiều ngang Cam Trước -> Lệch PHẢI (Kích motor RIGHT)

# ==============================================================================
# 3. CẤU HÌNH MÔ HÌNH AI NHẬN DIỆN VẬT THỂ
# ==============================================================================
AI_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'yolov8n.pt')
CONFIDENCE_THRESHOLD = 0.40

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
BBOX_RATIO_CRITICAL = 0.28   # >28% khung hình: Rất gần (< 1m) -> Báo động mức ĐỎ
BBOX_RATIO_WARNING  = 0.12   # >12% khung hình: Gần (1m - 2m) -> Báo động mức VÀNG
VOICE_COOLDOWN_SECONDS = 3.5

# ==============================================================================
# 5. CẤU HÌNH WEB DASHBOARD CHO GIÁM KHẢO / NGƯỜI THÂN
# ==============================================================================
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000

# ==============================================================================
# 6. CẤU HÌNH SOS & TELEGRAM BOT (TÙY CHỌN)
# ==============================================================================
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID   = ""
DEFAULT_LAT = 10.7769
DEFAULT_LON = 106.7009
GPS_SERIAL_PORT = "/dev/ttyUSB0"
