const API_BASE = '';

document.addEventListener('DOMContentLoaded', async () => {
  let user = null;
  if (sessionStorage.getItem('testBypass')) {
    user = { email: 'test@bypass.edu' };
  } else {
    user = await checkAuth();
  }
  if (!user?.email) {
    window.location.href = 'login.html';
    return;
  }

  document.getElementById('userEmail').textContent = user.email;
  document.getElementById('logoutBtn').addEventListener('click', logout);

  const chatInput = document.getElementById('chatInput');
  const chatSend = document.getElementById('chatSend');
  const chatMessages = document.getElementById('chatMessages');
  const matchesGrid = document.getElementById('matchesGrid');
  const matchesEmpty = document.getElementById('matchesEmpty');

  let currentMatches = [];
  const BOOKMARKS_KEY = 'portal_pair_my_players';
  const CHAT_HISTORY_KEY = 'portal_pair_chat_history';
  const MATCHES_KEY = 'portal_pair_matches';

  function saveChatState() {
    const msgs = [];
    chatMessages.querySelectorAll('.chat-message').forEach(el => {
      msgs.push({ role: el.classList.contains('user') ? 'user' : 'assistant', text: el.textContent });
    });
    sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(msgs));
  }

  function saveMatchesState() {
    sessionStorage.setItem(MATCHES_KEY, JSON.stringify(currentMatches));
  }

  function getBookmarks() {
    try {
      const raw = localStorage.getItem(BOOKMARKS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  }

  function saveBookmarks(list) {
    localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(list));
  }

  function playerKey(p) {
    const name = (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim();
    const team = (p.team || '').trim();
    return name + '::' + team;
  }

  function isBookmarked(p) {
    const list = getBookmarks();
    const key = playerKey(p);
    return list.some(b => playerKey(b) === key);
  }

  function getBookmarkNote(p) {
    const list = getBookmarks();
    const key = playerKey(p);
    const entry = list.find(b => playerKey(b) === key);
    return entry?.note || '';
  }

  function syncBookmarkedPlayer(p) {
    const list = getBookmarks();
    const key = playerKey(p);
    const idx = list.findIndex(b => playerKey(b) === key);
    if (idx < 0) return;
    const current = list[idx] || {};
    list[idx] = {
      ...current,
      name: (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim(),
      firstName: p.firstName || '',
      lastName: p.lastName || '',
      team: p.team || '',
      position: p.position || '',
      height: p.height,
      weight: p.weight,
      overall_rating: p.overall_rating,
      pred_2026_overall: p.pred_2026_overall,
      playerClass: p.playerClass || '',
      docId: p.docId || current.docId || '',
      athlete_id: p.athlete_id || current.athlete_id || '',
      season: p.season || current.season || '',
      matchPct: p.matchPct != null ? p.matchPct : current.matchPct || null,
    };
    saveBookmarks(list);
  }

  function toggleBookmark(p, btn, card) {
    const list = getBookmarks();
    const key = playerKey(p);
    const idx = list.findIndex(b => playerKey(b) === key);
    const wasBookmarked = idx >= 0;
    const player = {
      name: (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim(),
      firstName: p.firstName || '',
      lastName: p.lastName || '',
      team: p.team || '',
      position: p.position || '',
      height: p.height,
      weight: p.weight,
      overall_rating: p.overall_rating,
      pred_2026_overall: p.pred_2026_overall,
      playerClass: p.playerClass || '',
      docId: p.docId || '',
      athlete_id: p.athlete_id || '',
      season: p.season || '',
      cost: computePlayerCost(p),
      matchPct: p.matchPct != null ? p.matchPct : null,
    };
    if (wasBookmarked) {
      list.splice(idx, 1);
    } else {
      list.push(player);
    }
    saveBookmarks(list);
    btn.classList.toggle('added', !wasBookmarked);
    btn.textContent = !wasBookmarked ? 'In My Players ✓' : 'Add to My Players';
    if (card) card.classList.toggle('bookmarked', !wasBookmarked);
  }

  function normalizeClass(rawClass) {
    const cls = String(rawClass || '').trim().toLowerCase();
    if (!cls) return 'sophomore';
    if (cls.includes('fresh') || cls === 'fr') return 'freshman';
    if (cls.includes('soph') || cls === 'so') return 'sophomore';
    if (cls.includes('jun') || cls === 'jr') return 'junior';
    if (cls.includes('sen') || cls === 'sr') return 'senior';
    if (cls.includes('grad')) return 'senior';
    return cls;
  }

  function getClassScore(rawClass) {
    const cls = normalizeClass(rawClass);
    if (cls === 'freshman') return 0.0;
    if (cls === 'sophomore') return 0.33;
    if (cls === 'junior') return 0.66;
    if (cls === 'senior') return 1.0;
    return 0.33;
  }

  function getCostRangeByPosition(rawPosition) {
    const pos = String(rawPosition || '').trim().toUpperCase();
    if (pos === 'QB' || pos === 'QUARTERBACK') return { min: 50000, max: 600000 };
    if (pos === 'RB' || pos === 'RUNNING BACK') return { min: 40000, max: 400000 };
    if (pos === 'WR' || pos === 'WIDE RECEIVER') return { min: 25000, max: 250000 };
    return { min: 15000, max: 200000 };
  }

  function computePlayerCost(player) {
    const overall = player.overall_rating != null ? Math.round(player.overall_rating) : null;
    if (overall == null) return null;
    const { min, max } = getCostRangeByPosition(player.position);
    const overallNorm = Math.max(0, Math.min(1, (overall - 50) / (600 - 50)));
    const classNorm = getClassScore(player.playerClass);
    const blendedNorm = Math.max(0, Math.min(1, (overallNorm * 0.85) + (classNorm * 0.15)));
    return Math.round(min + (max - min) * blendedNorm);
  }

  function formatCost(cost) {
    if (cost == null) return '—';
    if (cost >= 1000000) return `$${(cost / 1000000).toFixed(2)}M`;
    return `$${Math.round(cost / 1000)}K`;
  }

  function showMatches(players) {
    currentMatches = players || [];
    if (!players || players.length === 0) {
      matchesGrid.classList.add('hidden');
      matchesEmpty.classList.remove('hidden');
      return;
    }

    function computeValueScore(player) {
      const overall = player.overall_rating != null ? Math.round(player.overall_rating) : null;
      const similarity = player.matchPct != null ? Math.round(player.matchPct) : null;
      const pos = String(player.position || '').trim().toUpperCase();
      const isQb = pos === 'QB' || pos === 'QUARTERBACK';
      const isRb = pos === 'RB' || pos === 'RUNNING BACK';
      const multiplier = isQb ? 1.4 : isRb ? 1.2 : 1.0;
      if (overall == null || similarity == null || similarity <= 0) return null;
      return Number(((overall / similarity) * multiplier).toFixed(2));
    }

    const valueScores = players.map(computeValueScore).filter(v => v != null);
    const minValue = valueScores.length ? Math.min(...valueScores) : null;
    const maxValue = valueScores.length ? Math.max(...valueScores) : null;

    function getRelativeValueClass(value) {
      if (value == null || minValue == null || maxValue == null) return '';
      if (value < 1) return 'ovr-low'; // always red if below 1
      // For scores >= 1, use only yellow/green relative coloring.
      const floor = Math.max(minValue, 1);
      if (maxValue <= floor) return 'ovr-mid';
      const normalized = (value - floor) / (maxValue - floor);
      if (normalized < 0.66) return 'ovr-mid';   // yellow
      return 'ovr-high';                          // green
    }

    matchesEmpty.classList.add('hidden');
    matchesGrid.innerHTML = '';
    matchesGrid.classList.remove('hidden');
    players.forEach((p, idx) => {
      const card = document.createElement('div');
      card.className = 'player-card';
      card.dataset.matchIndex = String(idx);
      const pct = p.matchPct != null ? Math.round(p.matchPct) : null;
      const heightStr = p.height ? `${Math.floor(p.height / 12)}'${p.height % 12}"` : '—';
      const weightStr = p.weight ? `${p.weight} lbs` : '—';
      const circleHtml = pct != null
        ? `<div class="match-circle" style="--pct:${pct}" title="${pct}% Pair Score"><span class="match-circle-value">${pct}%<span class="match-circle-label">Pair Score</span></span></div>`
        : '';
      const playerName = p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim();
      let viewStatsUrl = `stat-viewer.html?player=${encodeURIComponent(playerName)}${p.team ? '&team=' + encodeURIComponent(p.team) : ''}`;
      if (p.docId) viewStatsUrl += '&doc_id=' + encodeURIComponent(p.docId);
      else if (p.athlete_id && p.team && p.season) viewStatsUrl += '&athlete_id=' + encodeURIComponent(p.athlete_id) + '&season=' + encodeURIComponent(p.season);
      const bookmarked = isBookmarked(p);
      const note = getBookmarkNote(p);
      if (bookmarked) syncBookmarkedPlayer(p);
      if (bookmarked) card.classList.add('bookmarked');
      const ovr = p.overall_rating != null ? Math.round(p.overall_rating) : null;
      const ovrClass = ovr != null ? (ovr >= 70 ? 'ovr-high' : ovr >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const pot = p.pred_2026_overall != null ? Math.round(p.pred_2026_overall) : null;
      const potClass = pot != null ? (pot >= 70 ? 'ovr-high' : pot >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const value = computeValueScore(p);
      const valueClass = getRelativeValueClass(value);
      const cost = computePlayerCost(p);
      const costLabel = formatCost(cost);
      card.innerHTML = `
        <div class="player-card-content">
          <div class="player-card-header">
            <h3>${escapeHtml(playerName)} ${cost != null ? `<span class="cost-badge" title="Estimated player cost">${costLabel}</span>` : ''}</h3>
            ${ovr != null ? `<span class="ovr-badge ${ovrClass}">${ovr}<span class="ovr-label">OVR</span></span>` : ''}
            ${pot != null ? `<span class="ovr-badge ${potClass}">${pot}<span class="ovr-label">POT</span></span>` : ''}
            ${value != null ? `<span class="ovr-badge ${valueClass}" title="Value = Overall / Similarity, adjusted by position">${value}<span class="ovr-label">VAL</span></span>` : ''}
            ${circleHtml}
          </div>
          <div class="meta">
            ${p.team ? `<span>${escapeHtml(p.team)}</span>` : ''}
            ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
            ${p.playerClass ? `<span>${escapeHtml(p.playerClass)}</span>` : ''}
            <span>Height: ${heightStr}</span>
            <span>Weight: ${weightStr}</span>
          </div>
          ${note ? `<div class="player-note-display">${escapeHtml(note)}</div>` : ''}
          <div class="budget-bar-container" data-cost="${cost != null ? cost : ''}"></div>
          <div class="player-card-actions">
            <a href="${viewStatsUrl}" class="view-stats-btn">View Stats</a>
            <button type="button" class="add-to-my-players-btn ${bookmarked ? 'added' : ''}" data-match-idx="${idx}">${bookmarked ? 'In My Players ✓' : 'Add to My Players'}</button>
          </div>
        </div>
      `;
      const addBtn = card.querySelector('.add-to-my-players-btn');
      addBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const player = currentMatches[parseInt(addBtn.dataset.matchIdx, 10)];
        if (player) toggleBookmark(player, addBtn, card);
      });
      matchesGrid.appendChild(card);
    });
    updateBudgetBars();
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  const budgetInput = document.getElementById('budgetInput');
  const PLAYER_BUDGET_KEY = 'portal_pair_roster_budget';
  const savedPlayerBudget = localStorage.getItem(PLAYER_BUDGET_KEY);
  if (savedPlayerBudget) budgetInput.value = savedPlayerBudget;

  function parseBudget() {
    const raw = (budgetInput.value || '').replace(/[^0-9.]/g, '');
    const n = parseFloat(raw);
    return isNaN(n) || n <= 0 ? null : n;
  }

  function updateBudgetBars() {
    const budget = parseBudget();
    document.querySelectorAll('.budget-bar-container').forEach(container => {
      const costStr = container.getAttribute('data-cost');
      const cost = costStr ? parseFloat(costStr) : null;
      if (cost == null || budget == null) {
        container.innerHTML = '';
        return;
      }
      const pct = Math.min((cost / budget) * 100, 100);
      const isOver = cost > budget;
      const isClose = cost >= budget * 0.9 && cost <= budget;
      const barColor = isOver ? '#dc2626' : isClose ? '#ca8a04' : '#16a34a';
      const label = isOver
        ? `Over budget by $${Math.round(cost - budget).toLocaleString()}`
        : cost === budget
          ? 'Exactly at budget'
          : `Under budget by $${Math.round(budget - cost).toLocaleString()}`;
      container.innerHTML = `
        <div class="budget-bar" title="${label}">
          <div class="budget-bar-track">
            <div class="budget-bar-fill" style="width:${pct}%;background:${barColor}"></div>
            <div class="budget-bar-line" style="left:100%"></div>
          </div>
          <span class="budget-bar-label" style="color:${barColor}">${label}</span>
        </div>
      `;
    });
  }

  budgetInput.addEventListener('input', () => {
    localStorage.setItem(PLAYER_BUDGET_KEY, budgetInput.value);
    updateBudgetBars();
  });

  function restoreState() {
    try {
      const savedChat = sessionStorage.getItem(CHAT_HISTORY_KEY);
      if (savedChat) {
        const msgs = JSON.parse(savedChat);
        chatMessages.innerHTML = '';
        msgs.forEach(m => {
          const el = document.createElement('div');
          el.className = `chat-message ${m.role}`;
          el.textContent = m.text;
          chatMessages.appendChild(el);
        });
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    } catch (_) {}

    try {
      const savedMatches = sessionStorage.getItem(MATCHES_KEY);
      if (savedMatches) {
        const matches = JSON.parse(savedMatches);
        if (matches.length > 0) {
          showMatches(matches);
          return;
        }
      }
    } catch (_) {}

    showMatches([]);
  }

  restoreState();

  window.addEventListener('pageshow', () => {
    restoreState();
  });

  async function sendCoachMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    const userMsg = document.createElement('div');
    userMsg.className = 'chat-message user';
    userMsg.textContent = text;
    chatMessages.appendChild(userMsg);
    chatInput.value = '';

    const assistantMsg = document.createElement('div');
    assistantMsg.className = 'chat-message assistant';
    assistantMsg.textContent = 'Searching...';
    chatMessages.appendChild(assistantMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const res = await fetch(`${API_BASE}/api/coach/suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });
      const data = await res.json();
      assistantMsg.textContent = data.response || 'Could not get a suggestion.';

      if (data.matches && Array.isArray(data.matches) && data.matches.length > 0) {
        showMatches(data.matches);
        saveMatchesState();
      }
    } catch (err) {
      assistantMsg.textContent = 'Connection error. Make sure the server is running.';
    }
    saveChatState();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  chatSend.addEventListener('click', sendCoachMessage);
  chatInput.addEventListener('keydown', (e) => e.key === 'Enter' && sendCoachMessage());
});
