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
# 2. CẤU HÌNH KIẾN TRÚC 3 CAMERA TAM GIÁC ĐỒNG THỜI (CONTINUOUS LOW-FPS 120°)
# ==============================================================================
# Kiểu bố trí 3 Camera vật lý trên mũ:
# - 'TRI_120': Bố trí tam giác đều 120° (Trước 0°, Sau-Phải 120°, Sau-Trái 240°)
#              -> Phủ kín 100% không gian 360° không góc chết, tối ưu nhất cho mũ!
# - 'ORTHO_90': Bố trí góc vuông (Trước 0°, Sau 180°, Phải 90°)
CAMERA_LAYOUT = 'TRI_120'

# Danh sách 3 Camera theo kiến trúc tam giác đều 120°
ACTIVE_CAMERAS = ['FRONT', 'REAR_RIGHT', 'REAR_LEFT'] if CAMERA_LAYOUT == 'TRI_120' else ['FRONT', 'REAR', 'RIGHT']
AUTO_DISCOVER_CAMERAS = True

# Fallback index ưu tiên theo thứ tự cổng USB trên Hub:
# (Trên Linux mỗi webcam tạo 2 node, ví dụ video0 là hình, video1 là metadata)
CAMERA_INDICES = {
    'FRONT':      0,    # /dev/video0 (Cổng USB 1 - Cam Trước 0°)
    'REAR_RIGHT': 2,    # /dev/video2 (Cổng USB 2 - Cam Sau-Phải 120°)
    'REAR_LEFT':  4,    # /dev/video4 (Cổng USB 3 - Cam Sau-Trái 240°)
    'REAR':       2,    # Tương thích ngược nếu đặt tên REAR
    'RIGHT':      4     # Tương thích ngược nếu đặt tên RIGHT
}

# Độ phân giải gốc CIF (352x240) MJPEG V4L2-MMAP với tốc độ lấy mẫu FPS thấp (6 FPS/cam)
# Giúp cả 3 camera giữ luồng STREAMON đồng thời liên tục mà CPU vẫn mát (< 30%) và không nghẽn USB
CAM_WIDTH    = 352
CAM_HEIGHT   = 240
CAM_FPS      = 6
JPEG_QUALITY = 58
AI_IMG_SIZE  = 256

# Thời gian chờ V4L2 non-blocking (giây):
CAM_INIT_TIMEOUT_SEC = 1.80
CAM_READ_TIMEOUT_SEC = 0.60

# Ngưỡng phân vùng không gian ngang (Spatial Ratios):
# Cho Cam Trước (0°):
ZONE_FRONT_LEFT_RATIO  = 0.28   # < 28% chiều ngang Cam Trước -> Lệch sườn TRÁI (Kích motor LEFT)
ZONE_FRONT_RIGHT_RATIO = 0.72   # > 72% chiều ngang Cam Trước -> Lệch sườn PHẢI (Kích motor RIGHT)
# Cho Cam Sau-Phải (120°) và Sau-Trái (240°):
ZONE_REAR_SPLIT_RATIO  = 0.50   # Chia nửa ảnh giữa hướng hông sườn và hướng sau gáy

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
