(function () {
  const input = document.getElementById('navPlayerSearch');
  const dropdown = document.getElementById('navSearchDropdown');
  if (!input || !dropdown) return;

  let allPlayers = [];
  let loaded = false;

  async function loadPlayers() {
    if (loaded) return;
    try {
      const cached = sessionStorage.getItem('portal_pair_player_list');
      if (cached) {
        const parsed = JSON.parse(cached);
        if (Array.isArray(parsed) && parsed.length > 0) {
          allPlayers = parsed;
          loaded = true;
          return;
        }
      }
      const res = await fetch('/api/players/list');
      if (!res.ok) return;
      allPlayers = await res.json();
      loaded = true;
      sessionStorage.setItem('portal_pair_player_list', JSON.stringify(allPlayers));
    } catch (_) {}
  }

  loadPlayers();

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    if (q.length < 2) {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
      return;
    }
    const matches = allPlayers.filter(p =>
      p.name.toLowerCase().includes(q)
    ).slice(0, 8);
    renderDropdown(matches);
  });

  function renderDropdown(results) {
    if (results.length === 0) {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
      return;
    }
    dropdown.innerHTML = results.map((p, i) =>
      `<div class="nav-search-item" data-idx="${i}">
        <span class="nav-search-name">${escapeHtml(p.name)}</span>
        <span class="nav-search-meta">${escapeHtml(p.position)}${p.position && p.team ? ' · ' : ''}${escapeHtml(p.team)}</span>
      </div>`
    ).join('');
    dropdown.classList.remove('hidden');
    dropdown._results = results;
  }

  dropdown.addEventListener('click', (e) => {
    const item = e.target.closest('.nav-search-item');
    if (!item) return;
    const idx = parseInt(item.dataset.idx, 10);
    const p = dropdown._results?.[idx];
    if (!p) return;
    let url = `stat-viewer.html?player=${encodeURIComponent(p.name)}`;
    if (p.team) url += `&team=${encodeURIComponent(p.team)}`;
    window.location.href = url;
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-search-wrapper')) {
      dropdown.classList.add('hidden');
    }
  });

  input.addEventListener('focus', () => {
    loadPlayers();
    const q = input.value.trim().toLowerCase();
    if (q.length >= 2 && allPlayers.length > 0) {
      const matches = allPlayers.filter(p => p.name.toLowerCase().includes(q)).slice(0, 8);
      renderDropdown(matches);
    }
  });

  function escapeHtml(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
})();
