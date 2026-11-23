/**
 * Frontend MVC — Main Application Controller
 * Coordinates Model (store + apiClient), Router, and Views.
 */

import {
  apiRequest,
  createGardenArea,
  deleteGardenArea,
  handleAuthExpiry,
  loadCameraLogs,
  loadWorkspaceData,
  patchCameraLogStatus,
  refreshGardenAreas,
  refreshGardenActuators,
  triggerCapture,
  updateGardenArea,
  updatePumpControl,
  uploadDiagnose,
} from '../models/apiClient.js';
import {
  PAGES,
  PAGE_DESCRIPTIONS,
  clearSession,
  currentGarden,
  esc,
  fmt,
  gardenDevices,
  state,
} from '../models/store.js';
import { renderAdviceView, renderAlertsView } from '../views/alertsView.js';
import {
  eyeIcon,
  renderAuthScreenMarkup,
  renderUserPanelMarkup,
} from '../views/authView.js';
import { renderDashboardView } from '../views/dashboardView.js';
import { renderDiagnosisView } from '../views/diagnosisView.js';
import {
  renderGardenDetailView,
  renderGardenListView,
  renderGreenhouseForm,
} from '../views/gardenView.js';
import { renderHistoryView } from '../views/historyView.js';
import { applyRoute, readRoute, writeRoute } from './router.js';

let appEl;
let authScreenEl;
let appShellEl;
let navButtons;
let profileToggleEl;
let profilePanelEl;

function setProfileOpen(open) {
  if (open) profilePanelEl.innerHTML = renderUserPanelMarkup();
  profilePanelEl.hidden = !open;
  profileToggleEl.setAttribute('aria-expanded', String(open));
}

function renderHeader() {
  const brand = document.querySelector('#garden-name');
  if (brand) brand.textContent = 'Smart Garden';
  const fullName = state.user?.full_name || '';
  const initials = fullName
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0])
    .join('')
    .toLocaleUpperCase('vi-VN');
  const avatarIcon = profileToggleEl.querySelector('svg');
  const avatarInitials = document.querySelector('#profile-initials');
  avatarIcon?.toggleAttribute('hidden', Boolean(initials));
  if (avatarInitials) {
    avatarInitials.hidden = !initials;
    avatarInitials.textContent = initials;
  }
  profileToggleEl.setAttribute(
    'aria-label',
    state.user ? 'Thông tin người dùng: ' + fullName : 'Yêu cầu đăng nhập'
  );
}

export function render() {
  if (!state.user) {
    appShellEl.classList.add('auth-mode');
    authScreenEl.hidden = false;
    authScreenEl.innerHTML = renderAuthScreenMarkup();
    return;
  }

  appShellEl.classList.remove('auth-mode');
  authScreenEl.hidden = true;

  const detail =
    state.page === 'greenhouses' &&
    state.greenhouses.find((x) => x.greenhouse_id === state.detailId);
  const creating = state.page === 'greenhouses' && state.creatingGreenhouse;
  const editing =
    state.page === 'greenhouses' && Boolean(state.detailId) && state.editingGreenhouse;
  const creatingDev = state.page === 'greenhouses' && state.creatingDevice;
  const creatingArea = state.page === 'greenhouses' && state.creatingArea;
  const editingArea = state.page === 'greenhouses' && Boolean(state.editingAreaId);

  const title = creating
    ? 'Thêm khu vườn'
    : editing
      ? 'Chỉnh sửa khu vườn'
      : creatingDev
        ? 'Thêm thiết bị'
        : creatingArea
          ? 'Thêm khu vực trồng'
          : editingArea
            ? 'Chỉnh sửa khu vực trồng'
            : detail
              ? detail.name
              : PAGES[state.page][0];

  const description = editing
    ? 'Cập nhật thông tin khu vườn trồng ngoài trời của bạn.'
    : creatingDev
      ? 'Đăng ký thiết bị NodeMCU v2.0.0, ESP32-CAM hoặc Bơm nước.'
      : creatingArea || editingArea
        ? 'Thiết lập giống cây mẫu (Ớt/Xà lách) và tùy chỉnh ngưỡng cảnh báo nông học.'
        : detail
          ? (detail.location || 'Chưa có vị trí') +
            ' · ' +
            (detail.area_sqm ? fmt(detail.area_sqm, 0) + ' m²' : 'Chưa có diện tích')
          : PAGE_DESCRIPTIONS[state.page];

  navButtons.forEach((btn) => {
    const active = btn.dataset.page === state.page;
    btn.classList.toggle('active', active);
    if (active) btn.setAttribute('aria-current', 'page');
    else btn.removeAttribute('aria-current');
  });

  appEl.dataset.view = state.page;
  appEl.dataset.detail = String(Boolean(detail));
  renderHeader();

  let body;
  if (creating) {
    body = renderGreenhouseForm();
  } else if (editing) {
    body = renderGreenhouseForm(state.detailId);
  } else if (state.error) {
    body =
      '<div class="error-page"><b>Chưa kết nối được API</b><br>' +
      esc(state.error) +
      '<p><button type="button" class="link-button" data-action="refresh">Thử tải lại</button></p></div>';
  } else if (state.page === 'home') {
    body = renderDashboardView();
  } else if (state.page === 'history') {
    body = renderHistoryView();
  } else if (state.page === 'greenhouses') {
    body = state.detailId ? renderGardenDetailView(state.detailId) : renderGardenListView();
  } else if (state.page === 'camera') {
    body = renderDiagnosisView();
  } else if (state.page === 'advice') {
    body = renderAdviceView();
  } else {
    body = renderAlertsView();
  }

  if (
    state.page === 'greenhouses' &&
    !creating &&
    !editing &&
    !creatingDev &&
    !creatingArea &&
    !editingArea &&
    state.greenhouseNotice
  ) {
    body =
      '<p id="greenhouse-notice" class="banner" role="status" tabindex="-1">' +
      esc(state.greenhouseNotice) +
      '</p>' +
      body;
  }

  const eyebrow = creatingDev
    ? 'THIẾT BỊ'
    : creatingArea || editingArea
      ? 'KHU VỰC TRỒNG & NGƯỠNG NÔNG HỌC'
      : editing
        ? 'CHỈNH SỬA'
        : detail
          ? 'KHU VƯỜN NGOÀI TRỜI'
          : PAGES[state.page][1].toLocaleUpperCase('vi-VN');

  appEl.innerHTML =
    '<div class="page-header">' +
    '<div class="page-heading">' +
    '<span class="page-eyebrow">' + esc(eyebrow) + '</span>' +
    '<h1 class="page-title">' + esc(title) + '</h1>' +
    '<p class="subline">' + esc(description) + '</p>' +
    '</div>' +
    '<div class="page-status"><span aria-hidden="true">◷</span> Dữ liệu quan trắc · UTC+7</div>' +
    '</div>' +
    body;
}

