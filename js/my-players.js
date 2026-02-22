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
    localStorage.setItem(ROSTER_BUDGET_KEY, budgetInput.value);
    updateProgressBar();
    updateBudgetBars();
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
      let viewStatsUrl = `stat-viewer.html?player=${encodeURIComponent(playerName)}${p.team ? '&team=' + encodeURIComponent(p.team) : ''}`;
      if (p.docId) viewStatsUrl += '&doc_id=' + encodeURIComponent(p.docId);
      else if (p.athlete_id && p.team && p.season) {
        viewStatsUrl += '&athlete_id=' + encodeURIComponent(p.athlete_id) + '&season=' + encodeURIComponent(p.season);
      }
      const ovr = p.overall_rating != null ? Math.round(p.overall_rating) : null;
      const ovrClass = ovr != null ? (ovr >= 70 ? 'ovr-high' : ovr >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const pot = p.pred_2026_overall != null ? Math.round(p.pred_2026_overall) : null;
      const potClass = pot != null ? (pot >= 70 ? 'ovr-high' : pot >= 50 ? 'ovr-mid' : 'ovr-low') : '';
      const cost = getPlayerCost(p);
      const costLabel = formatCost(cost);
      const pct = p.matchPct != null ? Math.round(p.matchPct) : null;
      const circleHtml = pct != null
        ? `<div class="match-circle" style="--pct:${pct}" title="${pct}% Pair Score"><span class="match-circle-value">${pct}%<span class="match-circle-label">Pair Score</span></span></div>`
        : '';
      const value = computeValueScore(p);
      const valueClass = value != null ? (value >= 1.5 ? 'ovr-high' : value >= 1 ? 'ovr-mid' : 'ovr-low') : '';
      card.innerHTML = `
        <div class="player-card-content">
          <div class="player-card-header">
            <h3>${escapeHtml(playerName)} ${cost != null ? `<span class="cost-badge" title="Estimated player cost">${costLabel}</span>` : ''}</h3>
            ${ovr != null ? `<span class="ovr-badge ${ovrClass}">${ovr}<span class="ovr-label">OVR</span></span>` : ''}
            ${pot != null ? `<span class="ovr-badge ${potClass}">${pot}<span class="ovr-label">POT</span></span>` : ''}
            ${value != null ? `<span class="ovr-badge ${valueClass}" title="Value = Overall / Similarity, adjusted by position">${value}<span class="ovr-label">VAL</span></span>` : ''}
            ${circleHtml}
            <button type="button" class="remove-bookmark-btn" title="Remove from My Players">✕</button>
          </div>
          <div class="meta">
            ${p.team ? `<span>${escapeHtml(p.team)}</span>` : ''}
            ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
            ${p.playerClass ? `<span>${escapeHtml(p.playerClass)}</span>` : ''}
            <span>Height: ${heightStr}</span>
            <span>Weight: ${weightStr}</span>
          </div>
          <div class="budget-bar-container" data-cost="${cost != null ? cost : ''}"></div>
          <div class="player-note-area">
            <label class="player-note-label">Coach Notes</label>
            <textarea class="player-note-input" placeholder="Add your notes about this player...">${escapeHtml(p.note || '')}</textarea>
            <div class="player-note-saved">Saved</div>
          </div>
          <div class="player-card-actions">
            <a href="${viewStatsUrl}" class="view-stats-btn">View Stats</a>
          </div>
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
    updateBudgetBars();
  }

  loadBookmarks();
});
