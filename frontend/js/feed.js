import api from './api.js';
import { toast, toastError, buildAvatar, relativeTime, formatCount, infiniteScroll } from './ui.js';
import { injectStoryStyles, renderStoriesTray } from './story.js';

export async function renderFeedPage(container) {
  injectStoryStyles();
  container.innerHTML = `
    <div class="page-header">
      <h1 class="page-title">Feed</h1>
    </div>
    <div class="page-body">
      <div id="stories-tray" class="stories-bar"></div>
      <div class="feed-tabs">
        <button class="feed-tab active" data-tab="following">Following</button>
        <button class="feed-tab" data-tab="explore">Explore</button>
      </div>
      <div id="feed-container" class="feed"></div>
      <div id="feed-loader" style="display:none;padding:var(--s6);text-align:center">
        <div class="spinner" style="margin:0 auto"></div>
      </div>
    </div>
  `;

  let currentTab = 'following';
  let skip = 0;
  const limit = 10;
  let loading = false;
  let hasMore = true;

  const feedEl  = container.querySelector('#feed-container');
  const loaderEl = container.querySelector('#feed-loader');

  async function loadPosts(reset = false) {
    if (loading || !hasMore) return;
    loading = true;
    loaderEl.style.display = 'block';

    try {
      const items = currentTab === 'following'
        ? await api.posts.getFollowingFeed({ skip, limit })
        : await api.posts.getExploreFeed({ skip, limit });

      if (reset) feedEl.innerHTML = '';
      if (items.length === 0) { hasMore = false; }
      else {
        items.forEach(p => feedEl.appendChild(buildPostCard(p)));
        skip += items.length;
        if (items.length < limit) hasMore = false;
      }

      if (!hasMore && feedEl.children.length > 0) {
        const end = document.createElement('p');
        end.style.cssText = 'text-align:center;color:var(--text-muted);font-size:.82rem;padding:var(--s6)';
        end.textContent = "You're all caught up ✓";
        feedEl.appendChild(end);
      }
    } catch (err) {
      toastError('Failed to load posts');
    } finally {
      loading = false;
      loaderEl.style.display = 'none';
    }
  }

  container.querySelectorAll('.feed-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      container.querySelectorAll('.feed-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentTab = tab.dataset.tab;
      skip = 0; hasMore = true;
      loadPosts(true);
    });
  });

  infiniteScroll(window, () => loadPosts());

  renderStoriesTray(container);
  loadPosts(true);
} 

export function buildPostCard(post) {
  const card = document.createElement('article');
  card.className = 'post-card';
  card.dataset.postId = post.id;

  const avatar = buildAvatar({ src: post.author?.avatar_path, username: post.author?.username, size: 'sm' });
  const header = document.createElement('div');
  header.className = 'post-header';
  header.appendChild(avatar);
  header.innerHTML += `
    <div class="post-header-info">
      <div class="post-author">${escHtml(post.author?.username || 'unknown')}</div>
      ${post.location_name ? `<div class="post-location">${escHtml(post.location_name)}</div>` : ''}
    </div>
    <button class="post-menu" aria-label="Post options">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
      </svg>
    </button>
  `;
  header.prepend(avatar);
  card.appendChild(header);

  const media = post.media_items || [];
  if (media.length > 0) {
    card.appendChild(buildMediaSection(post.id, media));
  }

  card.appendChild(buildActions(post));

  card.appendChild(buildPostBody(post));

  card.appendChild(buildCommentInput(post.id));

  wirePostCard(card, post);
  return card;
}

function buildMediaSection(postId, items) {
  const wrap = document.createElement('div');
  wrap.className = 'post-media';

  if (items.length === 1) {
    wrap.appendChild(buildMediaItem(items[0]));
    return wrap;
  }

  let current = 0;

  const slides = document.createElement('div');
  slides.style.cssText = 'position:relative;overflow:hidden';
  items.forEach((item, i) => {
    const el = buildMediaItem(item);
    el.style.display = i === 0 ? 'block' : 'none';
    slides.appendChild(el);
  });

  const dots = document.createElement('div');
  dots.className = 'carousel-dots';
  items.forEach((_, i) => {
    const d = document.createElement('div');
    d.className = `carousel-dot${i === 0 ? ' active' : ''}`;
    dots.appendChild(d);
  });

  const prev = document.createElement('button');
  prev.className = 'carousel-btn prev';
  prev.innerHTML = '‹'; prev.style.display = 'none';

  const next = document.createElement('button');
  next.className = 'carousel-btn next';
  next.innerHTML = '›';

  function goTo(idx) {
    slides.children[current].style.display = 'none';
    dots.children[current].classList.remove('active');
    current = idx;
    slides.children[current].style.display = 'block';
    dots.children[current].classList.add('active');
    prev.style.display = current === 0 ? 'none' : 'flex';
    next.style.display = current === items.length - 1 ? 'none' : 'flex';
  }

  prev.addEventListener('click', () => goTo(current - 1));
  next.addEventListener('click', () => goTo(current + 1));

  slides.appendChild(prev);
  slides.appendChild(next);
  slides.appendChild(dots);
  wrap.appendChild(slides);
  return wrap;
}

function buildMediaItem(item) {
  if (item.media_type === 'video') {
    const v = document.createElement('video');
    v.src = item.media_path || item.url || ''; v.controls = true; v.style.width = '100%';
    return v;
  }
  const img = document.createElement('img');
  img.src = item.media_path || item.url || ''; img.alt = '';
  img.loading = 'lazy';
  return img;
}

