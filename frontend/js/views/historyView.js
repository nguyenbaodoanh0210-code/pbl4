/**
 * Frontend MVC — History & Analytics View
 * Synchronized with the 3 outdoor NodeMCU v2.0.0 metrics (DHT22 + LDR Light).
 */

import {
  OUTDOOR_METRICS,
  PERIODS,
  activeSensorDevice,
  areaForDevice,
  currentGarden,
  esc,
  fmt,
  formatDate,
  gardenSensorDevices,
  getPeriodLogs,
  state,
} from '../models/store.js';
import { drawTrendChart, gardenPicker, pill } from './components.js';

export function renderHistoryView() {
  const sensor = activeSensorDevice();
  if (!sensor) {
    return (
      '<div class="page-toolbar"><div class="garden-picker">' + gardenPicker() + '</div></div>' +
      '<div class="card empty empty-state">Chưa có thiết bị cảm biến nào để hiển thị lịch sử đo.</div>'
    );
  }

  const rows = getPeriodLogs(sensor);
  const metricDef = OUTDOOR_METRICS.find((x) => x[0] === state.metric) || OUTDOOR_METRICS[0];
  const [metricKey, metricLabel, metricUnit, , sensorCaption] = metricDef;
  const decimals = metricKey === 'light_level' ? 0 : 1;
  const values = rows
    .map((x) => x[metricKey])
    .filter((x) => x != null && Number.isFinite(Number(x)))
    .map(Number);
  const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const area = areaForDevice(sensor);

  return (
    '<div class="history-layout">' +
    '<section class="history-main">' +
    '<div class="page-toolbar">' +
    '<div class="garden-picker">' + gardenPicker() + '</div>' +
    '<div class="segmented">' +
    PERIODS.map(
      (x) =>
        '<button type="button" data-period="' + x[0] + '" class="' + (state.period === x[0] ? 'selected' : '') + '">' + x[1] + '</button>'
    ).join('') +
    '</div>' +
    '</div>' +
    '<div class="section-heading"><h2>Diễn biến môi trường ngoài trời</h2><span>' + rows.length + ' bản ghi</span></div>' +
    '<div class="tabs-chip">' +
    OUTDOOR_METRICS.map(
      (x) =>
        '<button type="button" class="chip ' + (state.metric === x[0] ? 'selected' : '') + '" data-metric="' + x[0] + '">' + esc(x[1]) + '</button>'
    ).join('') +
    '</div>' +
    (rows.length
      ? '<div class="card chart-card">' +
        '<div class="card-title">' + esc(metricLabel) + ' <span class="tiny">· ' + esc(sensorCaption) + '</span></div>' +
        '<div class="tiny">' + formatDate(rows[0].timestamp) + ' — ' + formatDate(rows.at(-1).timestamp) + '</div>' +
        drawTrendChart(rows, metricDef) +
        '<div class="row"><span>Số đo mới nhất</span><strong>' + fmt(rows.at(-1)[metricKey], decimals) + ' ' + esc(metricUnit) + '</strong></div>' +
        '</div>'
      : '<div class="card empty empty-state">Chưa có lịch sử quan trắc trong khoảng thời gian này.</div>') +
    '</section>' +
    '<aside class="history-aside">' +
    '<section class="card history-filters">' +
    '<div class="card-title">Nguồn dữ liệu</div>' +
    '<label for="device" class="field-label">Bộ cảm biến theo dõi</label>' +
    '<div class="select-wrap"><select id="device" class="select">' +
    gardenSensorDevices()
      .map(
        (x) =>
          '<option value="' + esc(x.device_id) + '" ' + (x.device_id === sensor.device_id ? 'selected' : '') + '>' + esc(x.device_id) + '</option>'
      )
      .join('') +
    '</select></div>' +
    '<p class="tiny">' + esc(currentGarden()?.name) + (area ? ' · ' + esc(area.name) : '') + '</p>' +
    pill(sensor.is_online ? 'Đang kết nối' : 'Ngoại tuyến', sensor.is_online ? '' : 'offline') +
    '</section>' +
    '<section class="card history-summary">' +
    '<div class="card-title">Trong khoảng đã chọn</div>' +
    '<div class="row"><span>Thấp nhất</span><strong>' + (values.length ? fmt(Math.min(...values), decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
    '<div class="row"><span>Trung bình</span><strong>' + (avg != null ? fmt(avg, decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
    '<div class="row"><span>Cao nhất</span><strong>' + (values.length ? fmt(Math.max(...values), decimals) : '—') + ' ' + esc(metricUnit) + '</strong></div>' +
    '<p class="tiny">' + esc(metricLabel) + ' · ' + rows.length + ' bản ghi đã lưu</p>' +
    '</section>' +
    '<button type="button" class="secondary-button" data-action="refresh">↻ &nbsp;Tải lại dữ liệu</button>' +
    '</aside>' +
    '</div>'
  );
}
