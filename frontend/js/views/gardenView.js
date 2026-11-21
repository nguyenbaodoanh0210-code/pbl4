/**
 * Frontend MVC — Garden, Outdoor Planting Areas, and Hardware Device Views
 * Stage 4C: Full CRUD for Planting Areas & Agronomic Crop Threshold Overrides.
 */

import {
  cropDetails,
  esc,
  fmt,
  formatDate,
  gardenDevices,
  latestReading,
  state,
} from '../models/store.js';
import { pill } from './components.js';

const STAGE_LABELS = {
  SEEDLING: 'Cây con',
  VEGETATIVE: 'Sinh trưởng',
  FLOWERING: 'Ra hoa',
  FRUITING: 'Kết trái',
  HARVEST: 'Thu hoạch',
};

export function addGreenhouseButton() {
  return '<button type="button" class="primary-button add-greenhouse-button" data-action="add-greenhouse">Thêm khu vườn</button>';
}

export function addDeviceButton() {
  return '<button type="button" class="primary-button add-device-button" data-action="add-device">Thêm thiết bị mới</button>';
}

export function addAreaButton() {
  return '<button type="button" class="primary-button add-area-button" data-action="add-area">Thêm khu vực trồng</button>';
}

export function renderGreenhouseForm(editingId = null) {
  const item = editingId ? state.greenhouses.find((x) => x.greenhouse_id === editingId) : null;
  const isEdit = Boolean(item);
  return (
    '<section class="greenhouse-create" aria-labelledby="greenhouse-form-title">' +
    '<div class="greenhouse-form-intro">' +
    '<h2 id="greenhouse-form-title">' + (isEdit ? 'Chỉnh sửa khu vườn' : 'Thông tin khu vườn') + '</h2>' +
    '<p>' + (isEdit ? 'Cập nhật tên, vị trí hoặc diện tích cho khu vườn trồng ngoài trời của bạn.' : 'Đặt tên và ghi lại vị trí để quản lý khu vườn ngoài trời của bạn.') + '</p>' +
    '<p>Dấu * là thông tin bắt buộc.</p></div>' +
    '<form id="greenhouse-form" class="greenhouse-form" data-mode="' + (isEdit ? 'edit' : 'create') + '">' +
    '<fieldset><legend class="visually-hidden">' + (isEdit ? 'Chỉnh sửa thông tin khu vườn' : 'Thông tin khu vườn mới') + '</legend>' +
    (isEdit ? '<input type="hidden" name="greenhouse_id" value="' + esc(item.greenhouse_id) + '">' : '') +
    '<label for="greenhouse-name">Tên khu vườn *<input id="greenhouse-name" name="name" maxlength="100" required autocomplete="off" value="' + (isEdit ? esc(item.name) : '') + '" placeholder="Ví dụ: Khu vườn ớt & xà lách"></label>' +
    '<label for="greenhouse-code">Mã khu vườn *<input id="greenhouse-code" ' + (isEdit ? 'disabled' : 'name="greenhouse_id" required') + ' maxlength="50" autocomplete="off" spellcheck="false" aria-describedby="greenhouse-code-hint" value="' + (isEdit ? esc(item.greenhouse_id) : '') + '" placeholder="Ví dụ: KV-01"><small id="greenhouse-code-hint">' + (isEdit ? 'Mã khu vườn cố định, không thể chỉnh sửa.' : 'Mã duy nhất để nhận diện khu vườn, không trùng với mã đã có.') + '</small></label>' +
    '<label for="greenhouse-location">Vị trí<input id="greenhouse-location" name="location" maxlength="255" autocomplete="off" value="' + (isEdit ? esc(item.location || '') : '') + '" placeholder="Ví dụ: Khu vườn ngoài trời, Đà Nẵng"></label>' +
    '<label for="greenhouse-area">Diện tích (m²)<input id="greenhouse-area" name="area_sqm" type="number" min="0" step="any" inputmode="decimal" value="' + (isEdit && item.area_sqm != null ? esc(item.area_sqm) : '') + '" placeholder="Ví dụ: 45"><small>Nếu nhập, diện tích phải lớn hơn 0.</small></label>' +
    '</fieldset>' +
    '<p class="greenhouse-form-error" id="greenhouse-form-error" role="alert" tabindex="-1" hidden></p>' +
    '<div class="greenhouse-form-actions"><button type="submit" class="primary-button">' + (isEdit ? 'Cập nhật khu vườn' : 'Lưu khu vườn') + '</button><button type="button" class="secondary-button" data-action="cancel-greenhouse">Hủy</button></div>' +
    '</form></section>'
  );
}

