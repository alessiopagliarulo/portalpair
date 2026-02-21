const express = require('express');
const path = require('path');
const fetch = require('node-fetch');

const app = express();
const PORT = 8080;
const CFB_API = 'https://api.collegefootballdata.com';

// API key - use env var in production, fallback for dev
const API_KEY = process.env.CFB_API_KEY || 'LmDXHHUmNpMMcViHUKEO7EWZiX6dEYWuIMQhZcSH95SQIweOR7NiuliwnX3MOk6W';

app.use(express.json());
app.use(express.static(path.join(__dirname)));

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
  console.log(`\n  ScoutBase running at http://localhost:${PORT}\n`);
});
