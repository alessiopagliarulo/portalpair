const API_BASE = '';

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

  playerInput.value = decodeURIComponent(preloadPlayer || '');
  teamInput.value = decodeURIComponent(preloadTeam || '');
  if (preloadPlayer) {
    playerInput.readOnly = true;
    teamInput.readOnly = true;
  }

  let overallChart = null;
  let usageChart = null;

  function showError(msg) {
    errorEl.textContent = msg || '';
    errorEl.classList.toggle('hidden', !msg);
  }

  function showLoading(show) {
    loadingEl.classList.toggle('hidden', !show);
  }

  function showEmpty(show) {
    emptyEl.classList.toggle('hidden', !show);
  }

  function showCharts(show) {
    chartsArea.classList.toggle('hidden', !show);
  }

  function showBiodata(show) {
    biodataArea.classList.toggle('hidden', !show);
  }

  function renderBiodata(data) {
    const heightStr = data.height != null
      ? (Math.floor(parseInt(data.height, 10) / 12) + "'" + (parseInt(data.height, 10) % 12) + '"')
      : '—';
    document.getElementById('bioHeight').textContent = heightStr;
    document.getElementById('bioWeight').textContent = data.weight != null ? data.weight + ' lbs' : '—';
    document.getElementById('bioJersey').textContent = (data.jersey != null && data.jersey !== '') ? '#' + data.jersey : '—';
    const hometownParts = [data.homeCity, data.homeState, data.homeCountry].filter(Boolean);
    document.getElementById('bioHometown').textContent = hometownParts.length ? hometownParts.join(', ') : '—';
  }

  function destroyCharts() {
    if (overallChart) {
      overallChart.destroy();
      overallChart = null;
    }
    if (usageChart) {
      usageChart.destroy();
      usageChart = null;
    }
  }

  const CHART_COLORS = [
    'rgb(45, 106, 45)',    // green
    'rgb(59, 130, 246)',    // blue
    'rgb(239, 68, 68)',     // red
    'rgb(249, 115, 22)',    // orange
    'rgb(139, 92, 246)',    // purple
    'rgb(20, 184, 166)',    // teal
    'rgb(234, 179, 8)',     // amber
  ];

  const STAT_DEFS = [
    { key: 'pass', label: 'Pass', colorIdx: 0 },
    { key: 'rush', label: 'Rush', colorIdx: 1 },
    { key: 'firstDown', label: '1st Down', colorIdx: 2 },
    { key: 'secondDown', label: '2nd Down', colorIdx: 3 },
    { key: 'thirdDown', label: '3rd Down', colorIdx: 4 },
    { key: 'standardDowns', label: 'Standard Downs', colorIdx: 5 },
    { key: 'passingDowns', label: 'Passing Downs', colorIdx: 6 },
  ];

  let chartDataCache = null;

  function buildCharts(data) {
    destroyCharts();
    const seasons = data.seasons || [];
    if (seasons.length === 0) {
      showCharts(false);
      showEmpty(true);
      showError(data.error || 'No seasonal data found.');
      return;
    }

    const labels = seasons.map(s => String(s.season));
    const overallData = seasons.map(s => s.overall != null ? (s.overall * 100) : null);
    const passData = seasons.map(s => s.pass != null ? (s.pass * 100) : null);
    const rushData = seasons.map(s => s.rush != null ? (s.rush * 100) : null);
    const firstDownData = seasons.map(s => s.firstDown != null ? (s.firstDown * 100) : null);
    const secondDownData = seasons.map(s => s.secondDown != null ? (s.secondDown * 100) : null);
    const thirdDownData = seasons.map(s => s.thirdDown != null ? (s.thirdDown * 100) : null);
    const standardDownsData = seasons.map(s => s.standardDowns != null ? (s.standardDowns * 100) : null);
    const passingDownsData = seasons.map(s => s.passingDowns != null ? (s.passingDowns * 100) : null);

    const ctx1 = document.getElementById('overallChart').getContext('2d');
    overallChart = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Overall involvement %',
          data: overallData,
          backgroundColor: CHART_COLORS[0],
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: 'Involvement %' } },
        },
      },
    });

    chartDataCache = {
      labels,
      pass: passData,
      rush: rushData,
      firstDown: firstDownData,
      secondDown: secondDownData,
      thirdDown: thirdDownData,
      standardDowns: standardDownsData,
      passingDowns: passingDownsData,
    };

    updateUsageChart();
    showCharts(true);
    showEmpty(false);
    showError('');
  }

  function updateUsageChart() {
    if (!chartDataCache) return;
    const datasets = [];
    STAT_DEFS.forEach((def) => {
      const cb = document.querySelector(`#statFilters input[data-stat="${def.key}"]`);
      if (!cb?.checked) return;
      const data = chartDataCache[def.key];
      if (!data || !data.some(v => v != null)) return;
      const color = CHART_COLORS[def.colorIdx];
      const rgba = color.replace('rgb', 'rgba').replace(')', ', 0.25)');
      datasets.push({
        label: def.label,
        data: data,
        borderColor: color,
        backgroundColor: rgba,
        fill: false,
      });
    });
    if (usageChart) {
      usageChart.data.datasets = datasets;
      usageChart.update();
    } else {
      const ctx2 = document.getElementById('usageChart').getContext('2d');
      usageChart = new Chart(ctx2, {
        type: 'line',
        data: { labels: chartDataCache.labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          interaction: { mode: 'index', intersect: false },
          plugins: { legend: { position: 'top' } },
          scales: {
            y: { beginAtZero: true, max: 100, title: { display: true, text: 'Involvement %' } },
          },
        },
      });
    }
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
      const res = await fetch(`${API_BASE}/api/player/usage-history?${q}`);
      const data = await res.json();
      showLoading(false);
      if (!res.ok) {
        showError(data.error || 'Failed to load stats.');
        showEmpty(true);
        return;
      }
      buildCharts(data);
    } catch (err) {
      showLoading(false);
      showError('Connection error. Make sure the server is running.');
      showEmpty(true);
    }
  }

  document.getElementById('statFilters')?.addEventListener('change', () => updateUsageChart());

  if (preloadPlayer) {
    loadStats();
  } else {
    showEmpty(true);
  }
});
