import api from './api.js';
import { getCurrentUser } from './auth.js';
import { buildAvatar, modal, toast, toastError, relativeTime, setButtonLoading } from './ui.js';

const REACTIONS = ['❤️', '🔥', '😂', '😮', '😢', '👏', '👍', '💯'];

export async function renderStoriesTray(container) {
  const tray = container.querySelector('#stories-tray');
  if (!tray) return;

  tray.innerHTML = buildTrayLoading();
  try {
    const items = await api.stories.getTray({ limit: 40 });
    tray.innerHTML = '';
    tray.appendChild(buildCreateStoryButton(() => renderStoriesTray(container)));

    if (!items.length) {
      const empty = document.createElement('span');
      empty.className = 'story-empty';
      empty.textContent = 'No stories yet';
      tray.appendChild(empty);
      return;
    }

    items.forEach(item => tray.appendChild(buildTrayItem(item)));
  } catch (err) {
    console.error('Stories tray:', err);
    tray.innerHTML = '';
    tray.appendChild(buildCreateStoryButton(() => renderStoriesTray(container)));
  }
}

function buildTrayLoading() {
  return `
    <div class="story-item" style="padding:var(--s3)">
      <div class="spinner" style="margin:0 auto"></div>
    </div>
  `;
}

function buildCreateStoryButton(onCreated) {
  const user = getCurrentUser();
  const item = document.createElement('button');
  item.className = 'story-item story-create-btn';

  const avatar = buildAvatar({
    src: user?.profile?.avatar_path || user?.avatar_url,
    username: user?.username || 'You',
    size: 'md',
  });

  const wrap = document.createElement('div');
  wrap.className = 'story-create-avatar';
  wrap.appendChild(avatar);
  wrap.insertAdjacentHTML('beforeend', '<span class="story-plus">+</span>');

  item.appendChild(wrap);
  item.insertAdjacentHTML('beforeend', '<span class="story-label">Your story</span>');
  item.addEventListener('click', () => openCreateStoryModal(onCreated));
  return item;
}

function buildTrayItem(storyUser) {
  const item = document.createElement('button');
  item.className = 'story-item';
  item.innerHTML = `
    <div class="story-ring ${storyUser.has_unseen ? '' : 'seen'}">
      <div class="story-avatar-wrap">
        <div class="story-avatar-slot"></div>
      </div>
    </div>
    <span class="story-label">${escHtml(storyUser.username)}</span>
  `;
  item.querySelector('.story-avatar-slot').appendChild(buildAvatar({
    src: storyUser.avatar_path,
    username: storyUser.username,
    size: 'md',
  }));
  item.addEventListener('click', () => openStoryViewer(storyUser.user_id));
  return item;
}

