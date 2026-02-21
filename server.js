require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');
const fetch = require('node-fetch');
const cookieParser = require('cookie-parser');

const app = express();
const PORT = 8080;
const CFB_API = 'https://api.collegefootballdata.com';
const AUTH0_DOMAIN = process.env.AUTH0_DOMAIN;
const AUTH0_CLIENT_ID = process.env.AUTH0_CLIENT_ID;
const AUTH0_CLIENT_SECRET = process.env.AUTH0_CLIENT_SECRET;
const COOKIE_SECRET = process.env.COOKIE_SECRET || 'portal-pair-dev-secret-change-in-production';
const DB_PATH = path.join(__dirname, 'data', 'logins.json');

app.use(express.json());
app.use(cookieParser(COOKIE_SECRET));
app.use(express.static(path.join(__dirname)));

const API_KEY = process.env.CFB_API_KEY || 'LmDXHHUmNpMMcViHUKEO7EWZiX6dEYWuIMQhZcSH95SQIweOR7NiuliwnX3MOk6W';

function ensureDbDir() {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

function loadLogins() {
  ensureDbDir();
  if (!fs.existsSync(DB_PATH)) return [];
  try {
    return JSON.parse(fs.readFileSync(DB_PATH, 'utf8'));
  } catch {
    return [];
  }
}

function saveLogin(email) {
  const logins = loadLogins();
  const existing = logins.find(l => l.email.toLowerCase() === email.toLowerCase());
  if (existing) return;
  logins.push({ email: email.toLowerCase(), createdAt: new Date().toISOString() });
  fs.writeFileSync(DB_PATH, JSON.stringify(logins, null, 2));
}

function isEduEmail(email) {
  const domain = (email || '').trim().toLowerCase().split('@')[1] || '';
  return domain.endsWith('.edu');
}

app.post('/api/auth/send-code', async (req, res) => {
  const email = (req.body?.email || '').trim().toLowerCase();
  if (!email || !email.includes('@')) {
    return res.status(400).json({ error: 'Invalid email' });
  }
  if (!isEduEmail(email)) {
    return res.status(400).json({ error: 'Only .edu email addresses are accepted.' });
  }
  if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID || !AUTH0_CLIENT_SECRET) {
    return res.status(503).json({ error: 'Auth0 not configured. Add AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET to .env' });
  }
  try {
    const r = await fetch(`https://${AUTH0_DOMAIN}/passwordless/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: AUTH0_CLIENT_ID,
        client_secret: AUTH0_CLIENT_SECRET,
        connection: 'email',
        email,
        send: 'code'
      })
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      return res.status(400).json({ error: data.error_description || data.error || 'Failed to send code' });
    }
    res.json({ success: true });
  } catch (err) {
    console.error('Auth0 passwordless/start:', err.message);
    res.status(500).json({ error: 'Failed to send verification code' });
  }
});

app.post('/api/auth/verify-code', async (req, res) => {
  const { email, code } = req.body || {};
  const e = (email || '').trim().toLowerCase();
  const c = (code || '').trim();
  if (!e || !e.includes('@') || !c) {
    return res.status(400).json({ error: 'Email and code required' });
  }
  if (!isEduEmail(e)) {
    return res.status(400).json({ error: 'Only .edu email addresses are accepted.' });
  }
  if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID || !AUTH0_CLIENT_SECRET) {
    return res.status(503).json({ error: 'Auth0 not configured' });
  }
  try {
    const r = await fetch(`https://${AUTH0_DOMAIN}/oauth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'http://auth0.com/oauth/grant-type/passwordless/otp',
        client_id: AUTH0_CLIENT_ID,
        client_secret: AUTH0_CLIENT_SECRET,
        username: e,
        otp: c,
        realm: 'email'
      })
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      return res.status(400).json({ error: data.error_description || data.error || 'Invalid code' });
    }
    saveLogin(e);
    res.cookie('user', e, {
      signed: true,
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000
    });
    res.json({ success: true, redirect: '/dashboard.html' });
  } catch (err) {
    console.error('Auth0 oauth/token:', err.message);
    res.status(500).json({ error: 'Verification failed' });
  }
});

app.get('/api/auth/me', (req, res) => {
  const email = req.signedCookies?.user;
  if (!email) return res.status(401).json({ error: 'Not authenticated' });
  res.json({ email });
});

app.post('/api/auth/logout', (req, res) => {
  res.clearCookie('user');
  res.json({ success: true });
});

// Testing bypass — skips Auth0 verification (dev only)
app.post('/api/auth/bypass', (req, res) => {
  const email = (req.body?.email || 'test@bypass.edu').trim().toLowerCase();
  const addr = email && email.includes('@') ? email : 'test@bypass.edu';
  saveLogin(addr);
  res.cookie('user', addr, {
    signed: true,
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 7 * 24 * 60 * 60 * 1000
  });
  res.json({ success: true, redirect: '/dashboard.html' });
});

// Proxy to College Football Data API
app.get('/api/player/search', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/player/search?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/player/usage', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/player/usage?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/stats/player/season', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/stats/player/season?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/ratings/elo', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/ratings/elo?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/teams', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/teams?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/player/portal', async (req, res) => {
  try {
    const params = new URLSearchParams(req.query).toString();
    const response = await fetch(`${CFB_API}/player/portal?${params}`, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    const data = await response.json();
    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// Mock coach suggestions (placeholder for Actian VectorAI + RAG)
app.post('/api/coach/suggest', async (req, res) => {
  const { query } = req.body || {};
  // Simulate RAG response - in production this would use VectorAI DB
  const suggestions = [
    'Try filtering by position and PIS > 75 for impact players.',
    'Consider players from smaller programs — they often have high Delta W scores.',
    'Check the transfer portal for available talent matching your criteria.'
  ];
  res.json({
    response: suggestions[Math.floor(Math.random() * suggestions.length)],
    matches: []
  });
});

app.listen(PORT, () => {
  ensureDbDir();
  console.log(`\n  ScoutBase running at http://localhost:${PORT}`);
  const auth0Ok = AUTH0_DOMAIN && AUTH0_CLIENT_ID && AUTH0_CLIENT_SECRET;
  console.log(auth0Ok ? '  Auth0: ENABLED (2FA email code)' : '  Auth0: add AUTH0_* to .env');
  console.log('');
});
