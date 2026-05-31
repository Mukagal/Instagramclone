import api from './api.js';
import { toast, toastError, buildAvatar, relativeTime, attachEmojiPicker, confirm, modal } from './ui.js';
import { getCurrentUser } from './auth.js';

let activeThreadId = null;
let messagesBefore = null;   
let loadingMessages = false;
let hasMoreMessages = true;

export async function renderMessagesPage(container, openThreadId = null) {
  const hasOpenThread = Boolean(openThreadId);
  container.innerHTML = `
    <div class="messages-layout ${hasOpenThread ? 'chat-mode' : 'list-mode'}" style="height:100vh">
      <!-- Thread list -->
      <div class="threads-list" id="threads-list">
        <div class="threads-header">
          <span class="threads-title">Messages</span>
          <button class="btn-icon" id="new-group-btn" title="New group">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
          </button>
        </div>
        <div class="threads-search">
          <input type="text" class="input" id="thread-search" placeholder="Search conversations…" />
        </div>
        <div class="thread-items" id="thread-items">
          <div style="padding:var(--s5);text-align:center"><div class="spinner" style="margin:0 auto"></div></div>
        </div>
      </div>

      <!-- Chat window -->
      <div class="chat-window" id="chat-window">
        <div class="empty-state" style="flex:1">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <p style="color:var(--text-muted)">Select a conversation</p>
        </div>
      </div>
    </div>
  `;

  await loadThreadList(container);

  container.querySelector('#new-group-btn').addEventListener('click', () => openNewGroupModal(container));

  const searchEl = container.querySelector('#thread-search');
  searchEl.addEventListener('input', () => filterThreadItems(container, searchEl.value.trim().toLowerCase()));

  if (openThreadId) openChatWindow(container, parseInt(openThreadId));
}

async function loadThreadList(container) {
  const listEl = container.querySelector('#thread-items');
  try {
    const threads = await api.messages.getThreads({ limit: 50 });
    listEl.innerHTML = '';
    if (threads.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>No conversations yet.</p></div>';
      return;
    }
    threads.forEach(t => listEl.appendChild(buildThreadItem(t, container)));
  } catch(err) {
    console.error("loadThreadList: ", err)
    listEl.innerHTML = '<div class="empty-state"><p>Failed to load.</p></div>';
  }
}

function buildThreadItem(thread, container) {
  const item = document.createElement('div');
  item.className = 'thread-item';
  item.dataset.threadId = thread.id;

  const name = getThreadName(thread);
  const preview = thread.last_message_preview || '';
  const unread  = thread.unread_count > 0;

  const _otherMember = !thread.is_group ? (thread.members || []).find(m => m.user_id !== getCurrentUser()?.id) : null;
  const avatarSrc = thread.is_group ? thread.group_cover_path : _otherMember?.avatar_path;
  const avatarUser = thread.is_group ? name : _otherMember?.username;
  const avatar = buildAvatar({ src: avatarSrc, username: avatarUser, size: 'sm' });

  item.appendChild(avatar);
  item.innerHTML += `
    <div class="thread-info">
      <div class="thread-name">
        <span>${escHtml(name)}</span>
        <span class="thread-time">${thread.last_message_at ? relativeTime(thread.last_message_at) : ''}</span>
      </div>
      <div class="thread-preview ${unread ? 'unread' : ''}">${escHtml(preview)}</div>
    </div>
    ${unread ? `<div class="thread-unread-dot"></div>` : ''}
  `;
  item.addEventListener('click', () => openChatWindow(container, thread.id));
  return item;
}

function filterThreadItems(container, query) {
  container.querySelectorAll('.thread-item').forEach(item => {
    const name = item.querySelector('.thread-name span')?.textContent.toLowerCase() || '';
    item.style.display = !query || name.includes(query) ? '' : 'none';
  });
}