function openCreateStoryModal(onCreated) {
  const m = modal({
    title: 'New story',
    content: `
      <div class="story-create-form">
        <div id="story-drop-zone" class="story-drop-zone">
          <input type="file" id="story-file" accept="image/*,video/*" style="display:none" />
          <div id="story-drop-empty">
            <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin:0 auto;opacity:.42">
              <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
            </svg>
            <p style="margin-top:var(--s2);color:var(--text-muted);font-size:.88rem">Choose an image or video</p>
          </div>
          <div id="story-preview" class="story-preview" style="display:none"></div>
        </div>
        <div class="input-group">
          <label>Caption</label>
          <textarea id="story-caption" class="input" rows="3" maxlength="2200" placeholder="Add a caption..." style="resize:vertical"></textarea>
        </div>
        <div class="input-group">
          <label>Link</label>
          <input id="story-link" class="input" type="url" placeholder="https://example.com" />
        </div>
        <div class="input-group">
          <label>Sticker</label>
          <select id="story-sticker-type" class="input">
            <option value="">None</option>
            <option value="poll">Poll</option>
            <option value="question">Question</option>
          </select>
        </div>
        <div id="story-poll-fields" class="story-sticker-fields" style="display:none">
          <input id="story-poll-question" class="input" maxlength="200" placeholder="Poll question" />
          <div class="flex gap-2">
            <input id="story-poll-a" class="input" maxlength="100" placeholder="Option A" />
            <input id="story-poll-b" class="input" maxlength="100" placeholder="Option B" />
          </div>
        </div>
        <div id="story-question-fields" class="story-sticker-fields" style="display:none">
          <input id="story-question-prompt" class="input" maxlength="200" placeholder="Question prompt" />
        </div>
        <label class="story-check">
          <input type="checkbox" id="story-close-friends" />
          Close friends only
        </label>
      </div>
    `,
    footer: `
      <div class="flex gap-3" style="justify-content:flex-end">
        <button class="btn btn-ghost btn-sm" id="story-cancel">Cancel</button>
        <button class="btn btn-primary btn-sm" id="story-submit" disabled>Share story</button>
      </div>
    `,
  });

  const fileInput = m.el.querySelector('#story-file');
  const dropZone = m.el.querySelector('#story-drop-zone');
  const preview = m.el.querySelector('#story-preview');
  const empty = m.el.querySelector('#story-drop-empty');
  const submit = m.el.querySelector('#story-submit');
  const stickerType = m.el.querySelector('#story-sticker-type');
  let selectedFile = null;

  stickerType.addEventListener('change', () => {
    m.el.querySelector('#story-poll-fields').style.display = stickerType.value === 'poll' ? 'grid' : 'none';
    m.el.querySelector('#story-question-fields').style.display = stickerType.value === 'question' ? 'grid' : 'none';
  });

  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    selectedFile = fileInput.files[0] || null;
    submit.disabled = !selectedFile;
    preview.innerHTML = '';
    if (!selectedFile) {
      preview.style.display = 'none';
      empty.style.display = '';
      return;
    }

    const url = URL.createObjectURL(selectedFile);
    const media = selectedFile.type.startsWith('video/')
      ? document.createElement('video')
      : document.createElement('img');
    media.src = url;
    if (media.tagName === 'VIDEO') media.controls = true;
    preview.appendChild(media);
    preview.style.display = 'block';
    empty.style.display = 'none';
  });

  m.el.querySelector('#story-cancel').addEventListener('click', m.close);
  submit.addEventListener('click', async () => {
    if (!selectedFile) return;
    setButtonLoading(submit, true);
    try {
      const meta = {
        caption: m.el.querySelector('#story-caption').value.trim(),
        linkUrl: m.el.querySelector('#story-link').value.trim(),
        closeFriendsOnly: m.el.querySelector('#story-close-friends').checked,
      };
      if (stickerType.value === 'poll') {
        meta.poll = {
          question: m.el.querySelector('#story-poll-question').value.trim(),
          option_a: m.el.querySelector('#story-poll-a').value.trim(),
          option_b: m.el.querySelector('#story-poll-b').value.trim(),
        };
      }
      if (stickerType.value === 'question') {
        meta.question = {
          prompt: m.el.querySelector('#story-question-prompt').value.trim(),
        };
      }
      await api.stories.create({
        ...meta,
      }, selectedFile);
      toast('Story shared', 'success', 2200);
      m.close();
      onCreated?.();
    } catch (err) {
      console.error('Create story:', err);
      toastError(err.message || 'Failed to share story');
    } finally {
      setButtonLoading(submit, false);
    }
  });
}

async function openStoryViewer(userId) {
  let stories = [];
  try {
    stories = await api.stories.getUserStories(userId);
  } catch (err) {
    console.error('Load stories:', err);
    toastError('Could not load stories');
    return;
  }
  if (!stories.length) {
    toast('No active stories', 'info', 1800);
    return;
  }

  let index = Math.max(0, stories.findIndex(story => !story.has_viewed));
  if (index < 0) index = 0;

  const m = modal({
    title: '',
    content: '<div id="story-viewer-root" class="story-viewer-root"></div>',
  });
  m.el.querySelector('.modal').classList.add('story-viewer-modal');

  const root = m.el.querySelector('#story-viewer-root');
  const render = async () => {
    const story = stories[index];
    try {
      stories[index] = await api.stories.markView(story.id);
    } catch (err) {
      console.error('Mark story view:', err);
    }
    drawStory(root, stories[index] || story, {
      index,
      total: stories.length,
      onPrev: () => {
        if (index > 0) { index -= 1; render(); }
      },
      onNext: () => {
        if (index < stories.length - 1) { index += 1; render(); }
        else m.close();
      },
      onReact: async reaction => {
        try {
          stories[index] = await api.stories.react(story.id, reaction).then(() => ({
            ...story,
            my_reaction: reaction,
          }));
          toast('Reaction sent', 'success', 1200);
          render();
        } catch (err) {
          console.error('Story reaction:', err);
          toastError('Could not react');
        }
      },
      onVote: async choice => {
        try {
          const poll = await api.stories.votePoll(story.id, choice);
          stories[index] = { ...story, poll };
          render();
        } catch (err) {
          console.error('Story poll:', err);
          toastError('Could not vote');
        }
      },
      onAnswer: async text => {
        try {
          await api.stories.answerQuestion(story.id, text);
          toast('Answer sent', 'success', 1200);
        } catch (err) {
          console.error('Story answer:', err);
          toastError('Could not send answer');
        }
      },
    });
  };
  render();
}

