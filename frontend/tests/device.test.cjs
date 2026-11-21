const { test } = require('node:test');
const assert = require('node:assert/strict');

test('device payload validates hardware types and enforces PUMP-only actuator', () => {
  const VALID_DEVICE_TYPES = ['SENSOR_NODE', 'CAMERA_NODE', 'CAMERA', 'ACTUATOR'];
  const VALID_ACTUATOR_TYPES = ['PUMP']; // No FAN allowed

  function validateDevice(payload) {
    if (!payload.device_id || !payload.device_id.trim()) {
      throw new Error('Vui lòng nhập mã thiết bị.');
    }
    if (!VALID_DEVICE_TYPES.includes(payload.device_type)) {
      throw new Error('Loại thiết bị không hợp lệ.');
    }
    if (payload.device_type === 'ACTUATOR' && payload.actuator_type && !VALID_ACTUATOR_TYPES.includes(payload.actuator_type)) {
      throw new Error('Chỉ hỗ trợ bộ điều khiển Bơm nước (PUMP), không hỗ trợ quạt gió.');
    }
    return true;
  }

  // NodeMCU sensor node
  assert.equal(validateDevice({ device_id: 'NODEMCU-01', device_type: 'SENSOR_NODE' }), true);

  // ESP32-CAM camera node
  assert.equal(validateDevice({ device_id: 'ESP32-CAM-01', device_type: 'CAMERA_NODE' }), true);

  // Water pump actuator
  assert.equal(validateDevice({ device_id: 'ACT-PUMP-01', device_type: 'ACTUATOR', actuator_type: 'PUMP' }), true);

  // Rejected FAN
  assert.throws(() => {
    validateDevice({ device_id: 'ACT-FAN-01', device_type: 'ACTUATOR', actuator_type: 'FAN' });
  }, /không hỗ trợ quạt gió/);

  // Rejected empty device_id
  assert.throws(() => {
    validateDevice({ device_id: '  ', device_type: 'SENSOR_NODE' });
  }, /mã thiết bị/);
});

test('pump control mode handles AUTO vs MANUAL correctly', () => {
  function preparePumpPayload(currentMode, action) {
    if (action.mode) {
      return { control_mode: action.mode };
    }
    if (action.toggle === 'on' || action.toggle === 'off') {
      return { control_mode: 'MANUAL', is_on: action.toggle === 'on' };
    }
    throw new Error('Hành động điều khiển không hợp lệ');
  }

  // Switching to AUTO
  assert.deepEqual(preparePumpPayload('MANUAL', { mode: 'AUTO' }), { control_mode: 'AUTO' });

  // Turning pump ON in manual mode
  assert.deepEqual(preparePumpPayload('MANUAL', { toggle: 'on' }), { control_mode: 'MANUAL', is_on: true });

  // Turning pump OFF
  assert.deepEqual(preparePumpPayload('MANUAL', { toggle: 'off' }), { control_mode: 'MANUAL', is_on: false });
});
