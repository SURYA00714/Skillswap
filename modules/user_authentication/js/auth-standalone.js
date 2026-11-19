/**
 * auth-standalone.js
 * Standalone authentication and security manager for SwapSkills module.
 * Runs completely in Live Server, file://, or with any static web server without backend dependencies.
 */

const STORAGE_USERS_KEY = 'swapskills_registered_users';
const STORAGE_CURRENT_USER_KEY = 'swapskills_current_session_user';

// Helper: Seed demo user if none exists
(function initMockData() {
  const existing = localStorage.getItem(STORAGE_USERS_KEY);
  if (!existing) {
    const demoUsers = [
      {
        id: 'usr_demo_101',
        fullName: 'Alex Morgan',
        email: 'alex@example.com',
        password: 'Password123!',
        gender: 'Prefer not to say',
        twoFactorEnabled: false,
        createdAt: new Date().toISOString()
      }
    ];
    localStorage.setItem(STORAGE_USERS_KEY, JSON.stringify(demoUsers));
  }
})();

// Get all users
function getRegisteredUsers() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_USERS_KEY)) || [];
  } catch (e) {
    return [];
  }
}

// Save user list
function saveRegisteredUsers(users) {
  localStorage.setItem(STORAGE_USERS_KEY, JSON.stringify(users));
}

// Get current logged-in user
function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_CURRENT_USER_KEY));
  } catch (e) {
    return null;
  }
}

// Set current logged-in user
function setCurrentUser(user) {
  localStorage.setItem(STORAGE_CURRENT_USER_KEY, JSON.stringify(user));
}

// Clear current session
function clearCurrentSession() {
  localStorage.removeItem(STORAGE_CURRENT_USER_KEY);
  sessionStorage.clear();
}

// Display notification toast
function showToast(message, type = 'info') {
  let toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toastContainer';
    toastContainer.style.cssText = `
      position: fixed;
      top: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    `;
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  const colors = {
    success: { bg: '#10b981', icon: 'fa-check-circle' },
    error: { bg: '#ef4444', icon: 'fa-exclamation-circle' },
    warning: { bg: '#f59e0b', icon: 'fa-exclamation-triangle' },
    info: { bg: '#6366f1', icon: 'fa-info-circle' }
  };
  const config = colors[type] || colors.info;

  toast.style.cssText = `
    background: ${config.bg};
    color: #ffffff;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    gap: 10px;
    animation: fadeInSlide 0.3s ease;
    pointer-events: auto;
  `;
  toast.innerHTML = `<i class="fas ${config.icon}"></i> <span>${message}</span>`;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Password strength calculation
function checkPasswordStrength(password) {
  let score = 0;
  if (!password) return { score: 0, label: '', color: 'transparent' };
  if (password.length >= 6) score += 1;
  if (password.length >= 10) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 2) return { score, label: 'Weak', color: '#ef4444', width: '33%' };
  if (score <= 4) return { score, label: 'Medium', color: '#f59e0b', width: '66%' };
  return { score, label: 'Strong', color: '#10b981', width: '100%' };
}

