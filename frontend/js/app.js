import api from './api.js';
import { initAuth, getCurrentUser, setCurrentUser, renderLoginPage, renderSignupPage, renderForgotPage } from './auth.js';
import { renderFeedPage } from './feed.js';
import { renderProfilePage } from './profile.js';
import { renderMessagesPage } from './messages.js';
import { renderNotificationsPage } from './notifications.js';
import { buildAvatar, toast, toastError, formatCount, modal, confirm, relativeTime } from './ui.js';
import { icons } from "./icons.js";

async function boot() {
  renderShell();
  renderBootLoader();

  const user = await initAuth();
  setupRouter();

  if (!user && requiresAuth(window.location.hash)) {
    window.location.hash = '#login';
  }
}

document.addEventListener('DOMContentLoaded', boot);
window.addEventListener('auth:unauthorized', () => {
  setCurrentUser(null);
  if (requiresAuth(window.location.hash)) {
    window.location.hash = '#login';
  }
});

function renderShell() {
  document.body.innerHTML = `
    <!-- MOBILE TOP BAR -->
    <div class="mobile-topbar" id="mobile-topbar">
      <div class="sidebar-brand" style="padding:0">
        <div class="sidebar-brand-icon">I</div>
        <span class="sidebar-brand-name">Instagram</span>
      </div>
      <div class="flex gap-2">
        <button class="btn-icon" id="mobile-search-btn">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </button>
      </div>
    </div>

    <!-- APP SHELL -->
    <div class="app-shell">
      <!-- SIDEBAR -->
      <nav class="sidebar" id="sidebar" style="display:none">
        <a href="#feed" class="sidebar-brand" style="text-decoration:none">
          <div class="sidebar-brand-icon">I</div>
          <span class="sidebar-brand-name">Instagram</span>
        </a>

        <div class="nav-section">
          <a href="#feed"       class="nav-link" data-route="feed">
            <span class="nav-icon">${icons.home}</span> Home
          </a>
          <a href="#explore"    class="nav-link" data-route="explore">
            <span class="nav-icon">${icons.search}</span> Explore
          </a>
          <a href="#messages"   class="nav-link" data-route="messages">
            <span class="nav-icon">${icons.message}</span> Messages
            <span class="nav-badge" id="unread-badge" style="display:none">0</span>
          </a>
          <a href="#notifications" class="nav-link" data-route="notifications">
            <span class="nav-icon">${icons.bell}</span> Notifications
          </a>

          <div class="nav-section-label">Create</div>
          <button class="nav-link" id="new-post-btn" style="width:100%;text-align:left">
            <span class="nav-icon">${icons.plus}</span> New post
          </button>

          <div class="nav-section-label">Me</div>
          <a href="#profile" class="nav-link" data-route="profile">
            <span class="nav-icon">${icons.user}</span> Profile
          </a>
          <a href="#saved"   class="nav-link" data-route="saved">
            <span class="nav-icon">${icons.bookmark}</span> Saved
          </a>
          <a href="#settings" class="nav-link" data-route="settings">
            <span class="nav-icon">${icons.settings}</span> Settings
          </a>
        </div>

        <div class="sidebar-user" id="sidebar-user" style="display:none">
          <div id="sidebar-avatar-slot"></div>
          <div class="sidebar-user-info">
            <div class="sidebar-user-name"  id="sidebar-username">—</div>
            <div class="sidebar-user-handle" id="sidebar-handle">—</div>
          </div>
          <button class="sidebar-user-more" id="logout-btn" title="Logout">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </nav>

      <!-- MAIN CONTENT -->
      <main class="main-content" id="main-content"></main>
    </div>

    <!-- MOBILE BOTTOM NAV -->
    <nav class="mobile-bottomnav" id="mobile-bottomnav" style="display:none">
      <div class="mobile-bottomnav-inner">
        <a href="#feed" class="mobile-nav-btn" data-route="feed">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          Home
        </a>
        <a href="#explore" class="mobile-nav-btn" data-route="explore">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          Explore
        </a>
        <button class="mobile-nav-btn" id="mobile-new-post">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
          Post
        </button>
        <a href="#messages" class="mobile-nav-btn" data-route="messages">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          Messages
        </a>
        <a href="#profile" class="mobile-nav-btn" data-route="profile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          Profile
        </a>
      </div>
    </nav>

    <!-- Toast container injected by ui.js -->
  `;

  document.querySelector('#new-post-btn')?.addEventListener('click', openNewPostModal);
  document.querySelector('#mobile-new-post')?.addEventListener('click', openNewPostModal);
  document.querySelector('#logout-btn')?.addEventListener('click', handleLogout);
}

