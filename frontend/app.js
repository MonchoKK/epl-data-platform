// EPL Club Data Platform - Frontend Application Logic

const API_BASE = window.location.origin.includes(":8000")
  ? window.location.origin
  : "http://127.0.0.1:8000";

let state = {
  standings: [],
  clubs: [],
  players: [],
  matches: [],
  topScorers: [],
  clubAnalytics: [],
};

// =========================================================================
// INITIALIZATION
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupModal();
  setupPipelineTrigger();
  setupFilters();
  fetchAllData();
});

// =========================================================================
// DATA FETCHING & API INTERACTION
// =========================================================================

async function fetchAllData() {
  try {
    await checkHealth();
    await Promise.all([
      fetchStandings(),
      fetchClubs(),
      fetchPlayers(),
      fetchMatches(),
      fetchAnalytics(),
    ]);
  } catch (err) {
    console.error("Error loading data from API:", err);
    showToast("⚠️ Could not reach API. Please ensure FastAPI server is running on port 8000.");
  }
}

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (res.ok) {
      const data = await res.json();
      const statusBadge = document.getElementById("pipeline-status-badge");
      const statusText = document.getElementById("pipeline-status-text");
      if (data.database_connected) {
        statusBadge.className = "status-indicator online";
        statusText.innerText = "Warehouse: Online";
      } else {
        statusBadge.className = "status-indicator";
        statusText.innerText = "Warehouse: Degraded";
      }
    }
  } catch {
    const statusBadge = document.getElementById("pipeline-status-badge");
    const statusText = document.getElementById("pipeline-status-text");
    statusBadge.className = "status-indicator";
    statusText.innerText = "API Offline";
  }
}

async function fetchStandings() {
  try {
    const res = await fetch(`${API_BASE}/api/standings`);
    if (!res.ok) return;
    state.standings = await res.json();
    renderStandings(state.standings);
    updateLineageCount("stat-loaded-count", state.standings.length * 4); // snapshot estimate
  } catch (e) {
    console.warn("Standings fetch failed", e);
  }
}

async function fetchClubs() {
  try {
    const res = await fetch(`${API_BASE}/api/clubs`);
    if (!res.ok) return;
    state.clubs = await res.json();
    renderClubs(state.clubs);
    populateClubDropdown(state.clubs);
  } catch (e) {
    console.warn("Clubs fetch failed", e);
  }
}

async function fetchPlayers() {
  try {
    const res = await fetch(`${API_BASE}/api/players?limit=100`);
    if (!res.ok) return;
    state.players = await res.json();
    renderPlayers(state.players);
  } catch (e) {
    console.warn("Players fetch failed", e);
  }
}

async function fetchMatches() {
  try {
    const res = await fetch(`${API_BASE}/api/matches`);
    if (!res.ok) return;
    state.matches = await res.json();
    renderMatches(state.matches);
  } catch (e) {
    console.warn("Matches fetch failed", e);
  }
}

async function fetchAnalytics() {
  try {
    const [scorersRes, analyticsRes] = await Promise.all([
      fetch(`${API_BASE}/api/analytics/top-scorers?limit=6`),
      fetch(`${API_BASE}/api/analytics/club-summary`),
    ]);

    if (scorersRes.ok) {
      state.topScorers = await scorersRes.json();
      renderTopScorers(state.topScorers);
    }
    if (analyticsRes.ok) {
      state.clubAnalytics = await analyticsRes.json();
      renderClubAnalytics(state.clubAnalytics);
    }
  } catch (e) {
    console.warn("Analytics fetch failed", e);
  }
}

// =========================================================================
// RENDERING FUNCTIONS
// =========================================================================

