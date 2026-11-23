/**
 * Frontend MVC — Model (Store & Domain Selectors)
 * Holds application state and pure selectors for outdoor garden telemetry,
 * NodeMCU v2.0.0 sensors (DHT22 + LDR Light), and Pump actuator controls.
 */

export const OUTDOOR_METRICS = [
  ['temperature', 'Nhiệt độ không khí', '°C', 'temperature', 'Cảm biến nhiệt độ'],
  ['humidity', 'Độ ẩm không khí', '%', 'humidity', 'Cảm biến độ ẩm'],
  ['soil_moisture', 'Độ ẩm đất', '%', 'humidity', 'Cảm biến đất đã hiệu chuẩn'],
  ['light_level', 'Cường độ ánh sáng', 'Lux', 'light_level', 'Cảm biến ánh sáng'],
];

export const PERIODS = [
  ['hour', 'Giờ', 3600000],
  ['day', 'Ngày', 86400000],
  ['week', 'Tuần', 604800000],
  ['month', 'Tháng', 2592000000],
];

export const PAGES = {
  home: ['Tổng quan vườn', 'Giám sát môi trường & Tưới nước'],
  history: ['Lịch sử & Xu hướng', 'Biểu đồ theo dõi'],
  greenhouses: ['Khu vườn & Cây trồng', 'Quản lý khu vườn'],
  camera: ['Chẩn đoán sức khỏe cây', 'Nhận diện bệnh qua ảnh'],
  advice: ['Hướng dẫn chăm sóc', 'Lời khuyên cho cây'],
  alerts: ['Thông báo & Cảnh báo', 'Cảnh báo thời tiết & sâu bệnh'],
};

export const PAGE_DESCRIPTIONS = {
  home: 'Theo dõi nhiệt độ, độ ẩm, ánh sáng và điều khiển tưới nước tự động cho khu vườn ngoài trời.',
  history: 'Xem lại biểu đồ nhiệt độ, độ ẩm và ánh sáng theo từng khung giờ trong ngày.',
  greenhouses: 'Quản lý các luống trồng cây, ngưỡng thời tiết phù hợp và danh sách thiết bị trong vườn.',
  camera: 'Chụp ảnh lá cây trực tiếp qua camera để nhận diện sâu bệnh và nhận hướng dẫn điều trị.',
  advice: 'Lời khuyên chăm sóc và phác đồ điều trị cây trồng dựa trên thời tiết thực tế.',
  alerts: 'Cảnh báo khi độ ẩm quá cao, nguy cơ nấm bệnh hoặc thiết bị mất kết nối.',
};

export const state = {
  page: 'home',
  greenhouses: [],
  areas: {},
  devices: [],
  logs: {},
  actuators: {},
  recommendations: [],
  notifications: [],
  greenhouseId: localStorage.getItem('ln-greenhouse') || '',
  deviceId: '',
  metric: 'temperature',
  period: 'day',
  detailId: '',
  creatingGreenhouse: false,
  editingGreenhouse: false,
  creatingDevice: false,
  greenhouseSaving: false,
  deviceSaving: false,
  pumpBusy: false,
  pumpAreaId: '',
  pumpMessage: '',
  pumpError: '',
  greenhouseNotice: '',
  error: '',
  token: sessionStorage.getItem('ln-access-token') || '',
  user: null,
  profileMode: 'info',
  authPage: 'login',
  authError: '',
  authBusy: false,
  authValues: {},
  sessionError: '',
  // Camera / Diagnosis page state
  cameraLogs: [],
  cameraLogsLoading: false,
  cameraLogsError: '',
  diagnosisResult: null,
  diagnosisLoading: false,
  diagnosisError: '',
  cameraUploadProgress: '',
  cameraTriggerBusy: false,
  cameraTriggerMsg: '',
  esp32StreamUrl: localStorage.getItem('ln-esp32-stream') || '',
  esp32StreamMode: 'snapshot', // 'snapshot' | 'stream'
  isScanning: false,
  // Stage 4C: Crops & Area state
  crops: [],
  creatingArea: false,
  editingAreaId: '',
  areaSaving: false,
  areaError: '',
};

export function cropDetails(cropStageId) {
  return state.crops.find((c) => c.crop_stage_id === cropStageId) || null;
}

export function cropLabel(cropStageId) {
  const c = cropDetails(cropStageId);
  if (!c) return 'Chưa gán cây trồng';
  return c.crop_name + (c.stage_name ? ' (' + c.stage_name + ')' : '');
}

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]
  ));
}

export function fmt(value, decimals = 1) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: decimals }).format(Number(value));
}

export function formatDate(value) {
  if (!value) return 'Chưa có dữ liệu';
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Ho_Chi_Minh',
  }).format(new Date(value));
}

