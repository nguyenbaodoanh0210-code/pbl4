/**
 * Frontend MVC — View 1: Environment Dashboard (Giao diện Giám sát Môi trường)
 * Displays real-time NodeMCU v2.0.0 metrics (DHT22 Temp/Humidity + LDR Light),
 * inline Analytics trend chart, and outdoor Water Pump control (Manual & Auto).
 */

import {
  OUTDOOR_METRICS,
  PERIODS,
  activeSensorDevice,
  areaForDevice,
  currentGarden,
  currentPumpData,
  esc,
  fmt,
  formatDate,
  getPeriodLogs,
  latestReading,
  state,
} from '../models/store.js';
import {
  drawTrendChart,
  gardenPicker,
  metricCard,
  pill,
  sensorNodePicker,
  sensorStatusBanner,
} from './components.js';
import { addGreenhouseButton } from './gardenView.js';

function renderPumpControlCard(garden) {
  const { pump, logs } = currentPumpData(garden.greenhouse_id);
  const mode = pump?.control_mode || 'AUTO';
  const isOn = Boolean(pump?.is_on);
  const isAuto = mode === 'AUTO';
  const busy = state.pumpBusy;
  const rules = pump?.auto_rules || {};

  const changedByMap = {
    USER: 'Điều khiển thủ công',
    AUTO_RULE: 'Luật tự động ngoài trời',
    AI: 'Đề xuất AI',
  };
  const changedByLabel = changedByMap[pump?.last_changed_by] || 'Hệ thống';

  const feedbackHtml = state.pumpError
    ? '<div class="banner danger pump-feedback" role="alert">' + esc(state.pumpError) + '</div>'
    : state.pumpMessage
      ? '<div class="banner pump-feedback" role="status">' + esc(state.pumpMessage) + '</div>'
      : '';

  const recentLogsHtml = logs.length
    ? '<div class="pump-history"><div class="pump-history-title">Lịch sử điều khiển gần đây</div>' +
      logs
        .slice(0, 3)
        .map(
          (log) =>
            '<div class="pump-log-item">' +
            '<div class="pump-log-head"><strong>' +
            esc(log.action === 'TURN_ON' ? 'Bật bơm' : log.action === 'TURN_OFF' ? 'Tắt bơm' : 'Đổi chế độ') +
            '</strong><span>' + formatDate(log.created_at) + '</span></div>' +
            '<p class="tiny">' + esc(log.reason || 'Đã ghi nhận lệnh.') + '</p>' +
            '</div>'
        )
        .join('') +
      '</div>'
    : '<p class="tiny" style="margin-top:14px">Chưa có lịch sử bật/tắt bơm nước.</p>';

  return (
    '<section class="card pump-control-card" aria-labelledby="pump-card-title">' +
    '<div class="pump-card-header">' +
    '<div><div class="tag">ĐIỀU KHIỂN THIẾT BỊ NGOÀI TRỜI</div><h3 id="pump-card-title" class="card-title">Bơm nước tưới vườn</h3></div>' +
    pill(isOn ? 'Đang bật' : 'Đang tắt', isOn ? '' : 'offline') +
    '</div>' +

    '<div class="pump-mode-block">' +
    '<span class="field-label">Chế độ vận hành</span>' +
    '<div class="segmented pump-mode-toggle" role="group" aria-label="Chế độ điều khiển bơm nước">' +
    '<button type="button" data-pump-mode="AUTO" class="' + (isAuto ? 'selected' : '') + '" ' + (busy ? 'disabled' : '') + '>Tự động (Auto)</button>' +
    '<button type="button" data-pump-mode="MANUAL" class="' + (!isAuto ? 'selected' : '') + '" ' + (busy ? 'disabled' : '') + '>Thủ công (Manual)</button>' +
    '</div>' +
    '</div>' +

    '<div class="pump-switch-panel ' + (isOn ? 'is-on' : 'is-off') + '">' +
    '<div class="pump-switch-copy">' +
    '<strong>' + (isOn ? 'Bơm nước đang tưới' : 'Bơm nước đang tạm dừng') + '</strong>' +
    '<span class="tiny">Cập nhật: ' + formatDate(pump?.updated_at) + ' · ' + esc(changedByLabel) + '</span>' +
    '</div>' +
    '<button type="button" class="' + (isOn ? 'secondary-button pump-stop-btn' : 'primary-button') + ' pump-toggle-btn" ' +
    'data-pump-toggle="' + (isOn ? 'off' : 'on') + '" ' +
    (isAuto || busy ? 'disabled' : '') + '>' +
    (busy ? 'Đang gửi lệnh…' : isOn ? 'Tắt bơm nước' : 'Bật bơm nước') +
    '</button>' +
    '</div>' +

    (isAuto
      ? '<p class="tiny pump-auto-note">Hệ thống đang ở chế độ <strong>Tự động</strong>: tự bật bơm khi nhiệt độ ≥ ' +
        fmt(rules.turn_on_temp_above ?? 33, 0) + '°C hoặc độ ẩm ≤ ' + fmt(rules.turn_on_humidity_below ?? 50, 0) +
        '%, và tự tắt khi độ ẩm ≥ ' + fmt(rules.turn_off_humidity_above ?? 75, 0) +
        '% để hạn chế nấm bệnh. Chuyển sang <strong>Thủ công</strong> để bật/tắt trực tiếp.</p>'
      : '<p class="tiny pump-auto-note">Đang ở chế độ <strong>Thủ công</strong>: bạn có toàn quyền bật/tắt bơm nước ngay lập tức.</p>') +

    feedbackHtml +
    recentLogsHtml +
    '</section>'
  );
}

