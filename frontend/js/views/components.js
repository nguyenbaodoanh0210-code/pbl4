/**
 * Frontend MVC — Shared View Components
 * Pure HTML template helpers (all API strings escaped via esc()).
 */

import {
  activeSensorDevice,
  areaForDevice,
  currentGarden,
  esc,
  evaluateMetricStatus,
  fmt,
  formatDate,
  gardenSensorDevices,
  state,
} from '../models/store.js';

const METRIC_ICONS = {
  temperature:
    '<rect x="9" y="2" width="6" height="14" rx="3"/><circle cx="12" cy="18" r="4"/><path d="M12 8v10"/><circle cx="12" cy="18" r="1.5" fill="currentColor" stroke="none"/>',
  humidity:
    '<path d="M12 2c-1.7 2.3-4.2 5.2-4.2 7.7a4.2 4.2 0 0 0 8.4 0C16.2 7.2 13.7 4.3 12 2Z"/><path d="M5.3 13.5c-1.2 1.6-2.3 3.1-2.3 4.4a2.3 2.3 0 0 0 4.6 0c0-1.3-1.1-2.8-2.3-4.4ZM18.7 13.5c-1.2 1.6-2.3 3.1-2.3 4.4a2.3 2.3 0 0 0 4.6 0c0-1.3-1.1-2.8-2.3-4.4Z"/>',
  light_level:
    '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.8 4.8l1.6 1.6M17.6 17.6l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.8 19.2l1.6-1.6M17.6 6.4l1.6-1.6"/>',
};

export function metricIcon(name) {
  return METRIC_ICONS[name]
    ? '<svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">' + METRIC_ICONS[name] + '</svg>'
    : esc(name);
}

export function pill(text, variant = '') {
  return '<span class="status-pill ' + esc(variant) + '"><span class="status-icon" aria-hidden="true">●</span>' + esc(text) + '</span>';
}

export function gardenPicker(label = 'Khu vườn đang xem') {
  if (!state.greenhouses.length) {
    return '<div class="card empty">Chưa có khu vườn nào trong API.</div>';
  }
  const activeId = currentGarden()?.greenhouse_id;
  return (
    '<div class="greenhouse-picker">' +
    '<label class="field-label" for="gh">' + esc(label) + '</label>' +
    '<div class="select-wrap greenhouse-select">' +
    '<select id="gh" class="select">' +
    state.greenhouses
      .map(
        (x) =>
          '<option value="' + esc(x.greenhouse_id) + '" ' +
          (x.greenhouse_id === activeId ? 'selected' : '') + '>' +
          esc(x.name) + (x.location ? ' · ' + esc(x.location) : '') +
          '</option>'
      )
      .join('') +
    '</select></div></div>'
  );
}

export function sensorNodePicker(label = 'Bộ cảm biến theo dõi') {
  const list = gardenSensorDevices();
  const active = activeSensorDevice();
  if (!list.length) return '';
  return (
    '<div class="sensor-picker">' +
    '<label class="field-label" for="device">' + esc(label) + '</label>' +
    '<div class="select-wrap greenhouse-select">' +
    '<select id="device" class="select">' +
    list
      .map((item) => {
        const area = areaForDevice(item);
        const suffix = area ? ' · ' + area.name : '';
        return (
          '<option value="' + esc(item.device_id) + '" ' +
          (item.device_id === active?.device_id ? 'selected' : '') + '>' +
          esc(item.device_id + suffix) +
          '</option>'
        );
      })
      .join('') +
    '</select></div></div>'
  );
}

export function sensorStatusBanner(device, latest) {
  if (!device) {
    return '<div class="banner warning">Chưa có bộ cảm biến nào được liên kết với khu vườn này.</div>';
  }
  if (!latest) {
    return '<div class="banner warning">Thiết bị ' + esc(device.device_id) + ' chưa có bản ghi cảm biến.</div>';
  }
  const area = areaForDevice(device);
  const zonePrefix = area ? area.name + ' · ' : '';
  if (device.is_online) {
    return (
      '<div class="banner">' +
      esc(zonePrefix + device.device_id) +
      ' đang hoạt động · cập nhật ' + formatDate(latest.timestamp) + '.</div>'
    );
  }
  return (
    '<div class="banner danger">' +
    esc(zonePrefix + device.device_id) +
    ' đang ngoại tuyến theo API. Bản ghi gần nhất: ' + formatDate(latest.timestamp) + '.</div>'
  );
}

export function metricCard(metricDef, value, thresholds) {
  const [key, title, unit, iconName, sensorCaption] = metricDef;
  const status = evaluateMetricStatus(key, value, thresholds);
  const decimals = key === 'light_level' ? 0 : 1;
  const badgeClass =
    status.level === 'danger' ? 'error' : status.level === 'warning' ? 'pending' : '';
  return (
    '<div class="metric metric-' + esc(status.level) + '">' +
    '<div class="metric-top">' +
    '<div class="metric-label"><span class="metric-icon" aria-hidden="true">' + metricIcon(iconName) + '</span><span>' + esc(title) + '</span></div>' +
    '<span class="metric-sensor-tag">' + esc(sensorCaption) + '</span>' +
    '</div>' +
    '<div class="metric-value">' + fmt(value, decimals) + '<span class="metric-unit">' + esc(unit) + '</span></div>' +
    '<div class="metric-status">' + pill(status.label, badgeClass) + '</div>' +
    '</div>'
  );
}

export function drawTrendChart(rows, metricDef) {
  const [key, title] = metricDef;
  const decimals = key === 'light_level' ? 0 : 1;
  const valid = rows.filter((x) => x[key] != null && Number.isFinite(Number(x[key])));
  if (valid.length < 2) {
    return '<div class="empty">Cần ít nhất hai điểm đo để vẽ biểu đồ xu hướng.</div>';
  }
  const values = valid.map((x) => Number(x[key]));
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const pts = values.map((v, i) => [
    46 + (i * 284) / (values.length - 1),
    120 - ((v - lo) * 90) / span,
  ]);
  const linePath = pts
    .map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1))
    .join(' ');
  const areaPath =
    linePath +
    ' L' + pts.at(-1)[0].toFixed(1) + ',124 L' + pts[0][0].toFixed(1) + ',124 Z';
  return (
    '<svg class="chart" viewBox="0 0 340 156" role="img" aria-label="Biểu đồ ' + esc(title) + '">' +
    '<line class="grid" x1="42" y1="28" x2="332" y2="28"/>' +
    '<line class="grid" x1="42" y1="74" x2="332" y2="74"/>' +
    '<line class="grid" x1="42" y1="120" x2="332" y2="120"/>' +
    '<text x="0" y="31">' + fmt(lo + span, decimals) + '</text>' +
    '<text x="0" y="77">' + fmt(lo + span / 2, decimals) + '</text>' +
    '<text x="0" y="123">' + fmt(lo, decimals) + '</text>' +
    '<path class="chart-area" d="' + areaPath + '"/>' +
    '<path class="line" d="' + linePath + '"/>' +
    '<circle class="dot" cx="' + pts.at(-1)[0].toFixed(1) + '" cy="' + pts.at(-1)[1].toFixed(1) + '" r="4"/>' +
    '</svg>'
  );
}
