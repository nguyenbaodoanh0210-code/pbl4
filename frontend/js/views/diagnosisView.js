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
  if (['healthy', 'khỏe mạnh', 'lá khỏe mạnh', 'ot_khoe_manh'].includes(String(key).toLowerCase())) return 'ok';
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
    timeZone: 'Asia/Ho_Chi_Minh',
  });
}

function statusPill(status) {
  const map = {
    PENDING: ['Đang xử lý', 'pill-warn'],
    NEW: ['Chưa xem xét', 'pill-neutral'],
    REVIEWED: ['Đã xem xét', 'pill-ok'],
    RESOLVED: ['Đã xử lý', 'pill-ok'],
    FLAGGED: ['Cần chú ý', 'pill-danger'],
  };
  const [label, cls] = map[status] || ['Không rõ', 'pill-neutral'];
  return pill(label, cls);
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
  const areas = state.areas[state.greenhouseId] || [];
  if (!areas.some(a => a.area_id === state.cameraAreaId)) state.cameraAreaId = '';
  const camDevices = state.devices.filter(d => ['CAMERA', 'CAMERA_NODE'].includes(d.device_type) &&
    d.status === 'ACTIVE' && d.greenhouse_id === state.greenhouseId &&
    (!state.cameraAreaId || d.area_id === state.cameraAreaId));
  const activeDevice = camDevices.find(d => d.device_id === state.cameraDeviceId)?.device_id || camDevices[0]?.device_id || '';
  const busy = state.cameraTriggerBusy || state.diagnosisLoading;

  // Determine current image to display in viewfinder:
  // 1. Live stream URL if active and enabled
  // 2. Currently selected diagnosis log image
  // 3. Most recent camera log image
  // 4. Default leaf sample
  const latestLog = [state.diagnosisResult, ...state.cameraLogs].find(log => log?.greenhouse_id === state.greenhouseId);
  const currentImgUrl = latestLog ? cameraImageUrl(latestLog.log_id) : '/styles/leaf-sample.jpg';
  const isStream = state.esp32StreamMode === 'stream' && state.esp32StreamUrl;
  const feedSrc = isStream ? state.esp32StreamUrl : currentImgUrl;

  const areaOptions = areas.map((a) =>
    '<option value="' + esc(a.area_id) + '" ' + (a.area_id === state.cameraAreaId ? 'selected' : '') + '>' + esc(a.name) + '</option>'
  ).join('');

  const camDevOptions = camDevices.length
    ? camDevices.map(d => '<option value="' + esc(d.device_id) + '" ' + (d.device_id === activeDevice ? 'selected' : '') + '>' + esc(d.device_id) + '</option>').join('')
    : '<option value="">Chưa có camera hoạt động</option>';

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
    pill('Kết nối camera chưa được xác minh', 'pill-neutral') +
    '</div>' +
    '</div>' +

    // Target Selection (Area & Device)
    '<div class="esp32-target-bar">' +
    '<div class="target-field">' +
    '<label for="trigger-cam-device">Thiết bị Camera</label>' +
    '<select id="trigger-cam-device" class="target-select" ' + (busy ? 'disabled' : '') + '>' + camDevOptions + '</select>' +
    '</div>' +
    '<div class="target-field">' +
    '<label for="diag-area">Khu vực quét</label>' +
    '<select id="diag-area" class="target-select" ' + (busy ? 'disabled' : '') + '><option value="">— Toàn vườn —</option>' + areaOptions + '</select>' +
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
    '<div class="hud-item"><span class="hud-dot"></span> ' + (isStream ? 'NGUỒN ẢNH CAMERA' : latestLog ? 'ẢNH ĐÃ LƯU' : 'ẢNH MINH HỌA') + '</div>' +
    '<div class="hud-item">Độ nét cao</div>' +
    '<div class="hud-item">' + (isStream ? 'Phụ thuộc camera' : 'Chờ yêu cầu chụp') + '</div>' +
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
    '<button type="button" class="btn-esp32-scan" id="trigger-cam-btn"' + (busy || !activeDevice ? ' disabled' : '') + '>' +
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
    '<label for="esp32-stream-input">Địa chỉ nguồn ảnh của Camera:' +
    '<input type="url" id="esp32-stream-input" placeholder="Ví dụ: http://192.168.4.1:81/stream" value="' + esc(state.esp32StreamUrl || '') + '">' +
    '</label>' +
    '<div class="stream-config-actions">' +
    '<button type="button" class="btn btn-secondary btn-sm" id="btn-apply-stream">Áp dụng Stream</button>' +
    '<button type="button" class="btn btn-secondary btn-sm" id="btn-snapshot-mode">Dùng chế độ Chụp tĩnh</button>' +
    '</div>' +
    '<small>Camera cần cùng mạng nội bộ. Firmware AI-Thinker hiện trả một ảnh tĩnh mỗi lần tải; chỉ firmware hỗ trợ MJPEG mới có video liên tục.</small>' +
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
    '<input type="file" id="diagnose-file" name="file" accept="image/jpeg,image/png" style="display:none" />' +
    '<button type="submit" class="btn btn-secondary btn-full" ' + (busy || !state.greenhouseId ? 'disabled' : '') + '>' +
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
  const diagnosis = log.final_diagnosis || log.cnn_diagnosis || '';
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
    '<p class="cam-date">' + esc(fmtDate(log.captured_at)) + '</p>' +
    (log.final_confidence != null
      ? '<div class="cam-conf-mini">' + confidenceBar(log.final_confidence) + '</div>'
      : '') +
    '</div>' +
    '</article>'
  );
}

