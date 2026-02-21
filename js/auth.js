// Auth0 integration for Portal Pair
let auth0 = null;

async function initAuth0() {
  const config = window.AUTH0_CONFIG || {};
  if (!config.domain || !config.clientId || config.domain.includes('YOUR_')) {
    console.warn('Auth0 not configured. Using demo mode.');
    return null;
  }

  const createClient = typeof createAuth0Client !== 'undefined' ? createAuth0Client : (window.createAuth0Client || window.auth0CreateClient);
  if (!createClient) {
    console.warn('Auth0 SPA SDK not loaded. Check browser console for script load errors.');
    return null;
  }

  try {
    const redirectUri = window.location.origin + '/dashboard.html';
    const authParams = { redirect_uri: redirectUri };
    if (config.audience) authParams.audience = config.audience;

    auth0 = await createClient({
      domain: config.domain,
      clientId: config.clientId,
      authorizationParams: authParams
    });
    return auth0;
  } catch (err) {
    console.error('Auth0 init failed:', err);
    return null;
  }
}

async function login() {
  if (!auth0) {
    alert('Auth0 is not configured. Add your domain and clientId in js/config.js');
    return;
  }
  await auth0.loginWithRedirect({
    authorizationParams: {
      screen_hint: 'signup'
    }
  });
}

async function loginOnly() {
  if (!auth0) {
    alert('Auth0 is not configured. Add your domain and clientId in js/config.js');
    return;
  }
  await auth0.loginWithRedirect();
}

async function logout() {
  if (auth0) {
    auth0.logout({
      logoutParams: {
        returnTo: window.location.origin + '/index.html'
      }
    });
  } else {
    window.location.href = 'index.html';
  }
}

async function isAuthenticated() {
  if (!auth0) return false;
  return auth0.isAuthenticated();
}

async function getUser() {
  if (!auth0) return null;
  return auth0.getUser();
}

async function handleRedirect() {
  if (!auth0) return false;
  const params = new URLSearchParams(window.location.search);
  const hasCode = params.has('code') || params.has('state');
  const hasHash = window.location.hash?.includes('code=') || window.location.hash?.includes('access_token=');
  if (!hasCode && !hasHash) return false;

  await auth0.handleRedirectCallback();
  window.history.replaceState({}, document.title, window.location.pathname);
  return true;
}
