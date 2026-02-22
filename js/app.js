const API_BASE = '';

// Elements
const searchInput = document.getElementById('searchInput');
const positionFilter = document.getElementById('positionFilter');
const yearFilter = document.getElementById('yearFilter');
const searchBtn = document.getElementById('searchBtn');
const resultsGrid = document.getElementById('resultsGrid');
const resultsHeader = document.getElementById('resultsHeader');
const resultsCount = document.getElementById('resultsCount');
const loading = document.getElementById('loading');
const emptyState = document.getElementById('emptyState');
const errorState = document.getElementById('errorState');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');

// Search players
async function searchPlayers() {
  const term = searchInput.value.trim();
  if (!term) return;

  hideAll();
  loading.classList.remove('hidden');

  try {
    const params = new URLSearchParams({
      searchTerm: term,
      year: yearFilter.value || '2024'
    });
    if (positionFilter.value) params.set('position', positionFilter.value);

    const res = await fetch(`${API_BASE}/api/player/search?${params}`);
    if (!res.ok) throw new Error('Search failed');
    const players = await res.json();

    if (!Array.isArray(players) || players.length === 0) {
      emptyState.classList.remove('hidden');
      emptyState.innerHTML = '<span class="empty-icon">🔍</span><p>No players found. Try a different name or filters.</p>';
    } else {
      resultsHeader.classList.remove('hidden');
      resultsCount.textContent = `${players.length} player${players.length !== 1 ? 's' : ''} found`;
      renderPlayers(players);
    }
  } catch (err) {
    errorState.classList.remove('hidden');
    errorState.textContent = 'Could not load players. Make sure the server is running (npm start).';
  } finally {
    loading.classList.add('hidden');
  }
}

function renderPlayers(players) {
  resultsGrid.innerHTML = '';
  resultsGrid.classList.remove('hidden');

  players.forEach((p) => {
    const card = document.createElement('div');
    card.className = 'player-card';

    const heightStr = p.height ? `${Math.floor(p.height / 12)}'${p.height % 12}"` : '-';
    const weightStr = p.weight ? `${p.weight} lbs` : '-';

    // Simplified PIS placeholder: use height/weight if available, else "-"
    const pisDisplay = computePISPlaceholder(p);

    card.innerHTML = `
      <h3>${escapeHtml(p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim())}</h3>
      <div class="meta">
        ${p.team ? `<span><span class="team-color" style="background:${p.teamColor || '#666'}"></span>${escapeHtml(p.team)}</span>` : ''}
        ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
        <span>Ht: ${heightStr}</span>
        <span>Wt: ${weightStr}</span>
      </div>
      <div><span class="pis-badge">PIS ${pisDisplay}</span></div>
    `;
    resultsGrid.appendChild(card);
  });
}

function computePISPlaceholder(p) {
  // Placeholder: real PIS needs S_adj = S_raw × (1 + W_elo) from Elo + season stats
  if (!p.height && !p.weight) return '-';
  let raw = 50;
  if (p.height) raw += Math.min((p.height - 60) * 2, 25);
  if (p.weight) raw += Math.min((p.weight - 180) / 10, 25);
  return Math.min(99, Math.max(0, Math.round(raw)));
}

function escapeHtml(s) {
  if (!s) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function hideAll() {
  resultsGrid.classList.add('hidden');
  resultsHeader.classList.add('hidden');
  emptyState.classList.add('hidden');
  errorState.classList.add('hidden');
  emptyState.innerHTML = '<span class="empty-icon">🏈</span><p>Search for college football players above.</p>';
}

// Coach chat
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
  assistantMsg.textContent = 'Thinking...';
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
  } catch (err) {
    assistantMsg.textContent = 'Connection error. Make sure the server is running.';
  }

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Event listeners
searchBtn.addEventListener('click', searchPlayers);
searchInput.addEventListener('keydown', (e) => e.key === 'Enter' && searchPlayers());
chatSend.addEventListener('click', sendCoachMessage);
chatInput.addEventListener('keydown', (e) => e.key === 'Enter' && sendCoachMessage());
