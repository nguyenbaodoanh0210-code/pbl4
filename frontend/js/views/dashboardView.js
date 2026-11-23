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

import { renderPumpControlCard } from './irrigationView.js';

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
    '<div class="metric-grid metric-grid-4">' +
    OUTDOOR_METRICS.map((m) => metricCard(m, latest?.[m[0]], thresholds)).join('') +
    '</div>' +
    '</section>' +

    '<div class="dashboard-analytics-split">' +
    renderInlineAnalyticsCard(sensor) +
    renderPumpControlCard(garden) +
    '</div>'
  );
}