function formatDeviceTypeLabel(hardwareModel, deviceType) {
  const m = (hardwareModel || '').toLowerCase();
  const t = (deviceType || '').toUpperCase();
  if (m.includes('nodemcu') || t === 'SENSOR_NODE') {
    return 'Cảm biến môi trường (Nhiệt độ, Độ ẩm, Ánh sáng)';
  }
  if (m.includes('esp32') || m.includes('cam') || t === 'CAMERA_NODE') {
    return 'Camera quét bệnh lá cây';
  }
  if (m.includes('bơm') || m.includes('pump') || t === 'ACTUATOR') {
    return 'Máy bơm nước tưới ngoài trời';
  }
  return hardwareModel || deviceType || 'Thiết bị';
}

function formatStatusLabel(status) {
  if (status === 'ACTIVE') return 'Đang hoạt động';
  if (status === 'INACTIVE') return 'Tạm ngừng';
  if (status === 'ERROR') return 'Báo lỗi';
  return status || '—';
}

export function renderDeviceForm(greenhouseId) {
  const h = state.greenhouses.find((x) => x.greenhouse_id === greenhouseId);
  const ghName = h ? h.name : greenhouseId;
  return (
    '<section class="greenhouse-create" aria-labelledby="device-form-title">' +
    '<div class="greenhouse-form-intro"><h2 id="device-form-title">Thông tin thiết bị mới</h2><p>Thêm bộ cảm biến môi trường, camera quét bệnh hoặc máy bơm tưới vào <strong>' + esc(ghName) + '</strong>.</p><p>Dấu * là thông tin bắt buộc.</p></div>' +
    '<form id="device-form" class="greenhouse-form">' +
    '<fieldset><legend class="visually-hidden">Thông tin thiết bị mới</legend>' +
    '<label for="device-id">Mã thiết bị *<input id="device-id" name="device_id" maxlength="50" required autocomplete="off" spellcheck="false" aria-describedby="device-id-hint" placeholder="Ví dụ: CAM-BIEN-01"><small id="device-id-hint">Mã duy nhất để nhận diện thiết bị, không trùng với mã đã có.</small></label>' +
    '<label for="device-type">Loại thiết bị *<div class="select-wrap"><select id="device-type" name="device_type" class="select" required>' +
    '<option value="SENSOR_NODE" selected>Bộ cảm biến môi trường (Nhiệt độ, Độ ẩm, Ánh sáng)</option>' +
    '<option value="CAMERA_NODE">Camera quét bệnh lá cây</option>' +
    '<option value="ACTUATOR">Máy bơm nước tưới ngoài trời</option>' +
    '</select></div><small>Chức năng hoạt động chính của thiết bị.</small></label>' +
    '<label for="device-status">Trạng thái ban đầu *<div class="select-wrap"><select id="device-status" name="status" class="select" required><option value="ACTIVE" selected>Đang hoạt động (ACTIVE)</option><option value="INACTIVE">Tạm ngừng (INACTIVE)</option></select></div><small>Trạng thái kích hoạt khi tạo.</small></label>' +
    '<label for="device-gh">Khu vườn liên kết<input id="device-gh" type="text" value="' + esc(ghName + ' (' + greenhouseId + ')') + '" disabled><small>Tự động gán vào khu vườn đang xem.</small></label>' +
    '</fieldset>' +
    '<p class="greenhouse-form-error" id="device-form-error" role="alert" tabindex="-1" hidden></p>' +
    '<div class="greenhouse-form-actions"><button type="submit" class="primary-button">Lưu thiết bị</button><button type="button" class="secondary-button" data-action="cancel-device">Hủy</button></div>' +
    '</form></section>'
  );
}

// ─── Stage 4C: Area & Crop Threshold Form ────────────────────────────────────