export function navigateRoute(update, { replace = false, scroll = true } = {}) {
  update();
  writeRoute(replace);
  render();
  if (state.page === 'camera') setTimeout(setupDropzone, 50);
  if (scroll) window.scrollTo(0, 0);
}

async function loadData() {
  if (!state.user) {
    render();
    return;
  }
  appEl.innerHTML =
    '<div class="loading-page"><span class="spinner"></span><p>Đang tải dữ liệu từ API…</p></div>';
  state.error = '';
  try {
    await loadWorkspaceData();
    state.error = '';
  } catch (error) {
    if (handleAuthExpiry(error)) {
      writeRoute(true);
    } else {
      state.error = error.message;
    }
  }
  render();
}

async function handlePumpAction({ mode, toggle }) {
  const garden = currentGarden();
  if (!garden || state.pumpBusy) return;
  state.pumpBusy = true;
  state.pumpError = '';
  state.pumpMessage = '';
  render();

  const payload = { area_id: state.pumpAreaId || null };
  if (mode) payload.control_mode = mode;
  if (toggle === 'on' || toggle === 'off') {
    payload.control_mode = 'MANUAL';
    payload.is_on = toggle === 'on';
  }

  try {
    const result = await updatePumpControl(garden.greenhouse_id, payload);
    const mqttOk = result?.mqtt?.published;
    if (toggle) {
      state.pumpMessage =
        mqttOk ? 'Đã gửi lệnh; chờ board xác nhận trạng thái relay.' :
          'Chưa gửi được lệnh tới board. Kiểm tra kết nối; không coi bơm đã đổi trạng thái.';
    } else {
      state.pumpMessage =
        mode === 'AUTO'
          ? 'Đã chuyển Bơm nước sang chế độ Tự động (Auto).'
          : 'Đã chuyển Bơm nước sang chế độ Thủ công (Manual).';
    }
  } catch (error) {
    if (handleAuthExpiry(error)) {
      writeRoute(true);
    } else {
      state.pumpError = error.message || 'Không thể điều khiển Bơm nước.';
    }
  } finally {
    state.pumpBusy = false;
    render();
  }
}

// ─── Camera / Diagnosis handlers ─────────────────────────────────────────────

async function handleIrrigationConfig(event) {
  const form = event.target.closest('#irrigation-config');
  if (!form) return;
  event.preventDefault();
  if (state.pumpBusy) return;
  const garden = currentGarden();
  const fields = Object.fromEntries(new FormData(form));
  const rules = { schema_version: 2, sensor_device_id: fields.sensor_device_id,
    hardware_verified: form.elements.hardware_verified.checked,
    rain_exposed: form.elements.rain_exposed.checked,
    allowed_start: fields.allowed_start || null, allowed_end: fields.allowed_end || null };
  for (const key of ['start_below_pct', 'stop_at_pct', 'base_run_seconds', 'max_run_seconds',
    'cooldown_seconds', 'max_daily_seconds', 'latitude', 'longitude', 'max_temperature_c',
    'max_light_lux', 'hot_day_c', 'morning_multiplier', 'rainy_evening_multiplier']) {
    rules[key] = fields[key] === '' ? null : Number(fields[key]);
  }
  state.pumpBusy = true;
  state.pumpError = '';
  try {
    await updatePumpControl(garden.greenhouse_id, { area_id: state.pumpAreaId || null,
      device_id: fields.device_id, auto_rules: rules,
      control_mode: form.elements.enabled.checked ? 'AUTO' : 'MANUAL' });
    state.pumpMessage = 'Đã lưu cấu hình. Tưới tự động cần tiến trình nhận cảm biến và số đo hợp lệ.';
  } catch (err) {
    state.pumpError = err.message;
  } finally {
    state.pumpBusy = false;
    render();
  }
}

