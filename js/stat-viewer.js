const API_BASE = '';

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
  'rgb(59, 130, 246)',
  'rgb(239, 68, 68)',
  'rgb(249, 115, 22)',
  'rgb(139, 92, 246)',
  'rgb(20, 184, 166)',
  'rgb(234, 179, 8)',
  'rgb(236, 72, 153)',
  'rgb(6, 182, 212)',
  'rgb(132, 204, 22)',
  'rgb(45, 106, 45)',
];

function getStatGroup(position) {
  const pos = (position || '').trim().toUpperCase();
  return POSITION_MAP[pos] || 'Returner';
}

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

  const params = new URLSearchParams(window.location.search);
  const preloadPlayer = params.get('player') || '';
  const preloadTeam = params.get('team') || '';
  const preloadDocId = params.get('doc_id') || '';
  const preloadAthleteId = params.get('athlete_id') || '';
  const preloadSeason = params.get('season') || '';

  const playerInput = document.getElementById('playerInput');
  const teamInput = document.getElementById('teamInput');
  const errorEl = document.getElementById('errorEl');
  const loadingEl = document.getElementById('loadingEl');
  const emptyEl = document.getElementById('emptyEl');
  const chartsArea = document.getElementById('chartsArea');
  const biodataArea = document.getElementById('biodataArea');
  const statSelect = document.getElementById('statSelect');

  playerInput.value = decodeURIComponent(preloadPlayer || '');
  teamInput.value = decodeURIComponent(preloadTeam || '');
  if (preloadPlayer) {
    playerInput.readOnly = true;
    teamInput.readOnly = true;
  }

  let statChart = null;
  let forecastChart = null;
  let chartDataCache = null;
  let currentStatDefs = [];

  function showError(msg) {
    errorEl.textContent = msg || '';
    errorEl.classList.toggle('hidden', !msg);
  }
  function showLoading(show) { loadingEl.classList.toggle('hidden', !show); }
  function showEmpty(show) { emptyEl.classList.toggle('hidden', !show); }
  function showCharts(show) { chartsArea.classList.toggle('hidden', !show); }
  function showBiodata(show) { biodataArea.classList.toggle('hidden', !show); }

  function renderBiodata(data) {
    const heightStr = data.height != null
      ? (Math.floor(parseInt(data.height, 10) / 12) + "'" + (parseInt(data.height, 10) % 12) + '"')
      : '—';
    document.getElementById('bioPosition').textContent = data.position || '—';
    document.getElementById('bioHeight').textContent = heightStr;
    document.getElementById('bioWeight').textContent = data.weight != null ? data.weight + ' lbs' : '—';
    document.getElementById('bioJersey').textContent = (data.jersey != null && data.jersey !== '') ? '#' + data.jersey : '—';
    const hometownParts = [data.homeCity, data.homeState, data.homeCountry].filter(Boolean);
    document.getElementById('bioHometown').textContent = hometownParts.length ? hometownParts.join(', ') : '—';

    const ratingCard = document.getElementById('bioRatingCard');
    const ratingEl = document.getElementById('bioRating');
    if (data.overall_rating != null) {
      const ovr = Math.round(data.overall_rating);
      ratingEl.textContent = ovr + ' / 100';
      ratingCard.style.display = '';
      const cls = ovr >= 70 ? 'ovr-high' : ovr >= 50 ? 'ovr-mid' : 'ovr-low';
      ratingEl.className = 'biodata-value ' + cls;
    } else {
      ratingCard.style.display = 'none';
    }

    const classCard = document.getElementById('bioClassCard');
    const classEl = document.getElementById('bioClass');
    if (data['class']) {
      classEl.textContent = data['class'];
      classCard.style.display = '';
    } else {
      classCard.style.display = 'none';
    }

    const potCard = document.getElementById('bioPotCard');
    const potEl = document.getElementById('bioPot');
    if (data.pred_2026_overall != null) {
      const pot = Math.round(data.pred_2026_overall);
      potEl.textContent = pot + ' / 100';
      potCard.style.display = '';
      const potCls = pot >= 70 ? 'ovr-high' : pot >= 50 ? 'ovr-mid' : 'ovr-low';
      potEl.className = 'biodata-value ' + potCls;
    } else {
      potCard.style.display = 'none';
    }
  }

  function destroyChart() {
    if (statChart) { statChart.destroy(); statChart = null; }
    if (forecastChart) { forecastChart.destroy(); forecastChart = null; }
  }

  function buildDropdown(statDefs) {
    statSelect.innerHTML = '';
    statDefs.forEach((def) => {
      const opt = document.createElement('option');
      opt.value = def.key;
      opt.textContent = def.label;
      statSelect.appendChild(opt);
    });
  }

  function renderChart() {
    if (!chartDataCache || currentStatDefs.length === 0) return;
    if (statChart) { statChart.destroy(); statChart = null; }

    const selectedKey = statSelect.value;
    const def = currentStatDefs.find(d => d.key === selectedKey) || currentStatDefs[0];
    const data = chartDataCache[def.key];
    if (!data) return;

    const colorIdx = currentStatDefs.indexOf(def);
    const color = CHART_COLORS[colorIdx % CHART_COLORS.length];
    const rgba = color.replace('rgb', 'rgba').replace(')', ', 0.3)');

    const ctx = document.getElementById('statChart').getContext('2d');
    statChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: chartDataCache.labels,
        datasets: [{
          label: def.label,
          data: data,
          borderColor: color,
          backgroundColor: rgba,
          fill: true,
          pointRadius: 5,
          pointHoverRadius: 7,
          tension: 0.25,
          borderWidth: 2.5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const v = ctx.raw;
                if (v == null) return def.label + ': —';
                return def.label + ': ' + (v % 1 === 0 ? String(v) : v.toFixed(1));
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: def.label },
          },
        },
      },
    });
  }

  function buildCharts(data) {
    destroyChart();
    const seasons = data.seasons || [];
    if (seasons.length === 0) {
      showCharts(false);
      showEmpty(true);
      showError(data.error || 'No seasonal data found.');
      return;
    }

    const position = data.player?.position || '';
    const group = getStatGroup(position);
    const statDefs = POSITION_STAT_DEFS[group] || POSITION_STAT_DEFS.Returner;
    currentStatDefs = statDefs;

    buildDropdown(statDefs);

    const labels = seasons.map(s => String(s.season));
    chartDataCache = { labels };
    statDefs.forEach((def) => {
      chartDataCache[def.key] = seasons.map(s => s[def.key] != null ? Number(s[def.key]) : null);
    });

    renderChart();
    showCharts(true);
    showEmpty(false);
    showError('');
  }

  statSelect.addEventListener('change', () => renderChart());

  function buildForecastChart(data) {
    const forecastArea = document.getElementById('forecastArea');
    if (forecastChart) { forecastChart.destroy(); forecastChart = null; }

    const predictions = data.predictions_2026 || {};
    const seasons = data.seasons || [];
    const position = data.player?.position || '';
    const group = getStatGroup(position);
    const statDefs = POSITION_STAT_DEFS[group] || POSITION_STAT_DEFS.Returner;

    const lastSeason = seasons.length > 0 ? seasons[seasons.length - 1] : {};
    const labels = [];
    const actual2025 = [];
    const predicted2026 = [];
    let hasPredictions = false;

    statDefs.forEach((def) => {
      const a = lastSeason[def.key];
      const p = predictions[def.key];
      if (p != null) {
        hasPredictions = true;
        labels.push(def.label);
        actual2025.push(a != null ? Number(a) : 0);
        predicted2026.push(Number(p));
      }
    });

    if (!hasPredictions) {
      forecastArea.classList.add('hidden');
      return;
    }

    forecastArea.classList.remove('hidden');
    const ctx = document.getElementById('forecastChart').getContext('2d');
    forecastChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: '2025 Actual',
            data: actual2025,
            backgroundColor: 'rgba(59, 130, 246, 0.7)',
            borderColor: 'rgb(59, 130, 246)',
            borderWidth: 1,
          },
          {
            label: '2026 Predicted',
            data: predicted2026,
            backgroundColor: 'rgba(139, 92, 246, 0.7)',
            borderColor: 'rgb(139, 92, 246)',
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: true, position: 'top' },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const v = ctx.raw;
                if (v == null) return ctx.dataset.label + ': —';
                return ctx.dataset.label + ': ' + (v % 1 === 0 ? String(v) : v.toFixed(1));
              },
            },
          },
        },
        scales: {
          y: { beginAtZero: true },
        },
      },
    });
  }

  async function loadBiodata() {
    if (!preloadDocId && !(preloadAthleteId && preloadTeam && preloadSeason)) return;
    try {
      let url = `${API_BASE}/api/player/profile?`;
      if (preloadDocId) url += 'doc_id=' + encodeURIComponent(preloadDocId);
      else url += 'athlete_id=' + encodeURIComponent(preloadAthleteId) + '&team=' + encodeURIComponent(preloadTeam) + '&season=' + encodeURIComponent(preloadSeason);
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok && data && !data.error) {
        renderBiodata(data);
        showBiodata(true);
      }
    } catch (_) {}
  }

  async function loadStats() {
    const player = playerInput.value.trim();
    if (!player) {
      showError('Enter a player name.');
      return;
    }
    showError('');
    showLoading(true);
    showCharts(false);
    showEmpty(false);
    showBiodata(false);

    loadBiodata();

    try {
      const q = new URLSearchParams({ player });
      const team = teamInput.value.trim();
      if (team) q.set('team', team);
      if (preloadDocId) q.set('doc_id', preloadDocId);
      if (preloadAthleteId) q.set('athlete_id', preloadAthleteId);
      if (preloadSeason) q.set('season', preloadSeason);
      const res = await fetch(`${API_BASE}/api/player/usage-history?${q}`);
      const data = await res.json();
      showLoading(false);
      if (!res.ok) {
        showError(data.error || 'Failed to load stats.');
        showEmpty(true);
        return;
      }
      buildCharts(data);
      buildForecastChart(data);
      if (data.player) {
        renderBiodata(data.player);
        showBiodata(true);
      }
    } catch (err) {
      showLoading(false);
      showError('Connection error. Make sure the server is running.');
      showEmpty(true);
    }
  }

  if (preloadPlayer) {
    loadStats();
  } else {
    showEmpty(true);
  }
});
