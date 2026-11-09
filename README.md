# Smart Helmet 360° - Mũ Bảo Hiểm Thông Minh Hỗ Trợ Người Khiếm Thị

Dự án nghiên cứu và phát triển hệ thống mũ bảo hiểm thông minh tích hợp thị giác máy tính toàn cảnh 360 độ (kiến trúc Continuous Low-FPS V4L2-MMAP), phản hồi xúc giác định hướng (4 kênh motor rung haptic) và cảnh báo giọng nói tiếng Việt thời gian thực.

Hệ thống được thiết kế tối ưu để triển khai trên bo mạch chủ **Raspberry Pi 4 (8GB RAM)** chạy hệ điều hành **Ubuntu 22.04 LTS / Raspberry Pi OS**.

---

## 📌 Điểm Nhấn Công Nghệ & Kiến Trúc Phần Cứng

1. **Thị giác toàn cảnh 360° không góc chết (Continuous Low-FPS V4L2-MMAP):**
   - 3 Camera USB góc rộng ($120^\circ - 130^\circ$) chuẩn UVC cắm qua USB Hub (Trước 0°, Sau 180°, Phải 90°), kết hợp thuật toán phân vùng không gian góc Trái (Spatial Zone Splitting) trên Camera Trước để bao quát toàn cảnh 360° và kích hoạt đủ 4 kênh Haptic.
   - Chạy đồng thời ở 6 FPS/cam với cơ chế Zero-Copy MMAP drain, triệt tiêu hoàn toàn lỗi nghẽn bus USB và lỗi treo chip USB Jieli (-110).
2. **Xử lý thị giác biên (Edge AI):**
   - Mô hình YOLOv8-Nano tối ưu hóa cho kiến trúc ARM64 của Raspberry Pi 4.
   - Nhận diện người đi bộ, phương tiện giao thông (xe máy, ô tô, xe đạp), chướng ngại vật tầm thấp.
   - Thuật toán ước lượng khoảng cách và đánh giá tốc độ tiệm cận (Optical Expansion Rate) để cảnh báo kịp thời khi vật cản lao tới.
3. **Cảnh báo đa phương thức:**
   - **4 Motor rung định hướng (Haptic feedback):** Bố trí 4 vị trí quanh vành mũ (Trước trán, Thái dương phải, Gáy sau, Thái dương trái). Vật cản hướng nào -> Rung dồn dập hướng đó.
   - **Cảnh báo âm thanh tiếng Việt:** Bộ lọc thông minh (Smart Filter) chống quá tải thính giác, định tuyến trực tiếp qua ALSA card 0 của Pi.
4. **Cứu hộ khẩn cấp SOS & Định vị:**
   - Nút bấm vật lý SOS trên vành mũ (kèm mạch lọc chống dội RC).
   - Tự động kích hoạt còi báo động, rung toàn bộ motor và gửi tọa độ GPS vệ tinh kèm liên kết Google Maps tới người thân qua Telegram.
5. **Giao diện Web Giám Sát Thời Gian Thực:**
   - Người thân và ban giám khảo có thể truy cập qua điện thoại/máy tính xem luồng camera thời gian thực, radar trạng thái haptic 4 hướng và thông số hệ thống.

---

## 🛠️ Yêu Cầu Phần Cứng

- **Bo mạch chủ:** Raspberry Pi 4 Model B (Khuyên dùng bản 4GB hoặc 8GB RAM).
- **Hệ điều hành:** Ubuntu 22.04 LTS (64-bit Server hoặc Desktop).
- **Camera:** 4x Module USB Camera cảm biến OV2710 hoặc GC2053 (FOV $120^\circ - 130^\circ$ M12 lens).
- **Hub USB:** Bo mạch USB Hub 4 cổng IC FE1.1s hoặc GL850G.
- **Rung Haptic:** 4x Motor rung đồng xu 1027 hoặc 1234 (3V-5V).
- **Mạch đệm điều khiển:** IC đệm Darlington ULN2003A (hoặc transistor MOSFET).
- **Âm thanh & Còi:** Còi chip Active Buzzer 5V 12mm + Loa mini hoặc tai nghe dẫn truyền xương jack 3.5mm.
- **Cảm biến phụ trợ:** Module GPS NEO-6M/8M (UART) và cảm biến Laser ToF VL53L0X (I2C).
- **Nguồn cấp:** Pin Li-ion 7.4V (2S) kết hợp mạch hạ áp DC-DC Buck LM2596S-5.0 / XL4015 (5V/5A).

