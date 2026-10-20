# Smart Helmet 360° - Mũ Bảo Hiểm Thông Minh Hỗ Trợ Người Khiếm Thị

Dự án nghiên cứu và phát triển hệ thống mũ bảo hiểm thông minh tích hợp thị giác máy tính toàn cảnh 360 độ (4 camera góc rộng cố định), phản hồi xúc giác định hướng (4 kênh motor rung haptic) và cảnh báo giọng nói tiếng Việt thời gian thực.

Hệ thống được thiết kế tối ưu để triển khai trên bo mạch chủ **Raspberry Pi 4 (8GB RAM)** chạy hệ điều hành **Ubuntu 22.04 LTS (Jammy Jellyfish)**.

---

## 📌 Điểm Nhấn Công Nghệ & Kiến Trúc Phần Cứng

1. **Thị giác toàn cảnh 360° không góc chết:**
   - 4 Camera USB góc rộng ($120^\circ - 130^\circ$) chuẩn UVC cắm qua IC Hub USB 4 cổng (FE1.1s / GL850G).
   - Loại bỏ hoàn toàn độ trễ cơ học của cơ cấu camera quay quét (0 ms delay).
2. **Xử lý thị giác biên (Edge AI):**
   - Mô hình YOLOv8-Nano tối ưu hóa cho kiến trúc ARM64 của Raspberry Pi 4.
   - Nhận diện người đi bộ, phương tiện giao thông (xe máy, ô tô, xe đạp), chướng ngại vật tầm thấp.
   - Thuật toán ước lượng khoảng cách và đánh giá tốc độ tiệm cận (Optical Expansion Rate) để cảnh báo kịp thời khi vật cản lao tới.
3. **Cảnh báo đa phương thức:**
   - **4 Motor rung định hướng (Haptic feedback):** Bố trí 4 vị trí quanh vành mũ (Trước trán, Thái dương phải, Gáy sau, Thái dương trái). Vật cản hướng nào -> Rung dồn dập hướng đó.
   - **Cảnh báo âm thanh tiếng Việt:** Bộ lọc thông minh (Smart Filter) chống quá tải thính giác, thông báo ngắn gọn dứt khoát.
4. **Cứu hộ khẩn cấp SOS & Định vị:**
   - Nút bấm vật lý SOS trên vành mũ (kèm mạch lọc chống dội RC).
   - Tự động kích hoạt còi báo động, rung toàn bộ motor và gửi tọa độ GPS vệ tinh kèm liên kết Google Maps tới người thân qua Telegram.
5. **Giao diện Web Giám Sát Thời Gian Thực:**
   - Người thân và ban giám khảo có thể truy cập qua điện thoại/máy tính xem luồng ghép 4 camera 360°, radar trạng thái haptic và thông số hệ thống.

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

### Bước 2: Chạy script cài đặt tự động (1-Click Setup)
```bash
chmod +x setup.sh
./setup.sh
```

Script sẽ tự động:
1. Cập nhật hệ thống Ubuntu `apt` và cài đặt các phụ thuộc (`v4l-utils`, `espeak-ng`, `ffmpeg`, `libatlas-base-dev`).
2. Khởi tạo môi trường ảo Python `venv` với cấu hình `--system-site-packages`.
3. Cài đặt các thư viện Python: `ultralytics`, `opencv-python-headless`, `flask`, `RPi.GPIO`, `pyserial`.
4. Tải trước trọng số mô hình `yolov8n.pt`.
5. Đăng ký và kích hoạt dịch vụ chạy ngầm `smart_helmet.service` (tự khởi động khi bật nguồn pin).

### Bước 3: Chạy thử nghiệm thủ công
```bash
source venv/bin/activate
python3 main.py
```

### Bước 4: Truy cập Web Dashboard Giám Sát
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
│   ├── camera_manager.py                # Quản lý 4 Camera đa luồng (Zero-Latency)
│   ├── ai_detector.py                   # Nhận diện vật thể YOLOv8n & tính cự ly
│   ├── haptic_controller.py             # Điều khiển 4 motor rung & còi buzzer
│   ├── voice_alert.py                   # Cảnh báo giọng nói tiếng Việt (Smart Filter)
│   ├── sos_manager.py                   # Quản lý sự cố khẩn cấp & gửi tin Telegram
│   ├── web_server.py                    # Giao diện Web Dashboard phục vụ thuyết trình
│   ├── setup.sh                         # Script cài đặt 1-Click trên Ubuntu
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
