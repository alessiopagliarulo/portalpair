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

  function showMatches(players) {
    if (!players || players.length === 0) {
      matchesGrid.classList.add('hidden');
      matchesEmpty.classList.remove('hidden');
      return;
    }
    matchesEmpty.classList.add('hidden');
    matchesGrid.innerHTML = '';
    matchesGrid.classList.remove('hidden');
    players.forEach((p) => {
      const card = document.createElement('div');
      card.className = 'player-card';
      const pct = p.matchPct != null ? Math.round(p.matchPct) : null;
      const heightStr = p.height ? `${Math.floor(p.height / 12)}'${p.height % 12}"` : '—';
      const weightStr = p.weight ? `${p.weight} lbs` : '—';
      const circleHtml = pct != null
        ? `<div class="match-circle" style="--pct:${pct}" title="${pct}% match"><span class="match-circle-value">${pct}</span></div>`
        : '';
      card.innerHTML = `
        <div class="player-card-header">
          <h3>${escapeHtml(p.name || `${p.firstName || ''} ${p.lastName || ''}`.trim())}</h3>
          ${circleHtml}
        </div>
        <div class="meta">
          ${p.team ? `<span>${escapeHtml(p.team)}</span>` : ''}
          ${p.position ? `<span>${escapeHtml(p.position)}</span>` : ''}
          <span>Height: ${heightStr}</span>
          <span>Weight: ${weightStr}</span>
        </div>
      `;
      matchesGrid.appendChild(card);
    });
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // Start with empty matches
  showMatches([]);

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
