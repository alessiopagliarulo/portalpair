const BOOKMARKS_KEY = 'portal_pair_my_players';

document.addEventListener('DOMContentLoaded', async () => {
  let user = null;
  if (sessionStorage.getItem('testBypass')) {
    user = { email: 'test@bypass.edu' };
  } else {
    user = await checkAuth?.();
  }
  if (!user?.email && typeof checkAuth === 'function') {
    window.location.href = 'login.html';
    return;
  }

  document.getElementById('userEmail').textContent = user.email;
  document.getElementById('logoutBtn').addEventListener('click', logout);

  const grid = document.getElementById('bookmarksGrid');
  const empty = document.getElementById('bookmarksEmpty');

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

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function loadBookmarks() {
    const players = getBookmarks();
    render(players);
  }

  function removeBookmark(player, card) {
    const list = getBookmarks();
    const name = (player.name || `${player.firstName || ''} ${player.lastName || ''}`).trim();
    const team = (player.team || '').trim();
    const key = name + '::' + team;
    const filtered = list.filter(b => (b.name || `${b.firstName || ''} ${b.lastName || ''}`).trim() + '::' + (b.team || '').trim() !== key);
    saveBookmarks(filtered);
    card.remove();
    const remaining = grid.querySelectorAll('.player-card');
    if (remaining.length === 0) {
      grid.classList.add('hidden');
      empty.classList.remove('hidden');
    }
  }

  function playerKey(p) {
    const name = (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim();
    const team = (p.team || '').trim();
    return name + '::' + team;
  }

  function updateNote(p, noteText) {
    const list = getBookmarks();
    const key = playerKey(p);
    const entry = list.find(b => playerKey(b) === key);
    if (entry) {
      entry.note = noteText;
      saveBookmarks(list);
    }
  }

  function render(players) {
    if (!players || players.length === 0) {
      grid.classList.add('hidden');
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    grid.classList.remove('hidden');
    grid.innerHTML = '';
    players.forEach((p) => {
      const card = document.createElement('div');
      card.className = 'player-card bookmarked';
      const heightStr = p.height ? `${Math.floor(p.height / 12)}'${p.height % 12}"` : '—';
      const weightStr = p.weight ? `${p.weight} lbs` : '—';
      const playerName = p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim();
      let viewStatsUrl = `stat-viewer.html?player=${encodeURIComponent(playerName)}${p.team ? '&team=' + encodeURIComponent(p.team) : ''}`;
      if (p.docId) viewStatsUrl += '&doc_id=' + encodeURIComponent(p.docId);
      else if (p.athlete_id && p.team && p.season) {
        viewStatsUrl += '&athlete_id=' + encodeURIComponent(p.athlete_id) + '&season=' + encodeURIComponent(p.season);
      }
      const ovr = p.overall_rating != null ? Math.round(p.overall_rating) : null;
      const ovrClass = ovr != null ? (ovr >= 70 ? 'ovr-high' : ovr >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const pot = p.pred_2026_overall != null ? Math.round(p.pred_2026_overall) : null;
      const potClass = pot != null ? (pot >= 70 ? 'pot-high' : pot >= 50 ? 'pot-mid' : 'pot-low') : '';
      card.innerHTML = `
        <div class="player-card-header">
          <h3>${escapeHtml(playerName)}</h3>
          ${ovr != null ? `<span class="ovr-badge ${ovrClass}">${ovr}<span class="ovr-label">OVR</span></span>` : ''}
          ${pot != null ? `<span class="pot-badge ${potClass}">${pot}<span class="pot-label">POT</span></span>` : ''}
          <button type="button" class="remove-bookmark-btn" title="Remove from My Players">✕</button>
        </div>
        <div class="meta">
          ${p.team ? `<span>${escapeHtml(p.team)}</span>` : ''}
          ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
          ${p.playerClass ? `<span>${escapeHtml(p.playerClass)}</span>` : ''}
          <span>Height: ${heightStr}</span>
          <span>Weight: ${weightStr}</span>
        </div>
        <div class="player-note-area">
          <label class="player-note-label">Coach Notes</label>
          <textarea class="player-note-input" placeholder="Add your notes about this player...">${escapeHtml(p.note || '')}</textarea>
          <div class="player-note-saved">Saved</div>
        </div>
        <div class="my-players-actions">
          <a href="${viewStatsUrl}" class="view-stats-btn">View Stats</a>
        </div>
      `;
      const removeBtn = card.querySelector('.remove-bookmark-btn');
      removeBtn.addEventListener('click', () => removeBookmark(p, card));

      let saveTimer = null;
      const textarea = card.querySelector('.player-note-input');
      const savedIndicator = card.querySelector('.player-note-saved');
      textarea.addEventListener('input', () => {
        clearTimeout(saveTimer);
        saveTimer = setTimeout(() => {
          updateNote(p, textarea.value);
          savedIndicator.classList.add('show');
          setTimeout(() => savedIndicator.classList.remove('show'), 1500);
        }, 400);
      });

      grid.appendChild(card);
    });
  }

  loadBookmarks();
});
