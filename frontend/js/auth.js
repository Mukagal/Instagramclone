import api from './api.js';
import { toast, toastError, setButtonLoading, setFieldError } from './ui.js';

let _currentUser = null;

export function getCurrentUser() { return _currentUser; }
export function setCurrentUser(u) { _currentUser = u; }
export function isLoggedIn() { return !!api.storage.getToken(); }


export async function initAuth() {
  if (!api.storage.getToken()) return null;
  try {
    _currentUser = await api.users.getMe();
    return _currentUser;
  } catch(err) {
    console.error("initAuth: ", err);
    
    api.storage.clearTokens();
    return null;
  }
}

export function renderLoginPage(container) {
  container.innerHTML = `
    <div class="auth-shell">
      <div class="auth-card card">
        <div class="auth-brand">
          <div class="auth-brand-icon">I</div>
          <span class="auth-brand-name">Instagram</span>
        </div>

        <h1 class="auth-heading">Welcome back</h1>
        <p class="auth-sub">Sign in to your account</p>

        <form id="login-form" novalidate>
          <div class="flex-col gap-3">
            <div class="input-group">
              <label for="login-email">Email</label>
              <input id="login-email" name="email" type="email" class="input" placeholder="you@example.com" autocomplete="email" required />
            </div>
            <div class="input-group">
              <label for="login-password">Password</label>
              <div class="input-password-wrap">
                <input id="login-password" name="password" type="password" class="input" placeholder="••••••••" autocomplete="current-password" required />
                <button type="button" class="password-toggle" aria-label="Toggle password">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div class="auth-forgot">
            <a href="#forgot" class="auth-link">Forgot password?</a>
          </div>

          <button type="submit" id="login-btn" class="btn btn-primary" style="width:100%;margin-top:var(--s5)">
            Sign in
          </button>
        </form>

        <div class="auth-divider"><span>or</span></div>

        <p class="auth-switch">
          Don't have an account? <a href="#signup" class="auth-link">Sign up</a>
        </p>
      </div>
    </div>
  `;

  injectAuthStyles();
  wireLoginForm(container);
}

function wireLoginForm(container) {
  const form = container.querySelector('#login-form');
  const btn = container.querySelector('#login-btn');
  const emailEl = container.querySelector('#login-email');
  const passEl = container.querySelector('#login-password');
  const toggleEl = container.querySelector('.password-toggle');

  toggleEl?.addEventListener('click', () => {
    passEl.type = passEl.type === 'password' ? 'text' : 'password';
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    setFieldError(emailEl, '');
    setFieldError(passEl, '');

    const email = emailEl.value.trim();
    const pass = passEl.value;
    if (!email) { setFieldError(emailEl, 'Email is required'); return; }
    if (!pass) { setFieldError(passEl,  'Password is required'); return; }

    setButtonLoading(btn, true);
    try {
      const data = await api.auth.login(email, pass);
      _currentUser = data.user;
      toast('Welcome back!', 'success');
      window.location.hash = '#feed';
    } catch (err) {
      toastError(err.message || 'Login failed');
    } finally {
      setButtonLoading(btn, false);
    }
  });
}

export function renderSignupPage(container) {
  container.innerHTML = `
    <div class="auth-shell">
      <div class="auth-card card">
        <div class="auth-brand">
          <div class="auth-brand-icon">I</div>
          <span class="auth-brand-name">Instagram</span>
        </div>

        <h1 class="auth-heading">Create account</h1>
        <p class="auth-sub">Join the community today</p>

        <form id="signup-form" novalidate>
          <div class="flex-col gap-3">
            <div class="flex gap-3">
              <div class="input-group" style="flex:1">
                <label for="su-fname">First name</label>
                <input id="su-fname" name="first_name" type="text" class="input" placeholder="Jane" required />
              </div>
              <div class="input-group" style="flex:1">
                <label for="su-lname">Last name</label>
                <input id="su-lname" name="last_name" type="text" class="input" placeholder="Doe" />
              </div>
            </div>
            <div class="input-group">
              <label for="su-username">Username</label>
              <input id="su-username" name="username" type="text" class="input" placeholder="janedoe" autocomplete="username" required />
            </div>
            <div class="input-group">
              <label for="su-email">Email</label>
              <input id="su-email" name="email" type="email" class="input" placeholder="jane@example.com" autocomplete="email" required />
            </div>
            <div class="input-group">
              <label for="su-password">Password</label>
              <input id="su-password" name="password" type="password" class="input" placeholder="At least 8 characters" autocomplete="new-password" required />
            </div>
          </div>

          <button type="submit" id="signup-btn" class="btn btn-primary" style="width:100%;margin-top:var(--s5)">
            Create account
          </button>
        </form>

        <p class="auth-terms">
          By signing up you agree to our <a href="#terms" class="auth-link">Terms</a> and <a href="#privacy" class="auth-link">Privacy Policy</a>.
        </p>

        <p class="auth-switch">
          Already have an account? <a href="#login" class="auth-link">Sign in</a>
        </p>
      </div>
    </div>
  `;

  injectAuthStyles();
  wireSignupForm(container);
}