export function clearSession() {
  state.creatingGreenhouse = false;
  state.editingGreenhouse = false;
  state.creatingDevice = false;
  state.greenhouseSaving = false;
  state.deviceSaving = false;
  state.pumpBusy = false;
  state.pumpMessage = '';
  state.pumpError = '';
  state.greenhouseNotice = '';
  state.token = '';
  state.user = null;
  state.greenhouses = [];
  state.areas = {};
  state.devices = [];
  state.logs = {};
  state.actuators = {};
  state.recommendations = [];
  state.notifications = [];
  state.greenhouseId = '';
  state.deviceId = '';
  state.detailId = '';
  sessionStorage.removeItem('ln-access-token');
  localStorage.removeItem('ln-greenhouse');
}

export function currentGarden() {
  return state.greenhouses.find((item) => item.greenhouse_id === state.greenhouseId)
    || state.greenhouses[0]
    || null;
}

export function gardenDevices(gardenId = currentGarden()?.greenhouse_id) {
  if (!gardenId) return [];
  return state.devices.filter((item) => item.greenhouse_id === gardenId);
}

export function gardenSensorDevices(gardenId = currentGarden()?.greenhouse_id) {
  const all = gardenDevices(gardenId);
  const sensors = all.filter((item) => item.device_type === 'SENSOR_NODE');
  return sensors.length ? sensors : all;
}

export function activeSensorDevice() {
  const list = gardenSensorDevices();
  return list.find((item) => item.device_id === state.deviceId) || list[0] || null;
}

export function latestReading(deviceId) {
  return state.logs[deviceId]?.[0] || null;
}

export function currentGardenAreas(gardenId = currentGarden()?.greenhouse_id) {
  return gardenId ? (state.areas[gardenId] || []) : [];
}

export function areaForDevice(device) {
  if (!device?.area_id) return null;
  return currentGardenAreas(device.greenhouse_id).find((a) => a.area_id === device.area_id) || null;
}

export function currentPumpData(gardenId = currentGarden()?.greenhouse_id) {
  if (!gardenId) return { pump: null, logs: [] };
  const payload = state.actuators[gardenId];
  const pump = payload?.actuators?.find((a) => a.actuator_type === 'PUMP' && (a.area_id || '') === state.pumpAreaId) || null;
  return { pump, logs: (payload?.recent_logs || []).filter(l => l.actuator_id === pump?.actuator_id) };
}

export function getPeriodLogs(device = activeSensorDevice()) {
  if (!device) return [];
  const all = (state.logs[device.device_id] || []).slice();
  if (!all.length) return [];
  const periodDef = PERIODS.find((p) => p[0] === state.period) || PERIODS[1];
  const span = periodDef[2];
  const newestTs = Math.max(Date.now(), Date.parse(all[0].timestamp) || 0);
  const cutoff = newestTs - span;
  const filtered = all.filter((item) => Date.parse(item.timestamp) >= cutoff);
  return filtered.sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
}

export function evaluateMetricStatus(metricKey, value, thresholds) {
  if (value == null || !Number.isFinite(Number(value))) {
    return { level: 'neutral', label: 'Chưa có số đo' };
  }
  const num = Number(value);
  const t = thresholds || {};
  if (metricKey === 'soil_moisture') {
    return { level: 'neutral', label: 'Ngưỡng tưới theo cấu hình từng khu' };
  }
  if (metricKey === 'temperature') {
    const minT = t.min_temp ?? 20;
    const maxT = t.max_temp ?? 33;
    if (num > maxT) return { level: 'danger', label: `Cao (> ${fmt(maxT, 0)}°C)` };
    if (num < minT) return { level: 'warning', label: `Thấp (< ${fmt(minT, 0)}°C)` };
    return { level: 'ok', label: `Tối ưu (${fmt(minT, 0)}–${fmt(maxT, 0)}°C)` };
  }
  if (metricKey === 'humidity') {
    const fungal = t.fungal_humidity_threshold ?? 85;
    const minH = t.min_humidity ?? 55;
    if (num >= fungal) return { level: 'danger', label: `Ẩm cao ≥ ${fmt(fungal, 0)}% · Nguy cơ nấm` };
    if (num < minH) return { level: 'warning', label: `Khô (< ${fmt(minH, 0)}%)` };
    return { level: 'ok', label: `Ổn định (${fmt(minH, 0)}–${fmt(fungal, 0)}%)` };
  }
  if (metricKey === 'light_level') {
    const minL = t.fungal_light_threshold ?? t.min_light ?? 8000;
    const maxL = t.max_light ?? 60000;
    if (num < minL) return { level: 'warning', label: `Ánh sáng yếu (< ${fmt(minL, 0)} Lux)` };
    if (num > maxL) return { level: 'warning', label: `Nắng gắt (> ${fmt(maxL, 0)} Lux)` };
    return { level: 'ok', label: 'Ánh sáng phù hợp' };
  }
  return { level: 'ok', label: 'Ổn định' };
}