function drawStory(root, story, actions) {
  const isVideo = story.media_type === 'video';
  root.innerHTML = `
    <div class="story-progress">
      ${Array.from({ length: actions.total }, (_, i) => `<span class="${i <= actions.index ? 'active' : ''}"></span>`).join('')}
    </div>
    <div class="story-viewer-head">
      <div id="story-author-slot"></div>
      <div>
        <div class="story-viewer-name">${escHtml(story.author?.username || 'story')}</div>
        <div class="story-viewer-time">${relativeTime(story.created_at)}</div>
      </div>
      <a class="story-link-btn" href="${escHtml(story.link_url || '#')}" target="_blank" rel="noopener" style="${story.link_url ? '' : 'display:none'}">Open link</a>
    </div>
    <div class="story-media-frame">
      <button class="story-nav-btn story-prev" ${actions.index === 0 ? 'disabled' : ''}>‹</button>
      ${isVideo
        ? `<video src="${escHtml(story.media_path)}" controls autoplay></video>`
        : `<img src="${escHtml(story.media_path)}" alt="" />`}
      <button class="story-nav-btn story-next">›</button>
    </div>
    ${story.caption ? `<p class="story-caption">${escHtml(story.caption)}</p>` : ''}
    ${story.poll ? buildPoll(story.poll) : ''}
    ${story.question ? buildQuestion(story.question) : ''}
    <div class="story-reactions">
      ${REACTIONS.map(r => `<button class="${story.my_reaction === r ? 'active' : ''}" data-reaction="${escHtml(r)}">${escHtml(r)}</button>`).join('')}
    </div>
  `;

  root.querySelector('#story-author-slot').appendChild(buildAvatar({
    src: story.author?.avatar_path,
    username: story.author?.username,
    size: 'sm',
  }));
  root.querySelector('.story-prev').addEventListener('click', actions.onPrev);
  root.querySelector('.story-next').addEventListener('click', actions.onNext);
  root.querySelectorAll('[data-reaction]').forEach(btn => {
    btn.addEventListener('click', () => actions.onReact(btn.dataset.reaction));
  });
  root.querySelectorAll('[data-poll-choice]').forEach(btn => {
    btn.addEventListener('click', () => actions.onVote(btn.dataset.pollChoice));
  });
  root.querySelector('.story-answer-submit')?.addEventListener('click', () => {
    const input = root.querySelector('.story-answer-input');
    const text = input.value.trim();
    if (!text) return;
    actions.onAnswer(text);
    input.value = '';
  });
}

function buildPoll(poll) {
  return `
    <div class="story-sticker story-poll">
      <div class="story-sticker-title">${escHtml(poll.question)}</div>
      <button data-poll-choice="a" class="${poll.my_vote === 'a' ? 'active' : ''}">
        ${escHtml(poll.option_a)} <span>${poll.votes_a || 0}</span>
      </button>
      <button data-poll-choice="b" class="${poll.my_vote === 'b' ? 'active' : ''}">
        ${escHtml(poll.option_b)} <span>${poll.votes_b || 0}</span>
      </button>
    </div>
  `;
}