function renderBootLoader() {
  const main = document.querySelector('#main-content');
  if (!main) return;
  main.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:var(--s8)">
      <div class="spinner" style="width:32px;height:32px;border-width:3px"></div>
    </div>
  `;
}

function updateSidebarUser() {
  const user = getCurrentUser();
  const sidebarEl = document.querySelector('#sidebar');
  const sidebarUser = document.querySelector('#sidebar-user');
  const mobileNav  = document.querySelector('#mobile-bottomnav');

  if (user) {
    sidebarEl.style.display = '';
    sidebarUser.style.display = 'flex';
    mobileNav.style.display = '';

    document.querySelector('#sidebar-username').textContent = user.profile?.full_name || user.full_name || user.username;
    document.querySelector('#sidebar-handle').textContent   = '@' + user.username;

    const slot = document.querySelector('#sidebar-avatar-slot');
    slot.innerHTML = '';
    slot.appendChild(buildAvatar({ src: user.profile?.avatar_path || user.avatar_url, username: user.username, size: 'xs' }));
  } else {
    sidebarEl.style.display = 'none';
    mobileNav.style.display = '';
  }
}

const AUTH_ROUTES  = ['login', 'signup', 'forgot'];
const GUEST_ROUTES = new Set(['login', 'signup', 'forgot', 'explore', 'post']);

function requiresAuth(hash) {
  const route = parseHash(hash).route;
  return !GUEST_ROUTES.has(route) && !AUTH_ROUTES.includes(route);
}

function parseHash(hash = '') {
  const clean = hash.replace(/^#/, '');
  const [route, ...params] = clean.split('/');
  return { route: route || 'feed', params };
}

function setupRouter() {
  const navigate = () => {
    const { route, params } = parseHash(window.location.hash);
    const user = getCurrentUser();

    updateSidebarUser();
    setActiveNavLink(route);

    const main = document.querySelector('#main-content');
    main.innerHTML = '';

    if (requiresAuth('#' + route) && !user) {
      window.location.hash = '#login';
      return;
    }
    if (AUTH_ROUTES.includes(route) && user) {
      window.location.hash = '#feed';
      return;
    }

    switch (route) {
      case 'login': renderLoginPage(main);    break;
      case 'signup': renderSignupPage(main);   break;
      case 'forgot': renderForgotPage(main);   break;
      case 'feed': renderFeedPage(main);      break;
      case 'explore': renderExplorePage(main);    break;
      case 'messages': renderMessagesPage(main, params[0]); break;
      case 'notifications': renderNotificationsPage(main); break;
      case 'profile':
        renderProfilePage(main, params[0] || (user ? user.username : ''));
        break;
      case 'saved': renderSavedPage(main);    break;
      case 'settings': renderSettingsPage(main); break;
      case 'post': renderPostDetailPage(main, params[0]); break;
      default:
        main.innerHTML = `<div class="empty-state" style="padding:var(--s8)"><p>Page not found.</p><a href="#feed" class="btn btn-ghost btn-sm" style="margin-top:var(--s3)">Go home</a></div>`;
    }
  };

  window.addEventListener('hashchange', navigate);
  navigate();
}

function setActiveNavLink(route) {
  document.querySelectorAll('[data-route]').forEach(el => {
    el.classList.toggle('active', el.dataset.route === route);
  });
}


function openNewPostModal() {
  const m = modal({
    title: 'New post',
    content: `
      <div class="flex-col gap-4">
        <div id="post-drop-zone" style="
          border: 2px dashed var(--border); border-radius: var(--r-md);
          padding: var(--s7); text-align: center; cursor: pointer;
          transition: border-color var(--t-fast), background var(--t-fast);
        ">
          <input type="file" id="post-files" accept="image/*,video/*" multiple style="display:none" />
          <div id="post-drop-content">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin:0 auto;opacity:.4">
              <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
            </svg>
            <p style="margin-top:var(--s2);color:var(--text-muted);font-size:.88rem">Drag & drop or click to select</p>
            <p style="font-size:.78rem;color:var(--text-muted);margin-top:4px">Up to 10 files · Images or videos</p>
          </div>
          <div id="post-previews" style="display:none;flex-wrap:wrap;gap:var(--s2);justify-content:center"></div>
        </div>

        <div class="input-group">
          <label>Caption</label>
          <textarea id="post-caption" class="input" rows="3" placeholder="Write a caption…" maxlength="2200" style="resize:vertical"></textarea>
        </div>

        <div class="input-group">
          <label>Location</label>
          <input id="post-location" type="text" class="input" placeholder="Add location" />
        </div>

        <div class="flex gap-4" style="flex-wrap:wrap">
          <label style="display:flex;align-items:center;gap:var(--s2);font-size:.85rem;cursor:pointer">
            <input type="checkbox" id="post-hide-likes" /> Hide like count
          </label>
          <label style="display:flex;align-items:center;gap:var(--s2);font-size:.85rem;cursor:pointer">
            <input type="checkbox" id="post-disable-comments" /> Disable comments
          </label>
        </div>
      </div>
    `,
    footer: `
      <div class="flex gap-3" style="justify-content:flex-end">
        <button class="btn btn-ghost btn-sm" id="post-cancel">Cancel</button>
        <button class="btn btn-primary btn-sm" id="post-submit" disabled>Share post</button>
      </div>
    `,
  });

  m.el.querySelector('#post-cancel').addEventListener('click', m.close);

  const dropZone   = m.el.querySelector('#post-drop-zone');
  const fileInput  = m.el.querySelector('#post-files');
  const previewsEl = m.el.querySelector('#post-previews');
  const dropContent = m.el.querySelector('#post-drop-content');
  const submitBtn  = m.el.querySelector('#post-submit');
  let selectedFiles = [];

  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--accent)'; dropZone.style.background = 'var(--accent-dim)'; });
  dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = ''; dropZone.style.background = ''; });
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault(); dropZone.style.borderColor = ''; dropZone.style.background = '';
    handleFiles([...e.dataTransfer.files]);
  });
  fileInput.addEventListener('change', () => handleFiles([...fileInput.files]));

  function handleFiles(files) {
    selectedFiles = files.slice(0, 10);
    previewsEl.innerHTML = '';
    if (selectedFiles.length === 0) return;

    dropContent.style.display = 'none';
    previewsEl.style.display  = 'flex';
    selectedFiles.forEach((f, i) => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'position:relative;width:80px;height:80px;border-radius:var(--r-sm);overflow:hidden;background:var(--bg-raised)';
      if (f.type.startsWith('image/')) {
        const img = document.createElement('img');
        img.style.cssText = 'width:100%;height:100%;object-fit:cover';
        img.src = URL.createObjectURL(f);
        wrap.appendChild(img);
      } else {
        wrap.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:.75rem;text-align:center;padding:4px">▶<br/>${f.name.slice(0,12)}</div>`;
      }
      previewsEl.appendChild(wrap);
    });
    submitBtn.disabled = false;
  }

  submitBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<div class="spinner"></div>';
    try {
      await api.posts.create({
        caption:         m.el.querySelector('#post-caption').value.trim(),
        locationName:    m.el.querySelector('#post-location').value.trim(),
        hideLikeCount:   m.el.querySelector('#post-hide-likes').checked,
        disableComments: m.el.querySelector('#post-disable-comments').checked,
      }, selectedFiles);
      m.close();
      toast('Post shared!', 'success');
      if (window.location.hash === '#feed' || window.location.hash === '') {
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      } else {
        window.location.hash = '#feed';
      }
    } catch (err) {
      toastError(err.message || 'Failed to create post');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Share post';
    }
  });
}