async function loadCameraHistory() {
  if (!state.user) return;
  state.cameraLogsLoading = true;
  state.cameraLogsError = '';
  render();
  try {
    state.cameraLogs = await loadCameraLogs(state.greenhouseId, 30);
  } catch (err) {
    state.cameraLogsError = err.message || 'Không tải được lịch sử chẩn đoán.';
  } finally {
    state.cameraLogsLoading = false;
    render();
  }
}

async function handleDiagnoseSubmit(event) {
  const form = event.target.closest('#diagnose-form');
  if (!form) return;
  event.preventDefault();

  const fileInput = form.querySelector('#diagnose-file');
  if (!fileInput?.files?.length) {
    state.diagnosisError = 'Vui lòng chọn một ảnh lá cây.';
    render();
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const gardenSel = form.querySelector('[name="greenhouse_id"]');
  const areaSel = form.querySelector('[name="area_id"]');
  const triggerSel = form.querySelector('[name="trigger_type"]');
  if (gardenSel?.value) formData.append('greenhouse_id', gardenSel.value);
  if (areaSel?.value) formData.append('area_id', areaSel.value);
  if (triggerSel?.value) formData.append('trigger_type', triggerSel.value);

  state.diagnosisLoading = true;
  state.diagnosisError = '';
  state.cameraUploadProgress = 'Đang tải ảnh lên và phân tích bệnh lá…';
  render();

  try {
    const result = await uploadDiagnose(formData);
    state.diagnosisResult = result;
    state.cameraUploadProgress = 'Phân tích hoàn tất!';
    // Refresh logs list
    state.cameraLogs = await loadCameraLogs(state.greenhouseId, 30).catch(() => state.cameraLogs);
  } catch (err) {
    if (handleAuthExpiry(err)) { writeRoute(true); return; }
    state.diagnosisError = err.message || 'Không thể phân tích ảnh. Vui lòng thử lại.';
    state.cameraUploadProgress = '';
  } finally {
    state.diagnosisLoading = false;
    render();
  }
}

async function handleTriggerCapture() {
  const deviceSel = document.querySelector('#trigger-cam-device');
  const deviceId = deviceSel?.value || 'ESP32-CAM-01';
  if (state.cameraTriggerBusy || state.isScanning) return;
  const areaId = document.querySelector('#diag-area')?.value || '';

  state.cameraTriggerBusy = true;
  state.isScanning = true;
  state.cameraTriggerMsg = 'Đang gửi lệnh quét tới vi điều khiển ESP32-CAM (' + deviceId + ')...';
  render();

  try {
    await triggerCapture(deviceId, areaId || undefined);
    state.cameraTriggerMsg = 'Đã gửi lệnh MQTT tới vi điều khiển ' + deviceId + '. Đang xử lý ảnh và chẩn đoán AI...';
    render();

    // Give ESP32-CAM time to capture & push, then reload logs
    await new Promise((resolve) => setTimeout(resolve, 1200));
    state.cameraLogs = await loadCameraLogs(state.greenhouseId, 30);
    if (state.cameraLogs.length > 0) {
      state.diagnosisResult = state.cameraLogs[0];
      state.cameraTriggerMsg = '✓ Quét và chẩn đoán bệnh lá hoàn tất từ ESP32-CAM (' + deviceId + ')!';
    }
  } catch (err) {
    if (handleAuthExpiry(err)) { writeRoute(true); return; }
    state.cameraTriggerMsg = 'Lưu ý: ' + (err.message || 'Không gửi được lệnh MQTT tới vi điều khiển.');
  } finally {
    state.cameraTriggerBusy = false;
    state.isScanning = false;
    render();
  }
}

async function handlePatchStatus(logId, status) {
  try {
    const updated = await patchCameraLogStatus(logId, status);
    if (state.diagnosisResult?.log_id === logId) state.diagnosisResult = updated;
    state.cameraLogs = state.cameraLogs.map((l) => l.log_id === logId ? updated : l);
    render();
  } catch (err) {
    if (handleAuthExpiry(err)) { writeRoute(true); return; }
    alert('Không thể cập nhật trạng thái: ' + err.message);
  }
}

function setupDropzone() {
  const dropzone = document.querySelector('#upload-dropzone');
  const fileInput = document.querySelector('#diagnose-file');
  const preview = document.querySelector('#upload-preview');
  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file || !preview) return;
    const url = URL.createObjectURL(file);
    preview.innerHTML = '<img src="' + url + '" alt="Ảnh đã chọn" /><span class="preview-name">' + file.name + '</span>';
    preview.hidden = false;
  });

  ['dragover', 'dragenter'].forEach((ev) => {
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add('dropzone--over'); });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    dropzone.addEventListener(ev, () => dropzone.classList.remove('dropzone--over'));
  });
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change'));
  });
}

