# HƯỚNG DẪN CHI TIẾT NẠP CODE & VẬN HÀNH TRÊN RASPBERRY PI 4
## DỰ ÁN SMART HELMET 360° AI (MŨ BẢO HIỂM THÔNG MINH BẢO VỆ NGƯỜI ĐI XE & KHIẾM THỊ)

Tài liệu này hướng dẫn chi tiết từ đấu nối dây phần cứng thực tế, tải mã nguồn từ GitHub về Raspberry Pi 4, kiểm tra chẩn đoán phần cứng cho đến khi khởi động toàn bộ hệ thống Edge AI 3 Camera.

---

### BƯỚC 1: SƠ ĐỒ ĐẤU NỐI DÂY THỰC TẾ TRÊN ĐẦU NỐI 40 CHÂN GPIO (J8)

> 💡 **TRA CỨU TRỰC QUAN:** Mở file **`so_do_noi_chan_smart_helmet_pi.html`** trên trình duyệt để xem sơ đồ màu 40 chân và bảng nối chi tiết!

Toàn bộ hệ thống chỉ sử dụng đúng **10 chân GPIO**:
* **HÀNG TRÊN (Chân Lẻ, phía trong bo mạch gần SoC):** Cọc **PIN 1** và **PIN 11**.
* **HÀNG DƯỚI (Chân Chẵn, sát mép ngoài bàn):** Cọc **PIN 2, 4, 6, 8, 10, 18, 20, 22**.