function buildActions(post) {
  const wrap = document.createElement('div');
  wrap.className = 'post-actions';

  const liked = post.is_liked || false;
  const saved = post.is_saved || false;

  wrap.innerHTML = `
    <button class="action-btn like-btn ${liked ? 'liked' : ''}" data-liked="${liked}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="${liked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
      </svg>
      <span class="like-count">${formatCount(post.like_count || 0)}</span>
    </button>
    <button class="action-btn comment-btn">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span>${formatCount(post.comment_count || 0)}</span>
    </button>
    <button class="action-btn share-btn">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
    <button class="action-btn action-btn-save save-btn ${saved ? 'saved' : ''}" data-saved="${saved}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="${saved ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
      </svg>
    </button>
  `;
  return wrap;
}

function buildPostBody(post) {
  const body = document.createElement('div');
  body.className = 'post-body';

  const likeCount = post.hide_like_count ? '' : `<div class="post-likes">${formatCount(post.like_count || 0)} likes</div>`;

  const caption = post.caption
    ? `<div class="post-caption">
         <span class="author-tag">${escHtml(post.author?.username || '')}</span>
         ${formatCaption(post.caption)}
       </div>`
    : '';

  const previewComments = post.preview_comments || [];
  const preview = previewComments.map(c => `
    <div class="comment-preview-item">
      <span class="author">${escHtml(c.author?.username || c.author_username || '')}</span>${escHtml(c.text || c.content || '')}
    </div>
  `).join('');

  const viewMore = post.comment_count > previewComments.length
    ? `<button class="view-comments-btn">View ${post.comment_count === 1 ? '1 comment' : `all ${formatCount(post.comment_count)} comments`}</button>`
    : '';

  body.innerHTML = `
    ${likeCount}
    ${caption}
    ${preview || viewMore
      ? `<div class="post-comments-preview">${preview}${viewMore}</div>`
      : ''}
    <div class="post-timestamp">${relativeTime(post.created_at)}</div>
  `;
  return body;
}

function buildCommentInput(postId) {
  const wrap = document.createElement('div');
  wrap.className = 'post-comment-input';
  wrap.innerHTML = `
    <textarea class="comment-field" rows="1" placeholder="Add a comment…" maxlength="500"></textarea>
    <button class="comment-submit" disabled>Post</button>
  `;
  return wrap;
}

function wirePostCard(card, post) {
  const postId = post.id;

  const likeBtn = card.querySelector('.like-btn');
  const likeCountEl = card.querySelector('.like-count');
  likeBtn.addEventListener('click', async () => {
    const isLiked = likeBtn.dataset.liked === 'true';
    const prev = parseInt(likeCountEl.textContent) || 0;

    likeBtn.dataset.liked = String(!isLiked);
    likeBtn.classList.toggle('liked', !isLiked);
    likeBtn.querySelector('svg').setAttribute('fill', !isLiked ? 'currentColor' : 'none');
    likeCountEl.textContent = formatCount(!isLiked ? prev + 1 : Math.max(0, prev - 1));

    try {
      if (isLiked) await api.posts.unlike(postId);
      else         await api.posts.like(postId);
    } catch(err) {
      console.error("wirePostCard Oprimistic: ", err)
      likeBtn.dataset.liked = String(isLiked);
      likeBtn.classList.toggle('liked', isLiked);
      likeBtn.querySelector('svg').setAttribute('fill', isLiked ? 'currentColor' : 'none');
      likeCountEl.textContent = formatCount(prev);
      toastError('Could not update like');
    }
  });

  const saveBtn = card.querySelector('.save-btn');
  saveBtn.addEventListener('click', async () => {
    const isSaved = saveBtn.dataset.saved === 'true';
    saveBtn.dataset.saved = String(!isSaved);
    saveBtn.classList.toggle('saved', !isSaved);
    saveBtn.querySelector('svg').setAttribute('fill', !isSaved ? 'currentColor' : 'none');
    try {
      if (isSaved) await api.posts.unsave(postId);
      else         await api.posts.save(postId);
    } catch(err) {
      console.error("wirePostCard save: ", err)
      saveBtn.dataset.saved = String(isSaved);
      saveBtn.classList.toggle('saved', isSaved);
      saveBtn.querySelector('svg').setAttribute('fill', isSaved ? 'currentColor' : 'none');
      toastError('Could not update save');
    }
  });

  const textarea = card.querySelector('.comment-field');
  const submitBtn = card.querySelector('.comment-submit');
  textarea.addEventListener('input', () => {
    submitBtn.disabled = textarea.value.trim().length === 0;
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
  });

  submitBtn.addEventListener('click', async () => {
    const text = textarea.value.trim();
    if (!text) return;
    submitBtn.disabled = true;
    try {
      await api.posts.addComment(postId, text);
      textarea.value = '';
      textarea.style.height = 'auto';
      toast('Comment posted', 'success', 1800);
    } catch(err) {
      console.error("wirePostCard submit comment: ", err)
      toastError('Failed to post comment');
      submitBtn.disabled = false;
    }
  });

  card.querySelector('.share-btn').addEventListener('click', () => {
    const url = `${window.location.origin}#post/${postId}`;
    navigator.clipboard?.writeText(url).then(() => toast('Link copied!', 'success', 1800));
  });

  card.querySelector('.view-comments-btn')?.addEventListener('click', () => {
    window.location.hash = `#post/${postId}`;
  });
}

function escHtml(str = '') {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatCaption(text = '') {
  return escHtml(text)
    .replace(/#(\w+)/g, '<span class="hashtag">#$1</span>')
    .replace(/@(\w+)/g, '<span class="author-tag">@$1</span>');
}