function renderStandings(standings) {
  const tbody = document.getElementById("standings-tbody");
  tbody.innerHTML = "";

  standings.forEach((row) => {
    const tr = document.createElement("tr");

    // Form pills
    let formHtml = '<div class="form-pills">';
    if (row.form && row.form !== "N/A") {
      const letters = row.form.split("-");
      letters.forEach((l) => {
        const cls = l.toLowerCase();
        formHtml += `<span class="form-pill ${cls}">${l}</span>`;
      });
    } else {
      formHtml += '<span style="color: var(--text-dim);">-</span>';
    }
    formHtml += "</div>";

    const isTop4 = row.dynamic_rank <= 4 ? "top-4" : "";

    tr.innerHTML = `
      <td><span class="rank-badge ${isTop4}">${row.dynamic_rank}</span></td>
      <td>
        <div class="club-cell">
          <span class="club-color-dot" style="background: ${row.primary_color || '#fff'}"></span>
          <span>${row.club_name}</span>
        </div>
      </td>
      <td>${row.played}</td>
      <td>${row.won}</td>
      <td>${row.drawn}</td>
      <td>${row.lost}</td>
      <td>${row.goals_for}</td>
      <td>${row.goals_against}</td>
      <td>${row.goal_difference > 0 ? "+" + row.goal_difference : row.goal_difference}</td>
      <td><span class="pts-badge">${row.points}</span></td>
      <td>${row.points_per_game}</td>
      <td>${formHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderClubs(clubs) {
  const grid = document.getElementById("clubs-grid");
  grid.innerHTML = "";

  clubs.forEach((club) => {
    const card = document.createElement("div");
    card.className = "club-card";
    card.innerHTML = `
      <div>
        <div class="card-top">
          <div class="club-name" style="border-left: 4px solid ${club.primary_color || '#00ff85'}; padding-left: 0.5rem;">
            ${club.name}
          </div>
          <span class="club-code">${club.short_name}</span>
        </div>
        <ul class="club-info-list">
          <li>Stadium: <span>${club.stadium}</span></li>
          <li>Capacity: <span>${club.capacity ? club.capacity.toLocaleString() : 'N/A'}</span></li>
          <li>City: <span>${club.city}</span></li>
          <li>Founded: <span>${club.founded_year}</span></li>
        </ul>
      </div>
    `;
    grid.appendChild(card);
  });
}

function renderPlayers(players) {
  const tbody = document.getElementById("players-tbody");
  tbody.innerHTML = "";

  players.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 600;">${p.name}</td>
      <td>${p.club_name || 'EPL Club'}</td>
      <td><span class="view-tag">${p.position}</span></td>
      <td>${p.nationality}</td>
      <td>#${p.jersey_number}</td>
      <td>${p.appearances}</td>
      <td style="font-weight: 700; color: var(--epl-green);">${p.goals}</td>
      <td>${p.assists}</td>
      <td style="font-weight: 700;">${p.goal_contributions}</td>
      <td>${p.goals_per_game}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMatches(matches) {
  const grid = document.getElementById("matches-grid");
  grid.innerHTML = "";

  matches.forEach((m) => {
    const card = document.createElement("div");
    card.className = "match-card";
    card.innerHTML = `
      <div class="match-meta">
        <span>Gameweek ${m.gameweek}</span>
        <span>${m.match_date ? m.match_date.slice(0, 10) : ''}</span>
      </div>
      <div class="match-fixture">
        <div class="match-team">${m.home_club_name || 'Home'}</div>
        <div class="match-score-pill">${m.score || `${m.home_score} - ${m.away_score}`}</div>
        <div class="match-team away">${m.away_club_name || 'Away'}</div>
      </div>
      <div class="match-result-badge">${m.result ? m.result.replace('_', ' ') : 'FINISHED'}</div>
    `;
    grid.appendChild(card);
  });
}

function renderTopScorers(scorers) {
  const container = document.getElementById("top-scorers-list");
  container.innerHTML = "";

  scorers.forEach((s) => {
    const row = document.createElement("div");
    row.className = "scorer-row";
    row.innerHTML = `
      <div class="scorer-info">
        <span class="scorer-rank">#${s.scorer_rank}</span>
        <div>
          <div class="scorer-name">${s.player_name}</div>
          <div class="scorer-team">${s.club_name} &bull; ${s.position}</div>
        </div>
      </div>
      <div class="scorer-goals">
        ${s.goals} <small>goals (${s.assists} assists)</small>
      </div>
    `;
    container.appendChild(row);
  });
}

function renderClubAnalytics(analytics) {
  const tbody = document.getElementById("club-analytics-tbody");
  tbody.innerHTML = "";

  analytics.forEach((a) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 600;">${a.club_name}</td>
      <td>${a.squad_size} players</td>
      <td style="color: var(--epl-green); font-weight: 700;">${a.squad_goals}</td>
      <td>${a.squad_assists}</td>
      <td>${a.avg_player_appearances}</td>
      <td>${a.capacity ? a.capacity.toLocaleString() : 'N/A'}</td>
    `;
    tbody.appendChild(tr);
  });
}

