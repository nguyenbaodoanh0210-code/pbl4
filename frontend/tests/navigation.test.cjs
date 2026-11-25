const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Strip ES module imports/exports for VM sandbox execution
const routerSource = fs
  .readFileSync(path.join(__dirname, '../js/controllers/router.js'), 'utf8')
  .replace(/import\s*\{[^}]*\}\s*from\s*['"][^'"]*['"];?/g, '')
  .replace(/export\s+(const|function)\s+/g, '$1 ');

function setup(initial = '/') {
  const PAGES = {
    home: ['Giám sát môi trường', 'Environment Dashboard'],
    history: ['Biểu đồ & Lịch sử', 'Analytics ngoài trời'],
    greenhouses: ['Khu vườn của bạn', 'Quản lý khu vườn'],
    camera: ['Chẩn đoán AI', 'Camera & Đa phương thức'],
    advice: ['Gợi ý chăm sóc', 'Khuyến nghị'],
    alerts: ['Thông báo', 'Theo dõi cảnh báo'],
  };
  const OUTDOOR_METRICS = [
    ['temperature', 'Nhiệt độ không khí', '°C'],
    ['humidity', 'Độ ẩm không khí', '%'],
    ['light_level', 'Cường độ ánh sáng', 'Lux'],
  ];
  const PERIODS = [
    ['hour', 'Giờ'],
    ['day', 'Ngày'],
    ['week', 'Tuần'],
    ['month', 'Tháng'],
  ];

  const state = {
    user: { user_id: 'test-user', full_name: 'Người dùng Test' },
    page: 'home',
    greenhouses: [{ greenhouse_id: 'garden-outdoor-01', name: 'Khu vườn ngoài trời' }],
    areas: { 'garden-outdoor-01': [{ area_id: 'area-chili-01', name: 'Luống ớt' }] },
    devices: [{ greenhouse_id: 'garden-outdoor-01', device_id: 'NODEMCU-01' }],
    greenhouseId: 'garden-outdoor-01',
    deviceId: '',
    detailId: '',
    creatingGreenhouse: false,
    editingGreenhouse: false,
    creatingDevice: false,
    creatingArea: false,
    editingAreaId: '',
    metric: 'temperature',
    period: 'day',
    authPage: 'login',
  };

  const location = new URL('http://local.test' + initial);
  const stack = [location.pathname + location.search];
  const entries = [null];
  let index = 0;
  const listeners = {};

  const history = {
    pushState(value, unused, url) {
      stack.splice(++index);
      entries.splice(index);
      stack.push(url);
      entries.push(value);
      location.href = 'http://local.test' + url;
    },
    replaceState(value, unused, url) {
      stack[index] = url;
      entries[index] = value;
      location.href = 'http://local.test' + url;
    },
  };

  const context = vm.createContext({
    state,
    PAGES,
    OUTDOOR_METRICS,
    PERIODS,
    location,
    window: { history, scrollTo() {}, addEventListener: (n, fn) => (listeners[n] = fn) },
    URL,
    URLSearchParams,
    Object,
  });

  vm.runInContext(routerSource, context);

  function navigateRoute(update, { replace = false } = {}) {
    update();
    context.writeRoute(replace);
  }

  return {
    state,
    location,
    stack,
    entries,
    context,
    navigateRoute,
    back() {
      if (index > 0) {
        index--;
        location.href = 'http://local.test' + stack[index];
        if (listeners.popstate) listeners.popstate({ state: entries[index] });
      }
    },
    forward() {
      if (index < stack.length - 1) {
        index++;
        location.href = 'http://local.test' + stack[index];
        if (listeners.popstate) listeners.popstate({ state: entries[index] });
      }
    },
  };
}

test('navigation to camera AI page creates reversible URL and history entry (Stage 4B)', () => {
  const f = setup();
  f.context.writeRoute(true);
  assert.equal(f.location.search, '?gh=garden-outdoor-01');

  f.navigateRoute(() => {
    f.state.page = 'camera';
  });
  assert.match(f.location.search, /page=camera/);
  assert.equal(f.state.page, 'camera');

  f.navigateRoute(() => {
    f.state.page = 'home';
  });
  assert.equal(f.location.search, '?gh=garden-outdoor-01');
});

test('navigation to garden detail and area creation preserves context (Stage 4C)', () => {
  const f = setup();
  f.context.writeRoute(true);

  f.navigateRoute(() => {
    f.state.page = 'greenhouses';
    f.state.detailId = 'garden-outdoor-01';
  });
  assert.match(f.location.search, /page=greenhouses/);
  assert.match(f.location.search, /detail=garden-outdoor-01/);

  f.navigateRoute(() => {
    f.state.creatingGreenhouse = true;
  });
  assert.match(f.location.search, /create=1/);
});

test('outdoor metrics selection syncs with URL parameters', () => {
  const f = setup();
  f.context.writeRoute(true);

  f.navigateRoute(() => {
    f.state.page = 'history';
    f.state.metric = 'humidity';
    f.state.period = 'week';
  });
  assert.match(f.location.search, /metric=humidity/);
  assert.match(f.location.search, /period=week/);
});

test('unauthenticated user is restricted to auth query parameters', () => {
  const f = setup();
  f.state.user = null;
  f.context.writeRoute(true);

  f.navigateRoute(() => {
    f.state.authPage = 'register';
  });
  assert.equal(f.location.search, '?auth=register');

  f.navigateRoute(() => {
    f.state.authPage = 'forgot';
  });
  assert.equal(f.location.search, '?auth=forgot');
});

test('deep link restores camera page and garden selection on load', () => {
  const f = setup('/?page=camera&gh=garden-outdoor-01');
  const route = f.context.readRoute();
  f.context.applyRoute(route);

  assert.equal(f.state.page, 'camera');
  assert.equal(f.state.greenhouseId, 'garden-outdoor-01');
});
