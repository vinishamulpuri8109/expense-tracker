/* app.js — Finance Assistant chat client */

const messagesEl   = document.getElementById('messages');
const form         = document.getElementById('chat-form');
const input        = document.getElementById('question-input');
const sendBtn      = document.getElementById('send-btn');
const statusDot    = document.getElementById('status-dot');
const statusText   = document.getElementById('status-text');
const categoriesEl = document.getElementById('top-categories');

// ---------------------------------------------------------------------------
// Sidebar: load top categories on page load
// ---------------------------------------------------------------------------

async function loadTopCategories() {
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: 'What were my top 6 spending categories from 2024-03-29 to 2025-03-30?'
      }),
    });

    if (!res.ok) throw new Error('API error');
    const data = await res.json();

    // Parse dollar amounts from the answer text using a regex.
    // The model returns something like "1. Healthcare — $12,345.67\n2. ..."
    // We render what we can parse; fall back gracefully.
    renderCategories(data.answer);
  } catch {
    categoriesEl.innerHTML =
      '<p style="font-size:12px;color:var(--text-muted)">Could not load summary.</p>';
  }
}

function renderCategories(answerText) {
  // Try to extract "Category ... $amount" patterns from the model's answer.
  const lines = answerText.split('\n').filter(l => l.trim());
  const items = [];

  for (const line of lines) {
    // Match lines like: "1. Groceries — $1,234.56" or "Healthcare: $999.00"
    const m = line.match(/([A-Za-z &]+?)\s*[:\-–—]\s*\$?([\d,]+\.?\d*)/);
    if (m) {
      const name   = m[1].replace(/^\d+\.\s*/, '').trim();
      const amount = parseFloat(m[2].replace(/,/g, ''));
      if (!isNaN(amount)) items.push({ name, amount });
    }
  }

  if (items.length === 0) {
    categoriesEl.innerHTML =
      '<p style="font-size:12px;color:var(--text-muted)">No data to display.</p>';
    return;
  }

  const max = Math.max(...items.map(i => i.amount));
  categoriesEl.innerHTML = items.map(({ name, amount }) => {
    const pct = Math.round((amount / max) * 100);
    const fmt = amount.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
    return `
      <div class="category-item">
        <div style="flex:1;min-width:0">
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px">
            <span class="category-name">${escHtml(name)}</span>
            <span class="category-amount">${fmt}</span>
          </div>
          <div class="category-bar-wrap">
            <div class="category-bar" style="width:${pct}%"></div>
          </div>
        </div>
      </div>`;
  }).join('');
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function appendMessage(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

function showTyping() {
  const wrap = document.createElement('div');
  wrap.className = 'message assistant';
  wrap.id = 'typing-msg';
  wrap.innerHTML = `
    <div class="bubble typing-indicator">
      <span></span><span></span><span></span>
    </div>`;
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeTyping() {
  document.getElementById('typing-msg')?.remove();
}

function setLoading(on) {
  sendBtn.disabled = on;
  input.disabled   = on;
  statusDot.classList.toggle('loading', on);
  statusText.textContent = on ? 'Thinking…' : 'Connected';
}

async function sendQuestion(question) {
  appendMessage('user', question);
  showTyping();
  setLoading(true);

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    removeTyping();

    if (res.status === 422) {
      const err = await res.json();
      const msg = err.detail?.[0]?.msg ?? 'Invalid question.';
      appendMessage('assistant', `⚠️ ${msg}`);
      return;
    }

    if (!res.ok) {
      appendMessage('assistant', '⚠️ Something went wrong. Please try again.');
      return;
    }

    const data = await res.json();
    appendMessage('assistant', data.answer);
  } catch {
    removeTyping();
    appendMessage('assistant', '⚠️ Could not reach the server.');
  } finally {
    setLoading(false);
  }
}

// ---------------------------------------------------------------------------
// Form submit
// ---------------------------------------------------------------------------

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  autoResize();
  await sendQuestion(q);
});

// Submit on Enter (Shift+Enter = newline)
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    form.dispatchEvent(new Event('submit'));
  }
});

// Auto-resize textarea
function autoResize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
}
input.addEventListener('input', autoResize);

// ---------------------------------------------------------------------------
// Suggested questions (sidebar)
// ---------------------------------------------------------------------------

document.querySelectorAll('.suggestions li').forEach(li => {
  li.addEventListener('click', () => {
    const q = li.dataset.q;
    if (!q) return;
    input.value = '';
    sendQuestion(q);
  });
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

loadTopCategories();
input.focus();
