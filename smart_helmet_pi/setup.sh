#!/bin/bash
# ==============================================================================
# SMART HELMET 360° - SCRIPT CÀI ĐẶT TỰ ĐỘNG 1-CLICK TRÊN RASPBERRY PI
# Đề tài Nghiên cứu Khoa học Kỹ thuật 2026
# ==============================================================================

set -e

echo "=========================================================="
echo "   BẮT ĐẦU CÀI ĐẶT SMART HELMET 360 TRÊN RASPBERRY PI    "
echo "=========================================================="

# 1. Cập nhật hệ điều hành Raspberry Pi OS
echo "[1/6] Đang cập nhật danh mục gói hệ điều hành apt..."
sudo apt update -y

# 2. Cài đặt các gói phụ trợ Linux bắt buộc
echo "[2/6] Đang cài đặt các thư viện hệ thống (v4l-utils, espeak-ng, ffmpeg)..."
sudo apt install -y python3-pip python3-venv python3-dev \
    v4l-utils espeak-ng libespeak-ng1 libatlas-base-dev \
    ffmpeg libgl1-mesa-glx git

# 3. Tạo môi trường ảo Python venv để tránh xung đột hệ thống trên Pi OS Bookworm
echo "[3/6] Đang tạo môi trường ảo Python (venv)..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv --system-site-packages
fi

source venv/bin/activate
pip install --upgrade pip

# 4. Cài đặt các thư viện Python
echo "[4/6] Đang cài đặt các thư viện Python từ requirements.txt..."
pip install -r requirements.txt

# 5. Tải trước mô hình YOLOv8-Nano
echo "[5/6] Đang tải mô hình YOLOv8-Nano..."
mkdir -p models
python3 -c "
try:
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')
    print('Tải model YOLOv8n thành công!')
except Exception as e:
    print('Chờ nạp model lúc chạy lần đầu:', e)
"

# 6. Cấu hình Dịch Vụ Tự Khởi Động Khi Bật Nguồn Mũ (systemd service)
echo "[6/6] Đang đăng ký dịch vụ tự khởi động cùng Raspberry Pi..."
SERVICE_FILE="/etc/systemd/system/smart_helmet.service"
CURRENT_USER=$(whoami)

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Smart Helmet 360 AI Service
After=network.target multi-user.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/venv/bin/python3 $SCRIPT_DIR/main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable smart_helmet.service

echo "=========================================================="
echo "🎉 CHÚC MỪNG! ĐÃ CÀI ĐẶT THÀNH CÔNG SMART HELMET 360°"
echo "=========================================================="
echo "1. Để chạy thử ngay: "
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo ""
echo "2. Để kiểm tra dịch vụ tự khởi động:"
echo "   sudo systemctl status smart_helmet.service"
echo ""
echo "3. Truy cập Web Dashboard từ điện thoại/máy tính giám khảo:"
echo "   http://<IP_CUA_CON_PI>:5000"
echo "=========================================================="