// Setup Registration Form
function setupRegistration() {
  const form = document.getElementById('emailSignUpForm');
  const passwordInput = document.getElementById('password');
  const confirmPasswordInput = document.getElementById('confirmPassword');
  const strengthMeter = document.getElementById('passwordStrength');
  const matchIndicator = document.getElementById('passwordMatch');

  if (passwordInput && strengthMeter) {
    passwordInput.addEventListener('input', () => {
      const result = checkPasswordStrength(passwordInput.value);
      strengthMeter.innerHTML = `
        <div style="height: 4px; width: 100%; background: #e2e8f0; border-radius: 2px; margin-top: 6px; overflow: hidden;">
          <div style="height: 100%; width: ${result.width}; background: ${result.color}; transition: all 0.3s;"></div>
        </div>
        <span style="font-size: 0.75rem; color: ${result.color}; font-weight: 600; margin-top: 4px; display: inline-block;">
          ${result.label ? 'Strength: ' + result.label : ''}
        </span>
      `;
    });
  }

  if (confirmPasswordInput && matchIndicator) {
    confirmPasswordInput.addEventListener('input', () => {
      if (!confirmPasswordInput.value) {
        matchIndicator.innerHTML = '';
        return;
      }
      if (confirmPasswordInput.value === passwordInput.value) {
        matchIndicator.innerHTML = '<span style="color: #10b981; font-size: 0.75rem; font-weight: 600;"><i class="fas fa-check"></i> Passwords match</span>';
      } else {
        matchIndicator.innerHTML = '<span style="color: #ef4444; font-size: 0.75rem; font-weight: 600;"><i class="fas fa-times"></i> Passwords do not match</span>';
      }
    });
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const password = passwordInput.value;
      const confirmPassword = confirmPasswordInput.value;
      const gender = document.getElementById('gender') ? document.getElementById('gender').value : 'Prefer not to say';

      if (password !== confirmPassword) {
        showToast('Passwords do not match', 'error');
        return;
      }

      if (password.length < 6) {
        showToast('Password must be at least 6 characters', 'warning');
        return;
      }

      const users = getRegisteredUsers();
      if (users.some(u => u.email.toLowerCase() === email.toLowerCase())) {
        showToast('An account with this email already exists', 'warning');
        return;
      }

      const newUser = {
        id: 'usr_' + Date.now(),
        fullName: email.split('@')[0],
        email: email,
        password: password,
        gender: gender,
        twoFactorEnabled: false,
        createdAt: new Date().toISOString()
      };

      users.push(newUser);
      saveRegisteredUsers(users);
      setCurrentUser(newUser);

      showToast('Account created successfully! Redirecting...', 'success');
      setTimeout(() => {
        window.location.href = 'security.html';
      }, 1200);
    });
  }
}

// Setup Login Form
function setupLogin() {
  const form = document.getElementById('emailSignInForm');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;

      const users = getRegisteredUsers();
      const user = users.find(u => u.email.toLowerCase() === email.toLowerCase() && u.password === password);

      if (user) {
        setCurrentUser(user);
        showToast('Sign in successful! Welcome back.', 'success');
        setTimeout(() => {
          window.location.href = 'security.html';
        }, 1000);
      } else {
        // Allow fallback / demo login if no exact match
        if (email && password.length >= 6) {
          const quickUser = {
            id: 'usr_' + Date.now(),
            fullName: email.split('@')[0],
            email: email,
            password: password,
            twoFactorEnabled: false,
            createdAt: new Date().toISOString()
          };
          users.push(quickUser);
          saveRegisteredUsers(users);
          setCurrentUser(quickUser);
          showToast('Signed in with new credentials!', 'success');
          setTimeout(() => {
            window.location.href = 'security.html';
          }, 1000);
        } else {
          showToast('Invalid email or password (min 6 characters)', 'error');
        }
      }
    });
  }
}

// Google Sign-In Simulation
function signInWithGoogle() {
  const demoEmail = 'google.user@example.com';
  const user = {
    id: 'usr_g_' + Date.now(),
    fullName: 'Google User',
    email: demoEmail,
    provider: 'google.com',
    twoFactorEnabled: false,
    createdAt: new Date().toISOString()
  };
  setCurrentUser(user);
  showToast('Google authentication successful! Redirecting...', 'success');
  setTimeout(() => {
    window.location.href = 'security.html';
  }, 1000);
}

// Forgot Password UI Helpers
function showForgotPassword() {
  const signInForm = document.getElementById('emailSignInForm');
  const forgotForm = document.getElementById('forgotPasswordForm');
  if (signInForm) signInForm.style.display = 'none';
  if (forgotForm) forgotForm.style.display = 'block';
}

function hideForgotPassword() {
  const signInForm = document.getElementById('emailSignInForm');
  const forgotForm = document.getElementById('forgotPasswordForm');
  if (signInForm) signInForm.style.display = 'block';
  if (forgotForm) forgotForm.style.display = 'none';
}

function resetPassword() {
  const emailInput = document.getElementById('resetEmail');
  if (!emailInput || !emailInput.value.trim()) {
    showToast('Please enter your email address', 'warning');
    return;
  }
  showToast(`Password reset link simulated for ${emailInput.value.trim()}`, 'success');
  setTimeout(() => {
    hideForgotPassword();
  }, 1500);
}
