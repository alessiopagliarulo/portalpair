// Landing page - Login / Sign up buttons
document.addEventListener('DOMContentLoaded', async () => {
  await initAuth0();

  // If already logged in, redirect to dashboard
  if (auth0 && (await isAuthenticated())) {
    window.location.href = 'dashboard.html';
    return;
  }

  document.getElementById('loginBtn').addEventListener('click', async () => {
    if (!auth0) {
      const cfg = window.AUTH0_CONFIG || {};
      const msg = (!cfg.domain || !cfg.clientId) 
        ? 'Auth0 not configured. Add domain and clientId in js/config.js'
        : 'Auth0 SDK failed to load. Try hard refresh (Ctrl+Shift+R) or check the browser console.';
      alert(msg);
      return;
    }
    await loginOnly();
  });
  document.getElementById('signupBtn').addEventListener('click', async () => {
    if (!auth0) {
      const cfg = window.AUTH0_CONFIG || {};
      const msg = (!cfg.domain || !cfg.clientId) 
        ? 'Auth0 not configured. Add domain and clientId in js/config.js'
        : 'Auth0 SDK failed to load. Try hard refresh (Ctrl+Shift+R) or check the browser console.';
      alert(msg);
      return;
    }
    await login();
  });
  document.getElementById('heroSignup').addEventListener('click', handleSignup);
  const finalSignup = document.getElementById('finalSignup');
  if (finalSignup) finalSignup.addEventListener('click', handleSignup);

  async function handleSignup() {
    if (!auth0) {
      const cfg = window.AUTH0_CONFIG || {};
      const msg = (!cfg.domain || !cfg.clientId) 
        ? 'Auth0 not configured. Add domain and clientId in js/config.js'
        : 'Auth0 SDK failed to load. Try hard refresh (Ctrl+Shift+R) or check the browser console.';
      alert(msg);
      return;
    }
    await login();
  }

  // Show demo link when Auth0 not configured
  const config = window.AUTH0_CONFIG || {};
  if (!config.domain || config.domain.includes('YOUR_')) {
    document.getElementById('demoLink').classList.remove('hidden');
  }

  // Scroll reveal for sections — animate every time you scroll to them
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      e.target.classList.toggle('revealed', e.isIntersecting);
    });
  }, { threshold: 0.15 });
  document.querySelectorAll('.how-step, .story-content, .cta-inner').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    observer.observe(el);
  });
  const revealedStyle = document.createElement('style');
  revealedStyle.textContent = '.revealed { opacity: 1 !important; transform: translateY(0) !important; }';
  document.head.appendChild(revealedStyle);
});