async function renderSavedPage(container) {
  container.innerHTML = `
    <div class="page-header"><h1 class="page-title">Saved</h1></div>
    <div style="padding:var(--s4)">
      <div id="saved-grid" class="post-grid" style="max-width:900px;margin:0 auto;padding:2px"></div>
      <div id="saved-loader" style="text-align:center;padding:var(--s6)"><div class="spinner" style="margin:0 auto"></div></div>
    </div>
  `;

  try {
    const posts = await api.posts.getSaved({ limit: 30 });
    const grid   = container.querySelector('#saved-grid');
    container.querySelector('#saved-loader').style.display = 'none';

    if (posts.length === 0) {
      grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;padding:var(--s8)"><p>Nothing saved yet.</p></div>';
    } else {
      const { buildGridItem } = await import('./profile.js').catch(() => ({ buildGridItem: null }));
      posts.forEach(p => {
        const item = document.createElement('div');
        item.className = 'post-grid-item';
        const img = document.createElement('img');
        img.src = getMediaUrl(p.media_items?.[0]);
        img.loading = 'lazy'; img.alt = '';
        item.appendChild(img);
        item.addEventListener('click', () => { window.location.hash = `#post/${p.id}`; });
        grid.appendChild(item);
      });
    }
  } catch (err) { console.error('Saved error:', err); toastError('Failed to load saved posts'); }
}