---

## 🔌 Sơ Đồ Đấu Nối Chân GPIO (Raspberry Pi 4)

| Thiết Bị | Chân BCM (GPIO) | Chân Vật Lý (Physical Pin) | Ghi Chú |
| :--- | :--- | :--- | :--- |
| **Motor Trước (Front)** | GPIO 17 | Pin 11 | Kích qua cổng đệm ULN2003A |
| **Motor Phải (Right)** | GPIO 27 | Pin 13 | Vị trí thái dương phải |
| **Motor Sau (Rear)** | GPIO 22 | Pin 15 | Vị trí gáy sau đầu |
| **Motor Trái (Left)** | GPIO 23 | Pin 16 | Vị trí thái dương trái |
| **Còi Báo Buzzer** | GPIO 24 | Pin 18 | Còi chíp 5V chủ động |
| **Nút Bấm Khẩn Cấp SOS** | GPIO 25 | Pin 22 | Kéo lên nội bộ, nhấn nối về GND (Pin 20) |
| **GPS UART (TX / RX)** | GPIO 14 / 15 | Pin 8 / Pin 10 | Kết nối module GPS NEO-6M |
| **Cảm Biến ToF (SDA / SCL)**| GPIO 2 / 3 | Pin 3 / Pin 5 | Giao tiếp I2C cảm biến Laser VL53L0X |
| **Nguồn Cấp 5V** | +5V | Pin 2, Pin 4 | Cấp nguồn 5V ổn áp từ mạch Buck |
| **Nối Đất Chung (GND)** | GND | Pin 6, 9, 14, 20 | Mass chung toàn hệ thống |

---

## 🚀 Hướng Dẫn Cài Đặt & Triển Khai Trên Ubuntu 22.04 (Pi 4 8GB)

### Bước 1: Clone kho lưu trữ
```bash
git clone https://github.com/trandat09062003/Smart_Helmet.git
cd Smart_Helmet/smart_helmet_pi
```

### Bước 2: Cắm Camera USB vào USB Hub & Raspberry Pi 4
- Cắm các mắt camera USB vào cổng trên **Bộ chia USB Hub (USB 3.0 SuperSpeed Hub)** theo thứ tự:
  - Cổng **USB1**: Camera **TRƯỚC** (Front - 0°)
  - Cổng **USB2**: Camera **SAU** (Rear - 180°)
  - Cổng **USB3**: Camera **PHẢI** (Right - 90°)
  *(Góc Trái được phân vùng tự động trên Camera Trước để điều khiển đủ 4 kênh haptic).*
- Cắm đầu dây USB của Hub vào cổng **USB 3.0 màu xanh dương** trên Raspberry Pi 4 để đảm bảo băng thông đường truyền tối ưu.

### Bước 3: Chạy script cài đặt tự động (1-Click Setup)
```bash
chmod +x setup.sh
./setup.sh
```

Script sẽ tự động:
1. Cập nhật hệ thống Linux `apt` và cài đặt các phụ thuộc (`v4l-utils`, `espeak-ng`, `ffmpeg`, `libatlas-base-dev`).
2. Khởi tạo môi trường ảo Python `venv` với cấu hình `--system-site-packages`.
3. Cài đặt các thư viện Python: `ultralytics`, `opencv-python-headless`, `flask`, `RPi.GPIO`, `pyserial`.
4. Tải trước trọng số mô hình `yolov8n.pt`.
5. Đăng ký và kích hoạt dịch vụ chạy ngầm `smart_helmet.service` (tự khởi động khi bật nguồn pin).

