import api from './api.js';
import { toast, toastError, buildAvatar, formatCount, confirm, setButtonLoading, modal, relativeTime } from './ui.js';
import { getCurrentUser } from './auth.js';

export async function renderProfilePage(container, userIdOrUsername) {
  container.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:center;padding:var(--s8)">
      <div class="spinner" style="width:32px;height:32px;border-width:3px"></div>
    </div>
  `;

  const me = getCurrentUser();
  let user;

  const isSelfProfile = !userIdOrUsername
    || String(userIdOrUsername) === String(me?.username)
    || String(userIdOrUsername) === String(me?.id);

  if (isSelfProfile && me) {
    user = me;
  } else {
    try {
      user = isNaN(userIdOrUsername)
        ? await api.users.getByUsername(userIdOrUsername)
        : await api.users.getById(userIdOrUsername);
    } catch(err) {
      console.error("User not Found  : ", err)
      container.innerHTML = `<div class="empty-state"><p>User not found.</p></div>`;
      return;
    }
  }

  const isSelf = me && me.id === user.id;

  container.innerHTML = `
    <div class="page-header">
      <button class="btn-icon" id="back-btn" aria-label="Back">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M19 12H5M12 19l-7-7 7-7"/>
        </svg>
      </button>
      <h1 class="page-title">${escHtml(user.username)}</h1>
    </div>

    <div class="profile-header">
      <div class="profile-avatar-wrap">
        <div class="story-ring" id="story-ring" style="display:inline-block">
          <div class="story-avatar-wrap">
            <div id="profile-avatar-slot"></div>
          </div>
        </div>
      </div>

      <div class="profile-info">
        <div class="profile-username-row">
          <span class="profile-username">${escHtml(user.username)}</span>
          <div class="flex gap-2" id="profile-actions"></div>
        </div>

        <div class="profile-stats">
          <div class="profile-stat" id="stat-posts">
            <span class="profile-stat-num" id="stat-posts-count">—</span>
            <span class="profile-stat-label">Posts</span>
          </div>
          <div class="profile-stat" id="stat-followers" role="button" tabindex="0">
            <span class="profile-stat-num">${formatCount(user.profile?.follower_count ?? user.follower_count ?? 0)}</span>
            <span class="profile-stat-label">Followers</span>
          </div>
          <div class="profile-stat" id="stat-following" role="button" tabindex="0">
            <span class="profile-stat-num">${formatCount(user.profile?.following_count ?? user.following_count ?? 0)}</span>
            <span class="profile-stat-label">Following</span>
          </div>
        </div>

        <div class="profile-bio">
          ${(user.profile?.full_name || user.full_name) ? `<span class="profile-name">${escHtml(user.profile?.full_name || user.full_name || '')}</span>` : ''}
          ${(user.profile?.bio || user.bio) ? `<p>${escHtml(user.profile?.bio || user.bio || '')}</p>` : ''}
          ${(user.profile?.website || user.website) ? `<a href="${escHtml(user.profile?.website || user.website || '')}" target="_blank" rel="noopener" class="profile-website">${escHtml(user.profile?.website || user.website || '')}</a>` : ''}
        </div>
      </div>
    </div>

    <div class="divider" style="margin:0"></div>

    <div id="profile-grid-section">
      <div id="profile-post-grid" class="post-grid" style="padding:2px"></div>
      <div id="profile-grid-loader" style="display:none;padding:var(--s5);text-align:center">
        <div class="spinner" style="margin:0 auto"></div>
      </div>
      <div id="profile-grid-empty" style="display:none">
        <div class="empty-state" style="padding:var(--s8)">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <p>No posts yet</p>
        </div>
      </div>
    </div>
  `;

  const avatarSlot = container.querySelector('#profile-avatar-slot');
  const avatarEl = buildAvatar({ src: user.profile?.avatar_path || user.avatar_url, username: user.username, size: 'xl' });
  avatarSlot.appendChild(avatarEl);

  renderProfileActions(container, user, isSelf, me);

  container.querySelector('#back-btn').addEventListener('click', () => history.back());

  container.querySelector('#stat-followers').addEventListener('click', () => openFollowModal(user.id, 'followers'));
  container.querySelector('#stat-following').addEventListener('click', () => openFollowModal(user.id, 'following'));

  await loadProfileGrid(container, user.id);
}

function renderProfileActions(container, user, isSelf, me) {
  const actionsEl = container.querySelector('#profile-actions');

  if (isSelf) {
    actionsEl.innerHTML = `
      <a href="#settings" class="btn btn-ghost btn-sm">Edit profile</a>
      <button class="btn btn-ghost btn-sm" id="archive-btn">Archive</button>
    `;
    container.querySelector('#archive-btn').addEventListener('click', () => {
      window.location.hash = '#archived';
    });
    return;
  }

  if (!me) {
    actionsEl.innerHTML = `<a href="#login" class="btn btn-primary btn-sm">Follow</a>`;
    return;
  }

  const isFollowing = user.is_following || false;
  const isPending   = user.follow_status === 'pending';

  actionsEl.innerHTML = `
    <button class="btn ${isFollowing ? 'btn-ghost' : 'btn-primary'} btn-sm" id="follow-btn">
      ${isPending ? 'Requested' : isFollowing ? 'Following' : 'Follow'}
    </button>
    <button class="btn btn-ghost btn-sm" id="dm-btn">Message</button>
    <button class="btn-icon" id="more-btn" aria-label="More options">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>
      </svg>
    </button>
  `;

  const followBtn = container.querySelector('#follow-btn');
  let following = isFollowing;
  let pending   = isPending;

  followBtn.addEventListener('click', async () => {
    if (following || pending) {
      const ok = await confirm({
        title: following ? 'Unfollow?' : 'Cancel request?',
        message: following
          ? `You'll stop seeing ${user.username}'s posts.`
          : 'Withdraw your follow request.',
        confirmLabel: following ? 'Unfollow' : 'Cancel request',
        danger: true,
      });
      if (!ok) return;
      setButtonLoading(followBtn, true);
      try {
        await api.users.unfollow(user.id);
        following = false; pending = false;
        followBtn.textContent = 'Follow';
        followBtn.classList.replace('btn-ghost', 'btn-primary');
      } catch(err) { 
        console.error("Unfollow: ", err)
        toastError('Action failed'); }
      finally { setButtonLoading(followBtn, false); }
    } else {
      setButtonLoading(followBtn, true);
      try {
        const res = await api.users.follow(user.id);
        if (res.status === 'pending') {
          pending = true; followBtn.textContent = 'Requested';
          followBtn.classList.replace('btn-primary', 'btn-ghost');
        } else {
          following = true; followBtn.textContent = 'Following';
          followBtn.classList.replace('btn-primary', 'btn-ghost');
          toast(`You followed ${user.username}`, 'success', 2000);
        }
      } catch(err) { 
        console.error("Follow: ", err)
        toastError('Action failed'); }
      finally { setButtonLoading(followBtn, false); }
    }
  });

  container.querySelector('#dm-btn').addEventListener('click', async () => {
    try {
      const thread = await api.messages.getOrCreateDM(user.id);
      window.location.hash = `#messages/${thread.id}`;
    } catch(err) { 
      console.error("Open dm: ", err)
      toastError('Could not open chat'); }
  });

  container.querySelector('#more-btn').addEventListener('click', (e) => {
    openMoreMenu(e.currentTarget, user);
  });
}

