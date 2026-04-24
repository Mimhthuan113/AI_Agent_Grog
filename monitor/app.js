/**
 * Aisha Pipeline Monitor — Standalone Real-time Dashboard
 * ========================================================
 * Kết nối SSE tới backend, hiển thị luồng xử lý animated.
 */

const API = 'http://localhost:8000';

// ── DOM refs ──────────────────────────
const connStatus = document.getElementById('connStatus');
const eventCountEl = document.getElementById('eventCount');
const feedList = document.getElementById('feedList');

// Node mapping: step name → node ID
const STEP_NODE_MAP = {
  'Rate Limiter': 'rate',
  'Sanitizer': 'sanitizer',
  'RBAC': 'rbac',
  'Rule Engine': 'rule',
  'Confirmation': 'rule',
  'Circuit Breaker': 'cb',
  'Execute HA': 'ha',
  'Audit Log': 'audit',
};

// Arrow index for each step
const STEP_ARROW_MAP = {
  'Rate Limiter': 2,
  'Sanitizer': 3,
  'RBAC': 4,
  'Rule Engine': 5,
  'Confirmation': 5,
  'Circuit Breaker': 6,
  'Execute HA': 7,
  'Audit Log': 7,
};

let eventCount = 0;

// ── SSE Connection ──────────────────
function connectSSE() {
  const evtSource = new EventSource(`${API}/monitor/events`);

  evtSource.onopen = () => {
    connStatus.textContent = '🟢 Đã kết nối';
    connStatus.classList.add('connected');
  };

  evtSource.addEventListener('pipeline', (e) => {
    const data = JSON.parse(e.data);
    eventCount++;
    eventCountEl.textContent = `${eventCount} events`;
    handlePipelineEvent(data);
  });

  evtSource.addEventListener('ping', () => {
    // Heartbeat — ignore
  });

  evtSource.onerror = () => {
    connStatus.textContent = '🔴 Mất kết nối';
    connStatus.classList.remove('connected');
    // Auto-reconnect (SSE does this by default)
  };
}

// ── Handle Pipeline Event ────────────
async function handlePipelineEvent(data) {
  // 1) Reset all nodes
  resetPipeline();

  // 2) Animate user → brain
  await animateNode('user', 'pass');
  await animateArrow(0, 'pass');
  await animateNode('brain', data.category === 'dangerous' ? 'fail' : 'pass');

  // 3) Nếu không phải Smart Home hay App Action
  if (data.category !== 'smart_home' && data.category !== 'app_action') {
    // Gọi general chat, tự kết thúc tại Siri Brain, gửi Log tới Audit
    addFeedCard(data);
    return;
  }

  // 4) Nhánh APP ACTION (System & File Ops)
  if (data.category === 'app_action') {
    // Chạy Animation nhánh Phải (app_action)
    await animateNode('router', 'pass');
    await animateArrow('router', 'pass');
    
    // Đang execute qua Node OS / File Ops
    const isSuccess = data.success ? 'pass' : 'fail';
    await animateNode('os', isSuccess);
    
    // Lấy chi tiết Data mô tả "Làm gì, Mở app gì" do Backend mới sinh ra!
    data.steps = data.steps && data.steps.length > 0 ? data.steps : [
      { name: 'App Router (Parse)', status: 'pass' },
      { name: 'OS Exec Ops', status: isSuccess },
      { name: 'Local Audit', status: isSuccess }
    ];

    // Ném xuống System Audit
    await animateArrow('os', isSuccess);
    await animateNode('audit-os', isSuccess);
    
    // Trộn về DB
    await animateNode('audit', isSuccess);
    addFeedCard(data);
    return;
  }

  // 5) Nhánh SMART HOME (HA Protocol)
  // Animate through pipeline steps
  const steps = data.steps || [];

  for (const step of steps) {
    const nodeId = STEP_NODE_MAP[step.name];
    const arrowIdx = STEP_ARROW_MAP[step.name];

    if (nodeId) {
      await animateNode(nodeId, step.status);
    }
    if (arrowIdx !== undefined && step.status !== 'skip') {
      await animateArrow(arrowIdx, step.status === 'pass' ? 'pass' : 'fail');
    }
    await sleep(200);
  }

  // Kết nút về Audit DB Chung cho xong màn
  await animateNode('audit', data.success ? 'pass' : 'fail');

  // 6) Add to feed
  addFeedCard(data);
}

// ── Animation Helpers ─────────────────
function resetPipeline() {
  document.querySelectorAll('.pipe-node').forEach(n => {
    n.classList.remove('active', 'pass', 'fail', 'skip', 'pending');
  });
  document.querySelectorAll('.pipe-arrow').forEach(a => {
    a.classList.remove('animate', 'pass', 'fail');
  });
}

async function animateNode(id, status) {
  const node = document.getElementById(`node-${id}`);
  if (!node) return;
  node.classList.add('active');
  await sleep(150);
  node.classList.remove('active');
  node.classList.add(status);
}

async function animateArrow(idx, status) {
  const arrow = document.getElementById(`arrow-${idx}`);
  if (!arrow) return;
  arrow.classList.add(status, 'animate');
  await sleep(300);
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── Feed Card Builder ─────────────────
function addFeedCard(data) {
  // Remove empty state
  const empty = feedList.querySelector('.feed-empty');
  if (empty) empty.remove();

  const card = document.createElement('div');
  card.className = `feed-card ${data.success ? 'success' : 'fail'}`;

  const isOwner = data.user_id === 'admin';
  const time = new Date(data.timestamp).toLocaleTimeString('vi-VN');

  const stepsHtml = (data.steps || []).map(s => {
    const cls = `s-${s.status}`;
    const icon = s.status === 'pass' ? '✓' : s.status === 'fail' ? '✗' : s.status === 'skip' ? '⊘' : '⏳';
    return `<span class="feed-step ${cls}">${icon} ${s.name}</span>`;
  }).join('');

  card.innerHTML = `
    <div class="feed-header">
      <span class="feed-user ${isOwner ? 'owner' : 'guest'}">${data.user_id}</span>
      <span class="feed-category cat-${data.category}">${data.category}</span>
      <span class="feed-time">${time}</span>
    </div>
    <div class="feed-message">→ "${data.message}"</div>
    <div class="feed-result">${data.success ? '✅' : '❌'} ${data.result}</div>
    ${stepsHtml ? `<div class="feed-steps">${stepsHtml}</div>` : ''}
  `;

  // Prepend (newest first)
  feedList.prepend(card);

  // Keep max 50 cards
  while (feedList.children.length > 50) {
    feedList.lastChild.remove();
  }
}

// ── Boot ──────────────────────────────
connectSSE();
