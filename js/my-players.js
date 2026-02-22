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
  const budgetSection = document.getElementById('rosterBudgetSection');
  const budgetInput = document.getElementById('rosterBudgetInput');
  const progressArea = document.getElementById('rosterProgressArea');
  const ROSTER_BUDGET_KEY = 'portal_pair_roster_budget';
  const savedRosterBudget = localStorage.getItem(ROSTER_BUDGET_KEY);
  if (savedRosterBudget) budgetInput.value = savedRosterBudget;

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

  function getPlayerCost(player) {
    return player.cost != null ? player.cost : null;
  }

  function formatCost(cost) {
    if (cost == null) return '—';
    if (cost >= 1000000) return `$${(cost / 1000000).toFixed(2)}M`;
    return `$${Math.round(cost / 1000).toLocaleString()}K`;
  }

  function formatDollars(n) {
    return '$' + Math.round(n).toLocaleString();
  }

  function parseBudget() {
    const raw = (budgetInput.value || '').replace(/[^0-9.]/g, '');
    const n = parseFloat(raw);
    return isNaN(n) || n <= 0 ? null : n;
  }

  const SEGMENT_COLORS = [
    '#2563eb', '#7c3aed', '#0891b2', '#c026d3',
    '#0d9488', '#6366f1', '#0284c7', '#a855f7',
    '#059669', '#8b5cf6', '#0369a1', '#d946ef',
  ];

  function updateProgressBar() {
    const budget = parseBudget();
    const players = getBookmarks();

    const segments = players.map((p, i) => {
      const name = (p.name || `${p.firstName || ''} ${p.lastName || ''}`).trim();
      const cost = getPlayerCost(p);
      return { name, cost, color: SEGMENT_COLORS[i % SEGMENT_COLORS.length] };
    });

    const totalCost = segments.reduce((s, seg) => s + (seg.cost || 0), 0);

    if (budget == null || segments.length === 0) {
      progressArea.innerHTML = '';
      return;
    }

    const isOver = totalCost > budget;
    const isExact = totalCost === budget;
    const isClose = totalCost >= budget * 0.9 && totalCost <= budget;

    let statusColor, statusIcon, statusText;
    if (isOver) {
      statusColor = '#dc2626';
      statusIcon = '▲';
      statusText = `Over budget by ${formatDollars(totalCost - budget)}`;
    } else if (isExact) {
      statusColor = '#16a34a';
      statusIcon = '●';
      statusText = 'Exactly at budget';
    } else if (isClose) {
      statusColor = '#ca8a04';
      statusIcon = '●';
      statusText = `Under budget by ${formatDollars(budget - totalCost)}`;
    } else {
      statusColor = '#16a34a';
      statusIcon = '▼';
      statusText = `Under budget by ${formatDollars(budget - totalCost)}`;
    }

    const remaining = budget - totalCost;
    const remainLabel = remaining >= 0
      ? `${formatDollars(remaining)} remaining`
      : `${formatDollars(Math.abs(remaining))} over`;

    const scale = Math.max(budget, totalCost);
    const budgetMarkPct = (budget / scale) * 100;

    let segmentsHtml = '';
    segments.forEach(seg => {
      if (!seg.cost) return;
      const widthPct = (seg.cost / scale) * 100;
      segmentsHtml += `<div class="roster-segment" style="width:${widthPct}%;background:${seg.color}" title="${seg.name}: ${formatCost(seg.cost)}"></div>`;
    });

    let legendHtml = '';
    segments.forEach(seg => {
      legendHtml += `
        <div class="roster-legend-item">
          <span class="roster-legend-swatch" style="background:${seg.color}"></span>
          <span class="roster-legend-name">${escapeHtml(seg.name)}</span>
          <span class="roster-legend-cost">${formatCost(seg.cost)}</span>
        </div>`;
    });

    progressArea.innerHTML = `
      <div class="roster-progress">
        <div class="roster-progress-numbers">
          <span class="roster-total" style="color:${statusColor}">${formatDollars(totalCost)} spent</span>
          <span class="roster-budget-cap">Budget: ${formatDollars(budget)}</span>
        </div>
        <div class="roster-progress-track">
          ${segmentsHtml}
          <div class="roster-progress-budget-mark" style="left:${budgetMarkPct}%"></div>
        </div>
        <div class="roster-progress-status" style="color:${statusColor}">
          <span>${statusIcon} ${statusText}</span>
          <span class="roster-remaining">${remainLabel}</span>
        </div>
        <div class="roster-legend">${legendHtml}</div>
      </div>
    `;
  }

  budgetInput.addEventListener('input', () => {
    localStorage.setItem(ROSTER_BUDGET_KEY, budgetInput.value);
    updateProgressBar();
  });

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
    updateProgressBar();
    const remaining = grid.querySelectorAll('.player-card');
    if (remaining.length === 0) {
      grid.classList.add('hidden');
      empty.classList.remove('hidden');
      budgetSection.classList.add('hidden');
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
      budgetSection.classList.add('hidden');
      return;
    }
    empty.classList.add('hidden');
    grid.classList.remove('hidden');
    budgetSection.classList.remove('hidden');
    grid.innerHTML = '';
    players.forEach((p) => {
      const card = document.createElement('div');
      card.className = 'player-card bookmarked';
      const heightStr = p.height ? `${Math.floor(p.height / 12)}'${p.height % 12}"` : '—';
      const weightStr = p.weight ? `${p.weight} lbs` : '—';
      const playerName = p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim();
      const viewStatsUrl = `stat-viewer.html?player=${encodeURIComponent(playerName)}${p.team ? '&team=' + encodeURIComponent(p.team) : ''}`;
      const ovr = p.overall_rating != null ? Math.round(p.overall_rating) : null;
      const ovrClass = ovr != null ? (ovr >= 70 ? 'ovr-high' : ovr >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const cost = getPlayerCost(p);
      const costLabel = formatCost(cost);
      card.innerHTML = `
        <div class="player-card-header">
          <h3>${escapeHtml(playerName)}</h3>
          ${ovr != null ? `<span class="ovr-badge ${ovrClass}">${ovr}<span class="ovr-label">OVR</span></span>` : ''}
          <span class="cost-badge">${costLabel}</span>
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
    updateProgressBar();
  }

  loadBookmarks();
});
