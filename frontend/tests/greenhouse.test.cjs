const { test } = require('node:test');
const assert = require('node:assert/strict');

test('garden area threshold validation enforces min <= max for temperature, humidity, light', () => {
  function validateThresholds(payload) {
    if (payload.custom_min_temp != null && payload.custom_max_temp != null && payload.custom_min_temp > payload.custom_max_temp) {
      throw new Error('Nhiệt độ tối thiểu phải nhỏ hơn hoặc bằng nhiệt độ tối đa.');
    }
    if (payload.custom_min_humidity != null && payload.custom_max_humidity != null && payload.custom_min_humidity > payload.custom_max_humidity) {
      throw new Error('Độ ẩm tối thiểu phải nhỏ hơn hoặc bằng độ ẩm tối đa.');
    }
    if (payload.custom_min_light != null && payload.custom_max_light != null && payload.custom_min_light > payload.custom_max_light) {
      throw new Error('Ánh sáng tối thiểu phải nhỏ hơn hoặc bằng ánh sáng tối đa.');
    }
    return true;
  }

  // Valid payload
  assert.equal(validateThresholds({ custom_min_temp: 20, custom_max_temp: 32 }), true);

  // Invalid temp
  assert.throws(() => {
    validateThresholds({ custom_min_temp: 35, custom_max_temp: 25 });
  }, /Nhiệt độ tối thiểu/);

  // Invalid humidity
  assert.throws(() => {
    validateThresholds({ custom_min_humidity: 90, custom_max_humidity: 60 });
  }, /Độ ẩm tối thiểu/);

  // Invalid light
  assert.throws(() => {
    validateThresholds({ custom_min_light: 50000, custom_max_light: 10000 });
  }, /Ánh sáng tối thiểu/);
});

test('garden name and area_id sanitation', () => {
  function sanitizeGarden(values) {
    const name = (values.name || '').trim();
    const id = (values.greenhouse_id || '').trim();
    const area_sqm = values.area_sqm != null && String(values.area_sqm).trim() !== '' ? Number(values.area_sqm) : null;
    if (!name) throw new Error('Vui lòng nhập tên khu vườn.');
    if (!id) throw new Error('Vui lòng nhập mã khu vườn.');
    if (area_sqm !== null && (!Number.isFinite(area_sqm) || area_sqm <= 0)) {
      throw new Error('Diện tích phải là số lớn hơn 0.');
    }
    return { name, greenhouse_id: id, area_sqm };
  }

  const clean = sanitizeGarden({ name: '  Vườn ớt ngoài trời  ', greenhouse_id: '  GARDEN-01  ', area_sqm: ' 45.5 ' });
  assert.equal(clean.name, 'Vườn ớt ngoài trời');
  assert.equal(clean.greenhouse_id, 'GARDEN-01');
  assert.equal(clean.area_sqm, 45.5);

  assert.throws(() => sanitizeGarden({ name: '', greenhouse_id: 'G-01' }), /tên khu vườn/);
  assert.throws(() => sanitizeGarden({ name: 'Vườn', greenhouse_id: '' }), /mã khu vườn/);
  assert.throws(() => sanitizeGarden({ name: 'Vườn', greenhouse_id: 'G-01', area_sqm: '-5' }), /lớn hơn 0/);
});
