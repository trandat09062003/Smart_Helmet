# HƯỚNG DẪN CHI TIẾT NẠP CODE VÀO RASPBERRY PI
## DỰ ÁN SMART HELMET 360° (MŨ BẢO HIỂM THÔNG MINH CHO NGƯỜI KHIẾM THỊ)

Tài liệu này hướng dẫn chi tiết từng bước từ đấu nối chân phần cứng, sao chép mã nguồn vào Raspberry Pi (Pi 4 hoặc Pi 5) cho đến khi hệ thống tự động khởi động chạy ngầm.

---

### BƯỚC 1: SƠ ĐỒ ĐẤU NỐI DÂY PHẦN CỨNG (GPIO PINOUT)

Trên đầu nối 40 chân GPIO của Raspberry Pi:

| Thiết Bị | Chân GPIO (BCM) | Chân Vật Lý (Physical Pin) | Ghi Chú Đấu Nối |
| :--- | :--- | :--- | :--- |
| **Motor Trước (Front)** | **GPIO 17** | Chân 11 | Kích qua cổng Collector/Drain transistor mạch đệm |
| **Motor Phải (Right)** | **GPIO 27** | Chân 13 | Vị trí thái dương phải của mũ |
| **Motor Sau (Rear)** | **GPIO 22** | Chân 15 | Vị trí gáy sau của mũ |
| **Motor Trái (Left)** | **GPIO 23** | Chân 16 | Vị trí thái dương trái của mũ |
| **Còi Báo Buzzer** | **GPIO 24** | Chân 18 | Còi chíp 5V chủ động (Active Buzzer) |
| **Nút Nhấn Khẩn Cấp SOS** | **GPIO 25** | Chân 22 | 1 chân vào GPIO 25, 1 chân vào **GND (Chân 20)** |
| **Nguồn Cấp Phụ Trợ** | **5V Power** | Chân 2 hoặc Chân 4 | Cấp nguồn cho mạch đệm motor |
| **Đường Nối Đất Chung** | **GND** | Chân 6, 9, 14, 20, 25, 30 | Nối mass chung toàn bộ hệ thống |

> ⚠️ **LƯU Ý QUAN TRỌNG:** Tuyệt đối **không** nối trực tiếp chân GPIO của Pi vào motor rung (vì motor tiêu thụ dòng 60–100mA, trong khi chân GPIO của Pi chỉ chịu tối đa 16mA). Bắt buộc phải qua mạch đệm Transistor NPN (2N2222, SS8050) hoặc IC đệm ULN2003 / MOSFET đã vẽ trong mạch Altium.

---

### BƯỚC 2: CẮM 4 CAMERA USB VÀO BỘ CHIA USB HUB

1. Cắm 4 mắt camera USB vào 4 cổng trên **Bộ chia USB Hub (USB 3.0 SuperSpeed 4 Ports Hub)** theo quy ước chuẩn:
   - Cổng **USB1**: Mắt camera **TRƯỚC** (Front - 0°)
   - Cổng **USB2**: Mắt camera **PHẢI** (Right - 90°)
   - Cổng **USB3**: Mắt camera **SAU** (Rear - 180°)
   - Cổng **USB4**: Mắt camera **TRÁI** (Left - 270°)
2. Cắm cáp ngõ ra của USB Hub vào cổng **USB 3.0 (cổng màu xanh dương)** trên Raspberry Pi 4 để đảm bảo băng thông truyền tải cao nhất.
3. Chạy script chẩn đoán tự động để test đồng thời 4 camera và kiểm tra FPS:
   ```bash
   python3 test_cameras.py
   ```
   *Script sẽ chụp ảnh ghép 4 mắt cam lưu vào `test_4cam_grid.jpg` để bạn kiểm tra góc nhìn thực tế trên mũ.*

---

### BƯỚC 3: SAO CHÉP MÃ NGUỒN VÀO RASPBERRY PI

