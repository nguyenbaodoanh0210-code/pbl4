import { currentPumpData, esc, formatDate, fmt, state } from '../models/store.js';

const statusLabels = { RUNNING: 'Board xác nhận đang tưới', STOPPED: 'Board xác nhận đã dừng',
  PENDING: 'Đã gửi bật · chờ board', PENDING_STOP: 'Đã gửi dừng · chờ board', UNKNOWN: 'Chưa có xác nhận mới từ board' };

export function renderPumpControlCard(garden) {
  const { pump, logs } = currentPumpData(garden.greenhouse_id);
  const r = pump?.auto_rules || {};
  const areas = state.areas[garden.greenhouse_id] || [];
  const devices = state.devices.filter(d => d.greenhouse_id === garden.greenhouse_id &&
    (d.area_id || '') === state.pumpAreaId && d.status === 'ACTIVE');
  const options = (sensor) => '<option value="">Chọn thiết bị</option>' + devices.filter(d =>
    sensor ? d.device_type === 'SENSOR_NODE' : ['SENSOR_NODE', 'ACTUATOR', 'PUMP'].includes(d.device_type))
    .map(d => '<option value="' + esc(d.device_id) + '" ' +
      (d.device_id === (sensor ? r.sensor_device_id : pump?.device_id) ? 'selected' : '') + '>' + esc(d.device_id) + '</option>').join('');
  const input = (key, label, value, min, max, required = true) =>
    '<label>' + label + '<input type="number" step="any" name="' + key + '" value="' + esc(r[key] ?? value ?? '') +
    '" min="' + min + '" max="' + max + '" ' + (required ? 'required' : '') + '></label>';
  const mode = pump?.control_mode || 'MANUAL';
  const stats = pump?.daily_statistics || [];
  const weather = pump?.weather;
  const loadError = state.actuators[garden.greenhouse_id]?.error;
  return '<section class="card irrigation-panel" aria-labelledby="pump-card-title">' +
    '<h3 id="pump-card-title">Bơm nước và lịch tưới</h3>' +
    (loadError ? '<p role="alert" class="banner danger">Không tải được trạng thái bơm: ' + esc(loadError) + '</p>' : '') +
    '<label>Khu vực điều khiển<select id="pump-area"><option value="">Toàn vườn</option>' +
    areas.map(a => '<option value="' + esc(a.area_id) + '" ' + (a.area_id === state.pumpAreaId ? 'selected' : '') + '>' + esc(a.name) + '</option>').join('') +
    '</select></label><p role="status"><strong>' + esc(statusLabels[pump?.status] || statusLabels.UNKNOWN) + '</strong></p>' +
    '<dl class="irrigation-times">' +
    [['Bắt đầu tưới (xác nhận)', pump?.started_at], ['Dừng chậm nhất (dự kiến)', pump?.scheduled_stop_at],
      ['Lần tưới gần nhất', pump?.last_irrigation_at]].map(([label, time]) =>
        '<div><dt>' + label + '</dt><dd>' + formatDate(time) + '</dd></div>').join('') +
    '<div><dt>Lần tưới tiếp theo</dt><dd>' + esc(pump?.next_irrigation_reason || 'Chưa cấu hình lịch tưới') + '</dd></div></dl>' +
    '<p class="tiny">Chế độ: ' + (mode === 'AUTO' ? 'Tự động theo đất' : 'Thủ công') +
    '. Xác nhận relay không thay thế cảm biến lưu lượng nước.</p>' +
    '<div class="irrigation-actions"><button type="button" class="primary-button" data-pump-toggle="on" ' +
    (state.pumpBusy || mode === 'AUTO' || !r.hardware_verified || pump?.is_on ? 'disabled' : '') + '>Tưới có thời hạn</button>' +
    '<button type="button" class="secondary-button" data-pump-toggle="off" ' + (state.pumpBusy ? 'disabled' : '') + '>Dừng và tắt tự động</button></div>' +
    (state.pumpError ? '<p role="alert" class="banner danger">' + esc(state.pumpError) + '</p>' : '') +
    (state.pumpMessage ? '<p role="status">' + esc(state.pumpMessage) + '</p>' : '') +
    '<details><summary>Cấu hình tưới và dự báo</summary><form id="irrigation-config"><fieldset ' + (state.pumpBusy || pump?.is_on ? 'disabled' : '') + '>' +
    '<label>Board điều khiển relay<select name="device_id" required>' + options(false) + '</select></label>' +
    '<label>Cảm biến đất cùng khu vực<select name="sensor_device_id" required>' + options(true) + '</select></label>' +
    '<div class="irrigation-fields">' +
    input('start_below_pct', 'Bật khi độ ẩm đất dưới (%)', '', 0, 99) +
    input('stop_at_pct', 'Dừng khi đất đạt (%)', '', 1, 100) +
    input('base_run_seconds', 'Thời lượng cơ sở (giây)', 20, 1, 120) +
    input('max_run_seconds', 'Thời hạn tự ngắt tối đa (giây)', 30, 1, 120) +
    input('cooldown_seconds', 'Khoảng nghỉ (giây)', 600, 60, 86400) +
    input('max_daily_seconds', 'Ngân sách tưới / 24 giờ (giây)', 600, 1, 3600) +
    input('max_temperature_c', 'Giới hạn nhiệt độ khi tưới (°C, tùy chọn)', '', -40, 85, false) +
    input('max_light_lux', 'Giới hạn ánh sáng (lux, tùy chọn)', '', 0, 200000, false) +
    '<label>Từ giờ<input type="time" name="allowed_start" value="' + esc(r.allowed_start || '') + '"></label>' +
    '<label>Đến giờ<input type="time" name="allowed_end" value="' + esc(r.allowed_end || '') + '"></label>' +
    input('latitude', 'Vĩ độ vườn', '', -90, 90, false) +
    input('longitude', 'Kinh độ vườn', '', -180, 180, false) +
    input('hot_day_c', 'Ngưỡng ngày nóng (°C)', 35, 25, 50) +
    input('morning_multiplier', 'Hệ số thời lượng sáng ngày nóng', 1, 1, 1.5) +
    input('rainy_evening_multiplier', 'Hệ số chiều trước ngày mưa', 1, .25, 1) +
    '</div><label><input type="checkbox" name="rain_exposed" ' + (r.rain_exposed ? 'checked' : '') + '> Khu trồng nhận nước mưa trực tiếp</label>' +
    '<label><input type="checkbox" name="hardware_verified" ' + (r.hardware_verified ? 'checked' : '') + '> Đã hiệu chuẩn đất và kiểm tra board tự ngắt bơm</label>' +
    '<label><input type="checkbox" name="enabled" ' + (mode === 'AUTO' ? 'checked' : '') + '> Bật tưới tự động</label>' +
    '<p class="tiny">Chọn ngưỡng theo cây và giá thể thực tế. Hệ số mặc định 1 nghĩa là chưa tăng/giảm. Thời lượng luôn bị chặn bởi giới hạn an toàn. Chỉ dự báo mưa không đủ để bỏ tưới khi đất khô.</p>' +
    '<button class="primary-button" type="submit">Lưu cấu hình</button></fieldset></form></details>' +
    '<h4>Thống kê tưới từng ngày</h4>' + (stats.length ? '<div class="irrigation-table"><table><thead><tr><th>Ngày</th><th>Số lần bắt đầu</th><th>Thời gian đã xác nhận</th></tr></thead><tbody>' +
      stats.map(d => '<tr><td>' + esc(d.date) + '</td><td>' + d.starts + '</td><td>' + d.confirmed_seconds + ' giây</td></tr>').join('') +
      '</tbody></table></div><p class="tiny">Chỉ cộng phiên có xác nhận bắt đầu và kết thúc. Chưa có lưu lượng để tính lít.</p>' :
      '<p class="tiny">Chưa có phiên tưới được board xác nhận.</p>') +
    '<h4>Dự báo tại vị trí vườn</h4>' +
    (weather?.available ? '<p class="tiny"><a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> · Cập nhật ' + formatDate(weather.fetched_at) + '</p>' +
      '<p>Hiện tại ngoài trời: ' + fmt(weather.current?.temperature_2m, 1) + ' °C · Ẩm ' + fmt(weather.current?.relative_humidity_2m, 0) + '%</p>' +
      weather.days.map(d => '<p>' + esc(d.date) + ': ' + fmt(d.min_temperature_c, 1) + '–' + fmt(d.max_temperature_c, 1) + ' °C · Mưa ' + fmt(d.rain_probability_pct, 0) + '% / ' + fmt(d.rain_mm, 1) + ' mm</p>').join('') +
      '<p class="tiny">Dự báo khu vực; số đo trong vườn hiển thị ở bảng cảm biến. Không suy ra mưa từ lux.</p>' :
      '<p class="tiny">' + esc(weather?.reason || 'Nhập tọa độ trong cấu hình để xem dự báo.') + '</p>') +
    '<details><summary>Lệnh điều khiển gần đây</summary>' +
    logs.slice(0, 10).map(l => '<p>' + formatDate(l.created_at) + ' · ' + esc(l.action) + ' · ' + esc(l.ack_status) + '<br>' + esc(l.reason || '') + '</p>').join('') +
    '</details></section>';
}