async function openChatWindow(container, threadId) {
  container.querySelector('.messages-layout')?.classList.replace('list-mode', 'chat-mode');

  container.querySelectorAll('.thread-item').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.threadId) === threadId);
  });

  activeThreadId = threadId;
  messagesBefore = null;
  hasMoreMessages = true;
  loadingMessages = false;

  const chatWin = container.querySelector('#chat-window');
  chatWin.innerHTML = `
    <div class="chat-header" id="chat-header">
      <div class="spinner" style="margin:0 auto"></div>
    </div>
    <div class="messages-area" id="messages-area">
      <div style="text-align:center;padding:var(--s4)"><div class="spinner" style="margin:0 auto"></div></div>
    </div>
    <div class="chat-input-area" id="chat-input-area" style="display:none"></div>
  `;

  let thread;
  try {
    thread = await api.messages.getThread(threadId);
  } catch(err) {
    console.error("openChatWindow: ", err)
    chatWin.innerHTML = '<div class="empty-state"><p>Could not load thread.</p></div>';
    return;
  }

  renderChatHeader(container, thread);
  renderChatInputArea(container, threadId);
  await loadMessages(container, threadId, true);

  const area = container.querySelector('#messages-area');
  area.scrollTop = area.scrollHeight;

  area.addEventListener('scroll', () => {
    if (area.scrollTop < 120 && !loadingMessages && hasMoreMessages) {
      loadMessages(container, threadId, false);
    }
  });
}