async function renderExplorePage(container) {
  container.innerHTML = `
    <div class="page-header"><h1 class="page-title">Explore</h1></div>
    <div style="padding:var(--s4) var(--s5) 0">
      <div style="position:relative;max-width:480px">
        <input id="explore-search" type="text" class="input" placeholder="Search people by username…"
          style="padding-left:40px" />
        <svg style="position:absolute;left:12px;top:50%;transform:translateY(-50%);opacity:.4;pointer-events:none"
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <div id="search-results" style="margin-top:var(--s3);max-width:480px"></div>
    </div>

    <div style="padding:var(--s4) var(--s5)">
      <p style="font-size:.78rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--text-muted);margin-bottom:var(--s3)">Latest posts</p>
      <div id="explore-grid" class="post-grid" style="max-width:900px"></div>
      <div id="explore-loader" style="text-align:center;padding:var(--s6)">
        <div class="spinner" style="margin:0 auto"></div>
      </div>
    </div>
  `;

  const searchEl   = container.querySelector('#explore-search');
  const resultsEl  = container.querySelector('#search-results');
  let searchTimeout;

  searchEl.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const q = searchEl.value.trim();
    if (!q) { resultsEl.innerHTML = ''; return; }
    searchTimeout = setTimeout(async () => {
      resultsEl.innerHTML = '<div style="padding:var(--s3);color:var(--text-muted);font-size:.85rem">Searching…</div>';
      try {
        const users = await api.users.search({ username: q, limit: 8 });
        if (users.length === 0) {
          resultsEl.innerHTML = '<div style="padding:var(--s3);color:var(--text-muted);font-size:.85rem">No users found.</div>';
          return;
        }
        resultsEl.innerHTML = '';
        const list = document.createElement('div');
        list.className = 'card';
        list.style.overflow = 'hidden';
        users.forEach(u => {
          const row = document.createElement('a');
          row.href = `#profile/${u.username}`;
          row.style.cssText = 'display:flex;align-items:center;gap:var(--s3);padding:var(--s3) var(--s4);transition:background var(--t-fast);text-decoration:none';
          row.onmouseenter = () => row.style.background = 'var(--bg-raised)';
          row.onmouseleave = () => row.style.background = '';
          const av = buildAvatar({ src: u.profile?.avatar_path || u.avatar_url, username: u.username, size: 'sm' });
          row.appendChild(av);
          row.innerHTML += `
            <div style="flex:1;min-width:0">
              <div style="font-size:.88rem;font-weight:600">${escHtml(u.username)}</div>
              ${(u.profile?.full_name||u.full_name) ? `<div style="font-size:.78rem;color:var(--text-muted)">${escHtml(u.profile?.full_name||u.full_name||'')}</div>` : ''}
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:.4;flex-shrink:0">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          `;
          list.appendChild(row);
        });
        resultsEl.appendChild(list);
      } catch(err) { console.error('Search error:', err); resultsEl.innerHTML = '<div style="padding:var(--s3);color:var(--danger);font-size:.85rem">Search failed.</div>'; }
    }, 350);
  });

  try {
    const posts = await api.posts.getExploreFeed({ limit: 30 });
    if (!container.isConnected) return;

    const grid   = container.querySelector('#explore-grid');
    const loader = container.querySelector('#explore-loader');
    if (!grid || !loader) return;

    loader.style.display = 'none';
    if (posts.length === 0) {
      grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1;padding:var(--s8)"><p>No posts yet.</p></div>';
    } else {
      posts.forEach(p => {
        const item = document.createElement('div');
        item.className = 'post-grid-item';
        const img = document.createElement('img');
        img.src = getMediaUrl(p.media_items?.[0]);
        img.alt = ''; img.loading = 'lazy';
        const overlay = document.createElement('div');
        overlay.className = 'post-grid-overlay';
        overlay.innerHTML = `
          <div class="grid-stat"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>${p.like_count||0}</div>
          <div class="grid-stat"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>${p.comment_count||0}</div>
        `;
        item.appendChild(img);
        item.appendChild(overlay);
        item.addEventListener('click', () => { window.location.hash = `#post/${p.id}`; });
        grid.appendChild(item);
      });
    }
  } catch(err) {
    console.error('Explore posts error:', err);
    if (!container.isConnected) return;

    const loader = container.querySelector('#explore-loader');
    if (loader) {
      loader.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">Could not load posts.</p>';
    }
  }
}

