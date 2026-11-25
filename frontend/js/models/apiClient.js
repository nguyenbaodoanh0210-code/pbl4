/**
 * Frontend MVC — Model (API Client)
 * Handles authenticated REST requests against the FastAPI MVC backend.
 */

import { state, clearSession } from './store.js';

export async function apiRequest(path, opts = {}) {
  const isFormData = typeof FormData !== 'undefined' && opts.body instanceof FormData;
  const headers = {
    Accept: 'application/json',
    ...(!isFormData && opts.body ? { 'Content-Type': 'application/json' } : {}),
    ...(state.token ? { Authorization: 'Bearer ' + state.token } : {}),
    ...opts.headers,
  };
  const response = await fetch(path, { cache: 'no-store', ...opts, headers });
  if (!response.ok) {
    let message = 'API trả về lỗi ' + response.status;
    try {
      const json = await response.json();
      if (typeof json.detail === 'string') message = json.detail;
    } catch {
      // Ignore non-JSON error payloads
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

export async function loadWorkspaceData() {
  const [gardens, devices, recommendations, notifications, crops] = await Promise.all([
    apiRequest('/api/greenhouses'),
    apiRequest('/api/devices'),
    apiRequest('/api/recommendations?limit=100'),
    apiRequest('/api/notifications?limit=50').catch(() => []),
    apiRequest('/api/crops').catch(() => []),
  ]);

  state.greenhouses = Array.isArray(gardens) ? gardens : [];
  state.devices = Array.isArray(devices) ? devices : [];
  state.recommendations = Array.isArray(recommendations) ? recommendations : [];
  state.notifications = Array.isArray(notifications) ? notifications : [];
  state.crops = Array.isArray(crops) ? crops : [];

  if (!state.greenhouses.some((g) => g.greenhouse_id === state.greenhouseId)) {
    state.greenhouseId = state.greenhouses[0]?.greenhouse_id || '';
  }
  if (state.greenhouseId) {
    localStorage.setItem('ln-greenhouse', state.greenhouseId);
  }

  const sensorNodes = state.devices.filter(
    (d) => d.device_type === 'SENSOR_NODE' || d.device_type === 'SENSOR'
  );

  await Promise.all([
    ...sensorNodes.map(async (device) => {
      try {
        state.logs[device.device_id] = await apiRequest(
          '/api/sensors/' + encodeURIComponent(device.device_id) + '?limit=200'
        );
      } catch {
        state.logs[device.device_id] = [];
      }
    }),
    ...state.greenhouses.map(async (garden) => {
      try {
        state.areas[garden.greenhouse_id] = await apiRequest(
          '/api/greenhouses/' + encodeURIComponent(garden.greenhouse_id) + '/areas'
        );
      } catch {
        state.areas[garden.greenhouse_id] = [];
      }
      try {
        state.actuators[garden.greenhouse_id] = await apiRequest(
          '/api/greenhouses/' + encodeURIComponent(garden.greenhouse_id) + '/actuators'
        );
      } catch {
        state.actuators[garden.greenhouse_id] = { actuators: [], recent_logs: [] };
      }
    }),
  ]);
}

export async function refreshGardenActuators(gardenId) {
  if (!gardenId) return;
  state.actuators[gardenId] = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/actuators'
  );
}

export async function updatePumpControl(gardenId, payload) {
  const result = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/actuators/PUMP',
    { method: 'PUT', body: JSON.stringify(payload) }
  );
  await refreshGardenActuators(gardenId);
  return result;
}

// ─── Garden Area / Crop Thresholds CRUD (Stage 4C) ───────────────────────────

export async function refreshGardenAreas(gardenId) {
  if (!gardenId) return;
  state.areas[gardenId] = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/areas'
  );
  return state.areas[gardenId];
}

export async function createGardenArea(gardenId, payload) {
  const result = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/areas',
    { method: 'POST', body: JSON.stringify(payload) }
  );
  await refreshGardenAreas(gardenId);
  return result;
}

export async function updateGardenArea(gardenId, areaId, payload) {
  const result = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/areas/' + encodeURIComponent(areaId),
    { method: 'PUT', body: JSON.stringify(payload) }
  );
  await refreshGardenAreas(gardenId);
  return result;
}

export async function deleteGardenArea(gardenId, areaId) {
  const result = await apiRequest(
    '/api/greenhouses/' + encodeURIComponent(gardenId) + '/areas/' + encodeURIComponent(areaId),
    { method: 'DELETE' }
  );
  await refreshGardenAreas(gardenId);
  return result;
}

// ─── Camera / Diagnosis API ───────────────────────────────────────────────────

export async function loadCameraLogs(gardenId, limit = 30) {
  const qs = gardenId ? `?greenhouse_id=${encodeURIComponent(gardenId)}&limit=${limit}` : `?limit=${limit}`;
  return apiRequest('/api/camera/logs' + qs);
}

export async function uploadDiagnose(formData) {
  return apiRequest('/api/camera/diagnose', { method: 'POST', body: formData });
}

export async function triggerCapture(deviceId, areaId, greenhouseId = state.greenhouseId) {
  return apiRequest('/api/camera/capture-trigger', {
    method: 'POST',
    body: JSON.stringify({ greenhouse_id: greenhouseId, device_id: deviceId, area_id: areaId }),
  });
}

export async function patchCameraLogStatus(logId, status) {
  return apiRequest('/api/camera/logs/' + encodeURIComponent(logId) + '/status', {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function cameraImageUrl(logId) {
  const t = state.token;
  // Thêm &_v=logId để buộc trình duyệt tải lại đúng ảnh mới nhất (chống cache)
  const base = '/api/camera/logs/' + encodeURIComponent(logId) + '/image';
  const qs = t
    ? '?token=' + encodeURIComponent(t) + '&_v=' + encodeURIComponent(logId)
    : '?_v=' + encodeURIComponent(logId);
  return base + qs;
}

// ─── Auth Expiry ──────────────────────────────────────────────────────────────

export function handleAuthExpiry(error) {
  if (error?.status === 401 || error?.status === 403) {
    clearSession();
    state.profileMode = 'info';
    state.sessionError = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    state.error = '';
    state.authPage = 'login';
    return true;
  }
  return false;
}
