// Auth0 integration for Portal Pair
let auth0 = null;

async function initAuth0() {
  const config = window.AUTH0_CONFIG || {};
  if (!config.domain || !config.clientId || config.domain.includes('YOUR_')) {
    console.warn('Auth0 not configured. Using demo mode.');
    return null;
  }

  if (typeof createAuth0Client === 'undefined') {
    console.warn('Auth0 SPA SDK not loaded.');
    return null;
  }
  auth0 = await createAuth0Client({
    domain: config.domain,
    client_id: config.clientId,
    authorizationParams: {
      redirect_uri: window.location.origin + '/dashboard.html',
      audience: config.audience || undefined
    }
  });
  return auth0;
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
