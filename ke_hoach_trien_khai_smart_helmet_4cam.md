# KẾ HOẠCH TRIỂN KHAI HỆ THỐNG 4 CAMERA CỐ ĐỊNH 360° - SMART HELMET
*(Dự án Mũ Thông Minh Hỗ Trợ Người Khiếm Thị - Đề Tài KHKT)*

## 1. Lý Do Chọn 4 Camera Cố Định Thay Vì Camera Xoay Góc

| Tiêu chí | Camera Xoay (1 Cam + Động cơ Servo/Bước) | Hệ Thống 4 Cam Cố Định (Trước - Sau - Trái - Phải) | Đánh giá |
| :--- | :--- | :--- | :--- |
| **Độ trễ quan sát** | Lớn (mất thời gian quay quét qua lại) | **Bằng 0** (Quan sát đồng thời 4 hướng liên tục) | 4 Cam an toàn vượt trội |
| **Điểm mù tức thời** | Có (khi nhìn phía trước thì mù hoàn toàn phía sau) | **Không có điểm mù** nếu góc FOV $\ge 110^\circ$ | Phát hiện kịp thời xe cộ từ sau/bên hông |
| **Độ bền cơ học** | Dễ hỏng nhông, kẹt dây xoay liên tục | **Cực bền** (Solid-state, không chi tiết chuyển động) | Chịu rung lắc tốt khi người dùng di chuyển |
| **Rung lắc & Tiếng ồn**| Motor rung và phát tiếng kêu sát tai người dùng | **Hoàn toàn êm ái**, không gây khó chịu | Tối ưu trải nghiệm cho người khiếm thị |
| **Độ mờ ảnh (Motion Blur)** | Mờ nhòe khi motor đang lia góc | **Ảnh sắc nét**, thuật toán AI nhận diện ổn định | Đầu vào tin cậy cho mô hình AI |

---

## 2. Xác Định & Lựa Chọn Camera Phù Hợp

### 2.1. Yêu cầu kỹ thuật bắt buộc của Camera
1. **Góc nhìn (FOV - Field of View):** 
   - Để 4 camera phủ kín $360^\circ$, mỗi cam phải có góc nhìn ngang (Horizontal FOV) $\ge 90^\circ$.
   - **Thực tế:** Cần chọn ống kính góc rộng từ **$110^\circ$ đến $140^\circ$** để có phần giao thoa chồng lấn góc (~$20^\circ - 30^\circ$ giữa hai cam liền kề), loại bỏ hoàn toàn góc chết ở khoảng cách gần ($< 1\,\text{m}$).
2. **Kích thước & Trọng lượng:** Dạng module bo trần (bare board) không vỏ kim loại nặng nề, kích thước gọn ($28 \times 28\,\text{mm}$ hoặc $32 \times 32\,\text{mm}$) để tích hợp chìm vào mũ bảo hiểm.
3. **Chuẩn kết nối & Giao tiếp:** USB UVC (chuẩn driver phổ thông không cần driver ngoài trên Linux).

### 2.2. So sánh & Đề xuất Module Cụ thể

| Phương án | Chi tiết Module | Ưu điểm | Nhược điểm | Đánh giá |
| :--- | :--- | :--- | :--- | :--- |
| **Phương án 1 (Khuyên dùng)** | **4x Module USB Camera 1080p/720p FOV 120° - 140°**<br>*(Cảm biến: OV2710 / GC2053 / IMX323)* | - Chuẩn UVC cắm là nhận trên Linux/RPi.<br>- Dễ nối dài dây USB qua vành mũ.<br>- Giá thành rẻ (~150k - 250k/cái).<br>- Hỗ trợ nén cứng MJPEG giảm tải CPU. | Cần 1 chip USB Hub 4 cổng (GL850G/FE1.1s) để gộp luồng. | **Khả thi nhất, ổn định nhất cho đề tài KHKT** |
| **Phương án 2** | **Bộ Arducam Camarray 4-Cam MIPI CSI** *(OV5647 / IMX219)* | - Đồng bộ khung hình mức phần cứng.<br>- Băng thông cao trực tiếp vào GPU/ISP. | - Giá thành rất cao ($> 2 - 3 triệu).<br>- Cáp FPC mềm rất dễ đứt gãy khi uốn quanh mũ. | Không tối ưu cho ngân sách học sinh |
| **Phương án 3** | **4x Module ESP32-S3 Camera truyền WiFi/RTSP** | - Không cần dây dẫn vật lý từ cam về bo chủ. | - Độ trễ mạng WiFi không đồng bộ.<br>- Dễ nghẽn mạng nội bộ, hao pin nhiều. | Rủi ro cao về độ trễ cảnh báo |

> **Chốt giải pháp:** Chọn **4 Module USB Camera góc rộng $120^\circ - 130^\circ$ chuẩn UVC (cảm biến OV2710 hoặc GC2053)** kết nối qua mạch gộp USB 2.0 Hub Controller (IC FE1.1s hoặc GL850G).

---

## 3. Kiến Trúc Bố Trí Phần Cứng & Góc Nhìn 360°

