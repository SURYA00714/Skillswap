// theme.js - Global Theme Toggle (Dark / Light) with LocalStorage persistence
(function() {
  function injectBaseThemeStyles() {
    if (document.getElementById('swapskills-theme-base-styles')) return;
    const style = document.createElement('style');
    style.id = 'swapskills-theme-base-styles';
    style.textContent = `
      [data-theme="dark"] ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
      }
      [data-theme="dark"] ::-webkit-scrollbar-track {
        background: #0b1120;
      }
      [data-theme="dark"] ::-webkit-scrollbar-thumb {
        background: #334155;
        border-radius: 4px;
      }
      [data-theme="dark"] ::-webkit-scrollbar-thumb:hover {
        background: #475569;
      }
      [data-theme="dark"] ::selection {
        background: rgba(99, 102, 241, 0.4);
        color: #ffffff;
      }
      body, .navbar, .card, .profile-card, .request-card, .detail-card, .modal-content, input, select, textarea {
        transition: background-color 0.25s ease, border-color 0.25s ease, color 0.25s ease;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function initTheme() {
    const savedTheme = localStorage.getItem('swapskills_theme') || 
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', savedTheme);
    injectBaseThemeStyles();
    updateThemeIcons(savedTheme);
  }

  function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('swapskills_theme', newTheme);
    updateThemeIcons(newTheme);
  }

  function updateThemeIcons(theme) {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      const isDark = theme === 'dark';
      btn.innerHTML = `
        <span class="theme-toggle-thumb"><i class="fas ${isDark ? 'fa-moon' : 'fa-sun'}"></i></span>
        <span class="theme-toggle-text">${isDark ? 'DARK<br>MODE' : 'LIGHT<br>MODE'}</span>
      `;
      btn.setAttribute('title', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');
      btn.setAttribute('aria-label', isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode');
    });
  }

  // Run immediately to prevent flash of wrong theme
  initTheme();

  // Attach event listeners once DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    
    // Delegate click event so all theme buttons work reliably everywhere
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('.theme-toggle-btn');
      if (btn) {
        e.preventDefault();
        toggleTheme();
      }
    });

    // Mobile menu toggle logic helper if present
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    if (mobileBtn && mobileMenu) {
      mobileBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        mobileBtn.classList.toggle('active');
        mobileMenu.classList.toggle('active');
      });
      document.addEventListener('click', function(e) {
        if (!mobileMenu.contains(e.target) && !mobileBtn.contains(e.target)) {
          mobileBtn.classList.remove('active');
          mobileMenu.classList.remove('active');
        }
      });
    }
  });

  window.toggleSkillSwapTheme = toggleTheme;
})();