### Bước 4: Kiểm tra nhanh Camera USB qua Hub
Trước khi chạy hệ thống chính, chạy script kiểm tra để xác nhận các camera nhận tín hiệu và đo FPS:
```bash
source venv/bin/activate
python3 test_cameras.py
```
*(Chương trình sẽ tự động dò các cổng camera, đo FPS đồng thời theo chế độ V4L2-MMAP Low-FPS).*

### Bước 5: Chạy thử nghiệm hệ thống AI
- **Chạy trực tiếp trong terminal:**
```bash
./run.sh
# hoặc: python3 main.py
```
- **Quản lý dịch vụ chạy ngầm:**
```bash
./start_background.sh   # Bật dịch vụ chạy ngầm
./status.sh             # Kiểm tra trạng thái dịch vụ và API
./stop.sh               # Tắt dịch vụ chạy ngầm
```

### Bước 6: Truy cập Web Dashboard Giám Sát
Mở trình duyệt trên điện thoại hoặc máy tính cùng mạng WiFi với Raspberry Pi:
```
http://<IP_RASPBERRY_PI>:5000
```
*(Ví dụ: `http://192.168.1.50:5000`)*

---

## 📂 Cấu Trúc Thư Mục Dự Án

```
Smart_Helmet/
├── smart_helmet_pi/                     # Mã nguồn phần mềm trên Raspberry Pi
│   ├── main.py                          # Bộ điều phối trung tâm hệ thống
│   ├── config.py                        # Cấu hình GPIO, Camera, Ngưỡng AI, GPS
│   ├── camera_manager.py                # Quản lý 3 Camera đồng thời V4L2-MMAP Low-FPS
│   ├── ai_detector.py                   # Nhận diện vật thể YOLOv8n & phân vùng không gian 4 hướng
│   ├── haptic_controller.py             # Điều khiển 4 motor rung & còi buzzer
│   ├── voice_alert.py                   # Cảnh báo giọng nói tiếng Việt (Smart Filter, card ALSA 0)
│   ├── sos_manager.py                   # Quản lý sự cố khẩn cấp & gửi tin Telegram
│   ├── web_server.py                    # Giao diện Web Dashboard phục vụ thuyết trình
│   ├── test_cameras.py                  # Script chẩn đoán và chụp thử nghiệm camera
│   ├── setup.sh                         # Script cài đặt 1-Click trên Ubuntu/Raspberry Pi OS
│   ├── run.sh                           # Khởi chạy ứng dụng trong venv
│   ├── start_background.sh              # Bật dịch vụ chạy ngầm systemd
│   ├── status.sh                        # Kiểm tra trạng thái dịch vụ & API
│   ├── stop.sh                          # Tắt dịch vụ chạy ngầm
│   ├── requirements.txt                 # Danh sách thư viện Python
│   └── README_HUONG_DAN_NAP_PI.md       # Cẩm nang chi tiết đấu nối phần cứng
├── Smart_Helmet/                        # Dự án thiết kế phần cứng Altium Designer
│   ├── Smart_Helmet.PrjPcb              # Project Altium Carrier Board
│   └── Smart_Helmet.SchDoc              # Bản vẽ nguyên lý mạch phụ trợ mũ
├── SCHEMATIC_PCB_VIEWER.html            # Trình tra cứu linh kiện BOM & CAD Altium
├── index.html                           # Trang web tổng quan kế hoạch & mô phỏng FOV
└── ke_hoach_trien_khai_smart_helmet_4cam.md # Bản thuyết minh kế hoạch triển khai KHKT
```

---

## 📄 Bản Quyền & Giấy Phép
Dự án được phát triển phục vụ mục đích nghiên cứu khoa học kỹ thuật và hỗ trợ cộng đồng người khiếm thị.
Mã nguồn mở theo giấy phép MIT License.