async function renderSettingsPage(container) {
  const user = getCurrentUser();
  container.innerHTML = `
    <div class="page-header"><h1 class="page-title">Settings</h1></div>
    <div style="padding:var(--s5) var(--s6);max-width:600px;width:100%">

      <!-- Avatar section -->
      <div class="card" style="padding:var(--s5);margin-bottom:var(--s4)">
        <div style="display:flex;align-items:center;gap:var(--s4)">
          <div id="settings-avatar-slot"></div>
          <div>
            <div style="font-size:.95rem;font-weight:600">${escHtml(user?.username || '')}</div>
            <input type="file" id="avatar-file" accept="image/*" style="display:none" />
            <button class="btn btn-ghost btn-sm" id="change-avatar-btn" style="margin-top:var(--s2)">Change photo</button>
          </div>
        </div>
      </div>

      <!-- Edit profile form -->
      <div class="card" style="padding:var(--s5);margin-bottom:var(--s4)">
        <h2 style="font-family:var(--font-serif);font-size:1.1rem;margin-bottom:var(--s5)">Edit profile</h2>
        <form id="settings-form" class="flex-col gap-4">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--s3)">
            <div class="input-group">
              <label>First name</label>
              <input name="first_name" type="text" class="input" value="${escHtml(user?.profile?.full_name?.split(' ')[0] || user?.first_name || '')}" />
            </div>
            <div class="input-group">
              <label>Last name</label>
              <input name="last_name" type="text" class="input" value="${escHtml(user?.profile?.full_name?.split(' ').slice(1).join(' ') || user?.last_name || '')}" />
            </div>
          </div>
          <div class="input-group">
            <label>Username</label>
            <input name="username" type="text" class="input" value="${escHtml(user?.username || '')}" />
          </div>
          <div class="input-group">
            <label>Bio</label>
            <textarea name="bio" class="input" rows="3" maxlength="150" style="resize:vertical">${escHtml(user?.profile?.bio || user?.bio || '')}</textarea>
            <span style="font-size:.72rem;color:var(--text-muted);text-align:right" id="bio-count">${(user?.bio||'').length}/150</span>
          </div>
          <div class="input-group">
            <label>Website</label>
            <input name="website" type="url" class="input" value="${escHtml(user?.profile?.website || user?.website || '')}" placeholder="https://..." />
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--s3) var(--s4);background:var(--bg-raised);border-radius:var(--r-md)">
            <div>
              <div style="font-size:.88rem;font-weight:500">Private account</div>
              <div style="font-size:.78rem;color:var(--text-muted)">Only approved followers can see your posts</div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" name="is_private" ${user?.is_private ? 'checked' : ''} id="private-toggle" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div style="display:flex;justify-content:flex-end">
            <button type="submit" class="btn btn-primary" id="save-settings-btn">Save changes</button>
          </div>
        </form>
      </div>

      <!-- Danger zone -->
      <div class="card" style="padding:var(--s5);border-color:rgba(224,92,92,0.2)">
        <h3 style="font-size:.9rem;font-weight:600;color:var(--danger);margin-bottom:var(--s2)">Danger zone</h3>
        <p style="font-size:.82rem;color:var(--text-muted);margin-bottom:var(--s4)">Once deleted, your account and all data cannot be recovered.</p>
        <button class="btn btn-danger btn-sm" id="delete-account-btn">Delete my account</button>
      </div>
    </div>
  `;

  injectSettingsStyles();

  const bioEl    = container.querySelector('[name="bio"]');
  const bioCount = container.querySelector('#bio-count');
  bioEl?.addEventListener('input', () => { bioCount.textContent = bioEl.value.length + '/150'; });

  const slot = container.querySelector('#settings-avatar-slot');
  slot.appendChild(buildAvatar({ src: user?.profile?.avatar_path || user?.avatar_url, username: user?.username, size: 'lg' }));
  container.querySelector('#change-avatar-btn').addEventListener('click', () => container.querySelector('#avatar-file').click());
  container.querySelector('#avatar-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      await api.users.uploadAvatar(file);
      toast('Avatar updated!', 'success');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    } catch(err) { 
      console.error("App Avatar ", err)
      toastError('Failed to upload'); }
  });

  container.querySelector('#settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = container.querySelector('#save-settings-btn');
    btn.disabled = true; btn.textContent = 'Saving…';
    const fd = new FormData(e.target);
    const data = {};
    fd.forEach((v, k) => { data[k] = v; });
    data.is_private = fd.has('is_private');
    try {
      const accountFields = {};
      const profileFields = {};
      ['username', 'is_private'].forEach(k => { if (data[k] !== undefined) accountFields[k] = data[k]; });
      ['bio', 'website', 'full_name'].forEach(k => { if (data[k] !== undefined) profileFields[k] = data[k]; });
      const fn = (data.first_name || '').trim();
      const ln = (data.last_name  || '').trim();
      if (fn || ln) profileFields.full_name = [fn, ln].filter(Boolean).join(' ');
      if (Object.keys(accountFields).length) await api.users.updateMe(accountFields);
      if (Object.keys(profileFields).length)  await api.users.updateProfile(profileFields);
      toast('Profile updated!', 'success');
    } catch (err) { toastError(err.message || 'Failed to save'); }
    finally { btn.disabled = false; btn.textContent = 'Save changes'; }
  });

  container.querySelector('#delete-account-btn').addEventListener('click', async () => {
    const ok = await confirm({ title: 'Delete account?', message: 'This is permanent and cannot be undone.', confirmLabel: 'Delete', danger: true });
    if (!ok) return;
    try {
      await api.users.deleteMe();
      api.storage.clearTokens();
      window.location.hash = '#login';
    } catch(err) {
      console.error("Delete account: ", err)
      toastError('Failed to delete account'); }
  });
}