export function renderAreaForm(greenhouseId, areaId = null) {
  const areas = state.areas[greenhouseId] || [];
  const area = areaId ? areas.find((a) => a.area_id === areaId) : null;
  const isEdit = Boolean(area);
  const h = state.greenhouses.find((x) => x.greenhouse_id === greenhouseId);
  const ghName = h ? h.name : greenhouseId;

  const cropOptions = state.crops.map((c) => {
    const stage = STAGE_LABELS[c.growth_stage] || c.growth_stage || '';
    const label = `${c.crop_name} — ${stage} (${c.min_temp}-${c.max_temp}°C, ${c.min_humidity}-${c.max_humidity}%)`;
    const selected = (area?.crop_stage_id === c.crop_stage_id) ? ' selected' : '';
    return `<option value="${esc(c.crop_stage_id)}"${selected}>${esc(label)}</option>`;
  }).join('');

  return (
    '<section class="greenhouse-create area-form-section" aria-labelledby="area-form-title">' +
    '<div class="greenhouse-form-intro">' +
    '<h2 id="area-form-title">' + (isEdit ? 'Chỉnh sửa khu vực & Ngưỡng cây trồng' : 'Thêm khu vực trồng ngoài trời mới') + '</h2>' +
    '<p>Khu vườn: <strong>' + esc(ghName) + '</strong>. Bạn có thể chọn cấu hình giống cây mẫu hoặc tùy chỉnh ngưỡng môi trường riêng.</p>' +
    '<p>Dấu * là thông tin bắt buộc.</p>' +
    '</div>' +

    '<form id="area-form" class="greenhouse-form" data-mode="' + (isEdit ? 'edit' : 'create') + '" data-area-id="' + esc(areaId || '') + '">' +
    '<fieldset>' +
    '<legend class="visually-hidden">' + (isEdit ? 'Chỉnh sửa khu vực' : 'Thêm khu vực') + '</legend>' +

    // Tên khu vực
    '<label for="area-name">Tên khu vực trồng *' +
    '<input id="area-name" name="name" maxlength="100" required autocomplete="off" value="' + (isEdit ? esc(area.name) : '') + '" placeholder="Ví dụ: Luống Ớt số 1, Vạt Xà lách phía Đông">' +
    '</label>' +

    // Mã khu vực (chỉ nhập khi tạo mới, nếu sửa thì readonly)
    '<label for="area-code">Mã khu vực' +
    '<input id="area-code" name="area_id" maxlength="50" autocomplete="off" spellcheck="false" ' + (isEdit ? 'disabled' : '') + ' value="' + (isEdit ? esc(area.area_id) : '') + '" placeholder="Ví dụ: area-chili-01 (để trống sẽ tự sinh mã)">' +
    '<small>' + (isEdit ? 'Mã định danh không thể thay đổi.' : 'Mã duy nhất nhận diện khu vực. Để trống hệ thống sẽ tự sinh mã.') + '</small>' +
    '</label>' +

    // Diện tích
    '<label for="area-sqm">Diện tích (m²)' +
    '<input id="area-sqm" name="area_sqm" type="number" min="0" step="any" inputmode="decimal" value="' + (isEdit && area.area_sqm != null ? esc(area.area_sqm) : '') + '" placeholder="Ví dụ: 25">' +
    '</label>' +

    // Giống cây & Giai đoạn
    '<label for="area-crop">Giống cây & Giai đoạn sinh trưởng' +
    '<div class="select-wrap">' +
    '<select id="area-crop" name="crop_stage_id" class="select">' +
    '<option value="">— Tự do / Tùy chỉnh hoàn toàn (Không chọn giống) —</option>' +
    cropOptions +
    '</select>' +
    '</div>' +
    '<small>Hệ thống tự động áp dụng khoảng nhiệt độ, độ ẩm và ánh sáng chuẩn của giống cây đã chọn.</small>' +
    '</label>' +

    // Ngưỡng tùy chỉnh (Overrides)
    '<div class="threshold-override-box">' +
    '<h3 class="override-box-title">⚙️ Tùy chỉnh ngưỡng môi trường riêng (Ghi đè)</h3>' +
    '<p class="override-box-desc">Để trống các ô bên dưới nếu muốn dùng mặc định từ giống cây đã chọn ở trên.</p>' +

    '<div class="form-grid-2col">' +
    '<label for="area-min-temp">Nhiệt độ tối thiểu (°C)' +
    '<input id="area-min-temp" name="custom_min_temp" type="number" step="0.5" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_min_temp != null ? esc(area.custom_min_temp) : '') + '">' +
    '</label>' +
    '<label for="area-max-temp">Nhiệt độ tối đa (°C)' +
    '<input id="area-max-temp" name="custom_max_temp" type="number" step="0.5" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_max_temp != null ? esc(area.custom_max_temp) : '') + '">' +
    '</label>' +
    '</div>' +

    '<div class="form-grid-2col">' +
    '<label for="area-min-hum">Độ ẩm tối thiểu (%)' +
    '<input id="area-min-hum" name="custom_min_humidity" type="number" step="1" min="0" max="100" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_min_humidity != null ? esc(area.custom_min_humidity) : '') + '">' +
    '</label>' +
    '<label for="area-max-hum">Độ ẩm tối đa (%)' +
    '<input id="area-max-hum" name="custom_max_humidity" type="number" step="1" min="0" max="100" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_max_humidity != null ? esc(area.custom_max_humidity) : '') + '">' +
    '</label>' +
    '</div>' +

    '<div class="form-grid-2col">' +
    '<label for="area-min-light">Ánh sáng tối thiểu (Lux)' +
    '<input id="area-min-light" name="custom_min_light" type="number" step="100" min="0" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_min_light != null ? esc(area.custom_min_light) : '') + '">' +
    '</label>' +
    '<label for="area-max-light">Ánh sáng tối đa (Lux)' +
    '<input id="area-max-light" name="custom_max_light" type="number" step="100" min="0" placeholder="Mặc định cây trồng" value="' + (isEdit && area.custom_max_light != null ? esc(area.custom_max_light) : '') + '">' +
    '</label>' +
    '</div>' +

    '<label for="area-fungal-hum">Ngưỡng độ ẩm kích hoạt cảnh báo nấm bệnh (%)' +
    '<input id="area-fungal-hum" name="custom_fungal_humidity_threshold" type="number" step="1" min="50" max="100" placeholder="Ví dụ: 85 (mặc định 85%)" value="' + (isEdit && area.custom_fungal_humidity_threshold != null ? esc(area.custom_fungal_humidity_threshold) : '') + '">' +
    '<small>Độ ẩm vượt ngưỡng này kết hợp ánh sáng yếu sẽ kích hoạt cảnh báo nguy cơ nấm bệnh lá.</small>' +
    '</label>' +

    '</div>' + // end threshold-override-box

    '</fieldset>' +

    '<p class="greenhouse-form-error" id="area-form-error" role="alert" tabindex="-1" hidden></p>' +
    '<div class="greenhouse-form-actions">' +
    '<button type="submit" class="primary-button">' + (isEdit ? 'Cập nhật khu vực' : 'Lưu khu vực trồng') + '</button>' +
    '<button type="button" class="secondary-button" data-action="cancel-area">Hủy</button>' +
    '</div>' +

    '</form>' +
    '</section>'
  );
}

