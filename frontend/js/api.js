const BASE_URL = 'http://127.0.0.1:8000/api/v1';  

const storage = {
  getToken() { return localStorage.getItem('access_token'); },
  setTokens(a, r) { localStorage.setItem('access_token', a); localStorage.setItem('refresh_token', r); },
  clearTokens() { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token'); },
  getRefreshToken() { return localStorage.getItem('refresh_token'); },
};

async function fetchWithTimeout(url, options = {}, timeoutMs = 12000) {
  if (options.signal) return fetch(url, options);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err.name === 'AbortError') {
      throw Object.assign(new Error('Request timed out'), { status: 408 });
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}
async function request(method, path, { body, params, form, signal } = {}) {
  const url = new URL(BASE_URL + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    });
  }

  const headers = {};
  const token = storage.getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let bodyPayload = undefined;
  if (form) {
    bodyPayload = form;
  } else if (body) {
    headers['Content-Type'] = 'application/json';
    bodyPayload = JSON.stringify(body);
  }
  let res = await fetchWithTimeout(url, { method, headers, body: bodyPayload, signal });

  if (res.status === 401 && storage.getRefreshToken()) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${storage.getToken()}`;
      res = await fetchWithTimeout(url, { method, headers, body: bodyPayload, signal });
    } else {
      storage.clearTokens();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    if (res.status === 401) {
      storage.clearTokens();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    throw Object.assign(new Error(err.detail || 'Request failed'), { status: res.status, data: err });
  }

  if (res.status === 204) return null;
  return res.json();
}

const get = (path, opts) => request('GET',    path, opts);
const post = (path, opts) => request('POST',   path, opts);
const patch = (path, opts) => request('PATCH',  path, opts);
const del = (path, opts) => request('DELETE', path, opts);

async function refreshAccessToken() {
  try {
    const refresh = storage.getRefreshToken();
    const res = await fetchWithTimeout(`${BASE_URL}/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${refresh}` },
    });
    if (!res.ok) { storage.clearTokens(); return false; }
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    return true;
  } catch(err) {
    console.error("Api: ", err)
    storage.clearTokens();
    return false;
  }
}

const auth = {
  signup(data)  { return post('/signup',  { body: data }); },

  async login(email, password) {
    const data = await post('/login', { body: { email, password } });
    storage.setTokens(data.access_token, data.refresh_token);
    return data;
  },

  async logout() {
    await post('/logout').catch(() => {});
    storage.clearTokens();
  },

  refresh() { return refreshAccessToken(); },

  verifyEmail(token) { return get('/verify-email', { params: { token } }); },

  forgotPassword(email) { return post('/forgot-password', { body: { email } }); },

  resetPassword(token, newPassword) { return post('/reset-password', { body: { token, new_password: newPassword } }); },
};

const users = {
  getMe() { return get('/users/me'); },

  updateMe(data) { return patch('/users/me', { body: data }); },

  updateProfile(data) { return patch('/users/me/profile', { body: data }); },

  deleteMe() { return del('/users/me'); },

  uploadAvatar(file) {
    const form = new FormData();
    form.append('file', file);
    return post('/users/me/avatar', { form });
  },

  search({ username, skip = 0, limit = 20 } = {}) {
    return get('/users', { params: { username, skip, limit } });
  },

  getById(id) { return get(`/users/${id}`); },

  getByUsername(username) { return get(`/users/by-username/${username}`); },

  follow(id) { return post(`/users/${id}/follow`); },

  unfollow(id) { return del(`/users/${id}/follow`); },

  acceptFollowRequest(requesterId) { return post(`/follow-requests/${requesterId}/accept`); },

  rejectFollowRequest(requesterId) { return del(`/follow-requests/${requesterId}/reject`); },

  removeFollower(followerId) { return del(`/users/${followerId}/remove-follower`); },

  getFollowers(id, { skip = 0, limit = 20 } = {}) {
    return get(`/users/${id}/followers`, { params: { skip, limit } });
  },

  getFollowing(id, { skip = 0, limit = 20 } = {}) {
    return get(`/users/${id}/following`, { params: { skip, limit } });
  },

  getFollowRequests() { return get('/users/me/follow-requests'); },

  block(id) { return post(`/users/${id}/block`); },

  unblock(id) { return del(`/users/${id}/block`); },

  getBlocked() { return get('/users/me/blocked'); },
};

const posts = {
  getExploreFeed({ sortBy = 'latest', keyword, skip = 0, limit = 20 } = {}) {
    return get('/feed', { params: { sort_by: sortBy, keyword, skip, limit } });
  },

  getFollowingFeed({ skip = 0, limit = 20 } = {}) {
    return get('/feed/following', { params: { skip, limit } });
  },

  
  create(meta, files) {
    const form = new FormData();
    if (meta.caption) form.append('caption', meta.caption);
    if (meta.locationName) form.append('location_name', meta.locationName);
    if (meta.hideLikeCount) form.append('hide_like_count', 'true');
    if (meta.disableComments) form.append('disable_comments', 'true');
    if (meta.taggedUserIds?.length) form.append('tagged_user_ids', meta.taggedUserIds.join(','));
    files.forEach(f => form.append('files', f));
    return post('/posts', { form });
  },

  getById(id) { return get(`/posts/${id}`); },

  update(id, data) { return patch(`/posts/${id}`, { body: data }); },

  toggleArchive(id) { return post(`/posts/${id}/archive`); },

  delete(id) { return del(`/posts/${id}`); },

  getUserPosts(userId, { sortBy = 'latest', skip = 0, limit = 20 } = {}) {
    return get(`/users/${userId}/posts`, { params: { sort_by: sortBy, skip, limit } });
  },

  getArchived() { return get('/users/me/posts/archived'); },

  like(id) { return post(`/posts/${id}/like`); },
  unlike(id) { return del(`/posts/${id}/like`); },
  getLikers(id) { return get(`/posts/${id}/likes`); },

  getComments(id, { skip = 0, limit = 20, includeReplies = false } = {}) {
    return get(`/posts/${id}/comments`, { params: { skip, limit, include_replies: includeReplies } });
  },
  getReplies(commentId, { skip = 0, limit = 20 } = {}) {
    return get(`/comments/${commentId}/replies`, { params: { skip, limit } });
  },
  addComment(postId, text, parentId = null) {
    return post(`/posts/${postId}/comments`, { body: { content: text, parent_id: parentId } });
  },
  updateComment(commentId, text) {
    return patch(`/comments/${commentId}`, { body: { content: text } });
  },
  deleteComment(commentId) {
    return del(`/comments/${commentId}`);
  },
  likeComment(id)   { return post(`/comments/${id}/like`); },
  unlikeComment(id) { return del(`/comments/${id}/like`); },

  save(postId, collectionId = null) {
    return post(`/posts/${postId}/save`, { params: { collection_id: collectionId } });
  },
  unsave(postId) { return del(`/posts/${postId}/save`); },
  getSaved({ skip = 0, limit = 20 } = {}) {
    return get('/users/me/saved', { params: { skip, limit } });
  },
  createCollection(name)  { return post('/collections', { body: { name } }); },
  getCollections()        { return get('/collections'); },

  getMyInteractions() { return get('/me/posts/interactions'); },
  getLikedPosts()     { return get('/me/liked-posts'); },
  getCommentedPosts() { return get('/me/commented-posts'); },
};

const messages = {
  getThreads({ skip = 0, limit = 30 } = {}) {
    return get('/threads', { params: { skip, limit } });
  },

  getOrCreateDM(targetId) { return post(`/threads/dm/${targetId}`); },

  createGroup(data) { return post('/threads/group', { body: data }); },

  getThread(id) { return get(`/threads/${id}`); },

  updateGroup(id, data) { return patch(`/threads/${id}`, { body: data }); },

  updateGroupCover(id, file) {
    const form = new FormData();
    form.append('file', file);
    return patch(`/threads/${id}/cover`, { form });
  },

  addMembers(threadId, memberIds) {
    return post(`/threads/${threadId}/members`, { body: memberIds });
  },

  removeMember(threadId, targetId) {
    return del(`/threads/${threadId}/members/${targetId}`);
  },

  leaveThread(id) { return post(`/threads/${id}/leave`); },

  promoteMember(threadId, targetId) {
    return post(`/threads/${threadId}/members/${targetId}/promote`);
  },

  
  getMessages(threadId, { skip = 0, limit = 30, beforeId } = {}) {
    return get(`/threads/${threadId}/messages`, {
      params: { skip, limit, before_id: beforeId },
    });
  },

  
  sendMessage(threadId, text, file = null) {
    const content = text?.trim();
    const messageType = file
      ? file.type.startsWith('video/')
        ? 'video'
        : file.type.startsWith('audio/')
          ? 'voice'
          : 'image'
      : 'text';

    const params = { message_type: messageType };
    if (content) params.content = content;

    let form = null;
    if (file) {
      form = new FormData();
      form.append('file', file);
    }

    return post(`/threads/${threadId}/messages`, { params, form });
  },

  unsendMessage(messageId) { return del(`/messages/${messageId}`); },

  addReaction(messageId, emoji) {
    return post(`/messages/${messageId}/reaction`, { body: { emoji } });
  },

  removeReaction(messageId) {
    return del(`/messages/${messageId}/reaction`);
  },
};

const stories = {
  create(meta, file) {
    const form = new FormData();
    form.append('file', file);
    if (meta.caption) form.append('caption', meta.caption);
    if (meta.locationName) form.append('location_name', meta.locationName);
    if (meta.closeFriendsOnly) form.append('close_friends_only', 'true');
    if (meta.linkUrl) form.append('link_url', meta.linkUrl);
    if (meta.mentionUserIds?.length) form.append('mention_user_ids', meta.mentionUserIds.join(','));
    if (meta.poll) form.append('poll', JSON.stringify(meta.poll));
    if (meta.question) form.append('question', JSON.stringify(meta.question));
    return post('/stories', { form });
  },

  getTray({ skip = 0, limit = 30 } = {}) {
    return get('/stories/tray', { params: { skip, limit } });
  },

  getUserStories(userId, { includeExpired = false } = {}) {
    return get(`/users/${userId}/stories`, { params: { include_expired: includeExpired } });
  },

  getById(id) { return get(`/stories/${id}`); },

  markView(id) { return post(`/stories/${id}/view`); },

  getViewers(id) { return get(`/stories/${id}/viewers`); },

  delete(id) { return del(`/stories/${id}`); },

  react(id, reaction) {
    return post(`/stories/${id}/reaction`, { body: { reaction } });
  },

  removeReaction(id) { return del(`/stories/${id}/reaction`); },

  votePoll(id, choice) {
    return post(`/stories/${id}/poll/vote`, { body: { choice } });
  },

  answerQuestion(id, answerText) {
    return post(`/stories/${id}/question/answers`, { body: { answer_text: answerText } });
  },

  getQuestionAnswers(id) {
    return get(`/stories/${id}/question/answers`);
  },

  createHighlight(data) { return post('/highlights', { body: data }); },
  getHighlights() { return get('/highlights'); },
  getUserHighlights(userId) { return get(`/users/${userId}/highlights`); },
  getHighlight(id) { return get(`/highlights/${id}`); },
  updateHighlight(id, data) { return patch(`/highlights/${id}`, { body: data }); },
  deleteHighlight(id) { return del(`/highlights/${id}`); },
  addToHighlight(highlightId, storyId) {
    return post(`/highlights/${highlightId}/stories/${storyId}`);
  },
  removeFromHighlight(highlightId, storyId) {
    return del(`/highlights/${highlightId}/stories/${storyId}`);
  },
};

const notifications = {
  list({ skip = 0, limit = 30 } = {}) {
    return get('/notifications', { params: { skip, limit } });
  },

  unreadCount() { return get('/notifications/unread-count'); },

  markRead(id) { return post(`/notifications/${id}/read`); },

  markAllRead() { return post('/notifications/read-all'); },

  delete(id) { return del(`/notifications/${id}`); },
};

const api = { auth, users, posts, messages, stories, notifications, storage };
export default api;
