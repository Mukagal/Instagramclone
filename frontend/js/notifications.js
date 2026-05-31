import api from './api.js';
import { buildAvatar, relativeTime, toastError } from './ui.js';
import { icons } from './icons.js';

const typeText = {
  like: 'liked your post',
  comment: 'commented on your post',
  comment_like: 'liked your comment',
  comment_reply: 'replied to your comment',
  follow: 'started following you',
  follow_request: 'requested to follow you',
  follow_accepted: 'accepted your follow request',
  mention: 'mentioned you',
  tag: 'tagged you',
  story_mention: 'mentioned you in a story',
  story_reaction: 'reacted to your story',
  reel_like: 'liked your reel',
  reel_comment: 'commented on your reel',
  live_start: 'started a live video',
};

export async function renderNotificationsPage(container) {
  container.innerHTML = `
    <section class="page">
      <div class="page-header">
        <h1>Notifications</h1>
        <button class="btn btn-ghost btn-sm" id="mark-all-read">Mark all read</button>
      </div>
      <div id="notifications-list" class="notifications-list">
        <div class="empty-state" style="padding:var(--s8)">
          <div class="spinner"></div>
        </div>
      </div>
    </section>
  `;

  injectNotificationStyles();
  const list = container.querySelector('#notifications-list');
  const markAllBtn = container.querySelector('#mark-all-read');

  markAllBtn.addEventListener('click', async () => {
    try {
      await api.notifications.markAllRead();
      list.querySelectorAll('.notification-item.unread').forEach((item) => {
        item.classList.remove('unread');
      });
    } catch (err) {
      toastError(err.message || 'Could not mark notifications read');
    }
  });

  try {
    const notifications = await api.notifications.list();
    if (!notifications.length) {
      list.innerHTML = `
        <div class="empty-state" style="padding:var(--s8)">
          <span class="empty-icon">${icons.bell}</span>
          <p>No notifications yet.</p>
        </div>
      `;
      return;
    }

    list.innerHTML = '';
    notifications.forEach((notification) => {
      list.appendChild(buildNotificationItem(notification));
    });
  } catch (err) {
    list.innerHTML = `
      <div class="empty-state" style="padding:var(--s8)">
        <p>Could not load notifications.</p>
      </div>
    `;
    toastError(err.message || 'Could not load notifications');
  }
}

function buildNotificationItem(notification) {
  const actor = notification.actor || {};
  const username = actor.username || 'Someone';
  const item = document.createElement('button');
  item.type = 'button';
  item.className = `notification-item ${notification.is_read ? '' : 'unread'}`;

  const avatar = buildAvatar({
    src: actor.avatar_path,
    username,
    size: 'md',
  });

  item.appendChild(avatar);

  const body = document.createElement('div');
  body.className = 'notification-body';
  body.innerHTML = `
    <div class="notification-copy">
      <strong>${escapeHtml(username)}</strong>
      <span>${escapeHtml(typeText[notification.notification_type] || 'sent you a notification')}</span>
    </div>
    <time>${relativeTime(notification.created_at)}</time>
  `;
  item.appendChild(body);

  const action = getNotificationHref(notification, actor);
  if (action) {
    item.addEventListener('click', async () => {
      await markReadQuietly(notification.id, item);
      window.location.hash = action;
    });
  } else {
    item.addEventListener('click', () => markReadQuietly(notification.id, item));
  }

  return item;
}

function getNotificationHref(notification, actor) {
  if (notification.post_id) return `#post/${notification.post_id}`;
  if (notification.reel_id) return `#post/${notification.reel_id}`;
  if (actor?.username) return `#profile/${actor.username}`;
  return '';
}

async function markReadQuietly(id, item) {
  if (!item.classList.contains('unread')) return;
  item.classList.remove('unread');
  try {
    await api.notifications.markRead(id);
  } catch (err) {
    item.classList.add('unread');
  }
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function injectNotificationStyles() {
  if (document.getElementById('notification-page-styles')) return;
  const style = document.createElement('style');
  style.id = 'notification-page-styles';
  style.textContent = `
    .notifications-list {
      display: flex;
      flex-direction: column;
      border-top: 1px solid var(--border);
    }

    .notification-item {
      width: 100%;
      display: flex;
      align-items: center;
      gap: var(--s3);
      padding: var(--s4) var(--s6);
      border: 0;
      border-bottom: 1px solid var(--border);
      background: transparent;
      color: var(--text-primary);
      text-align: left;
      cursor: pointer;
    }

    .notification-item:hover {
      background: var(--surface);
    }

    .notification-item.unread {
      background: rgba(244, 210, 110, 0.08);
    }

    .notification-item.unread::after {
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--accent);
      flex: 0 0 auto;
    }

    .notification-body {
      min-width: 0;
      flex: 1;
    }

    .notification-copy {
      display: flex;
      gap: 0.35rem;
      flex-wrap: wrap;
      font-size: 0.95rem;
      line-height: 1.35;
    }

    .notification-body time {
      display: block;
      margin-top: 0.2rem;
      color: var(--text-muted);
      font-size: 0.8rem;
    }
  `;
  document.head.appendChild(style);
}