function wireSignupForm(container) {
  const form = container.querySelector('#signup-form');
  const btn = container.querySelector('#signup-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const emailEl = form.querySelector('#su-email');
    const passEl = form.querySelector('#su-password');
    const userEl = form.querySelector('#su-username');

    setFieldError(emailEl, '');
    setFieldError(passEl, '');
    setFieldError(userEl, '');

    const payload = {
      first_name: form.querySelector('#su-fname').value.trim(),
      last_name: form.querySelector('#su-lname').value.trim(),
      username: userEl.value.trim(),
      email: emailEl.value.trim(),
      password: passEl.value,
    };

    if (!payload.username) { setFieldError(userEl,  'Username is required'); return; }
    if (!payload.email) { setFieldError(emailEl, 'Email is required'); return; }
    if (payload.password.length < 8) { setFieldError(passEl, 'Must be at least 8 characters'); return; }

    setButtonLoading(btn, true);
    try {
      await api.auth.signup(payload);
      toast('Account created! Check your email to verify.', 'success', 5000);
      window.location.hash = '#login';
    } catch (err) {
      toastError(err.message || 'Signup failed');
    } finally {
      setButtonLoading(btn, false);
    }
  });
}

export function renderForgotPage(container) {
  container.innerHTML = `
    <div class="auth-shell">
      <div class="auth-card card">
        <a href="#login" class="auth-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back to login
        </a>
        <h1 class="auth-heading" style="margin-top:var(--s4)">Reset password</h1>
        <p class="auth-sub">We'll send you a reset link.</p>

        <form id="forgot-form" novalidate>
          <div class="input-group" style="margin-top:var(--s4)">
            <label for="forgot-email">Email</label>
            <input id="forgot-email" type="email" class="input" placeholder="you@example.com" required />
          </div>
          <button type="submit" id="forgot-btn" class="btn btn-primary" style="width:100%;margin-top:var(--s5)">
            Send reset link
          </button>
        </form>
      </div>
    </div>
  `;

  injectAuthStyles();
  const form = container.querySelector('#forgot-form');
  const btn = container.querySelector('#forgot-btn');
  const emailEl = container.querySelector('#forgot-email');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = emailEl.value.trim();
    if (!email) { setFieldError(emailEl, 'Email is required'); return; }
    setButtonLoading(btn, true);
    try {
      await api.auth.forgotPassword(email);
      toast('If that email exists, a reset link has been sent.', 'success', 5000);
    } catch (err) {
      toastError(err.message || 'Request failed');
    } finally {
      setButtonLoading(btn, false);
    }
  });
}

function injectAuthStyles() {
  if (document.getElementById('auth-styles')) return;
  const style = document.createElement('style');
  style.id = 'auth-styles';
  style.textContent = `
    .auth-shell {
      min-height: 100vh;
      width: 100%;
      display: flex; align-items: center; justify-content: center;
      padding: var(--s4);
      background: var(--bg);
      /* Cover full screen even inside the grid column */
      position: fixed; inset: 0; overflow-y: auto;
    }
    .auth-card {
      width: min(440px, 100%);
      padding: var(--s7) var(--s6);
      /* Ensure it's above everything */
      position: relative; z-index: 1;
    }
    .auth-brand {
      display: flex; align-items: center; gap: var(--s2);
      margin-bottom: var(--s6);
    }
    .auth-brand-icon {
      width: 32px; height: 32px;
      background: var(--accent); color: #1a1400;
      font-weight: 700; font-size: 1rem;
      border-radius: var(--r-md);
      display: flex; align-items: center; justify-content: center;
    }
    .auth-brand-name {
      font-family: var(--font-serif); font-size: 1.25rem;
    }
    .auth-heading {
      font-family: var(--font-serif); font-size: 1.7rem; font-weight: 400;
      letter-spacing: -0.01em; margin-bottom: var(--s1);
    }
    .auth-sub { color: var(--text-secondary); font-size: .88rem; margin-bottom: var(--s5); }
    .auth-forgot { text-align: right; margin-top: var(--s2); }
    .auth-link { color: var(--accent); font-size: .85rem; transition: opacity var(--t-fast); }
    .auth-link:hover { opacity: .75; }
    .auth-divider {
      display: flex; align-items: center; gap: var(--s3);
      color: var(--text-muted); font-size: .8rem; margin: var(--s5) 0;
    }
    .auth-divider::before,.auth-divider::after {
      content:''; flex:1; height:1px; background: var(--border);
    }
    .auth-switch { text-align: center; font-size: .85rem; color: var(--text-secondary); margin-top: var(--s4); }
    .auth-terms  { text-align: center; font-size: .78rem; color: var(--text-muted); margin-top: var(--s3); line-height: 1.5; }
    .auth-back   {
      display: inline-flex; align-items: center; gap: 6px;
      color: var(--text-secondary); font-size: .85rem;
      transition: color var(--t-fast);
    }
    .auth-back:hover { color: var(--text-primary); }
    .input-password-wrap { position: relative; }
    .input-password-wrap .input { padding-right: 40px; }
    .password-toggle {
      position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
      color: var(--text-muted); transition: color var(--t-fast);
    }
    .password-toggle:hover { color: var(--text-primary); }
  `;
  document.head.appendChild(style);
}