function renderInlineAnalyticsCard(device) {
  const rows = getPeriodLogs(device);
  const metricDef = OUTDOOR_METRICS.find((m) => m[0] === state.metric) || OUTDOOR_METRICS[0];
  const [metricKey, metricLabel, metricUnit] = metricDef;
  const decimals = metricKey === 'light_level' ? 0 : 1;
  const values = rows
    .map((r) => r[metricKey])
    .filter((v) => v != null && Number.isFinite(Number(v)))
    .map(Number);
  const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

  return (
    '<section class="card analytics-card">' +
    '<div class="analytics-header">' +
    '<div><div class="tag">BIỂU ĐỒ THEO DÕI THỜI TIẾT</div><h3 class="card-title">' + esc(metricLabel) + '</h3></div>' +
    '<div class="segmented analytics-periods">' +
    PERIODS.map(
      (p) =>
        '<button type="button" data-period="' + p[0] + '" class="' + (state.period === p[0] ? 'selected' : '') + '">' + p[1] + '</button>'
    ).join('') +
    '</div>' +
    '</div>' +
    '<div class="tabs-chip">' +
    OUTDOOR_METRICS.map(
      (m) =>
        '<button type="button" class="chip ' + (state.metric === m[0] ? 'selected' : '') + '" data-metric="' + m[0] + '">' + esc(m[1]) + '</button>'
    ).join('') +
    '</div>' +
    (rows.length
      ? '<div class="tiny">' + formatDate(rows[0].timestamp) + ' — ' + formatDate(rows.at(-1).timestamp) + ' (' + rows.length + ' điểm đo)</div>' +
        drawTrendChart(rows, metricDef) +
        '<div class="analytics-stats">' +
        '<div><span>Thấp nhất</span><strong>' + (values.length ? fmt(Math.min(...values), decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
        '<div><span>Trung bình</span><strong>' + (avg != null ? fmt(avg, decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
        '<div><span>Cao nhất</span><strong>' + (values.length ? fmt(Math.max(...values), decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
        '<div><span>Mới nhất</span><strong>' + fmt(rows.at(-1)[metricKey], decimals) + ' ' + esc(metricUnit) + '</strong></div>' +
        '</div>'
      : '<div class="empty">Chưa có dữ liệu quan trắc trong khoảng thời gian đã chọn.</div>') +
    '<div class="analytics-footer">' +
    '<button type="button" class="link-button" data-page="history">Mở toàn bộ lịch sử quan trắc →</button>' +
    '<button type="button" class="link-button" data-action="refresh">↻ Làm mới số đo</button>' +
    '</div>' +
    '</section>'
  );
}

export function renderDashboardView() {
  const garden = currentGarden();
  if (!garden) {
    return (
      '<div class="card empty empty-state">Thêm khu vườn đầu tiên để bắt đầu theo dõi môi trường và điều khiển tưới nước.</div>' +
      '<div class="management-notice">' + addGreenhouseButton() + '</div>'
    );
  }

  const sensor = activeSensorDevice();
  const latest = sensor ? latestReading(sensor.device_id) : null;
  const area = areaForDevice(sensor);
  const thresholds = area?.effective_thresholds || null;
  const cropSummary = thresholds
    ? esc(thresholds.crop_name) + ' · Ngưỡng ẩm nấm ≥ ' + fmt(thresholds.fungal_humidity_threshold, 0) + '%'
    : 'Khu vườn trồng ngoài trời';

  return (
    '<div class="page-toolbar dashboard-toolbar">' +
    '<div class="garden-picker">' + gardenPicker() + '</div>' +
    (sensor ? '<div class="garden-picker">' + sensorNodePicker() + '</div>' : '') +
    '<div class="toolbar-note">' + sensorStatusBanner(sensor, latest) + '</div>' +
    '</div>' +

    '<section class="dashboard-overview">' +
    '<div class="section-heading"><h2>Thông số môi trường thời gian thực</h2><span>' + cropSummary + ' · ' + formatDate(latest?.timestamp) + '</span></div>' +
    '<div class="metric-grid metric-grid-3">' +
    OUTDOOR_METRICS.map((m) => metricCard(m, latest?.[m[0]], thresholds)).join('') +
    '</div>' +
    '</section>' +

    '<div class="dashboard-analytics-split">' +
    renderInlineAnalyticsCard(sensor) +
    renderPumpControlCard(garden) +
    '</div>'
  );
}