function togglePasswordVisibility(eyeButton) {
  const input = eyeButton.closest('.password-field')?.querySelector('input');
  if (!input) return;
  const visible = input.type === 'password';
  input.type = visible ? 'text' : 'password';
  eyeButton.setAttribute('aria-label', visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
  eyeButton.setAttribute('aria-pressed', String(visible));
  eyeButton.innerHTML = eyeIcon(visible);
}

async function handleAuthSubmit(event) {
  const form = event.target.closest('[data-auth-form]');
  if (!form) return;
  event.preventDefault();
  const mode = form.dataset.authForm;
  const payload = Object.fromEntries(new FormData(form).entries());
  const submitButton = form.querySelector('[type="submit"]');
  if (mode === 'register' && payload.password !== payload.password_confirm) {
    const confirmation = form.querySelector('[name="password_confirm"]');
    confirmation.setCustomValidity('Mật khẩu xác nhận không khớp');
    confirmation.reportValidity();
    confirmation.addEventListener('input', () => confirmation.setCustomValidity(''), { once: true });
    return;
  }
  delete payload.password_confirm;
  state.authValues = { email: payload.email || '', full_name: payload.full_name || '' };
  state.authError = '';
  state.authBusy = true;
  submitButton.disabled = true;
  submitButton.textContent = 'Đang xử lý…';
  try {
    const result = await apiRequest('/api/auth/' + mode, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    if (!result?.access_token || !result.user) {
      throw new Error('API không trả về phiên đăng nhập hợp lệ');
    }
    state.token = result.access_token;
    sessionStorage.setItem('ln-access-token', state.token);
    state.user = result.user;
    state.profileMode = 'info';
    state.authPage = 'login';
    state.page = 'home';
    state.detailId = '';
    state.creatingGreenhouse = false;
    state.editingGreenhouse = false;
    state.creatingDevice = false;
    state.authError = '';
    state.authValues = {};
    state.sessionError = '';
    state.error = '';
    setProfileOpen(false);
    await loadData();
    writeRoute(true);
  } catch (error) {
    state.authError = error.message;
    state.authBusy = false;
    if (authScreenEl.contains(form)) {
      authScreenEl.innerHTML = renderAuthScreenMarkup();
    } else {
      profilePanelEl.innerHTML = renderUserPanelMarkup();
    }
    return;
  }
  state.authBusy = false;
  if (state.user) profilePanelEl.innerHTML = renderUserPanelMarkup();
}

async function handleGreenhouseSubmit(event) {
  const form = event.target.closest('#greenhouse-form');
  if (!form) return;
  event.preventDefault();
  if (state.greenhouseSaving || !state.user) return;
  const isEdit = form.dataset?.mode === 'edit';
  const values = Object.fromEntries(new FormData(form).entries());
  const payload = {
    greenhouse_id: values.greenhouse_id.trim(),
    name: values.name.trim(),
    location: values.location.trim() || null,
    area_sqm: values.area_sqm.trim() === '' ? null : Number(values.area_sqm),
    environment_type: 'OUTDOOR',
  };
  const showError = (msg) => {
    const el = form.querySelector('#greenhouse-form-error');
    el.textContent = msg;
    el.hidden = false;
    el.focus();
  };
  if (!payload.name || !payload.greenhouse_id) {
    showError('Vui lòng nhập tên và mã khu vườn.');
    return;
  }
  if (payload.area_sqm !== null && (!Number.isFinite(payload.area_sqm) || payload.area_sqm <= 0)) {
    showError('Diện tích phải là số lớn hơn 0.');
    return;
  }
  if (!isEdit && state.greenhouses.some((h) => h.greenhouse_id === payload.greenhouse_id)) {
    showError('Mã khu vườn đã tồn tại. Vui lòng chọn mã khác.');
    return;
  }

  const submit = form.querySelector('[type="submit"]');
  state.greenhouseSaving = true;
  form.setAttribute('aria-busy', 'true');
  form.querySelector('fieldset').disabled = true;
  submit.disabled = true;
  submit.textContent = 'Đang lưu…';
  try {
    const saved = isEdit
      ? await apiRequest('/api/greenhouses/' + encodeURIComponent(payload.greenhouse_id), {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
      : await apiRequest('/api/greenhouses', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
    state.greenhouses = [
      ...state.greenhouses.filter((h) => h.greenhouse_id !== saved.greenhouse_id),
      saved,
    ];
    state.greenhouseId = saved.greenhouse_id;
    state.deviceId = '';
    state.detailId = isEdit ? saved.greenhouse_id : '';
    localStorage.setItem('ln-greenhouse', saved.greenhouse_id);
    state.greenhouseNotice = isEdit
      ? 'Đã cập nhật khu vườn “' + saved.name + '”.'
      : 'Đã thêm khu vườn “' + saved.name + '”.';
    navigateRoute(() => {
      state.creatingGreenhouse = false;
      state.editingGreenhouse = false;
      state.page = 'greenhouses';
    });
  } catch (error) {
    showError(error.message || 'Không thể lưu khu vườn.');
  } finally {
    state.greenhouseSaving = false;
    form.removeAttribute('aria-busy');
    if (form.isConnected) {
      form.querySelector('fieldset').disabled = false;
      submit.disabled = false;
      submit.textContent = isEdit ? 'Cập nhật khu vườn' : 'Lưu khu vườn';
    }
  }
}

async function handleDeviceSubmit(event) {
  const form = event.target.closest('#device-form');
  if (!form) return;
  event.preventDefault();
  if (state.deviceSaving || !state.user) return;
  const values = Object.fromEntries(new FormData(form).entries());
  const payload = {
    device_id: values.device_id.trim(),
    greenhouse_id: state.detailId,
    device_type: (values.device_type || 'SENSOR_NODE').trim(),
    status: (values.status || 'ACTIVE').trim(),
  };
  const showError = (msg) => {
    const el = form.querySelector('#device-form-error');
    el.textContent = msg;
    el.hidden = false;
    el.focus();
  };
  if (!payload.device_id) {
    showError('Vui lòng nhập mã thiết bị.');
    return;
  }
  if (state.devices.some((d) => d.device_id === payload.device_id)) {
    showError('Mã thiết bị đã tồn tại. Vui lòng chọn mã khác.');
    return;
  }
  const submit = form.querySelector('[type="submit"]');
  state.deviceSaving = true;
  form.setAttribute('aria-busy', 'true');
  form.querySelector('fieldset').disabled = true;
  submit.disabled = true;
  submit.textContent = 'Đang lưu…';
  try {
    const created = await apiRequest('/api/devices', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    state.devices = [...state.devices.filter((d) => d.device_id !== created.device_id), created];
    state.greenhouseNotice = 'Đã thêm thiết bị “' + created.device_id + '” vào khu vườn.';
    navigateRoute(() => {
      state.creatingDevice = false;
    });
  } catch (error) {
    showError(error.message || 'Không thể lưu thiết bị.');
  } finally {
    state.deviceSaving = false;
    form.removeAttribute('aria-busy');
    if (form.isConnected) {
      form.querySelector('fieldset').disabled = false;
      submit.disabled = false;
      submit.textContent = 'Lưu thiết bị';
    }
  }
}

async function handleAreaSubmit(event) {
  const form = event.target.closest('#area-form');
  if (!form) return;
  event.preventDefault();
  if (state.areaSaving || !state.user || !state.detailId) return;

  const isEdit = form.dataset?.mode === 'edit';
  const editingAreaId = form.dataset?.areaId;
  const values = Object.fromEntries(new FormData(form).entries());

  const numOrNull = (v) => (v !== undefined && String(v).trim() !== '' ? Number(v) : null);

  const payload = {
    name: values.name.trim(),
    crop_stage_id: values.crop_stage_id ? values.crop_stage_id.trim() : null,
    area_sqm: numOrNull(values.area_sqm),
    custom_min_temp: numOrNull(values.custom_min_temp),
    custom_max_temp: numOrNull(values.custom_max_temp),
    custom_min_humidity: numOrNull(values.custom_min_humidity),
    custom_max_humidity: numOrNull(values.custom_max_humidity),
    custom_min_light: numOrNull(values.custom_min_light),
    custom_max_light: numOrNull(values.custom_max_light),
    custom_fungal_humidity_threshold: numOrNull(values.custom_fungal_humidity_threshold),
  };

  if (!isEdit && values.area_id && values.area_id.trim()) {
    payload.area_id = values.area_id.trim();
  }

  const showError = (msg) => {
    const el = form.querySelector('#area-form-error');
    if (el) {
      el.textContent = msg;
      el.hidden = false;
      el.focus();
    }
  };

  if (!payload.name) {
    showError('Vui lòng nhập tên khu vực trồng.');
    return;
  }
  if (payload.area_sqm !== null && (!Number.isFinite(payload.area_sqm) || payload.area_sqm <= 0)) {
    showError('Diện tích phải là số lớn hơn 0.');
    return;
  }
  if (payload.custom_min_temp !== null && payload.custom_max_temp !== null && payload.custom_min_temp > payload.custom_max_temp) {
    showError('Nhiệt độ tối thiểu phải nhỏ hơn hoặc bằng nhiệt độ tối đa.');
    return;
  }
  if (payload.custom_min_humidity !== null && payload.custom_max_humidity !== null && payload.custom_min_humidity > payload.custom_max_humidity) {
    showError('Độ ẩm tối thiểu phải nhỏ hơn hoặc bằng độ ẩm tối đa.');
    return;
  }
  if (payload.custom_min_light !== null && payload.custom_max_light !== null && payload.custom_min_light > payload.custom_max_light) {
    showError('Ánh sáng tối thiểu phải nhỏ hơn hoặc bằng ánh sáng tối đa.');
    return;
  }

  const submit = form.querySelector('[type="submit"]');
  state.areaSaving = true;
  form.setAttribute('aria-busy', 'true');
  form.querySelector('fieldset').disabled = true;
  submit.disabled = true;
  submit.textContent = 'Đang lưu…';

  try {
    const saved = isEdit
      ? await updateGardenArea(state.detailId, editingAreaId, payload)
      : await createGardenArea(state.detailId, payload);

    state.greenhouseNotice = isEdit
      ? 'Đã cập nhật khu vực “' + saved.name + '”.'
      : 'Đã thêm khu vực trồng “' + saved.name + '”.';
    navigateRoute(() => {
      state.creatingArea = false;
      state.editingAreaId = '';
    });
  } catch (error) {
    if (handleAuthExpiry(error)) {
      writeRoute(true);
      return;
    }
    showError(error.message || 'Không thể lưu khu vực trồng.');
  } finally {
    state.areaSaving = false;
    form.removeAttribute('aria-busy');
    if (form.isConnected) {
      form.querySelector('fieldset').disabled = false;
      submit.disabled = false;
      submit.textContent = isEdit ? 'Cập nhật khu vực' : 'Lưu khu vực trồng';
    }
  }
}

function bindEvents() {
  window.addEventListener('popstate', (event) => {
    applyRoute(event.state?.greenhouseRoute || readRoute());
    state.greenhouseNotice = '';
    setProfileOpen(false);
    render();
    if (state.page === 'camera') {
      loadCameraHistory();
      setTimeout(setupDropzone, 50);
    }
  });

  profileToggleEl.addEventListener('click', () => setProfileOpen(profilePanelEl.hidden));

  profilePanelEl.addEventListener('click', (event) => {
    const eye = event.target.closest('[data-password-toggle]');
    if (eye) return togglePasswordVisibility(eye);
    const mode = event.target.closest('[data-profile-mode]')?.dataset.profileMode;
    if (mode) {
      event.stopPropagation();
      const email = profilePanelEl.querySelector('[name=email]')?.value || state.authValues.email || '';
      state.profileMode = mode;
      state.authError = '';
      state.authValues = mode === 'info' ? {} : { email };
      profilePanelEl.innerHTML = renderUserPanelMarkup();
      return;
    }
    if (event.target.closest('[data-auth-logout]')) {
      event.stopPropagation();
      clearSession();
      state.profileMode = 'info';
      state.authError = '';
      state.authValues = {};
      state.sessionError = '';
      state.error = '';
      state.authPage = 'login';
      writeRoute(true);
      render();
      setProfileOpen(false);
    }
  });

  authScreenEl.addEventListener('click', (event) => {
    const eye = event.target.closest('[data-password-toggle]');
    if (eye) return togglePasswordVisibility(eye);
    const pageBtn = event.target.closest('[data-auth-page]');
    if (pageBtn) {
      const page = pageBtn.dataset.authPage;
      const email = authScreenEl.querySelector('[name="email"]')?.value || state.authValues.email || '';
      const fullName = authScreenEl.querySelector('[name="full_name"]')?.value || state.authValues.full_name || '';
      navigateRoute(() => {
        state.authPage = page;
        state.authError = '';
        state.authValues = { email, ...(page === 'register' && fullName ? { full_name: fullName } : {}) };
      });
    }
  });

  authScreenEl.addEventListener('submit', handleAuthSubmit);
  profilePanelEl.addEventListener('submit', handleAuthSubmit);
  appEl.addEventListener('submit', handleGreenhouseSubmit);
  appEl.addEventListener('submit', handleDeviceSubmit);
  appEl.addEventListener('submit', handleAreaSubmit);
  appEl.addEventListener('submit', handleIrrigationConfig);
  appEl.addEventListener('change', event => {
    if (event.target.id === 'pump-area') {
      state.pumpAreaId = event.target.value;
      state.pumpError = '';
      state.pumpMessage = '';
      render();
    }
  });

  // Camera / Diagnosis form
  appEl.addEventListener('submit', handleDiagnoseSubmit);

  appEl.addEventListener('click', (event) => {
    // Trigger ESP32-CAM
    if (event.target.closest('#trigger-cam-btn')) {
      handleTriggerCapture();
      return;
    }
    // Stream config buttons
    if (event.target.closest('#btn-apply-stream')) {
      const url = document.querySelector('#esp32-stream-input')?.value.trim();
      if (url) {
        state.esp32StreamUrl = url;
        state.esp32StreamMode = 'stream';
        localStorage.setItem('ln-esp32-stream', url);
        render();
      }
      return;
    }
    if (event.target.closest('#btn-snapshot-mode')) {
      state.esp32StreamMode = 'snapshot';
      render();
      return;
    }
    // Patch camera log status
    const patchBtn = event.target.closest('[data-patch-status]');
    if (patchBtn) {
      const { logId, patchStatus } = patchBtn.dataset;
      handlePatchStatus(logId || patchBtn.dataset.logId, patchStatus || patchBtn.dataset.patchStatus);
      return;
    }
    // Select camera log
    const camCard = event.target.closest('[data-cam-log]');
    if (camCard) {
      const logId = camCard.dataset.camLog;
      state.diagnosisResult = state.cameraLogs.find((l) => l.log_id === logId) || null;
      render();
      return;
    }
    const pumpModeBtn = event.target.closest('[data-pump-mode]');
    if (pumpModeBtn) {
      handlePumpAction({ mode: pumpModeBtn.dataset.pumpMode });
      return;
    }
    const pumpToggleBtn = event.target.closest('[data-pump-toggle]');
    if (pumpToggleBtn) {
      handlePumpAction({ toggle: pumpToggleBtn.dataset.pumpToggle });
      return;
    }

    if (event.target.closest('[data-action="add-area"]')) {
      if (!state.user || state.areaSaving || !state.detailId) return;
      navigateRoute(() => {
        state.page = 'greenhouses';
        state.creatingArea = true;
        state.editingAreaId = '';
        state.creatingDevice = false;
        state.editingGreenhouse = false;
        state.greenhouseNotice = '';
      });
      document.querySelector('#area-name')?.focus();
      return;
    }
    if (event.target.closest('[data-action="cancel-area"]') && !state.areaSaving) {
      navigateRoute(() => {
        state.creatingArea = false;
        state.editingAreaId = '';
      });
      return;
    }
    const editAreaBtn = event.target.closest('[data-edit-area]');
    if (editAreaBtn) {
      const areaId = editAreaBtn.dataset.editArea;
      navigateRoute(() => {
        state.page = 'greenhouses';
        state.editingAreaId = areaId;
        state.creatingArea = false;
        state.creatingDevice = false;
        state.editingGreenhouse = false;
        state.greenhouseNotice = '';
      });
      return;
    }
    const delAreaBtn = event.target.closest('[data-delete-area]');
    if (delAreaBtn) {
      const areaId = delAreaBtn.dataset.deleteArea;
      const gardenId = state.detailId;
      const areas = state.areas[gardenId] || [];
      const targetArea = areas.find((a) => a.area_id === areaId);
      if (confirm('Bạn có chắc chắn muốn xóa khu vực trồng "' + (targetArea?.name || areaId) + '"?')) {
        (async () => {
          try {
            await deleteGardenArea(gardenId, areaId);
            state.greenhouseNotice = 'Đã xóa khu vực trồng “' + (targetArea?.name || areaId) + '”.';
            render();
          } catch (err) {
            alert('Không thể xóa khu vực trồng: ' + err.message);
          }
        })();
      }
      return;
    }

    if (event.target.closest('[data-action="add-greenhouse"]')) {
      if (!state.user || state.greenhouseSaving) return;
      navigateRoute(() => {
        state.page = 'greenhouses';
        state.detailId = '';
        state.creatingGreenhouse = true;
        state.editingGreenhouse = false;
        state.greenhouseNotice = '';
      });
      document.querySelector('#greenhouse-name')?.focus();
      return;
    }
    if (event.target.closest('[data-action="cancel-greenhouse"]') && !state.greenhouseSaving) {
      navigateRoute(() => {
        state.creatingGreenhouse = false;
        state.editingGreenhouse = false;
      });
      return;
    }
    if (event.target.closest('[data-action="edit-greenhouse"]')) {
      navigateRoute(() => {
        state.editingGreenhouse = true;
        state.creatingDevice = false;
        state.greenhouseNotice = '';
      });
      return;
    }
    if (event.target.closest('[data-action="delete-greenhouse"]')) {
      const id = state.detailId;
      const h = state.greenhouses.find((x) => x.greenhouse_id === id);
      const ds = gardenDevices(id);
      if (ds.length > 0) {
        alert('Khu vườn còn ' + ds.length + ' thiết bị liên kết. Vui lòng ngưng sử dụng hết thiết bị trước khi xóa khu vườn.');
        return;
      }
      if (confirm('Bạn có chắc chắn muốn xóa khu vườn "' + (h?.name || id) + '"?')) {
        (async () => {
          try {
            await apiRequest('/api/greenhouses/' + encodeURIComponent(id), { method: 'DELETE' });
            state.greenhouses = state.greenhouses.filter((x) => x.greenhouse_id !== id);
            state.greenhouseId = state.greenhouses[0]?.greenhouse_id || '';
            if (state.greenhouseId) localStorage.setItem('ln-greenhouse', state.greenhouseId);
            else localStorage.removeItem('ln-greenhouse');
            state.greenhouseNotice = 'Đã xóa khu vườn “' + (h?.name || id) + '”.';
            navigateRoute(() => {
              state.page = 'greenhouses';
              state.detailId = '';
              state.editingGreenhouse = false;
              state.creatingDevice = false;
            });
          } catch (err) {
            alert('Không thể xóa khu vườn: ' + err.message);
          }
        })();
      }
      return;
    }
    if (event.target.closest('[data-action="add-device"]')) {
      if (!state.user || state.deviceSaving || !state.detailId) return;
      navigateRoute(() => {
        state.page = 'greenhouses';
        state.creatingDevice = true;
        state.greenhouseNotice = '';
      });
      return;
    }
    if (event.target.closest('[data-action="cancel-device"]') && !state.deviceSaving) {
      navigateRoute(() => {
        state.creatingDevice = false;
      });
      return;
    }
    const delId = event.target.closest('[data-delete-device]')?.dataset.deleteDevice;
    if (delId) {
      if (confirm('Ngưng sử dụng thiết bị "' + delId + '"? (Lịch sử cảm biến vẫn được lưu giữ.)')) {
        (async () => {
          try {
            await apiRequest('/api/devices/' + encodeURIComponent(delId), { method: 'DELETE' });
            state.devices = state.devices.filter((d) => d.device_id !== delId);
            if (state.deviceId === delId) state.deviceId = '';
            state.greenhouseNotice = 'Đã ngưng sử dụng thiết bị “' + delId + '”.';
            render();
          } catch (err) {
            alert('Không thể cập nhật thiết bị: ' + err.message);
          }
        })();
      }
    }
  });

  document.addEventListener('click', async (event) => {
    if (!event.target.closest('.profile-menu')) setProfileOpen(false);
    const modeBtn = event.target.closest('[data-profile-mode]');
    if (modeBtn && !profilePanelEl.contains(modeBtn)) {
      state.profileMode = modeBtn.dataset.profileMode;
      state.authError = '';
      state.authValues = {};
      setProfileOpen(true);
      return;
    }
    const page = event.target.closest('[data-page]')?.dataset.page;
    if (page) {
      if (state.greenhouseSaving || state.deviceSaving) return;
      navigateRoute(() => {
        state.creatingGreenhouse = false;
        state.editingGreenhouse = false;
        state.creatingDevice = false;
        state.creatingArea = false;
        state.editingAreaId = '';
        state.greenhouseNotice = '';
        state.pumpMessage = '';
        state.pumpError = '';
        state.page = page;
        state.detailId = '';
      });
      if (page === 'camera') {
        loadCameraHistory();
        // Setup dropzone on next tick after render
        setTimeout(setupDropzone, 50);
      }
      return;
    }
    const metric = event.target.closest('[data-metric]')?.dataset.metric;
    if (metric) {
      navigateRoute(() => {
        state.metric = metric;
      }, { scroll: false });
      return;
    }
    const period = event.target.closest('[data-period]')?.dataset.period;
    if (period) {
      navigateRoute(() => {
        state.period = period;
      }, { scroll: false });
      return;
    }
    if (event.target.closest('[data-action="refresh"]')) {
      await loadData();
      return;
    }
    const open = event.target.closest('[data-open]')?.dataset.open;
    if (open) {
      navigateRoute(() => {
        state.detailId = open;
        state.editingGreenhouse = false;
        state.creatingDevice = false;
        state.creatingArea = false;
        state.editingAreaId = '';
        state.greenhouseId = open;
        localStorage.setItem('ln-greenhouse', open);
      });
      return;
    }
    const recId = event.target.closest('[data-apply]')?.dataset.apply;
    if (recId && confirm('Đánh dấu khuyến nghị này là đã áp dụng?')) {
      try {
        await apiRequest('/api/recommendations/' + encodeURIComponent(recId) + '/apply', {
          method: 'PUT',
        });
        await loadData();
      } catch (err) {
        alert('Không cập nhật được: ' + err.message);
      }
    }
  });

  document.addEventListener('change', (event) => {
    if (event.target.id === 'gh') {
      navigateRoute(() => {
        state.greenhouseId = event.target.value;
        state.detailId = '';
        state.editingGreenhouse = false;
        state.creatingDevice = false;
        state.creatingArea = false;
        state.editingAreaId = '';
        state.deviceId = '';
        state.pumpMessage = '';
        state.pumpError = '';
        localStorage.setItem('ln-greenhouse', state.greenhouseId);
      }, { scroll: false });
    } else if (event.target.id === 'device') {
      navigateRoute(() => {
        state.deviceId = event.target.value;
      }, { scroll: false });
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setProfileOpen(false);
  });
}

export async function startApp() {
  appEl = document.querySelector('#app');
  authScreenEl = document.querySelector('#auth-screen');
  appShellEl = document.querySelector('.app-shell');
  navButtons = [...document.querySelectorAll('.nav-item')];
  profileToggleEl = document.querySelector('#profile-toggle');
  profilePanelEl = document.querySelector('#profile-panel');

  bindEvents();
  // Refresh acknowledgements without erasing a configuration form being edited.
  let refreshingPump = false;
  setInterval(async () => {
    if (!state.user || state.page !== 'home' || state.pumpBusy || refreshingPump ||
        document.querySelector('.irrigation-panel details[open]')) return;
    const garden = currentGarden();
    if (!garden) return;
    refreshingPump = true;
    try {
      await refreshGardenActuators(garden.greenhouse_id);
      if (state.page === 'home' && !document.querySelector('.irrigation-panel details[open]')) render();
    } catch {
      // Preserve the last snapshot; its device timestamp remains visible.
    } finally { refreshingPump = false; }
  }, 10000);

  const route = readRoute();
  if (!state.token) {
    state.user = null;
    applyRoute(route);
    writeRoute(true);
    render();
    if (state.page === 'camera') {
      loadCameraHistory();
      setTimeout(setupDropzone, 50);
    }
    return;
  }
  try {
    state.user = await apiRequest('/api/auth/me');
    state.sessionError = '';
    await loadData();
    applyRoute(route);
    writeRoute(true);
    render();
    if (state.page === 'camera') {
      loadCameraHistory();
      setTimeout(setupDropzone, 50);
    }
  } catch (error) {
    if (error.status === 401 || error.status === 403) {
      clearSession();
      state.sessionError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    } else {
      state.sessionError = 'Không thể xác minh phiên đăng nhập: ' + error.message;
    }
    writeRoute(true);
    render();
  }
}
