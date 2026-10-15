/* ═══════════════════════════════════════════════════════════════
   灵兰 · App — 登录、注册、聊天、会话管理
   ═══════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────
let currentSessionId = null;
let sessions = [];
let activeAbortController = null;   // 正在进行的请求的 AbortController
let activeRequestSessionId = null;  // 正在进行的请求所属的会话 ID
let isProcessing = false;           // AI 思考中时锁定全部交互

// ── Init ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (api.getToken()) {
    showApp();
    loadSessions();
  }
});

// ═══════════════════════════════════════════════════════════════
// Auth
// ═══════════════════════════════════════════════════════════════
function setupAuth() {
  const tabLogin = document.getElementById('tabLogin');
  const tabRegister = document.getElementById('tabRegister');
  const formLogin = document.getElementById('formLogin');
  const formRegister = document.getElementById('formRegister');
  const errEl = document.getElementById('authError');

  tabLogin.addEventListener('click', () => {
    tabLogin.classList.add('active'); tabRegister.classList.remove('active');
    formLogin.classList.remove('hidden'); formRegister.classList.add('hidden');
    errEl.textContent = '';
  });
  tabRegister.addEventListener('click', () => {
    tabRegister.classList.add('active'); tabLogin.classList.remove('active');
    formRegister.classList.remove('hidden'); formLogin.classList.add('hidden');
    errEl.textContent = '';
  });

  document.getElementById('btnLogin').addEventListener('click', async () => {
    const phone = document.getElementById('loginPhone').value.trim();
    const pw = document.getElementById('loginPw').value;
    errEl.textContent = '';
    if (!phone || !pw) { errEl.textContent = '请填写手机号和密码'; return; }
    try {
      const res = await api.login(phone, pw);
      api.setToken(res.access_token);
      showApp(); loadSessions();
    } catch (e) { errEl.textContent = e.detail || '手机号或密码错误'; }
  });

  document.getElementById('btnRegister').addEventListener('click', async () => {
    const phone = document.getElementById('regPhone').value.trim();
    const pw = document.getElementById('regPw').value;
    const nick = document.getElementById('regNick').value.trim();
    errEl.textContent = '';
    if (!phone || !pw || !nick) { errEl.textContent = '请填写所有字段'; return; }
    try {
      const res = await api.register(phone, pw, nick);
      api.setToken(res.access_token);
      showApp(); loadSessions();
    } catch (e) { errEl.textContent = e.detail || '注册失败，请重试'; }
  });
}
setupAuth();

function showApp() {
  document.getElementById('authPage').classList.add('hidden');
  document.getElementById('appPage').classList.remove('hidden');
  loadProfile();
}

// ═══════════════════════════════════════════════════════════════
// Sessions
// ═══════════════════════════════════════════════════════════════
async function loadSessions() {
  try {
    const res = await api.listSessions();
    // 防御：过滤掉 session_id 无效的条目
    sessions = (res.data || []).filter(s => s.session_id && s.session_id !== 'undefined' && s.session_id !== 'null');
    renderSessions();
  } catch (e) { console.error('loadSessions:', e); }
}

function renderSessions() {
  const el = document.getElementById('sessionList');
  // 防御：过滤掉 session_id 无效的会话（防止 undefined/null 污染侧边栏）
  const validSessions = sessions.filter(s => s.session_id && s.session_id !== 'undefined' && s.session_id !== 'null');
  el.innerHTML = validSessions.map(s => `
    <div class="sidebar-session${s.session_id === currentSessionId ? ' active' : ''}" data-sid="${s.session_id}">
      <span class="indicator"></span>
      <div class="info">
        <div class="title">${s.title || '新会话'}</div>
        <div class="meta">${fmtDate(s.updated_at)} · 第${s.round_count || 0}轮</div>
      </div>
      <button class="btn-del" data-del="${s.session_id}" title="删除">×</button>
    </div>
  `).join('');

  // Click: select session
  el.querySelectorAll('.sidebar-session').forEach(div => {
    div.addEventListener('click', e => {
      if (e.target.classList.contains('btn-del')) return;
      selectSession(div.dataset.sid);
    });
  });
  // Delete button
  el.querySelectorAll('.btn-del').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      if (isProcessing) return;  // AI 思考中，禁止删除
      await api.deleteSession(btn.dataset.del);
      if (currentSessionId === btn.dataset.del) { currentSessionId = null; clearChat(); }
      await loadSessions();
    });
  });
}

async function selectSession(sid) {
  if (isProcessing) return;  // AI 思考中，禁止切换会话
  // 取消上一个会话正在进行中的请求，防止其响应污染当前会话
  cancelActiveRequest();

  currentSessionId = sid;
  renderSessions();
  clearChat();
  try {
    const res = await api.listMessages(sid);
    renderMessages(res.data || []);
    // 若会话已完成诊断，禁用输入框
    disableInputIfDiagnosisDone();
  } catch (e) {
    console.error('loadMessages:', e);
    // 加载失败时显示错误提示，而非空白页
    chatEl.innerHTML = `<div class="welcome">
      <h2>加载失败</h2>
      <p style="color:var(--mauve)">无法加载历史消息，请检查网络后重试</p>
    </div>`;
  }
  updateStageUI();
}

document.getElementById('btnNewSession').addEventListener('click', () => {
  if (isProcessing) return;  // AI 思考中，禁止操作
  cancelActiveRequest();
  currentSessionId = null;
  clearChat();
  showWelcome();
  updateStageUI();
  renderSessions();
});

function showWelcome() {
  chatEl.innerHTML = `<div class="welcome">
    <h2>灵兰健康</h2>
    <p>描述您的症状，AI 将为您逐步分析</p>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════
// Chat
// ═══════════════════════════════════════════════════════════════
const chatEl = document.getElementById('chatMessages');
const inputEl = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const stageEl = document.getElementById('stageBadge');
const expertEl = document.getElementById('expertBadge');
const roundEl = document.getElementById('roundInfo');

function clearChat() { chatEl.innerHTML = ''; inputEl.disabled = false; sendBtn.disabled = false; inputEl.placeholder = '描述您的症状...'; }
function scrollChat() { chatEl.scrollTop = chatEl.scrollHeight; }

// 取消当前活跃的请求（会话切换或新请求发起时调用）
function cancelActiveRequest() {
  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
    activeRequestSessionId = null;
  }
}

// 检查当前会话是否已出具诊断报告，若已出具则禁用输入
// 直接检测 DOM 中的 .report-card 元素，不依赖侧边栏数据或轮次计数
function disableInputIfDiagnosisDone() {
  const hasReport = chatEl.querySelector('.msg.assistant .report-card');
  if (hasReport) {
    inputEl.disabled = true;
    inputEl.placeholder = '诊断已完成，可新建会话继续';
    sendBtn.disabled = true;
  }
}

function updateStageUI() {
  stageEl.style.display = 'none'; expertEl.style.display = 'none';
  stageEl.classList.remove('expert');
  // Will be updated based on API response
}

function renderMessages(msgs) {
  chatEl.innerHTML = '';
  msgs.forEach(m => {
    const isReport = m.role === 'assistant' && (!m.options || m.options.length === 0) && m.content && m.content.length > 150;
    appendMessage(m.role, m.content, m.options, isReport);
  });
  disableHistoricalChoices();
  scrollChat();
}

// 禁用所有历史选项卡片，仅最后一条 AI 消息的选项可点击
function disableHistoricalChoices() {
  const allChoices = chatEl.querySelectorAll('.msg.assistant .choices');
  // 最后一个是当前轮次，保留可点击；其余全部禁用
  for (let i = 0; i < allChoices.length; i++) {
    if (i === allChoices.length - 1) continue;
    allChoices[i].querySelectorAll('.choice-card').forEach(card => {
      card.style.pointerEvents = 'none';
      card.style.opacity = '0.5';
      card.style.cursor = 'not-allowed';
    });
  }
}

function appendMessage(role, content, options, isReport = false) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar-icon';
  avatar.textContent = role === 'assistant' ? 'AI' : '我';
  div.appendChild(avatar);

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  if (content) {
    if (isReport && content.length > 80) {
      // 诊断报告：解析章节，结构化渲染
      const reportDiv = document.createElement('div');
      reportDiv.className = 'report-card';
      reportDiv.innerHTML = parseReport(content);
      bubble.appendChild(reportDiv);
    } else {
      const p = document.createElement('p');
      p.textContent = content;
      bubble.appendChild(p);
    }
  }
  if (options && options.length > 0) {
    const cd = document.createElement('div'); cd.className = 'choices';
    const letters = 'ABCDEFGH';
    options.slice(0, 4).forEach((opt, i) => {
      const card = document.createElement('button'); card.className = 'choice-card';
      card.innerHTML = `<span class="choice-letter">${letters[i]}</span> ${opt.label}`;
      card.addEventListener('click', () => {
        cd.querySelectorAll('.choice-card').forEach(c => { c.style.pointerEvents = 'none'; c.style.opacity = '0.5'; });
        card.classList.add('selected');
        sendChoice(opt.value, opt.label);
      });
      cd.appendChild(card);
    });
    const hint = document.createElement('p'); hint.className = 'choice-hint';
    hint.textContent = '也可以直接在下方输入框描述您的情况';
    cd.appendChild(hint);
    bubble.appendChild(cd);
  }
  div.appendChild(bubble);
  chatEl.appendChild(div);
  scrollChat();
}

function showThinking() {
  const div = document.createElement('div');
  div.className = 'msg assistant'; div.id = 'thinkingMsg';
  div.innerHTML = '<div class="avatar-icon">AI</div><div class="bubble thinking">思考中<span class="dots"></span></div>';
  chatEl.appendChild(div); scrollChat();
}
function hideThinking() {
  const el = document.getElementById('thinkingMsg');
  if (el) el.remove();
}

async function sendChoice(value, label) {
  if (!currentSessionId) return;
  if (isProcessing) return;  // AI 思考中，阻止操作

  // 取消上一个未完成的请求
  cancelActiveRequest();
  isProcessing = true;
  inputEl.disabled = true;

  const sessionIdForThisRequest = currentSessionId;
  appendMessage('user', label);
  showThinking();

  const controller = new AbortController();
  activeAbortController = controller;
  activeRequestSessionId = sessionIdForThisRequest;

  try {
    // 选项 label 来自后端，通常不含 PII，但仍做脱敏
    const sanitized = maskPII(label);
    const res = await api.sendMessage(sessionIdForThisRequest, sanitized, 'text', controller.signal);
    hideThinking();
    if (currentSessionId === sessionIdForThisRequest) {
      handleResponse(res);
    }
  } catch (e) {
    hideThinking();
    if (e.name === 'AbortError') {
      console.log('Choice request aborted for session:', sessionIdForThisRequest);
      return;
    }
    console.error('sendChoice:', e);
  } finally {
    if (activeRequestSessionId === sessionIdForThisRequest) {
      activeAbortController = null;
      activeRequestSessionId = null;
      isProcessing = false;
    }
    inputEl.disabled = false;
  }
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;
  if (isProcessing) return;  // AI 思考中，阻止重复发送
  isProcessing = true;
  sendBtn.disabled = true;
  inputEl.disabled = true;

  // PII 脱敏前置（安全红线 #4）
  const sanitized = maskPII(text);

  // 取消上一个未完成的请求
  cancelActiveRequest();

  // 首次发消息：自动创建会话 + 清掉欢迎页
  if (!currentSessionId) {
    chatEl.innerHTML = '';
    try {
      const res = await api.createSession();
      if (!res || !res.id) {
        sendBtn.disabled = false;
        return;
      }
      currentSessionId = res.id;
      await loadSessions();
    } catch (e) { console.error('auto create session:', e); sendBtn.disabled = false; return; }
  }

  // 仅当会话已存在时才清空输入框（避免创建失败导致输入丢失）
  inputEl.value = '';

  // 防御：确保会话 ID 有效
  if (!currentSessionId || currentSessionId === 'undefined' || currentSessionId === 'null') {
    console.error('Invalid session ID, aborting send');
    sendBtn.disabled = false; inputEl.focus();
    return;
  }

  // 快照：记录本次请求所属的会话 ID（防止响应时 session 已切换）
  const sessionIdForThisRequest = currentSessionId;
  appendMessage('user', text);
  showThinking();

  // 创建 AbortController 以便切换会话时取消请求
  const controller = new AbortController();
  activeAbortController = controller;
  activeRequestSessionId = sessionIdForThisRequest;

  try {
    // 发送脱敏后的文本给后端，前端仍显示原始输入
    const res = await api.sendMessage(sessionIdForThisRequest, sanitized, 'text', controller.signal);
    hideThinking();

    // 关键校验：仅当用户仍停留在该会话时才处理响应
    if (currentSessionId === sessionIdForThisRequest) {
      handleResponse(res);
    }
  } catch (e) {
    hideThinking();
    if (e.name === 'AbortError') {
      console.log('Request aborted for session:', sessionIdForThisRequest);
      return; // 主动取消，不显示错误
    }
    console.error('sendMessage:', e);
  } finally {
    // 仅当这个请求仍是"活跃请求"时才清除标记
    if (activeRequestSessionId === sessionIdForThisRequest) {
      activeAbortController = null;
      activeRequestSessionId = null;
      isProcessing = false;
    }
    sendBtn.disabled = false;
    inputEl.disabled = false;
    // 仅当用户仍在该会话时才聚焦输入框
    if (currentSessionId === sessionIdForThisRequest) {
      inputEl.focus();
    }
  }
}

function handleResponse(res) {
  // 诊断报告检测：next_action 标记 或 长文本无选项
  const isReport = res.next_action === 'diagnosis_ready'
    || res.current_stage === 'diagnose'
    || (res.response_content && res.response_content.length > 200 && (!res.options || res.options.length === 0));
  if (res.response_content) {
    appendMessage('assistant', res.response_content, res.options, isReport);
    // 新消息到达后，禁用历史选项（只有最新一轮可选）
    disableHistoricalChoices();
  }
  if (res.red_flag_raised) {
    stageEl.style.display = 'inline'; stageEl.textContent = '紧急';
    stageEl.style.background = 'var(--mauve-ghost)'; stageEl.style.color = 'var(--mauve)';
  } else if (isReport) {
    stageEl.style.display = 'inline'; stageEl.textContent = '诊断报告';
  } else if (res.current_stage === 'collect') {
    // Try to detect expert stage
    stageEl.style.display = 'inline'; stageEl.textContent = '问诊中';
  }
  if (res.round_count) roundEl.textContent = `第 ${res.round_count} / 10 轮`;

  // 若已出具诊断报告，禁用输入并刷新侧边栏以更新会话状态
  if (res.next_action === 'diagnosis_ready' || res.current_stage === 'diagnose') {
    inputEl.disabled = true; inputEl.placeholder = '诊断已完成，可新建会话继续';
    sendBtn.disabled = true;
  }
  loadSessions(); // refresh sidebar (updates sessions[] for disableInputIfDiagnosisDone)
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

// ═══════════════════════════════════════════════════════════════
// Profile
// ═══════════════════════════════════════════════════════════════
async function loadProfile() {
  try {
    const p = await api.getProfile();
    document.getElementById('sidebarName').textContent = p.nickname || '用户';
    document.getElementById('sidebarPhone').textContent = p.phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2');
    document.getElementById('sidebarAvatar').textContent = (p.nickname || '用')[0];
  } catch (e) { console.error('loadProfile:', e); }
}

document.getElementById('sidebarAvatar').addEventListener('click', () => {
  document.getElementById('profileModal').classList.remove('hidden');
  loadProfileForm();
});

document.getElementById('btnProfileSave').addEventListener('click', async () => {
  const data = {};
  const set = (k, v) => { if (v) data[k] = v; };
  set('nickname', document.getElementById('pfNick').value.trim());
  set('gender', document.getElementById('pfGender').value);
  set('height', parseFloat(document.getElementById('pfHeight').value) || undefined);
  set('weight', parseFloat(document.getElementById('pfWeight').value) || undefined);
  set('blood_type', document.getElementById('pfBlood').value);
  const allergies = document.getElementById('pfAllergies').value.trim();
  if (allergies) data.allergies = allergies.split(/[,，]/).map(s => s.trim());
  const chronic = document.getElementById('pfChronic').value.trim();
  if (chronic) data.chronic_diseases = chronic.split(/[,，]/).map(s => s.trim());
  try {
    await api.updateProfile(data);
    document.getElementById('profileModal').classList.add('hidden');
    loadProfile();
  } catch (e) { console.error('updateProfile:', e); }
});

document.getElementById('btnProfileCancel').addEventListener('click', () => {
  document.getElementById('profileModal').classList.add('hidden');
});

async function loadProfileForm() {
  try {
    const p = await api.getProfile();
    document.getElementById('pfNick').value = p.nickname || '';
    document.getElementById('pfGender').value = p.gender || '';
    document.getElementById('pfHeight').value = p.height || '';
    document.getElementById('pfWeight').value = p.weight || '';
    document.getElementById('pfBlood').value = p.blood_type || '';
    const mi = p.medical_info || {};
    document.getElementById('pfAllergies').value = (mi.allergies || []).join('，');
    document.getElementById('pfChronic').value = (mi.chronic_diseases || []).join('，');
  } catch (e) { console.error('loadProfileForm:', e); }
}

// ═══════════════════════════════════════════════════════════════
// Utils
// ═══════════════════════════════════════════════════════════════
function parseReport(text) {
  const esc = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  // 按双换行分段
  const paras = text.split(/\n\n+/).filter(p => p.trim());
  if (paras.length <= 1) {
    return '<div class="report-title">诊断报告</div><p>' + esc(text).replace(/\n/g, '<br>') + '</p>';
  }
  let html = '<div class="report-title">诊断报告</div>';
  paras.forEach(p => {
    const trimmed = p.trim();
    // 检测免责声明段落
    if (/免责声明|不能替代|仅供参考|及时就医/.test(trimmed)) {
      html += '<div class="disclaimer">' + String.fromCharCode(0x2695) + '&nbsp;'
           + esc(trimmed).replace(/\n/g, '<br>') + '</div>';
    } else {
      html += '<p>' + esc(trimmed).replace(/\n/g, '<br>') + '</p>';
    }
  });
  return html;
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return `今天 ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`;
  return `${d.getMonth()+1}月${d.getDate()}日`;
}

// 前端 PII 预脱敏（安全红线 #4）
const _ID_CARD_RE = /\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b/g;
const _PHONE_RE = /\b1[3-9]\d{9}\b/g;
function maskPII(text) {
  return text.replace(_ID_CARD_RE, '[身份证已隐藏]').replace(_PHONE_RE, '[手机号已隐藏]');
}
