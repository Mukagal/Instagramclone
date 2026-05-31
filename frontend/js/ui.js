let toastContainer = null;

function getToastContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    document.body.appendChild(toastContainer);
  }
  return toastContainer;
}

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'info'|'success'|'error'} type
 * @param {number} duration  ms before auto-dismiss
 */
export function toast(message, type = 'info', duration = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  const container = getToastContainer();
  container.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity 300ms, transform 300ms';
    el.style.opacity = '0';
    el.style.transform = 'translateX(12px)';
    setTimeout(() => el.remove(), 320);
  }, duration);
}

export const toastSuccess = (msg) => toast(msg, 'success');
export const toastError   = (msg) => toast(msg, 'error');

/**
 * Open a modal with custom HTML content.
 * Returns a { close } handle.
 *
 * @param {{ title?: string, content: string, footer?: string }} opts
 */
export function modal({ title = '', content = '', footer = '' } = {}) {
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';

  backdrop.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <span class="modal-title">${title}</span>
        <button class="btn-icon modal-close-btn" aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">${content}</div>
      ${footer ? `<div class="modal-footer" style="margin-top:var(--s5)">${footer}</div>` : ''}
    </div>
  `;

  document.body.appendChild(backdrop);
  document.body.style.overflow = 'hidden';

  const close = () => {
    backdrop.style.opacity = '0';
    backdrop.style.transition = 'opacity 200ms';
    setTimeout(() => {
      backdrop.remove();
      document.body.style.overflow = '';
    }, 200);
  };

  backdrop.querySelector('.modal-close-btn').addEventListener('click', close);
  backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
  document.addEventListener('keydown', function onKey(e) {
    if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey); }
  });

  return { el: backdrop, close };
}

/**
 * Promise-based confirm dialog.
 * @param {{ title?, message?, confirmLabel?, danger? }} opts
 * @returns {Promise<boolean>}
 */
export function confirm({ title = 'Are you sure?', message = '', confirmLabel = 'Confirm', danger = false } = {}) {
  return new Promise((resolve) => {
    const m = modal({
      title,
      content: message ? `<p style="color:var(--text-secondary);font-size:.9rem">${message}</p>` : '',
      footer: `
        <div class="flex gap-3" style="justify-content:flex-end">
          <button class="btn btn-ghost btn-sm" id="confirm-cancel">Cancel</button>
          <button class="btn ${danger ? 'btn-danger' : 'btn-primary'} btn-sm" id="confirm-ok">${confirmLabel}</button>
        </div>
      `,
    });

    m.el.querySelector('#confirm-cancel').addEventListener('click', () => { m.close(); resolve(false); });
    m.el.querySelector('#confirm-ok').addEventListener('click',     () => { m.close(); resolve(true);  });
  });
}

let globalSpinner = null;

export function showSpinner() {
  if (globalSpinner) return;
  globalSpinner = document.createElement('div');
  globalSpinner.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,0.45);backdrop-filter:blur(4px);
    display:flex;align-items:center;justify-content:center;z-index:9998;
  `;
  globalSpinner.innerHTML = '<div class="spinner" style="width:32px;height:32px;border-width:3px"></div>';
  document.body.appendChild(globalSpinner);
}

export function hideSpinner() {
  if (globalSpinner) { globalSpinner.remove(); globalSpinner = null; }
}

// ── Inline button loading state ───────────────
export function setButtonLoading(btn, loading) {
  if (loading) {
    btn.dataset.originalText = btn.innerHTML;
    btn.innerHTML = '<div class="spinner"></div>';
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
    btn.disabled = false;
  }
}

/**
 * Build an avatar <img> or initials <div>.
 * @param {{ src?, username?, size? }} opts
 * @returns {HTMLElement}
 */
export function buildAvatar({ src, username = '?', size = 'md' } = {}) {
  if (src) {
    const img = document.createElement('img');
    img.src = src;
    img.alt = username;
    img.className = `avatar avatar-${size}`;
    img.onerror = () => replaceWithInitials(img, username, size);
    return img;
  }
  return makeInitialsAvatar(username, size);
}