async function renderPostDetailPage(container, postId) {
  container.innerHTML = `
    <div class="page-header">
      <button class="btn-icon" onclick="history.back()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
      </button>
      <h1 class="page-title">Post</h1>
    </div>
    <div class="page-body">
      <div id="post-detail-slot"></div>
      <div id="comments-section" style="margin-top:var(--s4)"></div>
    </div>
  `;

  try {
    const { buildPostCard } = await import('./feed.js');
    const post = await api.posts.getById(postId);
    container.querySelector('#post-detail-slot').appendChild(buildPostCard(post));

    await loadFullComments(container, postId);
  } catch(err) {
    console.error("Post Detail Page: ", err)
    container.querySelector('#post-detail-slot').innerHTML = '<div class="empty-state"><p>Post not found.</p></div>';
  }
}

async function loadFullComments(container, postId) {
  const section = container.querySelector('#comments-section');
  section.innerHTML = `<div style="padding:var(--s3);font-weight:600;font-size:.88rem">Comments</div>`;

  try {
    const comments = await api.posts.getComments(postId, { limit: 50, includeReplies: true });
    if (comments.length === 0) {
      section.innerHTML += '<div class="empty-state" style="padding:var(--s5)"><p style="color:var(--text-muted)">No comments yet.</p></div>';
      return;
    }
    comments.forEach(c => section.appendChild(buildCommentItem(c, postId)));
  } catch(err) {
    console.error("loadFullComments: ", err)
     }
}

