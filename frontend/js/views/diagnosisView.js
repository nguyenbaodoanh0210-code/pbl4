/**
 * Frontend MVC — View: ESP32-CAM Live Viewfinder & Multimodal Disease Diagnosis
 * Stage 4B Redesign: Places the ESP32-CAM embedded camera scanner at the center,
 * featuring an agricultural viewfinder HUD, laser sweep animation, instant capture trigger,
 * and multimodal AI diagnosis (CNN + DHT22 & LDR sensors).
 */

import { cameraImageUrl } from '../models/apiClient.js';
import { esc, fmt, state } from '../models/store.js';
import { gardenPicker, pill } from './components.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const DISEASE_LABELS = {
  healthy: 'Lá khỏe mạnh',
  leaf_curl: 'Xoăn lá',
  leaf_spot: 'Đốm lá',
  whitefly: 'Ruồi trắng',
  yellowish: 'Vàng lá',
};

const DISEASE_SEVERITY = {
  healthy: 'ok',
  leaf_curl: 'warn',
  leaf_spot: 'warn',
  whitefly: 'danger',
  yellowish: 'danger',
};

function diseaseLabel(key) {
  return DISEASE_LABELS[key] || key || '—';
}

function severityClass(key) {
  return DISEASE_SEVERITY[key] || 'warn';
}

function confidenceBar(score) {
  const pct = score != null ? Math.round(score * 100) : 0;
  const cls = pct >= 80 ? 'bar-high' : pct >= 60 ? 'bar-mid' : 'bar-low';
  return (
    '<div class="conf-bar-wrap" aria-label="Độ tin cậy ' + pct + '%">' +
    '<div class="conf-bar ' + cls + '" style="width:' + Math.min(pct, 100) + '%"></div>' +
    '<span class="conf-pct">' + pct + '%</span>' +
    '</div>'
  );
}