async function loadProfileGrid(container, userId) {
  const grid = container.querySelector('#profile-post-grid');
  const loader = container.querySelector('#profile-grid-loader');
  const empty = container.querySelector('#profile-grid-empty');
  const statEl = container.querySelector('#stat-posts-count');

  loader.style.display = 'block';
  try {
    const posts = await api.posts.getUserPosts(userId, { limit: 30 });
    statEl.textContent = formatCount(posts.length);

    if (posts.length === 0) {
      empty.style.display = 'block';
    } else {
      posts.forEach(post => grid.appendChild(buildGridItem(post)));
    }
  } catch(err) {
    console.error("Load posts: ", err)
    toastError('Failed to load posts');
  } finally {
    loader.style.display = 'none';
  }
}

function buildGridItem(post) {
  const item = document.createElement('div');
  item.className = 'post-grid-item';

  const firstMedia = post.media_items?.[0];
  const isVideo = firstMedia?.media_type === 'video';
  const isCarousel = (post.media_items?.length || 0) > 1;

  item.innerHTML = `
    ${firstMedia ? `<img src="${escHtml(getMediaUrl(firstMedia))}" alt="" loading="lazy" />` : ''}
    <div class="post-grid-overlay">
      <div class="grid-stat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        ${formatCount(post.like_count || 0)}
      </div>
      <div class="grid-stat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        ${formatCount(post.comment_count || 0)}
      </div>
    </div>
    ${isVideo ? `<div style="position:absolute;top:8px;right:8px;color:#fff;opacity:.85"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg></div>` : ''}
    ${isCarousel ? `<div style="position:absolute;top:8px;right:8px;color:#fff;opacity:.85"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="2" width="13" height="13" rx="2"/><rect x="2" y="8" width="13" height="13" rx="2"/></svg></div>` : ''}
  `;

  item.addEventListener('click', () => { window.location.hash = `#post/${post.id}`; });
  return item;
}