function buildCommentItem(comment, postId) {
  const item = document.createElement('div');
  item.className = 'comment-item';
  const avatar = buildAvatar({ src: comment.author_avatar, username: comment.author_username, size: 'xs' });
  item.appendChild(avatar);
  item.innerHTML += `
    <div class="comment-body">
      <span class="comment-author">${escHtml(comment.author_username || '')}</span>
      <div class="comment-text">${escHtml(comment.content || '')}</div>
      <div class="comment-actions">
        <span class="comment-action" style="color:var(--text-muted);font-size:.75rem">${relativeTime(comment.created_at)}</span>
        <button class="comment-action like-comment" data-comment-id="${comment.id}" data-liked="${comment.is_liked || false}">
          ${comment.is_liked ? '♥' : '♡'} ${comment.like_count || 0}
        </button>
        <button class="comment-action reply-btn" data-comment-id="${comment.id}">Reply</button>
      </div>
      ${comment.replies?.length ? `<div class="comment-replies" id="replies-${comment.id}"></div>` : ''}
    </div>
  `;
  item.prepend(avatar);

  item.querySelector('.like-comment')?.addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    const isLiked = btn.dataset.liked === 'true';
    try {
      if (isLiked) await api.posts.unlikeComment(comment.id);
      else         await api.posts.likeComment(comment.id);
      btn.dataset.liked = String(!isLiked);
      btn.classList.toggle('liked', !isLiked);
    } catch(err) { 
      console.error("buildCommentItem: ", err)
      }
  });

  item.querySelector('.reply-btn')?.addEventListener('click', () => {
    const body = item.querySelector('.comment-body');
    const existing = body.querySelector('.reply-form');
    if (existing) {
      existing.querySelector('textarea')?.focus();
      return;
    }

    const form = document.createElement('div');
    form.className = 'reply-form';
    form.style.cssText = 'display:flex;gap:var(--s2);align-items:flex-end;margin-top:var(--s2)';
    form.innerHTML = `
      <textarea class="input reply-field" rows="1" maxlength="500" placeholder="Reply to ${escHtml(comment.author_username || 'comment')}..." style="resize:none;min-height:38px"></textarea>
      <button class="btn btn-primary btn-sm reply-submit" disabled>Reply</button>
      <button class="btn btn-ghost btn-sm reply-cancel">Cancel</button>
    `;
    body.appendChild(form);

    const field = form.querySelector('.reply-field');
    const submit = form.querySelector('.reply-submit');
    field.addEventListener('input', () => {
      submit.disabled = field.value.trim().length === 0;
      field.style.height = 'auto';
      field.style.height = field.scrollHeight + 'px';
    });
    form.querySelector('.reply-cancel').addEventListener('click', () => form.remove());
    submit.addEventListener('click', async () => {
      const text = field.value.trim();
      if (!text) return;
      submit.disabled = true;
      try {
        const reply = await api.posts.addComment(postId, text, comment.id);
        let repliesEl = item.querySelector(`#replies-${comment.id}`);
        if (!repliesEl) {
          repliesEl = document.createElement('div');
          repliesEl.className = 'comment-replies';
          repliesEl.id = `replies-${comment.id}`;
          body.appendChild(repliesEl);
        }
        repliesEl.appendChild(buildReplyItem(reply));
        form.remove();
      } catch(err) {
        console.error("reply comment: ", err);
        toastError('Failed to reply');
        submit.disabled = false;
      }
    });
    field.focus();
  });

  const repliesEl = item.querySelector(`#replies-${comment.id}`);
  if (repliesEl && comment.replies) {
    comment.replies.forEach(r => {
      repliesEl.appendChild(buildReplyItem(r));
    });
  }

  return item;
}

function buildReplyItem(reply) {
  const item = document.createElement('div');
  item.className = 'comment-item';
  item.innerHTML = `
    <div class="comment-body">
      <span class="comment-author">${escHtml(reply.author_username || '')}</span>
      <div class="comment-text">${escHtml(reply.content || '')}</div>
      <div class="comment-actions">
        <span class="comment-action" style="color:var(--text-muted);font-size:.75rem">${relativeTime(reply.created_at)}</span>
      </div>
    </div>
  `;
  return item;
}

async function handleLogout() {
  setCurrentUser(null);
  await api.auth.logout();
  window.location.hash = '#login';
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function escHtml(str = '') {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function getMediaUrl(media) {
  return media?.media_path || media?.url || media?.thumbnail_path || '';
}

function injectSettingsStyles() {
  if (document.getElementById('settings-styles')) return;
  const s = document.createElement('style');
  s.id = 'settings-styles';
  s.textContent = `
    .toggle-switch { position:relative; display:inline-block; width:44px; height:24px; flex-shrink:0; cursor:pointer; }
    .toggle-switch input { opacity:0; width:0; height:0; }
    .toggle-slider {
      position:absolute; inset:0;
      background:var(--bg-raised); border:1px solid var(--border);
      border-radius:var(--r-full); transition:all var(--t-fast);
    }
    .toggle-slider::before {
      content:''; position:absolute;
      width:18px; height:18px; left:2px; top:2px;
      background:var(--text-muted); border-radius:50%;
      transition:all var(--t-fast);
    }
    .toggle-switch input:checked + .toggle-slider { background:var(--accent); border-color:var(--accent); }
    .toggle-switch input:checked + .toggle-slider::before { transform:translateX(20px); background:#1a1400; }
  `;
  document.head.appendChild(s);
}