// ─── Area Card Renderer ───────────────────────────────────────────────────────

function renderAreaCard(area, greenhouseId) {
  const eff = area.effective_thresholds || {};
  const crop = cropDetails(area.crop_stage_id);
  const cropTitle = crop
    ? `${crop.crop_name} — ${STAGE_LABELS[crop.growth_stage] || crop.growth_stage || ''}`
    : eff.crop_name
      ? `${eff.crop_name} (${STAGE_LABELS[eff.growth_stage] || eff.growth_stage || ''})`
      : 'Chưa chọn giống cây';

  const hasCustom = Boolean(
    area.custom_min_temp != null ||
    area.custom_max_temp != null ||
    area.custom_min_humidity != null ||
    area.custom_max_humidity != null ||
    area.custom_min_light != null ||
    area.custom_max_light != null ||
    area.custom_fungal_humidity_threshold != null
  );

  return (
    '<article class="card area-card" data-area-id="' + esc(area.area_id) + '">' +
    '<div class="area-card-head">' +
    '<div>' +
    '<div class="area-tag">KHU VỰC TRỒNG</div>' +
    '<h3 class="area-name">' + esc(area.name) + '</h3>' +
    '<div class="tiny area-meta">' + esc(area.area_id) + ' · ' + (area.area_sqm ? fmt(area.area_sqm, 0) + ' m²' : 'Chưa có diện tích') + '</div>' +
    '</div>' +
    pill(hasCustom ? 'Tùy chỉnh riêng' : 'Theo giống cây', hasCustom ? '' : 'pill-ok') +
    '</div>' +

    '<div class="area-crop-info">' +
    '<span class="area-crop-icon">🌱</span>' +
    '<div class="area-crop-text"><strong>' + esc(cropTitle) + '</strong></div>' +
    '</div>' +

    // Effective Agronomic Thresholds Grid
    '<div class="threshold-matrix">' +
    '<div class="threshold-cell">' +
    '<span class="th-label">🌡️ Nhiệt độ</span>' +
    '<strong class="th-val">' + (eff.min_temp != null ? `${fmt(eff.min_temp, 0)} – ${fmt(eff.max_temp, 0)}°C` : '—') + '</strong>' +
    '</div>' +
    '<div class="threshold-cell">' +
    '<span class="th-label">💧 Độ ẩm khí</span>' +
    '<strong class="th-val">' + (eff.min_humidity != null ? `${fmt(eff.min_humidity, 0)} – ${fmt(eff.max_humidity, 0)}%` : '—') + '</strong>' +
    '</div>' +
    '<div class="threshold-cell">' +
    '<span class="th-label">☀️ Cường độ sáng</span>' +
    '<strong class="th-val">' + (eff.min_light != null ? `${fmt(eff.min_light, 0)} – ${fmt(eff.max_light, 0)} Lux` : '—') + '</strong>' +
    '</div>' +
    '<div class="threshold-cell">' +
    '<span class="th-label">🍄 Ngưỡng nấm</span>' +
    '<strong class="th-val">' + (eff.fungal_humidity_threshold != null ? `≥ ${fmt(eff.fungal_humidity_threshold, 0)}%` : '85%') + '</strong>' +
    '</div>' +
    '</div>' +

    '<div class="area-actions">' +
    '<button type="button" class="link-button area-edit-btn" data-edit-area="' + esc(area.area_id) + '">Chỉnh sửa ngưỡng →</button>' +
    '<button type="button" class="link-button area-delete-btn" data-delete-area="' + esc(area.area_id) + '" style="color:var(--red);margin-left:auto">Xóa khu vực</button>' +
    '</div>' +
    '</article>'
  );
}

