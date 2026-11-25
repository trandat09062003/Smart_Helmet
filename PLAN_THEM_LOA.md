# Kế hoạch tích hợp Loa ngoài (Jack 3.5mm + PAM8403 5V) cho Smart Helmet 360° AI

## 1. Mục tiêu
Bổ sung loa ngoài nhỏ (2 dây) vào hệ thống **Smart Helmet 360° AI (Raspberry Pi 4)** để phát cảnh báo giọng nói tiếng Việt và âm báo rõ ràng, **không tốn thêm cổng USB** và **không tốn thêm chân GPIO**.

---

## 2. Phần cứng & Đấu nối
* **Linh kiện cần thêm:**
  * 1x Mạch khuếch đại âm thanh mini **PAM8403 (5V)**
  * 1x Jack 3.5mm (3 chân: L, R, GND)
  * 1x Loa nhỏ 4Ω–8Ω (2 dây)
* **Sơ đồ đấu nối:**
  * **Tín hiệu âm thanh:** `Jack 3.5mm (Raspberry Pi 4)` $\rightarrow$ `L / G / R` trên **PAM8403**
  * **Nguồn cấp:** `Buck 5.1V (5V & GND)` $\rightarrow$ `5V / GND` trên **PAM8403**
  * **Ngõ ra loa:** `L+ / L-` (hoặc `R+ / R-`) trên **PAM8403** $\rightarrow$ `2 dây Loa nhỏ`
* **Lưu ý:**
  * Không cắm trực tiếp loa 2 dây vào Jack 3.5mm của Pi 4 (công suất ngõ ra tai nghe quá yếu, dễ gây nhỏ tiếng hoặc quá tải chip âm thanh).
  * Không dùng TDA2050 vì hệ thống chỉ có nguồn **5V** (TDA2050 cần 9V–24V).

---

## 3. Phần mềm (`smart_helmet_pi/voice_alert.py`)
Áp dụng cơ chế quản lý âm thanh từ dự án `AI_DMS_ubu`:
1. **Tự động mở tiếng & đặt âm lượng chuẩn (85%–90%):**
   * Khi khởi tạo `VoiceAlert`, chạy `amixer` (ALSA) và `pactl` (PulseAudio/PipeWire) để unmute và đặt default sink về `bcm2835` / `Headphones` / `analog`.
   * Giới hạn mức âm lượng ở **90%** để tránh rè/vỡ tiếng (clipping) khi qua mạch PAM8403.
2. **Giữ nguyên luồng phát `ALSA_CARD=0`:**
   * Tiếp tục xuất âm thanh qua `espeak-ng` / `espeak` (hoặc `paplay` / `aplay` nếu dùng file `.wav` thu sẵn) trên `ALSA_CARD=0` để không đụng độ với 4 camera USB.

---

## 4. Tài liệu & Kiểm thử
* Cập nhật sơ đồ khối **Jack 3.5mm + PAM8403 + Loa** vào `so_do_noi_chan_smart_helmet_pi.html`.
* Kiểm tra thực tế trên Raspberry Pi 4 bằng `aplay -l` (xác nhận `bcm2835 Headphones`) và chạy thử `voice_alert.py`.