function fmtDate(ts) {
  if (!ts) return '—';
  return new Date(ts).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function statusPill(status) {
  const map = {
    NEW: ['Mới quét', 'pill-warn'],
    PENDING: ['Đang xử lý', 'pill-warn'],
    REVIEWED: ['Đã xem xét', 'pill-ok'],
    RESOLVED: ['Đã xử lý', 'pill-ok'],
    FLAGGED: ['Cần chú ý', 'pill-danger'],
  };
  const [label, cls] = map[status] || ['Không rõ', 'pill-neutral'];
  return pill(label, cls);
}

/** Chuẩn hóa context môi trường từ 2 dạng tên trường của backend */
function resolveEnvContext(log) {
  if (log.sensor_context) return log.sensor_context;
  if (log.temperature_at_capture != null || log.humidity_at_capture != null || log.light_at_capture != null) {
    return {
      temperature: log.temperature_at_capture,
      humidity: log.humidity_at_capture,
      light_level: log.light_at_capture,
    };
  }
  return null;
}

function envSnapshot(ctx) {
  if (!ctx) return '';
  const fields = [
    ['Nhiệt độ', ctx.temperature, '°C'],
    ['Độ ẩm', ctx.humidity, '%'],
    ['Ánh sáng', ctx.light_level, ' Lux'],
  ];
  const items = fields.map(([label, val, unit]) =>
    '<li><span class="env-label">' + label + '</span>' +
    '<span class="env-val">' + (val != null ? fmt(val) + unit : '—') + '</span></li>'
  ).join('');
  return '<ul class="env-snapshot">' + items + '</ul>';
}

// ─── ESP32-CAM Viewfinder & Scanner Screen (Centerpiece) ───────────────────────

function renderEsp32CamScanner() {
  const camDevices = state.devices.filter((d) => d.device_type === 'CAMERA' || d.device_type === 'CAMERA_NODE');
  const areas = state.areas[state.greenhouseId] || [];
  const activeDevice = camDevices[0]?.device_id || 'ESP32-CAM-01';

  // Determine current image to display in viewfinder:
  // 1. Live stream URL if active and enabled
  // 2. Currently selected diagnosis log image
  // 3. Most recent camera log image
  // 4. Default leaf sample
  const latestLog = state.diagnosisResult || state.cameraLogs[0];
  const currentImgUrl = latestLog ? cameraImageUrl(latestLog.log_id) : '/styles/leaf-sample.jpg';
  const isStream = state.esp32StreamMode === 'stream' && state.esp32StreamUrl;
  const feedSrc = isStream ? state.esp32StreamUrl : currentImgUrl;

  const areaOptions = areas.map((a) =>
    '<option value="' + esc(a.area_id) + '">' + esc(a.name) + '</option>'
  ).join('');

  const camDevOptions = camDevices.length
    ? camDevices.map((d) => '<option value="' + esc(d.device_id) + '">' + esc(d.device_id) + '</option>').join('')
    : '<option value="ESP32-CAM-01">ESP32-CAM-01 (Mặc định)</option>';

  return (
    '<section class="esp32-scanner-section" aria-labelledby="esp32-scanner-title">' +

    // Top control bar
    '<div class="esp32-bar">' +
    '<div class="esp32-badge-group">' +
    '<span class="badge-dot-live' + (state.isScanning ? ' scanning' : '') + '"></span>' +
    '<strong id="esp32-scanner-title">Camera quét bệnh cây trồng</strong>' +
    '<span class="esp32-tag">CAMERA NGOÀI VƯỜN</span>' +
    '</div>' +
    '<div class="esp32-meta-pills">' +
    pill('Wi-Fi: Sẵn sàng', 'pill-ok') +
    pill('Tốc độ cao', 'pill-neutral') +
    '</div>' +
    '</div>' +

    // Target Selection (Area & Device)
    '<div class="esp32-target-bar">' +
    '<div class="target-field">' +
    '<label for="trigger-cam-device">Thiết bị Camera</label>' +
    '<select id="trigger-cam-device" class="target-select">' + camDevOptions + '</select>' +
    '</div>' +
    '<div class="target-field">' +
    '<label for="diag-area">Khu vực quét</label>' +
    '<select id="diag-area" class="target-select"><option value="">— Toàn vườn —</option>' + areaOptions + '</select>' +
    '</div>' +
    '</div>' +

    // ── THE VIEWFINDER SCREEN (Màn hình kính ngắm quét) ──
    '<div class="viewfinder-container' + (state.isScanning ? ' is-scanning' : '') + '" id="viewfinder-screen">' +

    // Image Feed / Stream
    '<div class="viewfinder-feed-wrap">' +
    '<img id="viewfinder-feed-img" src="' + esc(feedSrc) + '" alt="Hình ảnh từ Camera" onerror="this.src=\'data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22400%22 height=%22300%22 viewBox=%220 0 400 300%22><rect width=%22400%22 height=%22300%22 fill=%22%23162218%22/><text x=%2250%25%22 y=%2250%25%22 fill=%22%234ade80%22 font-size=%2216%22 font-family=%22sans-serif%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22>Đang chờ tín hiệu từ Camera...</text></svg>\'" />' +
    '</div>' +

    // HUD: Corner brackets [  ]
    '<div class="hud-corner hud-top-left" aria-hidden="true"></div>' +
    '<div class="hud-corner hud-top-right" aria-hidden="true"></div>' +
    '<div class="hud-corner hud-bottom-left" aria-hidden="true"></div>' +
    '<div class="hud-corner hud-bottom-right" aria-hidden="true"></div>' +

    // HUD: Center Reticle / Target Crosshairs
    '<div class="hud-reticle" aria-hidden="true">' +
    '<div class="reticle-circle"></div>' +
    '<div class="reticle-crosshair-h"></div>' +
    '<div class="reticle-crosshair-v"></div>' +
    '<span class="reticle-guide">HƯỚNG ỐNG KÍNH VÀO LÁ CÂY ĐỂ CHỤP</span>' +
    '</div>' +

    // HUD: Top overlay info
    '<div class="hud-top-bar" aria-hidden="true">' +
    '<div class="hud-item"><span class="hud-dot"></span> ' + (isStream ? 'VIDEO TRỰC TIẾP' : 'SẴN SÀNG CHỤP') + '</div>' +
    '<div class="hud-item">Độ nét cao</div>' +
    '<div class="hud-item">' + (isStream ? '15 hình/giây' : 'Chụp nhanh') + '</div>' +
    '</div>' +

    // HUD: Bottom overlay info
    '<div class="hud-bottom-bar" aria-hidden="true">' +
    '<span>Thiết bị: ' + esc(activeDevice) + '</span>' +
    '<span>Góc nhìn rộng · Tự động cân bằng sáng</span>' +
    '</div>' +

    // Laser Scanning Sweep Bar (Animated when scanning)
    '<div class="laser-scanner-line" aria-hidden="true"></div>' +

    // Scanning Status Overlay Text
    (state.isScanning ? (
      '<div class="scanning-hud-status">' +
      '<span class="scanner-spinner"></span>' +
      '<strong>ĐANG CHỤP ẢNH & KIỂM TRA SỨC KHỎE CÂY...</strong>' +
      '<small>Chụp ảnh lá cây qua camera ➔ Phân tích lá ➔ Đánh giá cùng thời tiết</small>' +
      '</div>'
    ) : '') +

    '</div>' + // end viewfinder-container

    // ── MAIN SCAN ACTION BUTTON (Bự, Nổi bật, Trọng tâm) ──
    '<div class="scan-action-wrap">' +
    '<button type="button" class="btn-esp32-scan' + (state.cameraTriggerBusy || state.isScanning ? ' disabled' : '') + '" id="trigger-cam-btn"' + (state.cameraTriggerBusy || state.isScanning ? ' disabled' : '') + '>' +
    (state.isScanning
      ? '<span class="spinner-sm"></span> ĐANG CHỤP ẢNH TỪ CAMERA…'
      : '<span class="scan-icon">📸</span> CHỤP ẢNH & CHẨN ĐOÁN BỆNH LÁ') +
    '</button>' +
    '</div>' +

    (state.cameraTriggerMsg ? '<p class="trigger-msg-box" role="status">' + esc(state.cameraTriggerMsg) + '</p>' : '') +

    // ── STREAM / IP CONFIGURATION TOOLBAR (Nhỏ gọn, tiện lợi) ──
    '<details class="esp32-stream-config">' +
    '<summary>⚙️ Cấu hình xem trực tiếp từ Camera</summary>' +
    '<div class="stream-config-body">' +
    '<label for="esp32-stream-input">Địa chỉ xem video trực tiếp của Camera:' +
    '<input type="url" id="esp32-stream-input" placeholder="Ví dụ: http://192.168.4.1:81/stream" value="' + esc(state.esp32StreamUrl || '') + '">' +
    '</label>' +
    '<div class="stream-config-actions">' +
    '<button type="button" class="btn btn-secondary btn-sm" id="btn-apply-stream">Áp dụng Stream</button>' +
    '<button type="button" class="btn btn-secondary btn-sm" id="btn-snapshot-mode">Dùng chế độ Chụp tĩnh</button>' +
    '</div>' +
    '<small>Khi camera cùng mạng WiFi nội bộ, bạn có thể nhập IP camera để xem video trực tiếp trên kính ngắm.</small>' +
    '</div>' +
    '</details>' +

    // ── FALLBACK FILE UPLOAD (Dự phòng cho kiểm thử offline) ──
    '<details class="manual-upload-fallback">' +
    '<summary>📁 Hoặc tải ảnh từ tệp máy tính (Dự phòng kiểm thử)</summary>' +
    '<div class="fallback-upload-body">' +
    '<p class="fallback-note">Dành cho trường hợp nộp ảnh mẫu kiểm thử hoặc ESP32-CAM chưa kết nối WiFi vườn.</p>' +
    '<form id="diagnose-form" aria-label="Form tải ảnh kiểm thử">' +
    '<div class="upload-dropzone" id="upload-dropzone" role="button" tabindex="0">' +
    '<p>Kéo thả ảnh kiểm thử vào đây hoặc bấm chọn tệp (.jpg, .png)</p>' +
    '<div id="upload-preview" class="upload-preview" hidden></div>' +
    '</div>' +
    '<input type="file" id="diagnose-file" name="file" accept="image/jpeg,image/png,image/webp" style="display:none" />' +
    '<button type="submit" class="btn btn-secondary btn-full" ' + (state.diagnosisLoading ? 'disabled' : '') + '>' +
    (state.diagnosisLoading ? 'Đang phân tích tệp…' : 'Phân tích tệp ảnh này') +
    '</button>' +
    (state.diagnosisError ? '<p class="form-error">' + esc(state.diagnosisError) + '</p>' : '') +
    '</form>' +
    '</div>' +
    '</details>' +

    '</section>'
  );
}

// ─── Camera Log Card ──────────────────────────────────────────────────────────

function cameraLogCard(log) {
  const imgSrc = cameraImageUrl(log.log_id);
  const diagnosis = log.final_diagnosis || log.ai_diagnosis || log.cnn_diagnosis || '';
  const confidence = log.final_confidence ?? log.confidence_score ?? log.cnn_confidence ?? null;
  const capturedAt = log.captured_at || log.timestamp;
  const sevCls = severityClass(diagnosis);
  const isSelected = state.diagnosisResult?.log_id === log.log_id;

  return (
    '<article class="cam-card' + (isSelected ? ' cam-card--selected' : '') + '" data-cam-log="' + esc(log.log_id) + '">' +
    '<div class="cam-thumb-wrap">' +
    '<img class="cam-thumb" src="' + esc(imgSrc) + '" alt="Ảnh quét ' + esc(log.log_id) + '" loading="lazy" onerror="this.closest(\'.cam-thumb-wrap\').classList.add(\'cam-thumb--err\')" />' +
    '<div class="cam-thumb-overlay"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 3h6v6M14 10l7-7M9 21H3v-6M10 14l-7 7"/></svg></div>' +
    '</div>' +
    '<div class="cam-card-body">' +
    '<span class="cam-disease diag-' + sevCls + '">' + esc(diseaseLabel(diagnosis)) + '</span>' +
    statusPill(log.status) +
    '<p class="cam-date">' + esc(fmtDate(capturedAt)) + '</p>' +
    (confidence != null
      ? '<div class="cam-conf-mini">' + confidenceBar(confidence) + '</div>'
      : '') +
    '</div>' +
    '</article>'
  );
}

// ─── Diagnosis Result Card ────────────────────────────────────────────────────

function renderDiagnosisResult() {
  const r = state.diagnosisResult;
  if (!r) {
    return (
      '<div class="diag-empty">' +
      '<div class="diag-empty-icon">🔬</div>' +
      '<h3>Chưa có kết quả phân tích</h3>' +
      '<p>Bấm nút <strong>"Chụp ảnh & chẩn đoán bệnh lá"</strong> trên màn hình camera để hệ thống chụp và phân tích ngay lập tức.</p>' +
      '</div>'
    );
  }

  const sevCls = severityClass(r.final_diagnosis || r.ai_diagnosis || r.cnn_diagnosis);
  const diag = r.final_diagnosis || r.ai_diagnosis || r.cnn_diagnosis;
  const cnnDiag = r.cnn_diagnosis || r.ai_diagnosis;
  const cnnConf = r.cnn_confidence ?? r.confidence_score ?? null;
  const finalConf = r.final_confidence ?? r.confidence_score ?? null;
  const capturedAt = r.captured_at || r.timestamp;
  const envCtx = resolveEnvContext(r);
  const delta = r.confidence_delta;
  const deltaStr = delta != null
    ? (delta >= 0 ? '+' : '') + fmt(delta * 100, 1) + '%'
    : null;

  return (
    '<div class="diag-result-card">' +
    // Header
    '<div class="diag-result-head diag-' + sevCls + '">' +
    '<div>' +
    '<span class="diag-head-tag">KẾT QUẢ PHÂN TÍCH SỨC KHỎE CÂY</span>' +
    '<h3 class="diag-badge">' + esc(diseaseLabel(diag)) + '</h3>' +
    '</div>' +
    statusPill(r.status) +
    '</div>' +

    // CNN Vision
    '<section class="diag-section">' +
    '<h4 class="diag-section-title">🔍 Nhận diện hình ảnh lá cây</h4>' +
    '<div class="diag-row"><span>Triệu chứng phát hiện</span><b>' + esc(diseaseLabel(cnnDiag)) + '</b></div>' +
    '<div class="diag-row"><span>Độ tin cậy hình ảnh</span>' + confidenceBar(cnnConf) + '</div>' +
    '</section>' +

    // Multimodal fusion
    (diag ? (
      '<section class="diag-section">' +
      '<h4 class="diag-section-title">🌿 Kết luận tổng hợp (Hình ảnh + Thời tiết)</h4>' +
      '<div class="diag-row"><span>Chẩn đoán cuối</span><b class="diag-' + sevCls + '">' + esc(diseaseLabel(diag)) + '</b></div>' +
      '<div class="diag-row"><span>Độ tin cậy tổng thể</span>' + confidenceBar(finalConf) + '</div>' +
      (deltaStr ? '<div class="diag-row"><span>Ảnh hưởng do thời tiết</span><b class="delta-' + (delta >= 0 ? 'up' : 'down') + '">' + deltaStr + '</b></div>' : '') +
      '</section>'
    ) : '') +

    // Environment snapshot
    (envCtx ? (
      '<section class="diag-section">' +
      '<h4 class="diag-section-title">🌤️ Thời tiết ngoài vườn lúc chụp ảnh</h4>' +
      envSnapshot(envCtx) +
      '</section>'
    ) : '') +

    // Recommendation
    (r.recommended_action ? (
      '<section class="diag-section diag-rec">' +
      '<h4 class="diag-section-title">💡 Lời khuyên chăm sóc & điều trị</h4>' +
      '<p class="diag-rec-text">' + esc(r.recommended_action) + '</p>' +
      '</section>'
    ) : '') +

    // Metadata
    '<div class="diag-meta">' +
    '<span>Camera: <code>' + esc(r.device_id || 'ESP32-CAM') + '</code></span>' +
    '<span>Thời điểm: ' + esc(fmtDate(capturedAt)) + '</span>' +
    '</div>' +

    // Action buttons
    '<div class="diag-actions">' +
    (r.status !== 'REVIEWED' && r.status !== 'RESOLVED'
      ? '<button type="button" class="btn btn-secondary" data-patch-status="REVIEWED" data-log-id="' + esc(r.log_id) + '">Đánh dấu Đã xem xét</button>'
      : '') +
    (r.status !== 'RESOLVED'
      ? '<button type="button" class="btn btn-primary" data-patch-status="RESOLVED" data-log-id="' + esc(r.log_id) + '">Đánh dấu Đã xử lý</button>'
      : '') +
    '</div>' +

    '</div>'
  );
}

// ─── Camera History List ──────────────────────────────────────────────────────

function renderCameraHistory() {
  if (state.cameraLogsLoading) {
    return '<div class="cam-history-loading"><span class="spinner"></span><p>Đang tải nhật ký quét…</p></div>';
  }
  if (state.cameraLogsError) {
    return '<p class="cam-history-error" role="alert">' + esc(state.cameraLogsError) + '</p>';
  }
  if (!state.cameraLogs.length) {
    return (
      '<div class="cam-history-empty">' +
      '<p>Chưa có lịch sử chụp ảnh nào từ camera. Hãy bấm nút Chụp ảnh để chẩn đoán cho cây.</p>' +
      '</div>'
    );
  }
  return (
    '<div class="cam-log-grid">' +
    state.cameraLogs.map(cameraLogCard).join('') +
    '</div>'
  );
}

// ─── Main Diagnosis View ──────────────────────────────────────────────────────

export function renderDiagnosisView() {
  return (
    '<div class="diagnosis-layout">' +

    // ── Left/Main column: ESP32-CAM Scanner & Viewfinder Screen
    '<div class="diag-left">' +
    '<div class="diag-picker-row">' +
    gardenPicker() +
    '</div>' +

    renderEsp32CamScanner() +

    '<section class="cam-history-section">' +
    '<h3 class="cam-history-title">Nhật ký quét từ ESP32-CAM' +
    (state.cameraLogs.length ? ' <span class="badge">' + state.cameraLogs.length + '</span>' : '') +
    '</h3>' +
    renderCameraHistory() +
    '</section>' +
    '</div>' +

    // ── Right column: Multimodal Diagnosis Result Detail
    '<div class="diag-right">' +
    '<div class="diag-result-wrap">' +
    '<h3 class="diag-result-title">Phân tích chẩn đoán AI</h3>' +
    renderDiagnosisResult() +
    '</div>' +
    '</div>' +

    '</div>'
  );
}