// ─── Garden List View ─────────────────────────────────────────────────────────

export function renderGardenListView() {
  if (!state.greenhouses.length) {
    return (
      '<div class="card empty empty-state"><div class="icon-tile" style="margin:auto auto 12px">⌂</div>Chưa có khu vườn nào được đăng ký.</div>' +
      '<div class="management-notice">' + addGreenhouseButton() + '</div>'
    );
  }
  return (
    '<div class="greenhouse-list-actions">' + addGreenhouseButton() + '</div>' +
    '<div class="section-heading"><h2>Khu vườn ngoài trời của bạn</h2><span>' + state.greenhouses.length + ' khu vườn · ' + state.devices.length + ' thiết bị</span></div>' +
    '<div class="collection-grid">' +
    state.greenhouses
      .map((h, i) => {
        const ds = gardenDevices(h.greenhouse_id);
        const on = ds.filter((x) => x.is_online).length;
        const areas = state.areas[h.greenhouse_id] || [];
        return (
          '<article class="card greenhouse-card">' +
          '<div class="greenhouse-cover" aria-hidden="true"><span class="greenhouse-cover-label">KHU VƯỜN / ' + String(i + 1).padStart(2, '0') + '</span></div>' +
          '<div class="greenhouse-card-body">' +
          '<div class="topline"><div class="icon-tile">⌂</div><div><h3>' + esc(h.name) + '</h3><div class="tiny">' + esc(h.location || 'Chưa có vị trí') + ' · ' + (h.area_sqm ? fmt(h.area_sqm, 0) + ' m²' : 'Chưa có diện tích') + '</div></div></div>' +
          '<p>' + pill(ds.length ? on + '/' + ds.length + ' thiết bị trực tuyến' : 'Chưa liên kết thiết bị', ds.length && on === ds.length ? '' : 'offline') +
          ' ' + pill(areas.length + ' khu vực trồng', 'pill-neutral') + '</p>' +
          '<div class="tiny">Mã khu vườn: ' + esc(h.greenhouse_id) + '</div>' +
          '<button type="button" class="link-button" data-open="' + esc(h.greenhouse_id) + '">Xem chi tiết khu vườn →</button>' +
          '</div></article>'
        );
      })
      .join('') +
    '</div>'
  );
}