// ─── Diagnosis Result Card ────────────────────────────────────────────────────

function renderDiagnosisResult() {
  const r = state.diagnosisResult?.greenhouse_id === state.greenhouseId ? state.diagnosisResult : null;
  if (!r) {
    return (
      '<div class="diag-empty">' +
      '<div class="diag-empty-icon">🔬</div>' +
      '<h3>Chưa có kết quả phân tích</h3>' +
      '<p>Bấm nút <strong>"Chụp ảnh & chẩn đoán bệnh lá"</strong> trên màn hình camera để hệ thống chụp và phân tích ngay lập tức.</p>' +
      '</div>'
    );
  }

  const sevCls = severityClass(r.final_diagnosis || r.cnn_diagnosis);
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
    '<h3 class="diag-badge">' + esc(diseaseLabel(r.final_diagnosis || r.cnn_diagnosis)) + '</h3>' +
    '</div>' +
    statusPill(r.status) +
    '</div>' +

    // CNN Vision
    '<section class="diag-section">' +
    '<h4 class="diag-section-title">🔍 Nhận diện hình ảnh lá cây</h4>' +
    '<div class="diag-row"><span>Triệu chứng phát hiện</span><b>' + esc(diseaseLabel(r.cnn_diagnosis)) + '</b></div>' +
    '<div class="diag-row"><span>Điểm nhận diện ảnh</span>' + confidenceBar(r.cnn_confidence) + '</div>' +
    '<p class="tiny">Điểm mô hình thử nghiệm, không phải độ chính xác đã kiểm chứng ngoài vườn.</p>' +
    '</section>' +

    // Multimodal fusion
    (r.final_diagnosis ? (
      '<section class="diag-section">' +
      '<h4 class="diag-section-title">🌿 Kết luận tổng hợp (Ảnh + Cảm biến)</h4>' +
      '<div class="diag-row"><span>Chẩn đoán cuối</span><b class="diag-' + sevCls + '">' + esc(diseaseLabel(r.final_diagnosis)) + '</b></div>' +
      '<div class="diag-row"><span>Độ tin cậy tổng thể</span>' + confidenceBar(r.final_confidence) + '</div>' +
      (deltaStr && r.sensor_context ? '<div class="diag-row"><span>Điều chỉnh theo cảm biến</span><b class="delta-' + (delta >= 0 ? 'up' : 'down') + '">' + deltaStr + '</b></div>' : '') +
      '</section>'
    ) : '') +

    // Environment snapshot
    (r.sensor_context ? (
      '<section class="diag-section">' +
      '<h4 class="diag-section-title">🌤️ Số đo cảm biến gần thời điểm nhận ảnh</h4>' +
      envSnapshot(r.sensor_context) +
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
    '<span>Nguồn: <code>' + esc(r.device_id || 'Ảnh tải lên') + '</code></span>' +
    '<span>Thời điểm: ' + esc(fmtDate(r.captured_at)) + '</span>' +
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
    state.cameraLogs.filter(log => log.greenhouse_id === state.greenhouseId).map(cameraLogCard).join('') +
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
