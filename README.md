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
- **Hệ thống Camera:** 3x Module USB Camera cảm biến OV2710 hoặc GC2053 (FOV $120^\circ - 130^\circ$ M12 lens) lắp tam giác đều $120^\circ$ bao quát $360^\circ$.
- **Hub USB:** Bo mạch USB Hub 4 cổng (chuẩn USB 3.0 cắm vào cổng USB 3.0 xanh dương Pi 4).
- **Mạch Còi Báo Động:** Còi chip Active Buzzer 5V kích qua **Transistor S8050 NPN** (vỏ TO-92) + Trở 1kΩ + Diode 1N4148.
- **Mạch Nút Bấm Khẩn Cấp:** Nút bấm vật lý SOS nối chân Pin 22 (GPIO 25) và Pin 20 (GND) + Tụ gốm 100nF (104) chống dội.
- **Định Vị GPS:** Module GPS NEO-6M kết nối giao tiếp Serial UART (Pin 8 TXD, Pin 10 RXD).
- **Nguồn Cấp:** Pin Li-ion 7.4V (2S) kết hợp mạch hạ áp DC-DC Buck XL4015 / LM2596S (5.10V / 5A) cắm trực tiếp vào Pin 2 (+5V) và Pin 6 (GND).

---

## 🔌 Sơ Đồ Cắm Dây & Đấu Nối Chân GPIO (Raspberry Pi 4)

> ⚡ **SƠ ĐỒ CẮM DÂY DUPONT TƯƠNG TÁC (DUY NHẤT 1 FILE HTML):** Mở trực tiếp file **[so_do_noi_chan_smart_helmet_pi.html](so_do_noi_chan_smart_helmet_pi.html)** trên trình duyệt:
> - Hướng dẫn cắm dây Dupont trực tiếp giữa Raspberry Pi 4 và 5 khối phần cứng thực tế (không cần làm mạch in PCB).
> - Mạch còi Transistor S8050 NPN (vỏ TO-92) kích còi buzzer 5V qua Pin 18 (GPIO 24).
> - Mạch nút bấm SOS qua Pin 22 (GPIO 25) và GND.
> - Cụm 3 Camera tam giác đều $120^\circ$ cắm vào Hub USB 3.0 kết nối cổng USB 3.0 xanh dương Pi 4.
> - Module GPS NEO-6M cắm 4 dây Dupont UART (Pin 8, 10, 4, 9).
> - Bật/tắt phát sáng làm nổi bật từng tuyến dây cắm (Còi S8050, Nút SOS, Nguồn Buck 5V, GPS, Cam USB).
> - 1-Click sao chép script Python test phần cứng hoàn chỉnh (`test_hardware_pi.py`).

| Khối Thiết Bị | Chân BCM (GPIO) | Chân Vật Lý (Physical Pin) | Hướng Dẫn Cắm Dây |
| :--- | :--- | :--- | :--- |
| **Mạch Còi (Transistor S8050)** | GPIO 24 | Pin 18 | Qua trở 1kΩ vào chân B (giữa) S8050, chân C vào (-) Còi, chân E vào GND |
| **Nút Bấm Khẩn Cấp SOS** | GPIO 25 | Pin 22 | 1 chân cắm Pin 22, 1 chân cắm Pin 20 (GND), kẹp tụ 100nF song song |
| **GPS UART (TXD)** | GPIO 14 | Pin 8 | Dây Dupont Cái-Cái cắm sang chân RXD của GPS NEO-6M |
| **GPS UART (RXD)** | GPIO 15 | Pin 10 | Dây Dupont Cái-Cái cắm sang chân TXD của GPS NEO-6M |
| **Nguồn Cấp 5.1V (Buck XL4015)**| +5V | Pin 2, Pin 4 | Cọc OUT+ từ Buck cắm vào Pin 2 (+5V Pi), Pin 4 cấp cho (+) Còi & GPS |
| **Nối Đất Chung (GND)** | GND | Pin 6, Pin 9, Pin 20 | Cọc OUT- từ Buck cắm Pin 6, Pin 9 cho GPS, Pin 20 cho SOS & S8050 |
| **Cụm 3 Camera USB (360°)** | USB 3.0 | Cổng Xanh Dương | 3 Cam cắm vào Hub USB 3.0, cáp Hub cắm vào cổng USB 3.0 màu xanh Pi 4 |

---

## 🚀 Hướng Dẫn Cài Đặt & Triển Khai Trên Ubuntu 22.04 (Pi 4 8GB)

### Bước 1: Clone kho lưu trữ
```bash
git clone https://github.com/trandat09062003/Smart_Helmet.git
cd Smart_Helmet/smart_helmet_pi
```

### Bước 2: Cắm 3 Camera USB vào USB Hub & Raspberry Pi 4 (Kiến trúc Tam Giác 120°)
- Bố trí 3 camera thành hình tam giác đều $120^\circ$ quanh mũ:
  - Cổng **USB1**: Camera **TRƯỚC** (`FRONT` - $0^\circ$)
  - Cổng **USB2**: Camera **SAU-PHẢI** (`REAR_RIGHT` - $120^\circ$)
  - Cổng **USB3**: Camera **SAU-TRÁI** (`REAR_LEFT` - $240^\circ$)
  *(Thuật toán AI phân vùng không gian quét kín trọn vẹn 360° không điểm mù và kích hoạt đủ 4 kênh Haptic).*
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
├── HUONG_DAN_NOI_CHAN.html              # Cẩm nang tương tác đấu nối chân GPIO & ngoại vi
├── SCHEMATIC_PCB_VIEWER.html            # Trình tra cứu linh kiện BOM & CAD Altium
└── index.html                           # Trang web tổng quan kế hoạch & mô phỏng FOV 360°
```

---

## 📄 Bản Quyền & Giấy Phép
Dự án được phát triển phục vụ mục đích nghiên cứu khoa học kỹ thuật và hỗ trợ cộng đồng người khiếm thị.
Mã nguồn mở theo giấy phép MIT License.