// ─── Garden Detail View (Areas + Devices) ─────────────────────────────────────

export function renderGardenDetailView(id) {
  const h = state.greenhouses.find((x) => x.greenhouse_id === id);
  if (!h) return renderGardenListView();
  if (state.editingGreenhouse) return renderGreenhouseForm(id);
  if (state.creatingDevice) return renderDeviceForm(id);
  if (state.creatingArea) return renderAreaForm(id, null);
  if (state.editingAreaId) return renderAreaForm(id, state.editingAreaId);

  const ds = gardenDevices(id);
  const areas = state.areas[id] || [];

  return (
    '<div class="greenhouse-list-actions">' +
    '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">' +
    addAreaButton() +
    addDeviceButton() +
    '<button type="button" class="secondary-button" data-action="edit-greenhouse" style="width:auto">Chỉnh sửa thông tin</button>' +
    '<button type="button" class="secondary-button" data-action="delete-greenhouse" style="width:auto;color:var(--red);border-color:#ecd2cf">Xóa khu vườn</button>' +
    '</div></div>' +

    // ── SECTION 1: Outdoor Planting Areas & Crop Thresholds (Stage 4C)
    '<div class="detail-heading" style="margin-top:24px">' +
    '<div class="section-heading">' +
    '<h2>Khu vực trồng & Ngưỡng cây trồng ngoài trời</h2>' +
    '<span>' + areas.length + ' khu vực · Tự động áp dụng ngưỡng nông học</span>' +
    '</div></div>' +

    '<div class="area-grid">' +
    (areas.length
      ? areas.map((a) => renderAreaCard(a, id)).join('')
      : '<div class="card empty empty-state">Khu vườn này chưa có khu vực trồng nào.</div><div class="management-notice">' + addAreaButton() + '</div>') +
    '</div>' +

    // ── SECTION 2: Hardware Devices (NodeMCU, ESP32-CAM, Pump)
    '<div class="detail-heading" style="margin-top:36px">' +
    '<div class="section-heading">' +
    '<h2>Thiết bị phần cứng liên kết</h2>' +
    '<span>' + ds.length + ' thiết bị</span>' +
    '</div></div>' +

    '<div class="device-grid">' +
    (ds.length
      ? ds
          .map((d) => {
            const l = latestReading(d.device_id);
            return (
              '<article class="card device-card">' +
              pill(d.is_online ? 'Đang kết nối' : 'Chưa kết nối', d.is_online ? '' : 'offline') +
              '<h3>' + esc(d.device_id) + '</h3>' +
              '<div class="tiny">' + esc(formatDeviceTypeLabel(d.hardware_model, d.device_type)) + ' · ' + esc(formatStatusLabel(d.status)) + '</div>' +
              '<div class="row"><span>Bản ghi gần nhất</span><strong>' + formatDate(l?.timestamp || d.last_updated) + '</strong></div>' +
              '<div class="device-actions" style="margin-top:12px;padding-top:10px;border-top:1px solid var(--line);display:flex;justify-content:flex-end">' +
              '<button type="button" class="link-button device-delete-btn" data-delete-device="' + esc(d.device_id) + '" style="color:var(--red);font-weight:600;font-size:11px;cursor:pointer">Ngưng sử dụng</button>' +
              '</div></article>'
            );
          })
          .join('')
      : '<div class="card empty empty-state">Khu vườn này chưa có thiết bị nào.</div><div class="management-notice">' + addDeviceButton() + '</div>') +
    '</div>'
  );
}
