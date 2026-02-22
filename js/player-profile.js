(function () {
    let chartBar = null;

  const POSITION_MAP = {
    QB: 'QB', RB: 'RB', FB: 'RB',
    WR: 'WR_TE', TE: 'WR_TE',
    OL: 'OL', OT: 'OL', OG: 'OL', C: 'OL',
    DL: 'DL', DE: 'DL', DT: 'DL', NT: 'DL',
    LB: 'LB', ILB: 'LB', OLB: 'LB', MLB: 'LB',
    DB: 'DB', CB: 'DB', S: 'DB', FS: 'DB', SS: 'DB',
    K: 'K', P: 'P',
    KR: 'Returner', PR: 'Returner',
  };

  const POSITION_STAT_DEFS = {
    QB: [
      { key: 'passing_yards', label: 'Passing Yards' },
      { key: 'passing_tds', label: 'Passing TDs' },
      { key: 'interceptions', label: 'Interceptions' },
      { key: 'completion_pct', label: 'Completion %' },
      { key: 'yards_per_attempt', label: 'Yards/Attempt' },
      { key: 'rushing_yards', label: 'Rushing Yards' },
      { key: 'rushing_tds', label: 'Rushing TDs' },
    ],
    RB: [
      { key: 'rushing_attempts', label: 'Rush Attempts' },
      { key: 'rushing_yards', label: 'Rushing Yards' },
      { key: 'yards_per_carry', label: 'Yards/Carry' },
      { key: 'rushing_tds', label: 'Rushing TDs' },
      { key: 'receptions', label: 'Receptions' },
      { key: 'receiving_yards', label: 'Receiving Yards' },
    ],
    WR_TE: [
      { key: 'targets', label: 'Targets' },
      { key: 'receptions', label: 'Receptions' },
      { key: 'receiving_yards', label: 'Receiving Yards' },
      { key: 'yards_per_catch', label: 'Yards/Catch' },
      { key: 'receiving_tds', label: 'Receiving TDs' },
    ],
    OL: [
      { key: 'sacks_allowed', label: 'Sacks Allowed' },
      { key: 'pressures_allowed', label: 'Pressures Allowed' },
      { key: 'penalties', label: 'Penalties' },
      { key: 'run_block_win_rate', label: 'Run Block Win %' },
      { key: 'pass_block_win_rate', label: 'Pass Block Win %' },
    ],
    DL: [
      { key: 'total_tackles', label: 'Total Tackles' },
      { key: 'tfl', label: 'TFL' },
      { key: 'sacks', label: 'Sacks' },
      { key: 'qb_hits', label: 'QB Hits' },
      { key: 'pressures', label: 'Pressures' },
    ],
    LB: [
      { key: 'total_tackles', label: 'Total Tackles' },
      { key: 'tfl', label: 'TFL' },
      { key: 'sacks', label: 'Sacks' },
      { key: 'interceptions', label: 'Interceptions' },
    ],
    DB: [
      { key: 'tackles', label: 'Tackles' },
      { key: 'interceptions', label: 'Interceptions' },
      { key: 'passes_defended', label: 'Passes Defended' },
      { key: 'completion_pct_allowed', label: 'Completion % Allowed' },
      { key: 'yards_allowed', label: 'Yards Allowed' },
    ],
    K: [
      { key: 'field_goal_pct', label: 'FG %' },
      { key: 'longest_fg', label: 'Longest FG' },
      { key: 'extra_point_pct', label: 'XP %' },
    ],
    P: [
      { key: 'punt_average', label: 'Punt Average' },
      { key: 'inside_20', label: 'Inside 20' },
      { key: 'touchbacks', label: 'Touchbacks' },
    ],
    Returner: [
      { key: 'kick_return_avg', label: 'Kick Ret Avg' },
      { key: 'punt_return_avg', label: 'Punt Ret Avg' },
      { key: 'return_tds', label: 'Return TDs' },
    ],
  };

  const CHART_COLORS = [
    'rgb(45, 106, 45)', 'rgb(59, 130, 246)', 'rgb(239, 68, 68)',
    'rgb(249, 115, 22)', 'rgb(139, 92, 246)', 'rgb(20, 184, 166)',
    'rgb(234, 179, 8)', 'rgb(236, 72, 153)', 'rgb(6, 182, 212)',
    'rgb(132, 204, 22)',
  ];

  const params = new URLSearchParams(window.location.search);
  const docId = params.get('doc_id');
  const athleteId = params.get('athlete_id');
  const team = params.get('team');
  const season = params.get('season');
  const name = params.get('name');
  const rank = params.get('rank');
  const stats = params.get('stats');

  const loadingEl = document.getElementById('profileLoading');
  const errorEl = document.getElementById('profileError');
  const contentEl = document.getElementById('profileContent');

  function showLoading() {
    loadingEl.classList.remove('hidden');
    errorEl.classList.add('hidden');
    contentEl.classList.add('hidden');
  }

  function showError(msg) {
    loadingEl.classList.add('hidden');
    contentEl.classList.add('hidden');
    errorEl.textContent = msg;
    errorEl.classList.remove('hidden');
  }

  function showContent() {
    loadingEl.classList.add('hidden');
    errorEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return '-';
    const div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
  }

  function heightStr(h) {
    if (h == null || h === '') return '-';
    const n = parseInt(h, 10);
    if (isNaN(n)) return '-';
    const ft = Math.floor(n / 12);
    const inch = n % 12;
    return ft + "'" + inch + '"';
  }

  function getStatGroup(position) {
    const pos = (position || '').trim().toUpperCase();
    return POSITION_MAP[pos] || 'Returner';
  }

  function formatStatValue(v) {
    if (v === null || v === undefined) return '-';
    const n = parseFloat(v);
    if (isNaN(n)) return '-';
    if (n === Math.floor(n)) return String(Math.floor(n));
    return n.toFixed(1);
  }

  function renderProfile(data) {
    const displayName = (data.firstName && data.lastName)
      ? data.firstName + ' ' + data.lastName
      : data.name || 'Unknown';
    document.getElementById('profileName').textContent = displayName;
    const metaParts = [];
    if (data.team) metaParts.push(data.team);
    if (data.position) metaParts.push(data.position);
    document.getElementById('profileMeta').textContent = metaParts.join(' · ');

    document.getElementById('bioHeight').textContent = heightStr(data.height);
    document.getElementById('bioWeight').textContent = data.weight != null ? data.weight + ' lbs' : '-';
    document.getElementById('bioJersey').textContent = data.jersey != null && data.jersey !== '' ? '#' + data.jersey : '-';
    const hometownParts = [data.homeCity, data.homeState, data.homeCountry].filter(Boolean);
    document.getElementById('bioHometown').textContent = hometownParts.length ? hometownParts.join(', ') : '-';

    const group = getStatGroup(data.position);
    const statDefs = POSITION_STAT_DEFS[group] || POSITION_STAT_DEFS.Returner;

    const fields = [
      ['firstName', 'First name'],
      ['lastName', 'Last name'],
      ['team', 'Team'],
      ['position', 'Position'],
    ];
    statDefs.forEach(function (def) {
      fields.push([def.key, def.label, formatStatValue]);
    });

    const dl = document.getElementById('profileFields');
    dl.innerHTML = '';
    fields.forEach(function (f) {
      const key = f[0];
      const label = f[1];
      const fmt = f[2] || function (v) { return v != null && v !== '' ? escapeHtml(String(v)) : '-'; };
      const val = data[key];
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.innerHTML = fmt(val);
      dl.appendChild(dt);
      dl.appendChild(dd);
    });

    const chartLabels = statDefs.map(function (x) { return x.label; });
    const chartValues = statDefs.map(function (x) {
      const v = data[x.key];
      return v != null ? parseFloat(v) : 0;
    });

    const barCtx = document.getElementById('usageBarChart').getContext('2d');
    if (chartBar) chartBar.destroy();
    chartBar = new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: chartLabels,
        datasets: [{
          label: 'Stats',
          data: chartValues,
          backgroundColor: chartLabels.map(function (_, i) { return CHART_COLORS[i % CHART_COLORS.length]; }),
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (ctx) { return ctx.raw % 1 === 0 ? String(ctx.raw) : ctx.raw.toFixed(1); } } },
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Value' } },
        },
      },
    });

    showContent();
  }

  function renderRankingOnly(rankVal, nameVal, statsVal) {
    document.getElementById('profileName').textContent = nameVal || 'Unknown';
    document.getElementById('profileMeta').textContent = 'Rank #' + (rankVal || '-') + (statsVal ? ' · ' + statsVal : '');

    const dl = document.getElementById('profileFields');
    dl.innerHTML = '';
    const rows = [['name', 'Name', nameVal], ['rank', 'Rank', rankVal], ['stats', 'Stats', statsVal]];
    rows.forEach(function (r) {
      const dt = document.createElement('dt');
      dt.textContent = r[1];
      const dd = document.createElement('dd');
      dd.textContent = r[2] != null ? r[2] : '-';
      dl.appendChild(dt);
      dl.appendChild(dd);
    });

    document.getElementById('biometricSection').style.display = 'none';
    document.querySelector('.profile-section:last-of-type').style.display = 'none';
    showContent();
  }

  if (docId) {
    showLoading();
    fetch('/api/player/profile?doc_id=' + encodeURIComponent(docId))
      .then(function (r) {
        if (!r.ok) throw new Error(r.status === 404 ? 'Player not found' : 'Failed to load profile');
        return r.json();
      })
      .then(renderProfile)
      .catch(function (err) {
        showError(err.message || 'Could not load player profile.');
      });
  } else if (athleteId && team && season) {
    showLoading();
    fetch('/api/player/profile?athlete_id=' + encodeURIComponent(athleteId) + '&team=' + encodeURIComponent(team) + '&season=' + encodeURIComponent(season))
      .then(function (r) {
        if (!r.ok) throw new Error(r.status === 404 ? 'Player not found' : 'Failed to load profile');
        return r.json();
      })
      .then(renderProfile)
      .catch(function (err) {
        showError(err.message || 'Could not load player profile.');
      });
  } else if (name != null && name !== '') {
    showLoading();
    renderRankingOnly(rank, name, stats);
  } else {
    showError('No player specified. Use doc_id or athlete_id, team, and season.');
  }
})();
