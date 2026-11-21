#ifndef WEB_UI_H
#define WEB_UI_H

#include <Arduino.h>
#include <pgmspace.h>

const char htmlPage[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Trạm Giám Sát Cây Trồng IoT</title>
  <style>
    body { text-align: center; background-color: #181a1b; color: #f0f0f0; font-family: Arial, sans-serif; margin: 0; padding: 20px; }
    h2 { color: #4CAF50; margin-bottom: 5px; }
    .sub { color: #aaa; font-size: 14px; margin-bottom: 20px; }
    .grid { display: flex; justify-content: center; gap: 15px; flex-wrap: wrap; max-width: 900px; margin: 0 auto 20px auto; }
    .card { background: #242729; border: 1px solid #383c3f; border-radius: 8px; padding: 15px 25px; min-width: 160px; }
    .card-title { font-size: 13px; color: #bbb; margin-bottom: 8px; }
    .card-val { font-size: 24px; font-weight: bold; color: #4CAF50; }
    .alert-box { max-width: 760px; margin: 0 auto 20px auto; padding: 12px; border-radius: 6px; background: #2c221e; border: 1px solid #ff9800; color: #ffb74d; font-size: 14px; display: none; }
    .btn-group { display: flex; justify-content: center; gap: 12px; flex-wrap: wrap; }
    button { padding: 13px 22px; font-size: 15px; font-weight: bold; cursor: pointer; color: white; border: none; border-radius: 6px; }
    .btn-cam { background-color: #4CAF50; }
    .btn-cam:hover { background-color: #45a049; }
    .btn-ai { background-color: #9C27B0; }
    .btn-ai:hover { background-color: #7B1FA2; }
    .btn-wifi { background-color: #2196F3; }
    .btn-wifi:hover { background-color: #0b7dda; }
    img { max-width: 92%; max-height: 68vh; border: 3px solid #383c3f; border-radius: 8px; margin-top: 20px; box-shadow: 0px 4px 20px rgba(0,0,0,0.6); }
    .wifi-panel { display: none; max-width: 460px; margin: 20px auto; background: #242729; border: 1px solid #444; border-radius: 8px; padding: 18px; text-align: left; }
    .wifi-item { padding: 10px; border-bottom: 1px solid #383c3f; cursor: pointer; display: flex; justify-content: space-between; }
    .wifi-item:hover { background: #303437; }
    input[type=text], input[type=password] { width: 100%; box-sizing: border-box; padding: 10px; margin: 8px 0 12px 0; border-radius: 5px; border: 1px solid #555; background: #181a1b; color: #fff; }
  </style>
</head>
<body>
  <h2>🌱 TRẠM GIÁM SÁT CÂY TRỒNG IOT (ESP32-S3 + OV5640)</h2>
  <p class="sub">Nhấn phím <b>SPACE (Dấu cách)</b> hoặc bấm nút bên dưới để chụp ảnh và chẩn đoán bệnh lá cây</p>

  <div class="grid">
    <div class="card">
      <div class="card-title">🌡️ NHIỆT ĐỘ KHÔNG KHÍ</div>
      <div class="card-val" id="temp">-- °C</div>
    </div>
    <div class="card">
      <div class="card-title">💧 ĐỘ ẨM KHÔNG KHÍ</div>
      <div class="card-val" id="hum">-- %</div>
    </div>
    <div class="card">
      <div class="card-title">🌱 ĐỘ ẨM ĐẤT</div>
      <div class="card-val" id="soil">-- %</div>
    </div>
    <div class="card" style="min-width: 220px; border-color: #9C27B0;">
      <div class="card-title">🧠 CHẨN ĐOÁN BỆNH (AI)</div>
      <div class="card-val" id="ai-disease" style="font-size: 18px; color: #ce93d8;">Đang chờ ảnh...</div>
      <div id="ai-conf" style="font-size: 13px; color: #bbb; margin-top: 5px;">Độ tin cậy: -- %</div>
    </div>
  </div>

  <div class="alert-box" id="alertBox"></div>

  <div class="btn-group">
    <button class="btn-cam" onclick="takePhoto()">📸 CHỤP ẢNH MỚI</button>
    <button class="btn-ai" onclick="analyzeCurrentPhoto()">🧠 CHẨN ĐOÁN AI</button>
    <button class="btn-wifi" onclick="scanWiFi()">🔍 QUÉT & ĐỔI WI-FI MỚI</button>
  </div>

  <div class="wifi-panel" id="wifiPanel">
    <h3 style="margin-top:0;color:#2196F3;">📶 Chọn mạng Wi-Fi mới (Chế độ STA)</h3>
    <div id="wifiList" style="max-height:180px;overflow-y:auto;margin-bottom:12px;">Đang quét sóng Wi-Fi...</div>
    <label>Tên Wi-Fi (SSID):</label>
    <input type="text" id="newSsid" placeholder="Chọn ở trên hoặc nhập tên Wi-Fi">
    <label>Mật khẩu Wi-Fi:</label>
    <input type="password" id="newPass" placeholder="Nhập mật khẩu (để trống nếu không có)">
    <div style="display:flex;gap:10px;">
      <button class="btn-cam" style="flex:1;" onclick="connectNewWiFi()">Kết Nối & Lưu</button>
      <button style="background:#666;" onclick="document.getElementById('wifiPanel').style.display='none'">Đóng</button>
    </div>
    <p id="wifiStatus" style="color:#ffb74d;font-size:13px;margin-bottom:0;"></p>
  </div>

  <br>
  <img id="photo" src="/capture" alt="Đang tải khung hình từ OV5640..." onload="analyzeCurrentPhoto()">

  <script>
    const AI_API_URL = "http://127.0.0.1:8000/predict";

    const DISEASE_LABELS = {
      "Bacterial": "⚠️ Bệnh đốm vi khuẩn",
      "fungal": "⚠️ Bệnh nấm lá",
      "healthy": "✅ Lá khỏe mạnh",
      "ot_dom_vi_khuan": "⚠️ Ớt đốm vi khuẩn",
      "ot_khoe_manh": "✅ Cây ớt khỏe mạnh"
    };

    function takePhoto() {
      document.getElementById('ai-disease').innerText = "⏳ Đang chụp ảnh...";
      document.getElementById('ai-disease').style.color = "#ffb74d";
      document.getElementById('photo').src = '/capture?t=' + new Date().getTime();
    }

    async function analyzeCurrentPhoto() {
      const imgEl = document.getElementById('photo');
      const statusEl = document.getElementById('ai-disease');
      const confEl = document.getElementById('ai-conf');

      if (!imgEl || !imgEl.complete || imgEl.naturalWidth === 0) {
        statusEl.innerText = "Chưa có ảnh camera";
        return;
      }

      statusEl.innerText = "⏳ Đang phân tích AI...";
      statusEl.style.color = "#ffb74d";

      try {
        const canvas = document.createElement('canvas');
        canvas.width = imgEl.naturalWidth;
        canvas.height = imgEl.naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(imgEl, 0, 0);

        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9));
        const formData = new FormData();
        formData.append('file', blob, 'esp32_ov5640.jpg');

        const response = await fetch(AI_API_URL, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) throw new Error('HTTP ' + response.status);

        const data = await response.json();
        const rawClass = data.predicted_class;
        const readableName = DISEASE_LABELS[rawClass] || rawClass;
        const isHealthy = (rawClass === 'healthy' || rawClass === 'ot_khoe_manh');

        statusEl.innerText = readableName;
        statusEl.style.color = isHealthy ? '#4CAF50' : '#ff5252';
        confEl.innerText = 'Độ tin cậy: ' + data.confidence_percent + ' %';
      } catch (err) {
        console.error('Lỗi AI Server:', err);
        statusEl.innerText = "❌ Lỗi kết nối AI Server";
        statusEl.style.color = "#ff5252";
        confEl.innerText = "Kiểm tra Uvicorn cổng 8000";
      }
    }

    function scanWiFi() {
      const panel = document.getElementById('wifiPanel');
      const list = document.getElementById('wifiList');
      panel.style.display = 'block';
      list.innerHTML = '⏳ Đang quét các mạng Wi-Fi xung quanh...';

      fetch('/scan-wifi')
        .then(res => res.json())
        .then(networks => {
          if (!networks.length) {
            list.innerHTML = 'Không tìm thấy mạng Wi-Fi nào.';
            return;
          }
          list.innerHTML = '';
          networks.forEach(net => {
            const div = document.createElement('div');
            div.className = 'wifi-item';
            div.innerHTML = `<span><b>${net.ssid}</b> ${net.secure ? '🔒' : '🔓'}</span><span style="color:#aaa;">${net.rssi} dBm</span>`;
            div.onclick = () => { document.getElementById('newSsid').value = net.ssid; };
            list.appendChild(div);
          });
        })
        .catch(() => { list.innerHTML = 'Lỗi khi quét Wi-Fi.'; });
    }

    function connectNewWiFi() {
      const ssid = document.getElementById('newSsid').value.trim();
      const pass = document.getElementById('newPass').value;
      const status = document.getElementById('wifiStatus');
      if (!ssid) { alert('Vui lòng chọn hoặc nhập tên Wi-Fi!'); return; }

      status.innerText = '🔄 Đang lưu và chuyển sang Wi-Fi "' + ssid + '"... Xem địa chỉ IP mới trên Serial Monitor.';
      fetch('/connect-wifi?ssid=' + encodeURIComponent(ssid) + '&pass=' + encodeURIComponent(pass))
        .catch(() => {});
    }

    function updateSensors() {
      fetch('/sensors')
        .then(res => res.json())
        .then(data => {
          document.getElementById('temp').innerText = data.temp !== null ? data.temp.toFixed(1) + ' °C' : 'Lỗi DHT22';
          document.getElementById('hum').innerText = data.hum !== null ? data.hum.toFixed(1) + ' %' : 'Lỗi DHT22';
          document.getElementById('soil').innerText = data.soil + ' %';

          const alertBox = document.getElementById('alertBox');
          if (data.alerts && data.alerts.length > 0) {
            alertBox.style.display = 'block';
            alertBox.innerHTML = '⚠️ <b>Cảnh báo môi trường:</b> ' + data.alerts.join(' | ');
          } else {
            alertBox.style.display = 'none';
          }
        })
        .catch(err => console.error('Lỗi đọc dữ liệu cảm biến:', err));
    }

    window.addEventListener('keydown', function(event) {
      if (event.code === 'Space' || event.keyCode === 32) {
        event.preventDefault();
        takePhoto();
      }
    });

    updateSensors();
    setInterval(updateSensors, 3000);
  </script>
</body>
</html>
)rawliteral";

#endif // WEB_UI_H