function renderChatHeader(container, thread) {
  const headerEl = container.querySelector('#chat-header');
  const name = getThreadName(thread);
  const _om = !thread.is_group ? (thread.members||[]).find(m=>m.user_id!==getCurrentUser()?.id) : null;
  const avatarSrc = thread.is_group ? thread.group_cover_path : _om?.avatar_path;
  const avatar = buildAvatar({ src: avatarSrc, username: name, size: 'sm' });

  headerEl.innerHTML = '';
  headerEl.appendChild(avatar);

  const info = document.createElement('div');
  info.innerHTML = `
    <div class="chat-title">${escHtml(name)}</div>
    <div class="chat-subtitle">
      ${thread.is_group
        ? `${(thread.members||[]).filter(m=>!m.left_at).length} members`
        : ''}
    </div>
  `;
  headerEl.appendChild(info);

  const actions = document.createElement('div');
  actions.className = 'chat-header-actions';

  if (thread.is_group) {
    const manageBtn = document.createElement('button');
    manageBtn.className = 'btn btn-ghost btn-sm';
    manageBtn.textContent = 'Manage';
    manageBtn.addEventListener('click', () => openGroupManageModal(thread));
    actions.appendChild(manageBtn);
  }

  const leaveBtn = document.createElement('button');
  leaveBtn.className = 'btn-icon';
  leaveBtn.title = 'Leave / close';
  leaveBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>`;
  leaveBtn.addEventListener('click', async () => {
    if (!thread.is_group) return;
    const ok = await confirm({ title: 'Leave group?', danger: true, confirmLabel: 'Leave' });
    if (!ok) return;
    try { await api.messages.leaveThread(thread.id); window.location.hash = '#messages'; toast('Left group', 'success'); }
    catch(err) { 
      console.error("renderChatHeader: ", err)
      toastError('Failed to leave'); }
  });
  actions.appendChild(leaveBtn);
  headerEl.appendChild(actions);
}

async function loadMessages(container, threadId, reset = false) {
  if (loadingMessages) return;
  loadingMessages = true;
  const area = container.querySelector('#messages-area');
  if (!area) { loadingMessages = false; return; }

  const prevHeight = area.scrollHeight;

  try {
    const items = await api.messages.getMessages(threadId, { limit: 30, beforeId: messagesBefore });
    if (items.length === 0) {
      hasMoreMessages = false;
      if (reset) {
        area.innerHTML = '<div class="empty-state" style="height:100%"><p>No messages yet.</p></div>';
      }
      return;
    }

    messagesBefore = items[0].id;
    if (items.length < 30) hasMoreMessages = false;

    if (reset) area.innerHTML = '';

    const fragment = buildMessageGroups(items, reset);
    if (reset) area.appendChild(fragment);
    else area.insertBefore(fragment, area.firstChild);

    if (!reset) area.scrollTop = area.scrollHeight - prevHeight;
  } catch(err) {
    console.error("loadMessages: ", err)
    toastError('Failed to load messages');
  } finally {
    loadingMessages = false;
  }
}

function buildMessageGroups(messages, isBottom = true) {
  const me = getCurrentUser();
  const fragment = document.createDocumentFragment();
  let lastDate = null;

  messages.forEach(msg => {
    const sentAt = msg.sent_at || msg.created_at || new Date().toISOString();

    const msgDate = new Date(sentAt).toDateString();
    if (msgDate !== lastDate) {
      const sep = document.createElement('div');
      sep.className = 'day-separator';
      sep.textContent = new Date(sentAt).toLocaleDateString(undefined, { weekday:'short', month:'short', day:'numeric' });
      fragment.appendChild(sep);
      lastDate = msgDate;
    }

    const isOwn = me && msg.sender_id === me.id;
    const group = document.createElement('div');
    group.className = `msg-group ${isOwn ? 'outgoing' : 'incoming'}`;
    group.dataset.msgId = msg.id;

    const row = document.createElement('div');
    row.className = 'msg-row';

    if (!isOwn) {
      const avatar = buildAvatar({ src: msg.sender_avatar, username: msg.sender_username, size: 'xs' });
      row.appendChild(avatar);
    }

    const bubbleWrap = document.createElement('div');

    if (msg.media_path && !msg.is_deleted) {
      const imgWrap = document.createElement('div');
      imgWrap.className = 'msg-image';
      if (msg.message_type === 'video') {
        imgWrap.innerHTML = `<video src="${escHtml(msg.media_path)}" controls style="max-width:240px;border-radius:var(--r-md)"></video>`;
      } else {
        imgWrap.innerHTML = `<img src="${escHtml(msg.media_path)}" alt="attachment" />`;
        imgWrap.querySelector('img').addEventListener('click', () => openLightbox(msg.media_path));
      }
      bubbleWrap.appendChild(imgWrap);
    }

    if (msg.content && !msg.is_deleted) {
      const bubble = document.createElement('div');
      bubble.className = 'msg-bubble';
      bubble.textContent = msg.content;
      bubbleWrap.appendChild(bubble);
    }

    if (msg.is_deleted) {
      const unsent = document.createElement('div');
      unsent.className = 'msg-bubble';
      unsent.style.cssText = 'color:var(--text-muted);font-style:italic;font-size:.82rem';
      unsent.textContent = 'Message unsent';
      bubbleWrap.appendChild(unsent);
    }

    if (msg.reactions?.length) {
      const reactRow = document.createElement('div');
      reactRow.className = 'msg-reactions';
      const grouped = groupReactions(msg.reactions);
      Object.entries(grouped).forEach(([emoji, count]) => {
        const pill = document.createElement('button');
        pill.className = 'reaction-pill';
        pill.innerHTML = `${emoji} <span>${count}</span>`;
        pill.addEventListener('click', () => toggleReaction(pill, msg.id, emoji));
        reactRow.appendChild(pill);
      });
      bubbleWrap.appendChild(reactRow);
    }

    const meta = document.createElement('div');
    meta.className = 'msg-meta';
    meta.textContent = relativeTime(sentAt);
    if (isOwn) meta.textContent += ' · Sent';
    bubbleWrap.appendChild(meta);

    row.appendChild(bubbleWrap);
    group.appendChild(row);
    attachMessageContextMenu(group, msg, isOwn);
    fragment.appendChild(group);
  });

  return fragment;
}

function attachMessageContextMenu(group, msg, isOwn) {
  group.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const existing = document.querySelector('.msg-context-menu');
    existing?.remove();

    const menu = document.createElement('div');
    menu.className = 'msg-context-menu';
    menu.style.cssText = `
      position:fixed;top:${e.clientY}px;left:${e.clientX}px;
      background:var(--bg-raised);border:1px solid var(--border);
      border-radius:var(--r-md);padding:var(--s2);min-width:150px;
      box-shadow:var(--shadow-md);z-index:600;
    `;

    const reactItem = createMenuItem('React', '😀', () => {
      menu.remove();
      promptReaction(msg.id);
    });
    menu.appendChild(reactItem);

    if (isOwn && !msg.is_deleted) {
      const unsendItem = createMenuItem('Unsend', '🗑', async () => {
        menu.remove();
        const ok = await confirm({ title: 'Unsend message?', danger: true, confirmLabel: 'Unsend' });
        if (!ok) return;
        try {
          await api.messages.unsendMessage(msg.id);
          group.querySelector('.msg-bubble').style.cssText = 'color:var(--text-muted);font-style:italic';
          group.querySelector('.msg-bubble').textContent = 'Message unsent';
        } catch(err) { 
          console.error("attachMessageContextMenu: ", err)
          toastError('Failed to unsend'); }
      });
      unsendItem.style.color = 'var(--danger)';
      menu.appendChild(unsendItem);
    }

    document.body.appendChild(menu);
    setTimeout(() => document.addEventListener('click', function h() { menu.remove(); document.removeEventListener('click', h); }, 0));
  });
}

function createMenuItem(label, icon, onClick) {
  const btn = document.createElement('button');
  btn.style.cssText = 'display:flex;align-items:center;gap:8px;padding:8px 12px;width:100%;border-radius:var(--r-sm);font-size:.85rem;transition:background var(--t-fast)';
  btn.innerHTML = `<span>${icon}</span> ${escHtml(label)}`;
  btn.onmouseenter = () => btn.style.background = 'var(--bg-surface)';
  btn.onmouseleave = () => btn.style.background = '';
  btn.addEventListener('click', onClick);
  return btn;
}

async function promptReaction(msgId) {
  const emojis = ['❤️','😂','😮','😢','😡','👍','🔥','🎉','👀','💯'];
  const m = modal({
    title: 'React',
    content: `<div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center">
      ${emojis.map(e => `<button class="react-emoji-btn" data-emoji="${e}" style="font-size:1.8rem;background:none;border:none;cursor:pointer;padding:6px;border-radius:8px;transition:background 120ms">${e}</button>`).join('')}
    </div>`,
  });
  m.el.querySelectorAll('.react-emoji-btn').forEach(btn => {
    btn.addEventListener('mouseenter', () => btn.style.background = 'var(--bg-raised)');
    btn.addEventListener('mouseleave', () => btn.style.background = 'none');
    btn.addEventListener('click', async () => {
      m.close();
      try { await api.messages.addReaction(msgId, btn.dataset.emoji); toast('Reaction added', 'success', 1500); }
      catch(err) { 
        console.error("promptReaction: ", err)
        toastError('Failed to react'); }
    });
  });
}

async function toggleReaction(pill, msgId, emoji) {
  const isOwn = pill.classList.contains('own');
  try {
    if (isOwn) { await api.messages.removeReaction(msgId); pill.classList.remove('own'); }
    else { await api.messages.addReaction(msgId, emoji); pill.classList.add('own'); }
  } catch(err) { 
    console.error("toggleReaction: ", err)
    toastError('Failed'); }
}

function groupReactions(reactions) {
  const map = {};
  reactions.forEach(r => { map[r.emoji] = (map[r.emoji] || 0) + 1; });
  return map;
}

function renderChatInputArea(container, threadId) {
  const area = container.querySelector('#chat-input-area');
  area.style.display = '';
  area.innerHTML = `
    <button class="btn-icon" id="attach-btn" title="Attach file">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
      </svg>
    </button>
    <input type="file" id="file-input" accept="image/*,video/*,audio/*" style="display:none" />
    <div class="chat-input-wrap">
      <button class="chat-emoji-btn" id="emoji-btn">😊</button>
      <textarea class="chat-textarea" id="chat-textarea" rows="1" placeholder="Message…"></textarea>
    </div>
    <button class="chat-send-btn" id="send-btn" disabled>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  `;

  const textarea = area.querySelector('#chat-textarea');
  const sendBtn = area.querySelector('#send-btn');
  const fileInput = area.querySelector('#file-input');
  let pendingFile = null;

  textarea.addEventListener('input', () => {
    sendBtn.disabled = !textarea.value.trim() && !pendingFile;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  });

  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click(); }
  });

  area.querySelector('#attach-btn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    pendingFile = fileInput.files[0] || null;
    if (pendingFile) {
      sendBtn.disabled = false;
      const preview = area.querySelector('#file-preview');
      if (!preview) {
        const p = document.createElement('div');
        p.id = 'file-preview';
        p.style.cssText = 'position:absolute;bottom:calc(100% + 4px);left:var(--s4);background:var(--bg-raised);border:1px solid var(--border);border-radius:var(--r-md);padding:6px 10px;font-size:.8rem;display:flex;align-items:center;gap:8px';
        p.innerHTML = `<span>📎 ${escHtml(pendingFile.name)}</span><button id="remove-file" style="color:var(--danger);font-size:.75rem">✕</button>`;
        area.style.position = 'relative';
        area.appendChild(p);
        p.querySelector('#remove-file').addEventListener('click', () => {
          pendingFile = null; fileInput.value = ''; p.remove();
          sendBtn.disabled = !textarea.value.trim();
        });
      }
    }
  });

  attachEmojiPicker(area.querySelector('#emoji-btn'), (emoji) => {
    textarea.value += emoji;
    textarea.dispatchEvent(new Event('input'));
    textarea.focus();
  });

  sendBtn.addEventListener('click', async () => {
    const text = textarea.value.trim();
    if (!text && !pendingFile) return;

    sendBtn.disabled = true;
    const file = pendingFile;

    const me = getCurrentUser();
    const fakeMsg = {
      id: Date.now(), content: text, sender_id: me?.id,
      sender_username: me?.username, sender_avatar: me?.profile?.avatar_path,
      created_at: new Date().toISOString(),
      media_path: file ? URL.createObjectURL(file) : null, is_deleted: false, reactions: [], read_receipts: [],
      message_type: file
        ? file.type.startsWith('video/')
          ? 'video'
          : file.type.startsWith('audio/')
            ? 'voice'
            : 'image'
        : 'text',
    };
    const msgArea = container.querySelector('#messages-area');
    msgArea.querySelector('.empty-state')?.remove();
    const frag = buildMessageGroups([fakeMsg]);
    msgArea.appendChild(frag);
    msgArea.scrollTop = msgArea.scrollHeight;

    textarea.value = '';
    textarea.style.height = 'auto';
    pendingFile = null;
    fileInput.value = '';
    area.querySelector('#file-preview')?.remove();

    try {
      await api.messages.sendMessage(threadId, text, file);
    } catch(err) {
      console.error("SendMessage: ", err)
      msgArea.querySelector(`[data-msg-id="${fakeMsg.id}"]`)?.remove();
      textarea.value = text;
      textarea.dispatchEvent(new Event('input'));
      toastError('Failed to send message');
    } finally {
      sendBtn.disabled = !textarea.value.trim() && !pendingFile;
    }
  });
}

function openNewGroupModal(container) {
  const m = modal({
    title: 'New group',
    content: `
      <div class="flex-col gap-4">
        <div class="input-group">
          <label>Group name</label>
          <input type="text" id="group-name-input" class="input" placeholder="e.g. Weekend crew" />
        </div>
        <div class="input-group">
          <label>Add members (search by username)</label>
          <input type="text" id="member-search-input" class="input" placeholder="Search…" />
          <div id="member-search-results" style="margin-top:var(--s2);max-height:180px;overflow-y:auto;display:flex;flex-direction:column;gap:4px"></div>
        </div>
        <div id="selected-members" style="display:flex;flex-wrap:wrap;gap:var(--s2)"></div>
      </div>
    `,
    footer: `
      <div class="flex gap-3" style="justify-content:flex-end">
        <button class="btn btn-ghost btn-sm" id="cancel-group">Cancel</button>
        <button class="btn btn-primary btn-sm" id="create-group-btn">Create group</button>
      </div>
    `,
  });

  const selectedIds = new Set();
  const selectedEl = m.el.querySelector('#selected-members');
  const searchEl = m.el.querySelector('#member-search-input');
  const resultsEl = m.el.querySelector('#member-search-results');

  m.el.querySelector('#cancel-group').addEventListener('click', m.close);

  let searchTimeout;
  searchEl.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
      const q = searchEl.value.trim();
      if (q.length < 2) { resultsEl.innerHTML = ''; return; }
      try {
        const users = await api.users.search({ username: q, limit: 6 });
        resultsEl.innerHTML = '';
        users.forEach(u => {
          const row = document.createElement('div');
          row.style.cssText = 'display:flex;align-items:center;gap:var(--s2);padding:6px 8px;border-radius:var(--r-sm);cursor:pointer;transition:background var(--t-fast)';
          row.onmouseenter = () => row.style.background = 'var(--bg-raised)';
          row.onmouseleave = () => row.style.background = '';
          const av = buildAvatar({ src: u.avatar_url, username: u.username, size: 'xs' });
          row.appendChild(av);
          row.innerHTML += `<span style="font-size:.87rem">${escHtml(u.username)}</span>`;
          row.prepend(av);
          row.addEventListener('click', () => {
            if (selectedIds.has(u.id)) return;
            selectedIds.add(u.id);
            addSelectedChip(u, selectedEl, selectedIds);
            resultsEl.innerHTML = '';
            searchEl.value = '';
          });
          resultsEl.appendChild(row);
        });
      } catch(err) { console.error("openNewGroup: ", err)/* ignore */ }
    }, 300);
  });

  m.el.querySelector('#create-group-btn').addEventListener('click', async () => {
    const name = m.el.querySelector('#group-name-input').value.trim();
    if (!name) { toast('Group name required', 'error'); return; }
    if (selectedIds.size === 0) { toast('Add at least one member', 'error'); return; }
    try {
      const thread = await api.messages.createGroup({ name, member_ids: [...selectedIds] });
      m.close();
      toast('Group created!', 'success');
      await loadThreadList(container);
      openChatWindow(container, thread.id);
    } catch(err) {
      console.error("Create group: ", err)
      toastError('Failed to create group'); }
  });
}

function addSelectedChip(user, container, selectedIds) {
  const chip = document.createElement('div');
  chip.style.cssText = 'display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:var(--accent-dim);border:1px solid var(--accent);border-radius:var(--r-full);font-size:.8rem';
  chip.innerHTML = `<span>${escHtml(user.username)}</span><button style="color:var(--accent);font-size:.75rem;margin-left:2px">✕</button>`;
  chip.querySelector('button').addEventListener('click', () => {
    selectedIds.delete(user.id);
    chip.remove();
  });
  container.appendChild(chip);
}

function openGroupManageModal(thread) {
  const me = getCurrentUser();
  const isAdmin = thread.members?.some(m => m.user_id === me?.id && m.is_admin);

  const membersHtml = (thread.members || []).map(mem => `
    <div class="user-follow-card" style="padding:var(--s2) 0" data-member-id="${mem.user_id}">
      <div class="avatar avatar-sm" style="background:var(--bg-raised);display:flex;align-items:center;justify-content:center;color:var(--text-muted)">
        ${(mem.username || '?')[0].toUpperCase()}
      </div>
      <div class="user-follow-info">
        <div class="user-follow-name">${escHtml(mem.username || '')} ${mem.is_admin ? '<span class="badge">Admin</span>' : ''}</div>
      </div>
      ${isAdmin && mem.user_id !== me?.id ? `
        <div class="flex gap-2">
          <button class="btn btn-ghost btn-sm promote-btn" data-uid="${mem.user_id}">Promote</button>
          <button class="btn btn-danger btn-sm remove-btn" data-uid="${mem.user_id}">Remove</button>
        </div>
      ` : ''}
    </div>
  `).join('');

  const m = modal({
    title: escHtml(thread.group_name || 'Group'),
    content: `
      <div class="flex-col gap-3">
        ${isAdmin ? `
          <div class="input-group">
            <label>Group name</label>
            <div class="flex gap-2">
              <input id="group-rename" type="text" class="input" value="${escHtml(thread.group_name || '')}" style="flex:1" />
              <button class="btn btn-primary btn-sm" id="rename-btn">Save</button>
            </div>
          </div>
          <div class="divider"></div>
        ` : ''}
        <div style="font-size:.8rem;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em">Members</div>
        <div>${membersHtml}</div>
      </div>
    `,
  });

  m.el.querySelector('#rename-btn')?.addEventListener('click', async () => {
    const name = m.el.querySelector('#group-rename').value.trim();
    if (!name) return;
    try { await api.messages.updateGroup(thread.id, { name }); toast('Renamed!', 'success'); m.close(); }
    catch(err) { 
      console.error("rename group: ", err)
      toastError('Failed'); }
  });

  m.el.querySelectorAll('.promote-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      try { await api.messages.promoteMember(thread.id, parseInt(btn.dataset.uid)); toast('Promoted to admin', 'success'); m.close(); }
      catch(err) { 
        console.error("Promote: ", err)
        toastError('Failed'); }
    });
  });
  m.el.querySelectorAll('.remove-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const ok = await confirm({ title: 'Remove member?', danger: true, confirmLabel: 'Remove' });
      if (!ok) return;
      try { await api.messages.removeMember(thread.id, parseInt(btn.dataset.uid)); toast('Member removed', 'success'); m.close(); }
      catch(err) { 
        console.error("Remove member: ", err)
        toastError('Failed'); }
    });
  });
}

function openLightbox(url) {
  const lb = document.createElement('div');
  lb.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:9999;cursor:zoom-out';
  lb.innerHTML = `<img src="${escHtml(url)}" style="max-width:90vw;max-height:90vh;object-fit:contain;border-radius:var(--r-md)" />`;
  lb.addEventListener('click', () => lb.remove());
  document.body.appendChild(lb);
}

function getThreadName(thread) {
  if (thread.group_name) return thread.group_name;
  if (!thread.is_group) {
    const me = getCurrentUser();
    const other = (thread.members || []).find(m => m.user_id !== me?.id);
    if (other) return other.username;
  }
  return 'Conversation';
}

function escHtml(str = '') {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
