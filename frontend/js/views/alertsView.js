/**
 * Frontend MVC — Advice & Alerts Views
 */

import { currentGarden, esc, formatDate, gardenDevices, latestReading, state } from '../models/store.js';
import { gardenPicker, pill } from './components.js';

export function renderAdviceView() {
  const ids = new Set(gardenDevices().map((x) => x.device_id));
  const areaIds = new Set((state.areas[currentGarden()?.greenhouse_id] || []).map((a) => a.area_id));
  const rows = state.recommendations.filter((x) => ids.has(x.device_id) || areaIds.has(x.area_id));
  return (
    '<div class="page-toolbar"><div class="garden-picker">' + gardenPicker() + '</div>' +
    '<div class="toolbar-note"><div class="banner">Lời khuyên chăm sóc cây dựa trên thời tiết thực tế và tình trạng sức khỏe lá cây.</div></div></div>' +
    '<div class="section-heading"><h2>Cần xem xét</h2><span>' + rows.length + ' gợi ý</span></div>' +
    '<div class="recommendation-grid">' +
    (rows.length
      ? rows
          .map(
            (r) =>
              '<article class="card recommendation-card">' +
              '<div class="tag">' + esc(r.source_type === 'MULTIMODAL' ? 'CHẨN ĐOÁN HÌNH ẢNH & THỜI TIẾT' : 'DỮ LIỆU THỜI TIẾT') + '</div>' +
              '<p>' + pill(r.status === 'PENDING' ? 'Chưa xác nhận' : r.status, r.status === 'PENDING' ? 'pending' : '') + '</p>' +
              '<h3>' + esc(r.condition_diagnosis || 'Khuyến nghị') + '</h3>' +
              '<div class="tiny">' + esc(r.device_id || 'Khu vườn') + ' · ' + formatDate(r.created_at) + '</div>' +
              '<p>' + esc(r.fertilizer_action || 'Chưa có hướng dẫn xử lý.') + '</p>' +
              (r.status === 'PENDING'
                ? '<button type="button" class="secondary-button" data-apply="' + esc(r.rec_id) + '">Đánh dấu đã áp dụng</button>'
                : '') +
              '</article>'
          )
          .join('')
      : '<div class="card empty empty-state">Chưa có khuyến nghị nào cho khu vườn này.</div>') +
    '</div>'
  );
}

export function renderAlertsView() {
  const ghId = currentGarden()?.greenhouse_id;
  const apiAlerts = state.notifications.filter((n) => !ghId || n.greenhouse_id === ghId);
  const offlineItems = gardenDevices()
    .filter((d) => !d.is_online)
    .map((d) => {
      const l = latestReading(d.device_id);
      return {
        severity: 'CRITICAL',
        title: d.device_id + ' chưa trực tuyến',
        message: l ? 'Bản ghi gần nhất ' + formatDate(l.timestamp) + '.' : 'Chưa có dữ liệu cảm biến.',
        created_at: l?.timestamp || d.last_updated,
      };
    });

  const allItems = [...apiAlerts, ...offlineItems];
  return (
    '<div class="page-toolbar"><div class="garden-picker">' + gardenPicker() + '</div>' +
    '<div class="toolbar-note"><div class="banner">Thông báo về nguy cơ nấm bệnh, điều kiện thời tiết bất thường và kết nối thiết bị.</div></div></div>' +
    '<div class="section-heading"><h2>Thông báo hiện tại</h2><span>' + allItems.length + ' mục</span></div>' +
    '<div class="notification-list">' +
    (allItems.length
      ? allItems
          .map((item) => {
            const sev = item.severity === 'CRITICAL' ? 'danger' : item.severity === 'WARNING' ? 'warning' : '';
            const pillType = item.severity === 'CRITICAL' ? 'error' : item.severity === 'WARNING' ? 'pending' : '';
            const pillLabel = item.severity === 'CRITICAL' ? 'Khẩn cấp' : item.severity === 'WARNING' ? 'Cảnh báo' : 'Thông tin';
            return (
              '<article class="card notification-card ' + sev + '">' +
              pill(pillLabel, pillType) +
              '<h3>' + esc(item.title) + '</h3>' +
              '<p class="tiny">' + esc(item.message) + ' · ' + formatDate(item.created_at) + '</p>' +
              '</article>'
            );
          })
          .join('')
      : '<div class="card empty empty-state">Chưa có cảnh báo nào cho khu vườn này.</div>') +
    '</div>'
  );
}