function makeInitialsAvatar(username, size) {
  const div = document.createElement('div');
  div.className = `avatar avatar-${size}`;
  div.textContent = getInitials(username);
  div.style.background = stringToColor(username);
  return div;
}

function replaceWithInitials(img, username, size) {
  const div = makeInitialsAvatar(username, size);
  img.replaceWith(div);
}

function getInitials(name = '') {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function stringToColor(str = '') {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = Math.abs(hash) % 360;
  return `hsl(${h},35%,28%)`;
}

export function relativeTime(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d`;
  const w = Math.floor(d / 7);
  if (w < 5) return `${w}w`;
  return new Date(dateStr).toLocaleDateString(undefined, { month:'short', day:'numeric' });
}

export function formatCount(n = 0) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
  return String(n);
}

const QUICK_EMOJIS = ['❤️','😂','😮','😢','😡','👍','🔥','🎉','👀','💯'];

/**
 * Attach a quick emoji picker to a trigger button.
 * @param {HTMLElement} trigger
 * @param {(emoji: string) => void} onPick
 */
export function attachEmojiPicker(trigger, onPick) {
  let picker = null;

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    if (picker) { picker.remove(); picker = null; return; }

    picker = document.createElement('div');
    picker.style.cssText = `
      position:absolute;bottom:calc(100% + 8px);right:0;
      background:var(--bg-raised);border:1px solid var(--border);
      border-radius:var(--r-md);padding:8px;
      display:flex;gap:4px;flex-wrap:wrap;width:200px;
      box-shadow:var(--shadow-md);z-index:500;
    `;
    QUICK_EMOJIS.forEach(emoji => {
      const btn = document.createElement('button');
      btn.textContent = emoji;
      btn.style.cssText = 'font-size:1.3rem;padding:4px;border-radius:6px;cursor:pointer;background:none;border:none;transition:background 120ms';
      btn.onmouseenter = () => btn.style.background = 'var(--bg-surface)';
      btn.onmouseleave = () => btn.style.background = 'none';
      btn.addEventListener('click', () => { onPick(emoji); picker.remove(); picker = null; });
      picker.appendChild(btn);
    });

    // position relative to trigger's parent
    const parent = trigger.closest('[style*="position"]') || trigger.parentElement;
    parent.style.position = 'relative';
    parent.appendChild(picker);

    const dismiss = (ev) => {
      if (!picker?.contains(ev.target)) { picker?.remove(); picker = null; document.removeEventListener('click', dismiss); }
    };
    setTimeout(() => document.addEventListener('click', dismiss), 0);
  });
}

// ═══════════════════════════════════════════════
// INFINITE SCROLL
// ═══════════════════════════════════════════════
/**
 * Call `callback` when user scrolls near the bottom of `scrollEl`.
 * @param {HTMLElement|Window} scrollEl
 * @param {() => Promise<void>} callback  should set a loading flag to debounce
 * @param {number} threshold  px from bottom
 * @returns {() => void}  cleanup function
 */
export function infiniteScroll(scrollEl, callback, threshold = 300) {
  const handler = () => {
    const el = scrollEl === window ? document.documentElement : scrollEl;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distFromBottom < threshold) callback();
  };
  scrollEl.addEventListener('scroll', handler, { passive: true });
  return () => scrollEl.removeEventListener('scroll', handler);
}

export function serializeForm(formEl) {
  const data = {};
  new FormData(formEl).forEach((v, k) => { data[k] = v; });
  return data;
}

export function setFieldError(inputEl, message) {
  let errEl = inputEl.parentElement.querySelector('.field-error');
  if (!message) { errEl?.remove(); return; }
  if (!errEl) {
    errEl = document.createElement('span');
    errEl.className = 'field-error';
    errEl.style.cssText = 'color:var(--danger);font-size:.78rem;margin-top:4px;display:block';
    inputEl.insertAdjacentElement('afterend', errEl);
  }
  errEl.textContent = message;
}