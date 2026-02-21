// Landing page - Login / Sign up buttons
document.addEventListener('DOMContentLoaded', async () => {
  await initAuth0();

  // If already logged in, redirect to dashboard
  if (auth0 && (await isAuthenticated())) {
    window.location.href = 'dashboard.html';
    return;
  }

  document.getElementById('loginBtn').addEventListener('click', loginOnly);
  document.getElementById('signupBtn').addEventListener('click', login);
  document.getElementById('heroSignup').addEventListener('click', login);

  // Show demo link when Auth0 not configured
  const config = window.AUTH0_CONFIG || {};
  if (!config.domain || config.domain.includes('YOUR_')) {
    document.getElementById('demoLink').classList.remove('hidden');
  }
});