function buildQuestion(question) {
  return `
    <div class="story-sticker">
      <div class="story-sticker-title">${escHtml(question.prompt)}</div>
      <div class="story-answer-row">
        <input class="input story-answer-input" maxlength="150" placeholder="Write an answer" />
        <button class="btn btn-primary btn-sm story-answer-submit">Send</button>
      </div>
    </div>
  `;
}

export function injectStoryStyles() {
  if (document.getElementById('story-feature-styles')) return;
  const style = document.createElement('style');
  style.id = 'story-feature-styles';
  style.textContent = `
    #stories-tray {
      margin-bottom: var(--s4);
      border-bottom: 1px solid var(--border);
    }
    .story-create-btn { background:none; border:0; color:inherit; }
    .story-create-avatar { position:relative; }
    .story-plus {
      position:absolute; right:-2px; bottom:-2px;
      width:18px; height:18px; border-radius:50%;
      background:var(--accent); color:#1a1400;
      display:flex; align-items:center; justify-content:center;
      font-size:.8rem; font-weight:700; border:2px solid var(--bg);
    }
    .story-empty { align-self:center; color:var(--text-muted); font-size:.82rem; padding:0 var(--s3); }
    .story-drop-zone {
      border:2px dashed var(--border);
      border-radius:var(--r-md);
      padding:var(--s6);
      text-align:center;
      cursor:pointer;
    }
    .story-preview img, .story-preview video {
      width:100%; max-height:360px; object-fit:contain; border-radius:var(--r-md);
    }
    .story-check { display:flex; align-items:center; gap:var(--s2); font-size:.86rem; color:var(--text-secondary); }
    .story-sticker-fields { gap:var(--s2); }
    .story-viewer-modal { width:min(520px, calc(100vw - 24px)); padding:0; overflow:hidden; }
    .story-viewer-modal .modal-header { display:none; }
    .story-viewer-root { background:#050505; min-height:640px; display:flex; flex-direction:column; }
    .story-progress { display:flex; gap:4px; padding:10px 12px 0; }
    .story-progress span { flex:1; height:3px; border-radius:999px; background:rgba(255,255,255,.18); }
    .story-progress span.active { background:var(--accent); }
    .story-viewer-head { display:flex; align-items:center; gap:var(--s3); padding:var(--s3); }
    .story-viewer-name { font-weight:600; font-size:.92rem; }
    .story-viewer-time { color:var(--text-muted); font-size:.74rem; }
    .story-link-btn { margin-left:auto; color:var(--accent); font-size:.82rem; }
    .story-media-frame { position:relative; flex:1; display:flex; align-items:center; justify-content:center; min-height:360px; }
    .story-media-frame img, .story-media-frame video { width:100%; max-height:520px; object-fit:contain; }
    .story-nav-btn {
      position:absolute; top:50%; transform:translateY(-50%);
      width:36px; height:36px; border-radius:50%;
      background:rgba(0,0,0,.45); color:white; font-size:1.6rem; z-index:2;
    }
    .story-nav-btn:disabled { opacity:.25; }
    .story-prev { left:10px; }
    .story-next { right:10px; }
    .story-caption { padding:0 var(--s4) var(--s3); font-size:.9rem; }
    .story-reactions { display:flex; justify-content:center; gap:6px; padding:var(--s3); border-top:1px solid var(--border); }
    .story-reactions button { font-size:1.1rem; padding:6px 8px; border-radius:999px; }
    .story-reactions button.active, .story-reactions button:hover { background:var(--bg-raised); }
    .story-sticker { margin:0 var(--s4) var(--s3); padding:var(--s3); background:var(--bg-surface); border:1px solid var(--border); border-radius:var(--r-md); }
    .story-sticker-title { font-weight:600; margin-bottom:var(--s2); }
    .story-poll button { width:100%; display:flex; justify-content:space-between; padding:9px 12px; border-radius:var(--r-md); color:var(--text-primary); }
    .story-poll button.active, .story-poll button:hover { background:var(--accent-dim); color:var(--accent); }
    .story-answer-row { display:flex; gap:var(--s2); align-items:center; }
    @media (max-width: 768px) {
      .story-viewer-root { min-height:calc(100vh - 120px); }
    }
  `;
  document.head.appendChild(style);
}

function escHtml(str = '') {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