function updateLineageCount(elementId, count) {
  const el = document.getElementById(elementId);
  if (el) el.innerText = count;
}

// =========================================================================
// EVENT HANDLERS & FILTERS
// =========================================================================

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
    });
  });
}

function setupModal() {
  const btnOpen = document.getElementById("btn-view-sql");
  const btnClose = document.getElementById("btn-close-modal");
  const modal = document.getElementById("sql-modal");

  btnOpen.addEventListener("click", () => modal.classList.add("active"));
  btnClose.addEventListener("click", () => modal.classList.remove("active"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("active");
  });
}

function setupPipelineTrigger() {
  const btn = document.getElementById("btn-trigger-pipeline");
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Ingesting &amp; Transforming...';

    try {
      const res = await fetch(`${API_BASE}/api/pipeline/trigger`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        showToast(`✅ ELT Pipeline executed successfully! ${data.report.loader.total_loaded} entities loaded.`);
        await fetchAllData();
      } else {
        showToast("❌ Failed to trigger pipeline.");
      }
    } catch (e) {
      showToast("❌ Error triggering pipeline: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">⚡</span> Run ELT Pipeline';
    }
  });
}

function setupFilters() {
  // Club search
  const clubInput = document.getElementById("club-search-input");
  clubInput.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    const filtered = state.clubs.filter(
      (c) => c.name.toLowerCase().includes(q) || c.city.toLowerCase().includes(q)
    );
    renderClubs(filtered);
  });

  // Player search & dropdowns
  const playerSearch = document.getElementById("player-search-input");
  const positionSelect = document.getElementById("player-position-select");
  const clubSelect = document.getElementById("player-club-select");

  const filterPlayers = () => {
    const q = playerSearch.value.toLowerCase();
    const pos = positionSelect.value;
    const cid = clubSelect.value;

    const filtered = state.players.filter((p) => {
      const matchesName = p.name.toLowerCase().includes(q);
      const matchesPos = pos ? p.position === pos : true;
      const matchesClub = cid ? String(p.club_id) === String(cid) : true;
      return matchesName && matchesPos && matchesClub;
    });
    renderPlayers(filtered);
  };

  playerSearch.addEventListener("input", filterPlayers);
  positionSelect.addEventListener("change", filterPlayers);
  clubSelect.addEventListener("change", filterPlayers);

  // Match gameweek selector
  const gwSelect = document.getElementById("match-gameweek-select");
  gwSelect.addEventListener("change", (e) => {
    const gw = e.target.value;
    if (!gw) {
      renderMatches(state.matches);
    } else {
      const filtered = state.matches.filter((m) => String(m.gameweek) === String(gw));
      renderMatches(filtered);
    }
  });
}

function populateClubDropdown(clubs) {
  const select = document.getElementById("player-club-select");
  select.innerHTML = '<option value="">All Clubs</option>';
  clubs.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.club_id;
    opt.innerText = c.name;
    select.appendChild(opt);
  });
}

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.innerText = msg;
  toast.classList.add("show");
  setTimeout(() => {
    toast.classList.remove("show");
  }, 4000);
}
