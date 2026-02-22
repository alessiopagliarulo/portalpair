(function () {
    let chartBar = null;

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
    if (s === null || s === undefined) return '—';
    const div = document.createElement('div');
    div.textContent = String(s);
    return div.innerHTML;
  }

  function pct(v) {
    if (v === null || v === undefined) return '—';
    const n = parseFloat(v);
    if (isNaN(n)) return '—';
    return (n * 100).toFixed(1) + '%';
  }

  function heightStr(h) {
    if (h == null || h === '') return '—';
    const n = parseInt(h, 10);
    if (isNaN(n)) return '—';
    const ft = Math.floor(n / 12);
    const inch = n % 12;
    return ft + "'" + inch + '"';
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

    // Biometric section
    document.getElementById('bioHeight').textContent = heightStr(data.height);
    document.getElementById('bioWeight').textContent = data.weight != null ? data.weight + ' lbs' : '—';
    document.getElementById('bioJersey').textContent = data.jersey != null && data.jersey !== '' ? '#' + data.jersey : '—';
    const hometownParts = [data.homeCity, data.homeState, data.homeCountry].filter(Boolean);
    document.getElementById('bioHometown').textContent = hometownParts.length ? hometownParts.join(', ') : '—';

    const fields = [
      ['firstName', 'First name'],
      ['lastName', 'Last name'],
      ['team', 'Team'],
      ['position', 'Position'],
      ['overall', 'Overall involvement', (v) => pct(v)],
      ['pass', 'Pass involvement', (v) => pct(v)],
      ['rush', 'Rush involvement', (v) => pct(v)],
      ['firstDown', '1st down involvement', (v) => pct(v)],
      ['secondDown', '2nd down involvement', (v) => pct(v)],
      ['thirdDown', '3rd down involvement', (v) => pct(v)],
      ['standardDowns', 'Standard downs involvement', (v) => pct(v)],
      ['passingDowns', 'Passing downs involvement', (v) => pct(v)],
    ];

    const dl = document.getElementById('profileFields');
    dl.innerHTML = '';
    fields.forEach(function (f) {
      const key = f[0];
      const label = f[1];
      const fmt = f[2] || function (v) { return v != null && v !== '' ? escapeHtml(String(v)) : '—'; };
      const val = data[key];
      const dt = document.createElement('dt');
      dt.textContent = label;
      const dd = document.createElement('dd');
      dd.innerHTML = fmt(val);
      dl.appendChild(dt);
      dl.appendChild(dd);
    });

    const usageKeys = [
      { key: 'overall', label: 'Overall' },
      { key: 'pass', label: 'Pass' },
      { key: 'rush', label: 'Rush' },
      { key: 'firstDown', label: '1st down' },
      { key: 'secondDown', label: '2nd down' },
      { key: 'thirdDown', label: '3rd down' },
      { key: 'standardDowns', label: 'Standard downs' },
      { key: 'passingDowns', label: 'Passing downs' },
    ];

    const labels = usageKeys.map(function (x) { return x.label; });
    const values = usageKeys.map(function (x) {
      const v = data[x.key];
      return v != null ? parseFloat(v) * 100 : 0;
    });

    const CHART_COLORS = [
      'rgb(45, 106, 45)',   /* green */
      'rgb(59, 130, 246)',  /* blue */
      'rgb(239, 68, 68)',   /* red */
      'rgb(249, 115, 22)',  /* orange */
      'rgb(139, 92, 246)',  /* purple */
      'rgb(20, 184, 166)',  /* teal */
      'rgb(234, 179, 8)',   /* amber */
      'rgb(236, 72, 153)',  /* pink */
    ];
    const barCtx = document.getElementById('usageBarChart').getContext('2d');
    if (chartBar) chartBar.destroy();
    chartBar = new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Involvement %',
          data: values,
          backgroundColor: labels.map(function (_, i) { return CHART_COLORS[i % CHART_COLORS.length]; }),
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (ctx) { return ctx.raw.toFixed(1) + '%'; } } },
        },
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: 'Involvement %' } },
        },
      },
    });

    showContent();
  }

  function renderRankingOnly(rankVal, nameVal, statsVal) {
    document.getElementById('profileName').textContent = nameVal || 'Unknown';
    document.getElementById('profileMeta').textContent = 'Rank #' + (rankVal || '—') + (statsVal ? ' · ' + statsVal : '');

    const dl = document.getElementById('profileFields');
    dl.innerHTML = '';
    const rows = [['name', 'Name', nameVal], ['rank', 'Rank', rankVal], ['stats', 'Stats', statsVal]];
    rows.forEach(function (r) {
      const dt = document.createElement('dt');
      dt.textContent = r[1];
      const dd = document.createElement('dd');
      dd.textContent = r[2] != null ? r[2] : '—';
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
