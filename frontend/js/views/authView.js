/**
 * Frontend MVC — Auth & User Profile Views
 */

import { esc, state } from '../models/store.js';

export function eyeIcon(visible) {
  return visible
    ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A11.5 11.5 0 0 1 12 5c5.5 0 9 7 9 7a14 14 0 0 1-3 3.8M6.2 6.2C3.8 7.8 2 12 2 12s3.5 7 10 7a10 10 0 0 0 4-.8"/></svg>'
    : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
}

function passwordField(name, label, autocomplete, minLength = 0) {
  const length = minLength ? `minlength="${minLength}" maxlength="128"` : '';
  return `<label>${label}<span class="password-field"><input type="password" name="${name}" autocomplete="${autocomplete}" ${length} required><button type="button" class="password-toggle" data-password-toggle aria-label="Hiện mật khẩu" aria-pressed="false">${eyeIcon(false)}</button></span></label>`;
}

export function renderUserPanelMarkup() {
  if (state.profileMode === 'login' || state.profileMode === 'register') {
    const isRegister = state.profileMode === 'register';
    const values = state.authValues;
    const errorMarkup = state.authError ? `<p class="auth-message" role="alert">${esc(state.authError)}</p>` : '';
    const passwordFields =
      passwordField('password', 'Mật khẩu', isRegister ? 'new-password' : 'current-password', isRegister ? 12 : 0) +
      (isRegister ? passwordField('password_confirm', 'Xác nhận mật khẩu', 'new-password', 12) : '');
    return (
      `<div class="auth-panel-title"><button class="panel-back" type="button" data-profile-mode="info" aria-label="Quay lại"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg></button><strong>${isRegister ? 'Đăng ký' : 'Đăng nhập'}</strong></div>` +
      `<form class="auth-form" data-auth-form="${state.profileMode}">` +
      (isRegister ? `<label>Họ và tên<input type="text" name="full_name" maxlength="100" autocomplete="name" required value="${esc(values.full_name || '')}"></label>` : '') +
      `<label>Email<input type="email" name="email" maxlength="254" autocomplete="email" required value="${esc(values.email || '')}"></label>` +
      (isRegister ? `<label>Số điện thoại <small>(không bắt buộc)</small><input type="tel" name="phone_number" maxlength="40" autocomplete="tel" value="${esc(values.phone_number || '')}"></label>` : '') +
      passwordFields +
      (!isRegister ? '<button class="forgot-link" type="button" data-profile-mode="forgot">Quên mật khẩu?</button>' : '') +
      errorMarkup +
      `<button class="primary-button" type="submit" ${state.authBusy ? 'disabled' : ''}>${state.authBusy ? 'Đang xử lý…' : isRegister ? 'Tạo tài khoản' : 'Đăng nhập'}</button></form>` +
      `<p class="auth-switch">${isRegister ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'} <button type="button" data-profile-mode="${isRegister ? 'login' : 'register'}">${isRegister ? 'Đăng nhập' : 'Đăng ký'}</button></p>`
    );
  }
  if (state.profileMode === 'forgot') {
    return (
      '<div class="auth-panel-title"><button class="panel-back" type="button" data-profile-mode="login" aria-label="Quay lại đăng nhập"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7"/></svg></button><strong>Quên mật khẩu</strong></div>' +
      `<label class="auth-email-label">Email<input type="email" autocomplete="email" value="${esc(state.authValues.email || '')}" required></label>` +
      '<p class="auth-info">API hiện chưa có chức năng gửi liên kết đặt lại mật khẩu. Vui lòng liên hệ quản trị viên để được hỗ trợ.</p>' +
      '<button class="secondary-button" type="button" disabled>Khôi phục mật khẩu chưa khả dụng</button>'
    );
  }
  if (!state.user) {
    return (
      '<strong class="user-panel-heading">Thông tin cá nhân</strong>' +
      '<div class="auth-required"><b>Yêu cầu đăng nhập</b><p>' + esc(state.sessionError || 'Cần đăng nhập để truy cập tài nguyên này.') + '</p></div>' +
      '<button class="primary-button" type="button" data-profile-mode="login">Đăng nhập</button>'
    );
  }
  const user = state.user;
  const initials = (user.full_name || '?')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0])
    .join('')
    .toLocaleUpperCase('vi-VN');
  return (
    '<strong class="user-panel-heading">Thông tin cá nhân</strong>' +
    '<div class="user-panel-person"><span class="user-panel-avatar" aria-hidden="true">' + esc(initials) + '</span><span><b>' + esc(user.full_name || 'Người dùng') + '</b><small>' + esc(user.email || 'Chưa có email') + '</small></span></div>' +
    (user.phone_number ? '<p class="user-panel-note">Số điện thoại: ' + esc(user.phone_number) + '</p>' : '') +
    '<button class="link-button auth-logout" type="button" data-auth-logout>Đăng xuất</button>'
  );
}