```
                  [Camera 1: TRƯỚC] (FOV 120°)
                     \         /
                      \       /
[Camera 4: TRÁI] <---  ( NÓN )  ---> [Camera 2: PHẢI] (FOV 120°)
(FOV 120°)            /       \
                     /         \
                   [Camera 3: SAU] (FOV 120°)
```

- **Phần giao thoa 4 góc:** Mỗi camera quét $120^\circ$. Tổng $4 \times 120^\circ = 480^\circ$ phủ vượt mức $360^\circ$, tạo vùng đệm chồng lấn $30^\circ$ ở mỗi góc giao nhau (Trước-Trái, Trước-Phải, Sau-Trái, Sau-Phải), đảm bảo phát hiện vật cản từ mọi hướng tiếp cận.

### Hệ Thống Cảnh Báo Đa Phương Thức
- **4 Motor rung định hướng:** Bố trí 4 vị trí trên vành lót nón (Trước trán, Gáy sau, Thái dương trái, Thái dương phải). Vật cản phát hiện từ góc nào thì rung motor ở hướng đó.
- **Loa mini / Tai nghe dẫn truyền xương:** Phát giọng nói hướng dẫn định tuyến và cảnh báo cấp độ cao (*"Cẩn thận bên trái", "Có hố/bậc thang phía trước"*).

---

## 4. Kế Hoạch Triển Khai Chi Tiết (8 Tuần)

### Giai đoạn 1: Chuẩn bị linh kiện & Khảo sát góc nhìn (Tuần 1 - Tuần 2)
1. Đặt mua mẫu linh kiện:
   - 4 module USB Camera góc rộng $120^\circ$ (kích thước nhỏ gọn $32 \times 32\,\text{mm}$ hoặc $28 \times 28\,\text{mm}$).
   - 1 mạch USB Hub 4 cổng dạng mạch trần (kích thước siêu mỏng).
   - 4 motor rung đồng xu $1027$ hoặc $1234$.
   - Module khuếch đại âm thanh mini + loa nhỏ / tai nghe jack 3.5mm.
   - Bo mạch chủ: Raspberry Pi 5 (hoặc Orange Pi 5) + thẻ nhớ tốc độ cao A2 V30.
2. Kiểm tra thực tế góc phủ FOV trên máy tính:
   - Dùng script Python OpenCV mở đồng thời 4 camera.
   - Đánh dấu góc phủ thực tế xem có bị méo góc quá mức không.

### Giai đoạn 2: Thiết kế phần cứng PCB & Gá cơ khí (Tuần 3 - Tuần 4)
1. **Thiết kế Altium Designer:**
   - Vẽ schematic mạch phụ trợ (Carrier board): Khối hạ áp DC-DC $5\text{V}/5\text{A}$, khối đệm lái 4 motor rung (sử dụng MOSFET / Transistor), khối kết nối nút SOS và còi buzzer.
   - Thiết kế layout PCB dạng module nhỏ gọn gắn bên trong hoặc phía sau mũ.
2. **Thiết kế 3D & In vỏ gá (3D Printing):**
   - Thiết kế 4 vỏ ngàm giữ mắt camera nghiêng nhẹ khoảng $5^\circ - 10^\circ$ hướng xuống để quan sát mặt đường và chân người đi lại.
   - Vỏ bảo vệ bộ xử lý tản nhiệt tốt, dây cáp đi ngầm dưới lớp lót xốp nón.

### Giai đoạn 3: Phát triển phần mềm & AI Nhận Diện Đa Hướng (Tuần 5 - Tuần 7)
1. **Thu thập luồng hình ảnh song song:**
   - Dùng thư viện đa luồng `threading` trong Python đọc đồng thời 4 luồng camera với chuẩn MJPEG, độ phân giải $640 \times 480$ @ $15\text{fps}$ để tối ưu hiệu năng.
2. **Xử lý AI nhẹ (Lightweight Edge AI):**
   - Sử dụng **YOLOv8-Nano (YOLOv8n)** hoặc **YOLOv11n** đã convert sang định dạng ONNX/NCNN/TensorRT.
   - Chia trọng số ưu tiên:
     - **Cam Trước:** Chạy AI liên tục để phát hiện người, xe cộ, cột điện, bậc tam cấp, chướng ngại vật ngay trước mặt.
     - **Cam Sau & 2 Bên Trái/Phải:** Chạy AI phát hiện xe hoặc người tiến lại gần với tốc độ nhanh (Blind-spot & Proximity Detection).
3. **Thuật toán phản hồi:**
   - Vật cản bên nào $\rightarrow$ Kích hoạt motor rung bên đó tương ứng.
   - Khoảng cách càng gần $\rightarrow$ Tần số rung càng dồn dập.
   - Loa đọc cảnh báo ngắn gọn, dứt khoát: *"Xe tiếp cận bên trái", "Có vật cản phía trước"*.

### Giai đoạn 4: Thử nghiệm mô hình & Hoàn thiện báo cáo KHKT (Tuần 8)
1. Thử nghiệm thực tế trong môi trường an toàn (hành lang lớp học, sân trường có chướng ngại vật giả lập).
2. Tinh chỉnh thuật toán lọc bớt cảnh báo thừa (tránh gây nhức đầu cho người dùng).
3. Biên tập hồ sơ, bản vẽ Altium, mô hình 3D, poster thuyết trình KHKT.
