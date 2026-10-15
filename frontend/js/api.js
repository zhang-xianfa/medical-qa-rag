/* ═══════════════════════════════════════════════════════════════
   灵兰 API Client — 封装后端接口调用
   ═══════════════════════════════════════════════════════════════ */

const API_BASE = '/api/v1';

const api = {
  _token: null,

  setToken(token) { this._token = token; },
  getToken() { return this._token; },
  clearToken() { this._token = null; },

  async _fetch(method, path, body = null, signal = null) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (this._token) opts.headers['Authorization'] = `Bearer ${this._token}`;
    if (body) opts.body = JSON.stringify(body);
    if (signal) opts.signal = signal;
    const res = await fetch(`${API_BASE}${path}`, opts);
    const data = res.status === 204 ? null : await res.json().catch(() => ({}));
    if (!res.ok) throw { status: res.status, ...data };
    return data;
  },

  // ── Auth ──────────────────────────
  register(phone, password, nickname) {
    return this._fetch('POST', '/auth/register', { phone, password, nickname });
  },
  login(phone, password) {
    return this._fetch('POST', '/auth/login', { phone, password });
  },

  // ── Profile ────────────────────────
  getProfile() { return this._fetch('GET', '/profile'); },
  updateProfile(data) { return this._fetch('PATCH', '/profile', data); },

  // ── Sessions ───────────────────────
  createSession() { return this._fetch('POST', '/sessions'); },
  listSessions(status, limit = 50) {
    const params = new URLSearchParams({ limit });
    if (status) params.set('status', status);
    return this._fetch('GET', `/sessions?${params}`);
  },
  getSession(id) { return this._fetch('GET', `/sessions/${id}`); },
  deleteSession(id) { return this._fetch('DELETE', `/sessions/${id}`); },

  // ── Messages ───────────────────────
  sendMessage(sessionId, content, contentType = 'text', signal = null) {
    return this._fetch('POST', `/sessions/${sessionId}/messages`, { content, content_type: contentType }, signal);
  },
  listMessages(sessionId, limit = 200) {
    return this._fetch('GET', `/sessions/${sessionId}/messages?limit=${limit}`);
  },

  // ── Health ─────────────────────────
  health() { return this._fetch('GET', '/health'); },
};
