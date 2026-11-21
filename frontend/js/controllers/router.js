/**
 * Frontend MVC — Controller (URL Router)
 * Synchronizes UI state with browser history & query parameters.
 */

import { OUTDOOR_METRICS, PAGES, PERIODS, state } from '../models/store.js';

export const ROUTE_FIELDS = [
  'page',
  'detailId',
  'creatingGreenhouse',
  'editingGreenhouse',
  'creatingDevice',
  'greenhouseId',
  'deviceId',
  'metric',
  'period',
  'authPage',
];

export function routeSnapshot() {
  return Object.fromEntries(ROUTE_FIELDS.map((key) => [key, state[key]]));
}

export function readRoute() {
  const query = new URLSearchParams(location.search);
  return {
    page: query.get('page') || 'home',
    detailId: query.get('detail') || '',
    creatingGreenhouse: query.get('create') === '1',
    editingGreenhouse: query.get('edit') === '1',
    creatingDevice: query.get('create_device') === '1',
    greenhouseId: query.get('gh') || '',
    deviceId: query.get('device') || '',
    metric: query.get('metric') || 'temperature',
    period: query.get('period') || 'day',
    authPage: query.get('auth') || 'login',
  };
}

export function applyRoute(route) {
  const page = Object.hasOwn(PAGES, route.page) ? route.page : 'home';
  state.page = page;
  state.detailId =
    page === 'greenhouses' && state.greenhouses.some((h) => h.greenhouse_id === route.detailId)
      ? route.detailId
      : '';
  state.creatingGreenhouse = page === 'greenhouses' && Boolean(route.creatingGreenhouse);
  state.editingGreenhouse =
    page === 'greenhouses' && Boolean(state.detailId) && Boolean(route.editingGreenhouse);
  state.creatingDevice =
    page === 'greenhouses' && Boolean(state.detailId) && Boolean(route.creatingDevice);
  state.greenhouseId = state.greenhouses.some((h) => h.greenhouse_id === route.greenhouseId)
    ? route.greenhouseId
    : state.greenhouses[0]?.greenhouse_id || '';
  state.deviceId = state.devices.some(
    (d) => d.device_id === route.deviceId && d.greenhouse_id === state.greenhouseId
  )
    ? route.deviceId
    : '';
  state.metric = OUTDOOR_METRICS.some((m) => m[0] === route.metric)
    ? route.metric
    : 'temperature';
  state.period = PERIODS.some((p) => p[0] === route.period) ? route.period : 'day';
  state.authPage = ['login', 'register', 'forgot'].includes(route.authPage)
    ? route.authPage
    : 'login';
  if (state.detailId) state.greenhouseId = state.detailId;
}

export function routeUrl(route = routeSnapshot()) {
  const url = new URL(location.href);
  const query = new URLSearchParams();
  if (!state.user) {
    if (route.authPage !== 'login') query.set('auth', route.authPage);
  } else {
    if (route.page !== 'home') query.set('page', route.page);
    if (route.detailId) query.set('detail', route.detailId);
    if (route.creatingGreenhouse) query.set('create', '1');
    if (route.editingGreenhouse) query.set('edit', '1');
    if (route.creatingDevice) query.set('create_device', '1');
    if (route.greenhouseId) query.set('gh', route.greenhouseId);
    if (route.deviceId) query.set('device', route.deviceId);
    if (route.metric !== 'temperature') query.set('metric', route.metric);
    if (route.period !== 'day') query.set('period', route.period);
  }
  url.search = query.toString();
  return url.pathname + url.search + url.hash;
}

export function writeRoute(replace = false) {
  const route = routeSnapshot();
  const url = routeUrl(route);
  const current = location.pathname + location.search + location.hash;
  const method = replace || url === current ? 'replaceState' : 'pushState';
  window.history[method]({ greenhouseRoute: route }, '', url);
}