async function openFollowModal(userId, type) {
  const m = modal({
    title: type === 'followers' ? 'Followers' : 'Following',
    content: '<div id="follow-modal-list" style="max-height:400px;overflow-y:auto"><div style="padding:var(--s5);text-align:center"><div class="spinner" style="margin:0 auto"></div></div></div>',
  });

  const listEl = m.el.querySelector('#follow-modal-list');
  try {
    const items = type === 'followers'
      ? await api.users.getFollowers(userId)
      : await api.users.getFollowing(userId);

    if (items.length === 0) {
      listEl.innerHTML = '<div class="empty-state"><p>No users yet.</p></div>';
      return;
    }

    listEl.innerHTML = '';
    items.forEach(u => listEl.appendChild(buildUserFollowCard(u, m.close)));
  } catch(err) {
    console.error("Followers: ", err)
    listEl.innerHTML = '<div class="empty-state"><p>Failed to load.</p></div>';
  }
}

function buildUserFollowCard(user, onClose) {
  const card = document.createElement('div');
  card.className = 'user-follow-card';
  const avatar = buildAvatar({ src: user.avatar_url, username: user.username, size: 'sm' });
  card.appendChild(avatar);
  card.innerHTML += `
    <div class="user-follow-info">
      <div class="user-follow-name">${escHtml(user.username)}</div>
      ${user.full_name ? `<div class="user-follow-meta">${escHtml(user.full_name)}</div>` : ''}
    </div>
    <a href="#profile/${user.username}" class="btn btn-ghost btn-sm" style="flex-shrink:0">View</a>
  `;
  card.querySelector('a').addEventListener('click', () => { onClose?.(); });
  card.prepend(avatar);
  return card;
}

function openMoreMenu(trigger, user) {
  const existing = document.querySelector('.profile-more-menu');
  if (existing) { existing.remove(); return; }

  const menu = document.createElement('div');
  menu.className = 'profile-more-menu';
  menu.style.cssText = `
    position:absolute;right:0;top:calc(100% + 6px);
    background:var(--bg-raised);border:1px solid var(--border);
    border-radius:var(--r-md);overflow:hidden;min-width:160px;
    box-shadow:var(--shadow-md);z-index:500;
  `;
  menu.innerHTML = `
    <button class="menu-item" style="display:flex;align-items:center;gap:var(--s2);padding:10px var(--s4);width:100%;color:var(--danger);font-size:.87rem;transition:background var(--t-fast)">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
      Block user
    </button>
    <button class="menu-item" style="display:flex;align-items:center;gap:var(--s2);padding:10px var(--s4);width:100%;color:var(--text-secondary);font-size:.87rem;transition:background var(--t-fast)">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
      Report
    </button>
  `;

  menu.querySelectorAll('.menu-item').forEach(item => {
    item.addEventListener('mouseenter', () => item.style.background = 'var(--bg-surface)');
    item.addEventListener('mouseleave', () => item.style.background = '');
  });

  const [blockBtn] = menu.querySelectorAll('.menu-item');
  blockBtn.addEventListener('click', async () => {
    menu.remove();
    const ok = await confirm({
      title: `Block ${user.username}?`,
      message: 'They won\'t be able to find your profile or posts.',
      confirmLabel: 'Block', danger: true,
    });
    if (ok) {
      try { await api.users.block(user.id); toast('User blocked', 'success'); }
      catch(err) { 
        console.error("Bloack user: ", err)
        toastError('Failed to block user'); }
    }
  });

  trigger.style.position = 'relative';
  trigger.appendChild(menu);
  setTimeout(() => document.addEventListener('click', function h() {
    menu.remove(); document.removeEventListener('click', h);
  }), 0);
}

function escHtml(str = '') {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function getMediaUrl(media) {
  return media?.media_path || media?.url || media?.thumbnail_path || '';
}
