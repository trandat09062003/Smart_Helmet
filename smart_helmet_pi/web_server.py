"""
SMART HELMET 360 - MÁY CHỦ WEB DASHBOARD GIÁM SÁT THỜI GIAN THỰC
Kiến trúc Triple-Camera 360° (Chạy đồng thời 3 Camera ở FPS thấp + Phân Vùng 4 Hướng Haptic)
Phục vụ thuyết trình cuộc thi KHKT và cho người thân theo dõi từ xa qua điện thoại
"""
import time
import os
import cv2
import logging
from flask import Flask, Response, render_template_string, jsonify, request

logger = logging.getLogger("WebServer")


def create_app(camera_mgr, haptic_ctrl, sos_mgr, ai_detector, state_holder):
    app = Flask(__name__)

    # HTML Giao diện Dashboard công nghệ cao (Triple-Stream 3 Camera + 4 Haptic Radar)
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Smart Helmet 360° - Trung Tâm Giám Sát 3 Camera Đồng Thời</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg: #090e1a;
                --panel: #111a2e;
                --panel-hover: #16223b;
                --border: rgba(255, 255, 255, 0.08);
                --cyan: #00f0ff;
                --green: #00e676;
                --yellow: #ffb300;
                --red: #ff3366;
                --text: #f8fafc;
                --text-dim: #94a3b8;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Plus Jakarta Sans', sans-serif;
                background-color: var(--bg);
                color: var(--text);
                padding: 20px;
                background-image: radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.08) 0%, transparent 40%),
                                  radial-gradient(circle at 90% 80%, rgba(255, 51, 102, 0.08) 0%, transparent 40%);
            }
            .header {
                display: flex;
                flex-wrap: wrap;
                justify-content: space-between;
                align-items: center;
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 16px 24px;
                margin-bottom: 20px;
            }
            .title-group h1 {
                font-size: 1.4rem;
                font-weight: 800;
                color: #fff;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .badge-live {
                background: rgba(0, 230, 118, 0.2);
                color: var(--green);
                border: 1px solid var(--green);
                padding: 3px 10px;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 700;
                animation: pulse 2s infinite;
            }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            
            .grid-main {
                display: grid;
                grid-template-columns: 1.95fr 1fr;
                gap: 20px;
            }
            @media (max-width: 1024px) {
                .grid-main { grid-template-columns: 1fr; }
            }

            .card {
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 16px;
                padding: 20px;
                overflow: hidden;
            }
            .card-title {
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 15px;
                color: var(--cyan);
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .video-box {
                position: relative;
                width: 100%;
                background: #000;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid rgba(0, 240, 255, 0.3);
            }
            .video-box img {
                width: 100%;
                height: auto;
                display: block;
            }
            
            /* Radar 360 & Haptic */
            .radar-wrapper {
                position: relative;
                width: 240px;
                height: 240px;
                margin: 10px auto;
                border-radius: 50%;
                border: 2px dashed rgba(0, 240, 255, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                background: radial-gradient(circle, rgba(0, 240, 255, 0.05) 0%, transparent 70%);
            }
            .helmet-core {
                width: 86px;
                height: 86px;
                border-radius: 50%;
                background: #1e293b;
                border: 2px solid var(--cyan);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                font-size: 0.72rem;
                font-weight: 700;
                color: var(--cyan);
                box-shadow: 0 0 20px rgba(0, 240, 255, 0.3);
            }
            .haptic-node {
                position: absolute;
                width: 44px;
                height: 44px;
                border-radius: 50%;
                background: #1e293b;
                border: 2px solid var(--border);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.7rem;
                font-weight: 800;
                transition: all 0.2s ease;
            }
            .haptic-node.active {
                background: var(--red);
                border-color: #fff;
                color: #fff;
                box-shadow: 0 0 20px var(--red);
                transform: scale(1.15);
            }
            .node-front { top: 8px; left: calc(50% - 22px); }
            .node-right { top: calc(50% - 22px); right: 8px; }
            .node-rear  { bottom: 8px; left: calc(50% - 22px); }
            .node-left  { top: calc(50% - 22px); left: 8px; }

            /* Telemetry Stats */
            .stats-row {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
                margin-top: 15px;
            }
            .cam-stats-row {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin-top: 14px;
            }
            @media (max-width: 768px) {
                .cam-stats-row { grid-template-columns: 1fr; }
            }
            .stat-mini {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 12px 14px;
            }
            .stat-label { font-size: 0.74rem; color: var(--text-dim); }
            .stat-val { font-size: 1.02rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #fff; margin-top: 4px; }

            /* Action Buttons */
            .btn-group {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
                margin-top: 15px;
            }
            .btn {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid var(--border);
                color: var(--text);
                padding: 10px;
                border-radius: 10px;
                font-size: 0.85rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .btn:hover { background: var(--panel-hover); border-color: var(--cyan); }
            .btn-sos {
                grid-column: span 2;
                background: rgba(255, 51, 102, 0.2);
                border-color: var(--red);
                color: var(--red);
                font-weight: 700;
            }
            .btn-sos:hover { background: var(--red); color: #fff; }

            /* Log box */
            .log-box {
                background: #060911;
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 12px;
                height: 140px;
                overflow-y: auto;
                font-family: 'JetBrains Mono', monospace;
                font-size: 0.78rem;
                color: #38bdf8;
                margin-top: 15px;
            }
            .log-item { margin-bottom: 6px; }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title-group">
                <h1>Smart Helmet 360° AI Dashboard</h1>
                <p style="font-size: 0.85rem; color: var(--text-dim); margin-top: 3px;">
                    Dự án Nghiên Cứu KHKT 2026 • Hệ thống 3 Camera Chạy Đồng Thời ở FPS Thấp + Phân Vùng 4 Hướng Haptic
                </p>
            </div>
            <div>
                <span class="badge-live">● 3-CAM SIMULTANEOUS LOW-FPS</span>
            </div>
        </div>

        <div class="grid-main">
            <!-- Cột Trái: Luồng 3 Camera Đồng Thời (Trước, Sau, Phải) -->
            <div class="card">
                <div class="card-title">
                    <span>Luồng Thị Giác Đồng Thời 3 Camera (Trước 0° • Sau 180° • Phải 90°)</span>
                </div>
                <div class="video-box">
                    <img src="/video_feed" alt="3 Camera Triple Stream">
                </div>
                <div style="margin-top: 12px; font-size: 0.85rem; color: var(--text-dim); display:flex; justify-content:space-between; align-items:center;">
                    <span>Chế độ: <b>Continuous Low-FPS V4L2-MMAP (3 Cam Đồng Thời + Tách Vùng Trái/Trước)</b></span>
                    <span id="fpsDisplay">Stream FPS: 6.0</span>
                </div>
                <!-- Bảng trạng thái trực tiếp các mắt Camera -->
                <div class="cam-stats-row" id="camStatsContainer">
                    <!-- Được cập nhật tự động qua JavaScript từ /api/status -->
                </div>
                <div style="margin-top: 12px;">
                    <button class="btn" style="width:100%; border-color: var(--cyan); color: var(--cyan);" onclick="rescanCameras()">
                        QUÉT & KẾT NỐI LẠI CÁC CỔNG CAMERA USB
                    </button>
                </div>
            </div>

            <!-- Cột Phải: Radar Haptic & Điều Khiển -->
            <div class="card">
                <div class="card-title">
                    <span>Mô Phỏng Radar Mũ & 4 Motor Rung Haptic</span>
                </div>

                <div class="radar-wrapper">
                    <div class="helmet-core">
                        <span>SMART</span>
                        <span>HELMET</span>
                    </div>
                    <div class="haptic-node node-front" id="nodeFRONT">TRƯỚC</div>
                    <div class="haptic-node node-right" id="nodeRIGHT">PHẢI</div>
                    <div class="haptic-node node-rear"  id="nodeREAR">SAU</div>
                    <div class="haptic-node node-left"  id="nodeLEFT">TRÁI</div>
                </div>

                <!-- Thông số phần cứng -->
                <div class="stats-row">
                    <div class="stat-mini">
                        <div class="stat-label">Nhiệt Độ CPU Pi</div>
                        <div class="stat-val" id="cpuTemp">-- °C</div>
                    </div>
                    <div class="stat-mini">
                        <div class="stat-label">Tải CPU</div>
                        <div class="stat-val" id="cpuUsage">-- %</div>
                    </div>
                    <div class="stat-mini">
                        <div class="stat-label">Tọa Độ GPS (Vĩ độ)</div>
                        <div class="stat-val" id="gpsLat">10.7769</div>
                    </div>
                    <div class="stat-mini">
                        <div class="stat-label">Tọa Độ GPS (Kinh độ)</div>
                        <div class="stat-val" id="gpsLon">106.7009</div>
                    </div>
                </div>

                <!-- Nút bấm kiểm tra chức năng -->
                <div class="btn-group">
                    <button class="btn" onclick="testVibe('FRONT')">Rung Trước</button>
                    <button class="btn" onclick="testVibe('RIGHT')">Rung Phải</button>
                    <button class="btn" onclick="testVibe('LEFT')">Rung Trái</button>
                    <button class="btn" onclick="testVibe('REAR')">Rung Sau</button>
                    <button class="btn btn-sos" onclick="triggerSOS()">TEST NÚT BẤM SOS KHẨN CẤP</button>
                </div>

                <!-- Nhật ký sự kiện AI -->
                <div class="log-box" id="eventLogs">
                    <div class="log-item">[HỆ THỐNG] Đã khởi động Smart Helmet 360 (Chế độ 3 Camera Đồng Thời Low-FPS).</div>
                </div>
            </div>
        </div>

        <script>
            // Định kỳ cập nhật trạng thái motor rung & thông số hệ thống
            setInterval(() => {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        // Cập nhật trạng thái đèn rung haptic (4 hướng)
                        for (const dir of ['FRONT', 'RIGHT', 'REAR', 'LEFT']) {
                            const el = document.getElementById('node' + dir);
                            if (el) {
                                if (data.haptic[dir]) {
                                    el.classList.add('active');
                                } else {
                                    el.classList.remove('active');
                                }
                            }
                        }

                        // Cập nhật thông số hệ thống
                        if (data.cpu_temp) document.getElementById('cpuTemp').innerText = data.cpu_temp + ' °C';
                        if (data.cpu_usage) document.getElementById('cpuUsage').innerText = data.cpu_usage + ' %';
                        if (data.gps) {
                            document.getElementById('gpsLat').innerText = data.gps.lat;
                            document.getElementById('gpsLon').innerText = data.gps.lon;
                        }
                        if (data.fps) document.getElementById('fpsDisplay').innerText = 'Stream FPS: ' + data.fps.toFixed(1);

                        // Cập nhật trạng thái trực tiếp các mắt Camera (hỗ trợ cả Tri-120 và Ortho-90)
                        if (data.cameras) {
                            const container = document.getElementById('camStatsContainer');
                            const labelMap = {
                                'FRONT':      '1. CAM TRƯỚC (0°)',
                                'REAR_RIGHT': '2. CAM SAU-PHẢI (120°)',
                                'REAR_LEFT':  '3. CAM SAU-TRÁI (240°)',
                                'REAR':       '2. CAM SAU (180°)',
                                'RIGHT':      '3. CAM PHẢI (90°)',
                                'LEFT':       '4. CAM TRÁI (270°)'
                            };

                            let html = '';
                            for (const [dir, camInfo] of Object.entries(data.cameras)) {
                                const title = labelMap[dir] || ('CAM ' + dir);
                                const isConn = camInfo && camInfo.connected;
                                const borderStyle = isConn ? 'rgba(0, 230, 118, 0.5)' : 'rgba(255, 255, 255, 0.08)';
                                const textVal = isConn 
                                    ? `● LIVE ${camInfo.device} (${camInfo.fps || 0} FPS • #${camInfo.frames || 0})`
                                    : '○ Chờ kết nối USB';
                                const colorVal = isConn ? '#00e676' : '#ffb300';

                                html += `
                                <div class="stat-mini" style="border-color:${borderStyle};">
                                    <div class="stat-label">${title}</div>
                                    <div class="stat-val" style="font-size:0.86rem; color:${colorVal};">${textVal}</div>
                                </div>`;
                            }
                            if (html && container) {
                                container.innerHTML = html;
                            }
                        }

                        // Thêm log mới nếu có
                        if (data.recent_log) {
                            const box = document.getElementById('eventLogs');
                            if (!box.firstChild || box.firstChild.innerText !== data.recent_log) {
                                const div = document.createElement('div');
                                div.className = 'log-item';
                                div.innerText = data.recent_log;
                                box.prepend(div);
                                if (box.children.length > 20) box.removeChild(box.lastChild);
                            }
                        }
                    })
                    .catch(err => console.error(err));
            }, 1000);

            function testVibe(direction) {
                fetch('/api/test_vibrate?dir=' + direction, { method: 'POST' });
            }

            function triggerSOS() {
                if (confirm("Kích hoạt thử nghiệm báo động SOS cứu hộ?")) {
                    fetch('/api/trigger_sos', { method: 'POST' });
                }
            }

            function rescanCameras() {
                fetch('/api/rescan_cameras', { method: 'POST' })
                    .then(r => r.json())
                    .then(() => {
                        const box = document.getElementById('eventLogs');
                        const div = document.createElement('div');
                        div.className = 'log-item';
                        div.innerText = '[CAMERA] Đang quét lại 3 cổng Camera USB (Trước • Sau • Phải)...';
                        box.prepend(div);
                    });
            }
        </script>
    </body>
    </html>
    """

    @app.route('/')
    def index():
        return render_template_string(HTML_TEMPLATE)

    def generate_video_stream():
        """Truyền phát luồng hình ảnh MJPEG siêu nhẹ (dùng chung bộ đệm nén sẵn ở FPS thấp)"""
        last_bytes = None
        while True:
            try:
                frame_bytes = state_holder.get('quad_jpeg')
                if frame_bytes is None:
                    frame = state_holder.get('quad_frame')
                    if frame is None:
                        frame = camera_mgr.get_triple_view()
                    ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 58])
                    if ret:
                        frame_bytes = jpeg.tobytes()

                if frame_bytes is not None and frame_bytes is not last_bytes:
                    last_bytes = frame_bytes
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception:
                time.sleep(0.15)
            time.sleep(0.12)

    @app.route('/video_feed')
    def video_feed():
        return Response(generate_video_stream(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route('/api/status')
    def get_status():
        cpu_temp = "--"
        try:
            if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    cpu_temp = f"{float(f.read().strip()) / 1000.0:.1f}"
            else:
                cpu_temp = "45.2"
        except Exception:
            cpu_temp = "45.0"

        return jsonify({
            'haptic': haptic_ctrl.get_status(),
            'cameras': camera_mgr.get_camera_status(),
            'gps': sos_mgr.gps_coords,
            'cpu_temp': cpu_temp,
            'cpu_usage': state_holder.get('cpu_usage', '22'),
            'fps': state_holder.get('fps', 6.0),
            'recent_log': state_holder.get('latest_log', None)
        })

    @app.route('/api/test_vibrate', methods=['POST'])
    def test_vibrate():
        direction = request.args.get('dir', 'FRONT')
        haptic_ctrl.vibrate(direction, pattern="warning")
        return jsonify({'status': 'ok', 'direction': direction})

    @app.route('/api/trigger_sos', methods=['POST'])
    def test_sos():
        sos_mgr.trigger_sos(source="DASHBOARD_WEB_GIAM_KHAO")
        return jsonify({'status': 'sos_activated'})

    @app.route('/api/rescan_cameras', methods=['POST'])
    def rescan_cameras():
        if hasattr(camera_mgr, 'reset_unresponsive_devices'):
            camera_mgr.reset_unresponsive_devices()
        state_holder['latest_log'] = "[CAMERA] Đã yêu cầu quét lại 3 cổng Camera USB."
        return jsonify({'status': 'rescanning'})

    return app
