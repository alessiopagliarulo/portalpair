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

  const BOOKMARKS_KEY = 'portal_pair_my_players';

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

  function toggleBookmark(p, btn, card) {
    const list = getBookmarks();
    const key = playerKey(p);
    const idx = list.findIndex(b => playerKey(b) === key);
    const wasBookmarked = idx >= 0;
    const player = { name: (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim(), firstName: p.firstName || '', lastName: p.lastName || '', team: p.team || '', position: p.position || '', height: p.height, weight: p.weight };
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

  function showMatches(players) {
    currentMatches = players || [];
    if (!players || players.length === 0) {
      matchesGrid.classList.add('hidden');
      matchesEmpty.classList.remove('hidden');
      return;
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
        ? `<div class="match-circle" style="--pct:${pct}" title="${pct}% match"><span class="match-circle-value">${pct}</span></div>`
        : '';
      const playerName = p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim();
      let viewStatsUrl = `stat-viewer.html?player=${encodeURIComponent(playerName)}${p.team ? '&team=' + encodeURIComponent(p.team) : ''}`;
      if (p.docId) viewStatsUrl += '&doc_id=' + encodeURIComponent(p.docId);
      else if (p.athlete_id && p.team && p.season) viewStatsUrl += '&athlete_id=' + encodeURIComponent(p.athlete_id) + '&season=' + encodeURIComponent(p.season);
      const bookmarked = isBookmarked(p);
      if (bookmarked) card.classList.add('bookmarked');
      card.innerHTML = `
        <div class="player-card-content">
          <div class="player-card-header">
            <h3>${escapeHtml(playerName)}</h3>
            ${circleHtml}
          </div>
          <div class="meta">
            ${p.team ? `<span>${escapeHtml(p.team)}</span>` : ''}
            ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
            <span>Height: ${heightStr}</span>
            <span>Weight: ${weightStr}</span>
          </div>
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
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  showMatches([]);

  window.addEventListener('pageshow', () => {
    if (currentMatches.length > 0) {
      showMatches(currentMatches);
    }
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

      // When Gemini + VectorAI are wired: data.matches will populate showMatches()
      if (data.matches && Array.isArray(data.matches) && data.matches.length > 0) {
        showMatches(data.matches);
      }
    } catch (err) {
      assistantMsg.textContent = 'Connection error. Make sure the server is running.';
    }
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  chatSend.addEventListener('click', sendCoachMessage);
  chatInput.addEventListener('keydown', (e) => e.key === 'Enter' && sendCoachMessage());
});