| Cọc PIN # | Vị Trí Cọc Thực Tế | Tên Chân (BCM) | Màu Dây Cắm | Linh Kiện Đích & Chân Nối | Chức Năng Kỹ Thuật |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **PIN 1** | Hàng Trên (ngoài cùng Phải) | `3V3_PWR` | 🟠 Cam | Module GPS NEO-6M (Chân `VCC`) | Cấp nguồn 3.3V nuôi module GPS. |
| **PIN 2** | Hàng Dưới (ngoài cùng Phải) | `5V_PWR_IN` | 🔴 Đỏ to (20AWG) | Mạch Buck XL4015 (Cực `OUT+`) | **Nguồn chính 5.10V nuôi Pi 4**. *Đo VOM trước khi cắm!* |
| **PIN 4** | Hàng Dưới (cột 2 từ Phải) | `5V_PWR_OUT` | 🔴 Đỏ | Cực `(+)` 4 Motor // & Cực `(+)` Còi Buzzer | Cấp nguồn +5V cho cơ cấu chấp hành (motor + còi). |
| **PIN 6** | Hàng Dưới (cột 3 từ Phải) | `GND_MASS` | ⚫ Đen to (20AWG) | Cực `OUT-` Buck, `GND` GPS, `Emitter` 2N2222 | **Mass chung toàn hệ thống**. Bắt buộc thông mạch. |
| **PIN 8** | Hàng Dưới (cột 4 từ Phải) | `GPIO 14` (TXD) | 🟣 Tím | Module GPS NEO-6M (Chân `RXD`) | UART TX ➔ RX (Pi gửi lệnh sang GPS). |
| **PIN 10** | Hàng Dưới (cột 5 từ Phải) | `GPIO 15` (RXD) | 🔵 Xanh Dương | Module GPS NEO-6M (Chân `TXD`) | UART RX 🠔 TX (Pi nhận toạ độ NMEA từ GPS). |
| **PIN 11** | Hàng Trên (cột 6 từ Phải) | `GPIO 17` | 🟢 Xanh Lá | Qua trở `1kΩ` ➔ `Base` 2N2222 (4 Motor //) | Kích rung toàn bộ cụm 4 motor rung mắc song song. |
| **PIN 18** | Hàng Dưới (cột 9 từ Phải) | `GPIO 24` | 🌸 Hồng | Qua trở `1kΩ` ➔ `Base` S8050 (Còi Buzzer) | Kích còi báo động Active Buzzer 5V. |
| **PIN 20** | Hàng Dưới (cột 10 từ Phải) | `GND_MASS` | ⚫ Đen | `Emitter` S8050 & Chân 2 Nút Bấm SOS | Mass âm cho còi và chân đối diện nút SOS. |
| **PIN 22** | Hàng Dưới (cột 11 từ Phải) | `GPIO 25` | 🟡 Vàng | Chân 1 Nút Bấm Khẩn Cấp SOS | Tín hiệu nút SOS (Active LOW, **ĐÃ BỎ TỤ LỌC**). |

*(30 chân còn lại hoàn toàn để trống - NC).*

---

### BƯỚC 2: CẮM CỤM 3 CAMERA (CSI + USB 3.0)

1. **Camera Trước (MIPI CSI):** Cắm cáp dải ribbon vào cổng CSI (Camera Slot) trên bo mạch Pi 4, mặt tiếp xúc màu bạc quay về phía cổng HDMI.
2. **Camera Điểm Mù Trái:** Cắm vào cổng USB 3.0 màu xanh (Trên).
3. **Camera Điểm Mù Phải:** Cắm vào cổng USB 3.0 màu xanh (Dưới).

---

### BƯỚC 3: TẢI CODE TỪ GITHUB VỀ RASPBERRY PI 4

Mở Terminal trên Raspberry Pi 4 (hoặc SSH vào Pi):

```bash
# 1. Cập nhật hệ thống và cài đặt git
sudo apt update && sudo apt install -y git python3-pip python3-opencv

# 2. Clone mã nguồn dự án từ GitHub
cd ~
git clone https://github.com/trandat09062003/Smart_Helmet.git

# 3. Di chuyển vào thư mục code Pi
cd ~/Smart_Helmet/smart_helmet_pi

# 4. Cấp quyền thực thi cho các file script
chmod +x *.sh *.py
```

---

### BƯỚC 4: CÀI ĐẶT MÔI TRƯỜNG & THƯ VIỆN PHẦN MỀM

Chạy script cài đặt tự động (mất khoảng 3-5 phút):

```bash
./setup.sh
```

Hoặc cài thủ công qua pip:
```bash
pip3 install -r requirements.txt
```

---

### BƯỚC 5: CHẨN ĐOÁN & KIỂM TRA PHẦN CỨNG (HARDWARE TEST)

Trước khi chạy hệ thống chính, chạy công cụ kiểm tra tự động để đảm bảo 100% linh kiện hoạt động tốt:

```bash
python3 test_hardware.py
```
* **Chọn 1:** Test cụm 4 motor rung (rung mạnh trong 1.2s).
* **Chọn 2:** Test còi Buzzer (kêu 3 tiếng bíp ngắn).
* **Chọn 3:** Test nút bấm SOS (bấm nút trên mũ để phát hiện mức 0).
* **Chọn 4:** Test module GPS (đọc bản tin NMEA qua cổng UART).
* **Chọn 5:** Chạy toàn bộ bài test tự động.

Kiểm tra hình ảnh từ 3 camera:
```bash
python3 test_cameras.py
```

---

### BƯỚC 6: KHỞI ĐỘNG HỆ THỐNG CHÍNH

#### Cách 1: Chạy trực tiếp trên Terminal (Xem log thời gian thực):
```bash
./run.sh
```
Hoặc:
```bash
python3 main.py
```

#### Cách 2: Chạy ngầm trong nền (Chạy tự động khi gắn mũ lên xe):
```bash
./start_background.sh
```

* **Kiểm tra trạng thái đang chạy:**
  ```bash
  ./status.sh
  ```
* **Xem log thời gian thực:**
  ```bash
  tail -f smart_helmet.log
  ```
* **Dừng chương trình:**
  ```bash
  ./stop.sh
  ```

---

### BƯỚC 7: TRUY CẬP WEB DASHBOARD GIÁM SÁT 360°

Khi hệ thống đang chạy, bạn có thể dùng điện thoại hoặc máy tính bảng kết nối cùng mạng WiFi với Pi để xem camera và toạ độ:
* Mở trình duyệt web gõ: `http://<IP_CỦA_PI_4>:5000`
* Ví dụ: `http://192.168.1.50:5000`
* Giao diện sẽ hiển thị đồng thời:
  * 3 Luồng Camera Live Stream (Trước, Sau-Phải, Sau-Trái).
  * Hộp nhận diện vật thể AI Bounding Box (Người, Ô tô, Xe máy, Xe tải...).
  * Bản đồ GPS vị trí hiện tại.
  * Trạng thái rung haptic 4 hướng và còi cảnh báo.