function authLayout(content) {
  const isRegister = state.authPage === 'register';
  const isForgot = state.authPage === 'forgot';
  const title = isForgot ? 'Tìm lại kết nối.' : isRegister ? 'Đăng ký' : 'Đăng nhập';
  const description = isForgot
    ? 'Trở lại với khu vườn ngoài trời và những thông số bạn đang theo dõi.'
    : isRegister
      ? 'Bắt đầu theo dõi môi trường, tưới nước tự động và nhận diện sức khỏe cây trồng.'
      : 'Theo dõi thời gian thực nhiệt độ, độ ẩm, ánh sáng và điều khiển bơm nước cho khu vườn của bạn.';
  return `<div class="auth-hero"><div class="auth-hero-copy"><h1>${title}</h1><p class="auth-hero-description">${description}</p></div><div class="auth-hero-footer"><span>Chăm vườn, an tâm.</span><a href="https://unsplash.com/photos/a-greenhouse-filled-with-lots-of-potted-plants-uSgwNO-_v2I" target="_blank" rel="noopener noreferrer">Ảnh vườn cây / Unsplash ↗</a></div></div><div class="auth-phone"><div class="auth-card">${content}</div></div>`;
}

export function renderAuthScreenMarkup() {
  const isRegister = state.authPage === 'register';
  const message = state.authError || state.sessionError;
  const errorMarkup = message ? `<p class="auth-message" role="alert">${esc(message)}</p>` : '';
  if (state.authPage === 'forgot') {
    return authLayout(
      `<span class="auth-card-kicker">TÀI KHOẢN</span><h2>Khôi phục mật khẩu</h2><p class="auth-description">Nhập email tài khoản để bắt đầu khôi phục.</p><label class="auth-email-label">Email *<input type="email" name="email" autocomplete="email" value="${esc(state.authValues.email || '')}" required></label><p class="auth-info">API hiện chưa có chức năng gửi liên kết đặt lại mật khẩu. Vui lòng liên hệ quản trị viên để được hỗ trợ.</p><button class="primary-button" type="button" disabled>Khôi phục mật khẩu chưa khả dụng</button><p class="auth-switch"><button type="button" data-auth-page="login">← Quay lại đăng nhập</button></p>`
    );
  }
  const passwordFields =
    passwordField('password', 'Mật khẩu *', isRegister ? 'new-password' : 'current-password', isRegister ? 12 : 0) +
    (isRegister ? passwordField('password_confirm', 'Xác nhận mật khẩu *', 'new-password', 12) : '');
  return authLayout(
    `<span class="auth-card-kicker">KHU VƯỜN NGOÀI TRỜI</span><h2>${isRegister ? 'Tạo một khởi đầu xanh.' : 'Chào mừng trở lại.'}</h2><p class="auth-description">${isRegister ? 'Tạo tài khoản để quản lý khu vườn ớt và xà lách của bạn.' : 'Đăng nhập để giám sát môi trường và điều khiển bơm nước.'}</p><p class="auth-required-hint">Dấu * là thông tin bắt buộc.</p><form class="auth-form auth-page-form" data-auth-form="${state.authPage}">` +
      (isRegister ? `<label>Họ và tên *<input type="text" name="full_name" maxlength="100" autocomplete="name" required value="${esc(state.authValues.full_name || '')}"></label>` : '') +
      `<label>Email *<input type="email" name="email" maxlength="254" autocomplete="email" required value="${esc(state.authValues.email || '')}"></label>` +
      passwordFields +
      (!isRegister ? '<button class="forgot-link" type="button" data-auth-page="forgot">Quên mật khẩu?</button>' : '') +
      errorMarkup +
      `<button class="primary-button auth-submit" type="submit" ${state.authBusy ? 'disabled' : ''}>${state.authBusy ? 'Đang xử lý…' : isRegister ? 'Tạo tài khoản' : 'Đăng nhập'}</button></form>` +
      `<p class="auth-switch">${isRegister ? 'Bạn đã có tài khoản?' : 'Bạn chưa có tài khoản?'} <button type="button" data-auth-page="${isRegister ? 'login' : 'register'}">${isRegister ? 'Đăng nhập →' : 'Đăng ký →'}</button></p>`
  );
}