Toàn bộ mã nguồn đã được tạo sẵn trong thư mục:
`c:\Users\Public\Documents\Altium\08052026\Smart_helmet\smart_helmet_pi\`

Bạn có thể chép vào Pi bằng 1 trong 3 cách sau:

#### Cách 1: Dùng USB Flash Drive (Đơn giản nhất)
1. Cắm USB vào máy tính Windows, copy toàn bộ thư mục `smart_helmet_pi` vào USB.
2. Rút USB cắm sang Raspberry Pi.
3. Mở Terminal trên Pi và copy vào thư mục cá nhân:
   ```bash
   cp -r /media/$USER/* /smart_helmet_pi ~/smart_helmet_pi
   cd ~/smart_helmet_pi
   ```

#### Cách 2: Dùng phần mềm WinSCP (Truyền qua mạng WiFi)
1. Bật tính năng SSH trên Raspberry Pi.
2. Tải phần mềm WinSCP trên máy tính, nhập IP của con Pi, tài khoản và mật khẩu.
3. Kéo thả thư mục `smart_helmet_pi` từ máy tính vào thư mục `/home/<tên_user>/` trên Pi.

---

### BƯỚC 4: CHẠY CÀI ĐẶT TỰ ĐỘNG (1-CLICK SETUP)

Mở Terminal trên Raspberry Pi và chạy 2 lệnh sau:

```bash
cd ~/smart_helmet_pi
chmod +x setup.sh
./setup.sh
```

**Script `setup.sh` sẽ tự động làm toàn bộ các việc sau:**
- Cập nhật thư viện Linux OS, cài `espeak-ng` (giọng nói tiếng Việt), `ffmpeg`, `v4l-utils`.
- Tạo môi trường ảo Python `venv` độc lập.
- Cài đặt đầy đủ `opencv`, `ultralytics` (YOLOv8-Nano), `flask`, `RPi.GPIO`.
- Tự động tải sẵn mô hình AI `yolov8n.pt`.
- Đăng ký dịch vụ `smart_helmet.service` để **mũ tự động khởi động chạy ngầm mỗi khi cắm pin/bật nguồn!**

---

### BƯỚC 5: KIỂM TRA CHẠY THỬ & ĐIỀU KHIỂN

#### 1. Chạy thử nghiệm trực tiếp trên màn hình:
```bash
cd ~/smart_helmet_pi
source venv/bin/activate
python3 main.py
```
- Khi khởi động: Mũ sẽ kêu "bíp", rung nhẹ 4 hướng và loa phát giọng nói: *"Hệ thống Mũ thông minh 360 độ đã sẵn sàng hoạt động."*
- Đưa tay hoặc để người di chuyển xung quanh 4 hướng:
  - Vật cản ở góc nào -> Motor hướng đó rung cảnh báo.
  - Vật cản tiến lại gần -> Rung dồn dập và phát loa thông báo.

#### 2. Mở Giao diện Web Dashboard phục vụ Thuyết trình & Giám khảo:
Mở trình duyệt (trên điện thoại hoặc laptop bất kỳ kết nối cùng WiFi với con Pi):
```
http://<Địa_chỉ_IP_con_Pi>:5000
```
*(Ví dụ: `http://192.168.1.15:5000`)*

**Trên Web Dashboard bạn sẽ thấy:**
- Khung nhìn 4 Camera thời gian thực ghép toàn cảnh 360° với khung nhận diện Bounding Box AI.
- Vòng tròn Radar mô phỏng trạng thái 4 motor rung (sáng đỏ khi rung).
- Tọa độ GPS thời gian thực.
- Nút bấm test còi và test báo động SOS.

#### 3. Quản lý Dịch vụ Tự Khởi Động:
- Xem trạng thái: `sudo systemctl status smart_helmet.service`
- Khởi động lại: `sudo systemctl restart smart_helmet.service`
- Tạm dừng: `sudo systemctl stop smart_helmet.service`
