/* Экран одного турнира: составы, матчи, таблица и редактор протокола.
 *
 * Отдельная страница, а не вкладка в SPA: app.js уже большой, а редактор протокола
 * — самостоятельный экран. Токен лежит в localStorage того же origin, поэтому
 * авторизация работает без изменений.
 *
 * Раскладка протокола повторяет бумажный бланк: составы двух команд с номерами
 * и две таблицы «ВЗЯТИЕ ВОРОТ» с колонками № | период | ВРЕМЯ | Г(ГОЛ) | П(ПАС).
 */

const API = "/api/admin";
const TOKEN_KEY = "admin_jwt";

const $ = (id) => document.getElementById(id);
const show = (el, on) => el.classList.toggle("hidden", !on);

const TOURNAMENT_ID = new URLSearchParams(location.search).get("id");

// Состояние страницы.
const state = {
  tournament: null,
  roster: [],          // строки заявки турнира
  games: [],
  protocol: null,      // открытый матч
  addTeamId: null,     // команда, в состав которой добавляем
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function authHeaders() {
  const t = localStorage.getItem(TOKEN_KEY);
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function apiFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (opts.body && typeof opts.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  Object.assign(headers, authHeaders());
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  const text = await res.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = { detail: text }; }
  }
  if (!res.ok) {
    if (res.status === 401) {
      show($("content"), false);
      show($("authError"), true);
    }
    const d = data?.detail;
    const msg = d ? (Array.isArray(d) ? d.map((x) => x.msg).join(", ") : String(d)) : res.statusText;
    throw new Error(msg || "Ошибка запроса");
  }
  return data;
}

function fail(targetId, err) {
  const el = $(targetId);
  el.textContent = err.message;
  show(el, true);
}

function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = String(iso).split("-");
  return `${d}.${m}.${y}`;
}

/* ------------------------------ время MM:SS ------------------------------ */

/** Нормализовать ввод времени: «1336» → «13:36». Зеркалит app/core/clock.py. */
function normalizeClock(raw) {
  const v = String(raw ?? "").trim();
  if (!v) return "";
  if (v.includes(":")) return v;
  if (!/^\d+$/.test(v)) return v;
  if (v.length <= 2) return `00:${v.padStart(2, "0")}`;
  const mm = v.slice(0, -2);
  const ss = v.slice(-2);
  return `${mm.padStart(2, "0")}:${ss}`;
}

/* -------------------------------- турнир -------------------------------- */

async function loadTournament() {
  const all = await apiFetch("/tournaments?limit=200");
  state.tournament = all.find((t) => t.id === TOURNAMENT_ID) || null;
  if (!state.tournament) throw new Error("Турнир не найден");
  const t = state.tournament;
  $("tTitle").textContent = t.title;
  const bits = [t.age_category];
  if (t.birth_year) bits.push(t.birth_year);
  bits.push(`${fmtDate(t.start_date)} — ${fmtDate(t.end_date)}`);
  if (t.arena?.name) bits.push(t.arena.name);
  if (t.game_format) bits.push(`формат ${t.game_format}`);
  $("tMeta").textContent = bits.join(" · ");

  const hint = $("regulationHint");
  if (t.period_minutes == null || t.periods_count == null) {
    hint.textContent =
      "У турнира не заданы длительность и количество периодов. Без них время и период гола " +
      "не проверяются, а минуты в воротах не считаются — задайте их в карточке турнира.";
    show(hint, true);
  } else {
    show(hint, false);
  }
  document.title = `${t.title} — статистика`;
}

function teamsOfTournament() {
  return state.tournament?.teams || [];
}

/* -------------------------------- составы -------------------------------- */

async function loadRoster() {
  show($("rosterError"), false);
  state.roster = await apiFetch(`/tournaments/${TOURNAMENT_ID}/roster`);
  renderRoster();
}

function rosterOfTeam(teamId) {
  return state.roster.filter((e) => e.team_id === teamId);
}

function renderRoster() {
  const host = $("rosterByTeam");
  host.innerHTML = "";
  const teams = teamsOfTournament();
  if (!teams.length) {
    host.innerHTML = '<p class="muted">В турнире нет команд — добавьте их в карточке турнира.</p>';
    return;
  }
  for (const team of teams) {
    const entries = rosterOfTeam(team.id);
    const box = document.createElement("div");
    box.className = "roster-team";

    const head = document.createElement("div");
    head.className = "row space-between";
    const h = document.createElement("h3");
    h.textContent = `${team.name} — ${entries.length} игроков`;
    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn";
    addBtn.textContent = "Добавить игроков";
    addBtn.addEventListener("click", () => openRosterAddModal(team));
    head.appendChild(h);
    head.appendChild(addBtn);
    box.appendChild(head);

    if (!entries.length) {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = "Состав пуст.";
      box.appendChild(p);
    } else {
      const wrap = document.createElement("div");
      wrap.className = "table-wrap";
      const table = document.createElement("table");
      table.className = "table";
      table.innerHTML =
        "<thead><tr><th>№</th><th>ФИО</th><th>Амплуа</th><th></th></tr></thead>";
      const tbody = document.createElement("tbody");
      for (const e of entries) {
        const tr = document.createElement("tr");

        const tdNum = document.createElement("td");
        tdNum.setAttribute("data-label", "№");
        const numInput = document.createElement("input");
        numInput.type = "number";
        numInput.min = "1";
        numInput.max = "99";
        numInput.value = e.number ?? "";
        numInput.style.width = "5em";
        numInput.addEventListener("change", async () => {
          try {
            const raw = String(numInput.value).trim();
            await apiFetch(`/tournaments/${TOURNAMENT_ID}/roster/${e.id}`, {
              method: "PATCH",
              body: JSON.stringify({ number: raw === "" ? null : Number.parseInt(raw, 10) }),
            });
            await loadRoster();
          } catch (err) {
            fail("rosterError", err);
            numInput.value = e.number ?? "";
          }
        });
        tdNum.appendChild(numInput);
        tr.appendChild(tdNum);

        const tdName = document.createElement("td");
        tdName.setAttribute("data-label", "ФИО");
        tdName.textContent = e.full_name;
        tr.appendChild(tdName);

        const tdPos = document.createElement("td");
        tdPos.setAttribute("data-label", "Амплуа");
        tdPos.innerHTML = e.position ? escapeHtml(e.position) : '<span class="muted">—</span>';
        tr.appendChild(tdPos);

        const tdAct = document.createElement("td");
        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn danger btn-small";
        del.textContent = "Убрать";
        del.addEventListener("click", async () => {
          if (!window.confirm(`Убрать ${e.full_name} из состава? Если он играл в матчах, статистика этих матчей останется.`)) return;
          try {
            await apiFetch(`/tournaments/${TOURNAMENT_ID}/roster/${e.id}`, { method: "DELETE" });
            await loadRoster();
          } catch (err) {
            fail("rosterError", err);
          }
        });
        tdAct.appendChild(del);
        tr.appendChild(tdAct);

        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      wrap.appendChild(table);
      box.appendChild(wrap);
    }
    host.appendChild(box);
  }
}

/* ------------------- модалка: добавить игроков в состав ------------------- */

async function openRosterAddModal(team) {
  state.addTeamId = team.id;
  $("rosterAddTitle").textContent = `Добавить игроков — ${team.name}`;
  $("rosterAddSearch").value = "";
  $("rosterAddMsg").textContent = "";
  show($("rosterAddMsg"), false);
  show($("rosterAddModal"), true);
  $("rosterAddModal").setAttribute("aria-hidden", "false");
  await renderRosterAddList();
}

function closeRosterAddModal() {
  show($("rosterAddModal"), false);
  $("rosterAddModal").setAttribute("aria-hidden", "true");
}

async function renderRosterAddList() {
  const q = String($("rosterAddSearch").value || "").trim();
  const path = q ? `/players?limit=500&search=${encodeURIComponent(q)}` : "/players?limit=500";
  const players = await apiFetch(path);
  const already = new Set(rosterOfTeam(state.addTeamId).map((e) => e.player_id));
  const list = $("rosterAddList");
  list.innerHTML = "";
  const available = players.filter((p) => !already.has(p.id));
  if (!available.length) {
    list.innerHTML = `<li class="muted">${q ? "Ничего не найдено" : "Все игроки справочника уже заявлены"}</li>`;
    return;
  }
  for (const p of available) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "row gap";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.dataset.playerId = p.id;

    const label = document.createElement("span");
    label.className = "grow";
    label.textContent = p.position ? `${p.full_name} (${p.position})` : p.full_name;

    const num = document.createElement("input");
    num.type = "number";
    num.min = "1";
    num.max = "99";
    num.placeholder = "№";
    num.style.width = "5em";
    num.dataset.numberFor = p.id;

    row.appendChild(cb);
    row.appendChild(label);
    row.appendChild(num);
    li.appendChild(row);
    list.appendChild(li);
  }
}

/* --------------------------------- матчи --------------------------------- */

function fillTeamSelect(id, selectedId) {
  const sel = $(id);
  sel.innerHTML = "";
  for (const t of teamsOfTournament()) {
    const o = document.createElement("option");
    o.value = t.id;
    o.textContent = t.name;
    sel.appendChild(o);
  }
  if (selectedId) sel.value = selectedId;
}

function renderTeamSelects() {
  const teams = teamsOfTournament();
  fillTeamSelect("gcTeamA");
  fillTeamSelect("gcTeamB");
  if (teams.length > 1) $("gcTeamB").value = teams[1].id;
}

async function loadGames() {
  show($("gamesError"), false);
  state.games = await apiFetch(`/tournaments/${TOURNAMENT_ID}/games`);
  const rows = $("gameRows");
  rows.innerHTML = "";
  if (!state.games.length) {
    rows.innerHTML = '<tr><td colspan="8" class="muted">Матчей пока нет</td></tr>';
    return;
  }
  for (const g of state.games) {
    const tr = document.createElement("tr");
    const score = g.score_a != null && g.score_b != null ? `${g.score_a} : ${g.score_b}` : "—";
    const shots = g.shots_a != null && g.shots_b != null ? `${g.shots_a} : ${g.shots_b}` : "—";
    const when = `${fmtDate(g.date)}${g.time ? " · " + g.time : ""}`;
    tr.innerHTML = `
      <td data-label="№">${g.position}</td>
      <td data-label="Дата">${escapeHtml(when)}</td>
      <td data-label="Команды">${escapeHtml(g.team_a.name)} — ${escapeHtml(g.team_b.name)}</td>
      <td data-label="Голы">${escapeHtml(score)}</td>
      <td data-label="Броски">${escapeHtml(shots)}</td>
      <td data-label="Статус">${g.is_finished ? "сыгран" : "не сыгран"}</td>
      <td data-label="Скан">${
        g.scan
          ? `<a href="${escapeHtml(g.scan)}" target="_blank" rel="noopener">открыть</a>`
          : '<span class="muted">—</span>'
      }</td>
    `;
    const tdAct = document.createElement("td");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-small";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openGameEditModal(g));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    const protoBtn = document.createElement("button");
    protoBtn.type = "button";
    protoBtn.className = "btn primary btn-small";
    protoBtn.textContent = "Протокол";
    protoBtn.addEventListener("click", () => openProtocol(g.id));
    tdAct.appendChild(protoBtn);
    tdAct.appendChild(document.createTextNode(" "));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "btn danger btn-small";
    del.textContent = "Удалить";
    del.addEventListener("click", async () => {
      if (!window.confirm(`Удалить матч №${g.position} (${g.team_a.name} — ${g.team_b.name})? Протокол и голы исчезнут.`)) return;
      try {
        await apiFetch(`/games/${g.id}`, { method: "DELETE" });
        await Promise.all([loadGames(), loadStandings()]);
      } catch (err) {
        fail("gamesError", err);
      }
    });
    tdAct.appendChild(del);
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

/* -------------------------------- таблица -------------------------------- */

async function loadStandings() {
  const rows = $("standingRows");
  rows.innerHTML = "";
  const res = await fetch(`/tournaments/${TOURNAMENT_ID}/standings`);
  if (!res.ok) {
    rows.innerHTML = '<tr><td colspan="10" class="muted">Таблица недоступна (турнир скрыт с сайта)</td></tr>';
    return;
  }
  const data = await res.json();
  if (!data.length) {
    rows.innerHTML = '<tr><td colspan="10" class="muted">Нет команд</td></tr>';
    return;
  }
  for (const r of data) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.place}</td>
      <td>${escapeHtml(r.team.name)}</td>
      <td>${r.games}</td><td>${r.wins}</td><td>${r.draws}</td><td>${r.losses}</td>
      <td>${r.goalsFor}</td><td>${r.goalsAgainst}</td><td>${r.goalDiff}</td>
      <td><strong>${r.points}</strong></td>
    `;
    rows.appendChild(tr);
  }
}

/* --------------------------- правка матча --------------------------- */

function openGameEditModal(g) {
  $("geId").value = g.id;
  $("gameEditTitle").textContent =
    `МАТЧ № ${g.position} · ${g.team_a.name} — ${g.team_b.name}`;
  fillTeamSelect("geTeamA", g.team_a.id);
  fillTeamSelect("geTeamB", g.team_b.id);
  $("geDate").value = g.date;
  $("geTime").value = g.time ? String(g.time).slice(0, 5) : "";
  $("gePosition").value = String(g.position);
  $("geScoreA").value = g.score_a ?? "";
  $("geScoreB").value = g.score_b ?? "";
  $("geShotsA").value = g.shots_a ?? "";
  $("geShotsB").value = g.shots_b ?? "";
  $("geVideoUrl").value = g.video_url || "";
  $("geScan").value = g.scan || "";
  $("geLabelGoalsA").textContent = `Голы — ${g.team_a.name}`;
  $("geLabelGoalsB").textContent = `Голы — ${g.team_b.name}`;
  $("geLabelShotsA").textContent = `Броски — ${g.team_a.name}`;
  $("geLabelShotsB").textContent = `Броски — ${g.team_b.name}`;
  renderScanPreview();
  $("gameEditMsg").textContent = "";
  show($("gameEditMsg"), false);
  show($("geScanMsg"), false);
  show($("gameEditModal"), true);
  $("gameEditModal").setAttribute("aria-hidden", "false");
}

function closeGameEditModal() {
  show($("gameEditModal"), false);
  $("gameEditModal").setAttribute("aria-hidden", "true");
}

/** Ссылка на текущий скан рядом с полем — чтобы было видно, что он приложен. */
function renderScanPreview() {
  const el = $("geScanPreview");
  const url = String($("geScan").value || "").trim();
  if (!url) {
    show(el, false);
    return;
  }
  el.innerHTML = `Приложено: <a href="${escapeHtml(url)}" target="_blank" rel="noopener">открыть скан</a>`;
  show(el, true);
}

/* ------------------------------- протокол ------------------------------- */

/** Игроки состава команды, доступные для отметки «играл». */
function lineupSource(teamId) {
  return rosterOfTeam(teamId);
}

/** Кто отмечен как игравший: player_id → {number, name, isGoalie}. */
function playedMap(side) {
  const host = side === "a" ? $("prLineupA") : $("prLineupB");
  const out = new Map();
  host.querySelectorAll("[data-played]").forEach((cb) => {
    if (!cb.checked) return;
    const pid = cb.dataset.played;
    const goalie = host.querySelector(`[data-goalie="${pid}"]`);
    out.set(pid, {
      number: cb.dataset.number ? Number.parseInt(cb.dataset.number, 10) : null,
      name: cb.dataset.name,
      isGoalie: !!(goalie && goalie.checked),
    });
  });
  return out;
}

/** Номер → player_id среди отмеченных как игравшие (для колонок Г(ГОЛ)/П(ПАС)). */
function numberIndex(side) {
  const idx = new Map();
  for (const [pid, info] of playedMap(side)) {
    if (info.number != null) idx.set(String(info.number), pid);
  }
  return idx;
}

function renderLineup(side, teamId, playedLines) {
  const host = side === "a" ? $("prLineupA") : $("prLineupB");
  host.innerHTML = "";
  const entries = lineupSource(teamId);
  if (!entries.length) {
    host.innerHTML = '<p class="muted">Состав на турнир не заявлен — сначала заполните составы выше.</p>';
    return;
  }
  const byPlayer = new Map(playedLines.map((l) => [l.player_id, l]));
  for (const e of entries) {
    const line = byPlayer.get(e.player_id);
    const row = document.createElement("label");
    row.className = "lineup-row";

    const played = document.createElement("input");
    played.type = "checkbox";
    played.dataset.played = e.player_id;
    played.dataset.number = e.number ?? "";
    played.dataset.name = e.full_name;
    played.checked = !!line;
    played.addEventListener("change", refreshDerived);

    const num = document.createElement("span");
    num.className = "lineup-num";
    num.textContent = e.number != null ? `№${e.number}` : "—";

    const name = document.createElement("span");
    name.className = "lineup-name";
    name.textContent = e.full_name;

    const goalieWrap = document.createElement("span");
    goalieWrap.className = "muted";
    const goalie = document.createElement("input");
    goalie.type = "checkbox";
    goalie.dataset.goalie = e.player_id;
    goalie.checked = line ? !!line.is_goalie : e.position === "вратарь";
    goalie.addEventListener("change", refreshDerived);
    goalieWrap.appendChild(goalie);
    goalieWrap.appendChild(document.createTextNode(" вратарь"));

    row.appendChild(played);
    row.appendChild(num);
    row.appendChild(name);
    row.appendChild(goalieWrap);
    host.appendChild(row);
  }
}

function goalRow(side, ev) {
  const tr = document.createElement("tr");

  const tdNo = document.createElement("td");
  tdNo.className = "goal-no";
  tr.appendChild(tdNo);

  const mk = (type, value, cls) => {
    const td = document.createElement("td");
    const inp = document.createElement("input");
    inp.type = type;
    inp.value = value ?? "";
    if (cls) inp.dataset.role = cls;
    td.appendChild(inp);
    tr.appendChild(td);
    return inp;
  };

  const period = mk("number", ev?.period ?? 1, "period");
  period.min = "1";
  period.max = "10";

  const time = mk("text", ev?.time ?? "", "time");
  time.placeholder = "MM:SS";
  // Секретарь набирает «1336» — приводим к виду бланка при уходе из поля.
  time.addEventListener("blur", () => { time.value = normalizeClock(time.value); });

  const scorer = mk("text", ev?.player_number ?? "", "scorer");
  scorer.placeholder = "№";

  const assistNumbers = [ev?.assist1_number, ev?.assist2_number].filter((x) => x != null);
  const assists = mk("text", assistNumbers.join(", "), "assists");
  assists.placeholder = "№ или №, №";

  for (const inp of [period, time, scorer, assists]) {
    inp.addEventListener("input", refreshDerived);
  }

  const tdAct = document.createElement("td");
  const del = document.createElement("button");
  del.type = "button";
  del.className = "btn danger btn-small";
  del.textContent = "×";
  del.title = "Удалить строку";
  del.addEventListener("click", () => { tr.remove(); refreshDerived(); });
  tdAct.appendChild(del);
  tr.appendChild(tdAct);

  return tr;
}

function renderGoals(side, events) {
  const tbody = side === "a" ? $("prGoalsA") : $("prGoalsB");
  tbody.innerHTML = "";
  for (const ev of events) tbody.appendChild(goalRow(side, ev));
}

/** Прочитать таблицу голов одной команды из DOM. */
function readGoals(side) {
  const tbody = side === "a" ? $("prGoalsA") : $("prGoalsB");
  const idx = numberIndex(side);
  const out = [];
  tbody.querySelectorAll("tr").forEach((tr) => {
    const get = (role) => tr.querySelector(`[data-role="${role}"]`);
    const periodEl = get("period");
    const timeEl = get("time");
    const scorerEl = get("scorer");
    const assistsEl = get("assists");

    const assistNums = String(assistsEl.value || "")
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean);

    const scorerNum = String(scorerEl.value || "").trim();
    const row = {
      period: Number.parseInt(periodEl.value, 10) || 1,
      time: normalizeClock(timeEl.value),
      scorerNum,
      assistNums,
      scorerId: idx.get(scorerNum) || null,
      assistIds: assistNums.map((n) => idx.get(n) || null),
      el: { scorerEl, assistsEl, timeEl },
    };
    // Пустая строка (ничего не заполнено) игнорируется.
    row.empty = !scorerNum && !row.time && !assistNums.length;
    out.push(row);
  });
  return out;
}

/** Пересчитать нумерацию, подсветку неизвестных номеров и сверку со счётом. */
function refreshDerived() {
  const p = state.protocol;
  if (!p) return;

  let problems = 0;
  const counts = { a: 0, b: 0 };

  for (const side of ["a", "b"]) {
    const tbody = side === "a" ? $("prGoalsA") : $("prGoalsB");
    const rows = readGoals(side);
    let n = 0;
    tbody.querySelectorAll("tr").forEach((tr, i) => {
      const row = rows[i];
      const cell = tr.querySelector(".goal-no");
      if (row.empty) {
        if (cell) cell.textContent = "";
      } else {
        n += 1;
        if (cell) cell.textContent = String(n);
      }

      // Подсветка: номер не найден среди отмеченных как игравшие.
      row.el.scorerEl.classList.toggle("bad", !row.empty && !row.scorerId);
      const badAssist = row.assistIds.some((x) => x === null);
      row.el.assistsEl.classList.toggle("bad", !row.empty && badAssist);
      // Автор не может ассистировать сам себе.
      const selfAssist = row.scorerId && row.assistIds.includes(row.scorerId);
      if (selfAssist) row.el.assistsEl.classList.add("bad");
      if (!row.empty && (!row.scorerId || badAssist || selfAssist)) problems += 1;
    });
    counts[side] = n;
  }

  // Сверка таймлайна со счётом — приём из protocol.html соседнего проекта.
  const scoreA = $("prScoreA").value === "" ? null : Number.parseInt($("prScoreA").value, 10);
  const scoreB = $("prScoreB").value === "" ? null : Number.parseInt($("prScoreB").value, 10);
  const mism = $("prMismatch");
  const msgs = [];
  if (scoreA != null && scoreA !== counts.a) {
    msgs.push(`${p.teamAName}: в таймлайне ${counts.a} гол(ов), в табло ${scoreA}`);
  }
  if (scoreB != null && scoreB !== counts.b) {
    msgs.push(`${p.teamBName}: в таймлайне ${counts.b} гол(ов), в табло ${scoreB}`);
  }
  if (problems) msgs.push(`Не распознано номеров: ${problems} (номер должен быть у игрока, отмеченного «играл»)`);
  mism.textContent = msgs.join(". ");
  show(mism, msgs.length > 0);

  renderGoalieHints();
}

/** Вратарские ПШ/ОБ — считаются из табло, поэтому только показываем. */
function renderGoalieHints() {
  const p = state.protocol;
  const scoreA = $("prScoreA").value === "" ? null : Number.parseInt($("prScoreA").value, 10);
  const scoreB = $("prScoreB").value === "" ? null : Number.parseInt($("prScoreB").value, 10);
  const shotsA = $("prShotsA").value === "" ? null : Number.parseInt($("prShotsA").value, 10);
  const shotsB = $("prShotsB").value === "" ? null : Number.parseInt($("prShotsB").value, 10);

  for (const side of ["a", "b"]) {
    const el = side === "a" ? $("prGoalieA") : $("prGoalieB");
    const goalies = [...playedMap(side)].filter(([, i]) => i.isGoalie);
    // Пропущено = голы соперника, отражено = броски соперника − его голы.
    const oppScore = side === "a" ? scoreB : scoreA;
    const oppShots = side === "a" ? shotsB : shotsA;

    if (!goalies.length) {
      el.textContent = "Вратарь не отмечен — вратарская статистика за этот матч не начислится.";
      show(el, true);
      continue;
    }
    if (goalies.length > 1) {
      el.textContent =
        "Отмечено больше одного вратаря. Броски и голы в табло относятся к команде целиком, " +
        "поэтому распределить их между вратарями нельзя — матч не войдёт в их ПШ/ОБ.";
      show(el, true);
      continue;
    }
    if (oppScore == null) {
      el.textContent = "Заполните голы в табло, чтобы увидеть вратарскую статистику.";
      show(el, true);
      continue;
    }
    const saves = oppShots == null ? null : Math.max(oppShots - oppScore, 0);
    const name = goalies[0][1].name;
    el.textContent =
      `${name}: пропущено ${oppScore}` +
      (saves == null ? ", отражено — заполните броски соперника" : `, отражено ${saves}`);
    show(el, true);
  }
}

async function openProtocol(gameId) {
  const data = await apiFetch(`/games/${gameId}/protocol`);
  const g = data.game;
  state.protocol = {
    gameId,
    teamAId: g.team_a.id,
    teamBId: g.team_b.id,
    teamAName: g.team_a.name,
    teamBName: g.team_b.name,
  };

  $("protocolTitle").textContent = `МАТЧ № ${g.position} · ${g.team_a.name} — ${g.team_b.name} · ${fmtDate(g.date)}`;
  $("protocolRegulation").textContent =
    data.period_minutes && data.periods_count
      ? `Регламент: ${data.periods_count} × ${data.period_minutes} мин`
      : "Регламент турнира не задан";
  $("prTeamAName").textContent = g.team_a.name;
  $("prTeamBName").textContent = g.team_b.name;
  $("prLabelGoalsA").textContent = `Голы — ${g.team_a.name}`;
  $("prLabelGoalsB").textContent = `Голы — ${g.team_b.name}`;
  $("prLabelShotsA").textContent = `Броски — ${g.team_a.name}`;
  $("prLabelShotsB").textContent = `Броски — ${g.team_b.name}`;
  $("prScoreA").value = g.score_a ?? "";
  $("prScoreB").value = g.score_b ?? "";
  $("prShotsA").value = g.shots_a ?? "";
  $("prShotsB").value = g.shots_b ?? "";

  renderLineup("a", g.team_a.id, data.stat_lines.filter((l) => l.team_id === g.team_a.id));
  renderLineup("b", g.team_b.id, data.stat_lines.filter((l) => l.team_id === g.team_b.id));
  renderGoals("a", data.events.filter((e) => e.team_id === g.team_a.id));
  renderGoals("b", data.events.filter((e) => e.team_id === g.team_b.id));

  $("protocolMsg").textContent = "";
  show($("protocolMsg"), false);
  show($("protocolModal"), true);
  $("protocolModal").setAttribute("aria-hidden", "false");
  refreshDerived();
}

function closeProtocol() {
  show($("protocolModal"), false);
  $("protocolModal").setAttribute("aria-hidden", "true");
  state.protocol = null;
}

async function saveProtocol() {
  const p = state.protocol;
  if (!p) return;
  const msg = $("protocolMsg");
  msg.textContent = "";
  show(msg, false);

  const stat_lines = [];
  for (const [side, teamId] of [["a", p.teamAId], ["b", p.teamBId]]) {
    for (const [pid, info] of playedMap(side)) {
      stat_lines.push({ player_id: pid, team_id: teamId, is_goalie: info.isGoalie });
    }
  }

  const events = [];
  for (const [side, teamId] of [["a", p.teamAId], ["b", p.teamBId]]) {
    for (const row of readGoals(side)) {
      if (row.empty) continue;
      if (!row.scorerId) {
        msg.textContent = `Гол с временем ${row.time || "—"}: номер автора ${row.scorerNum || "—"} не найден среди отмеченных «играл».`;
        show(msg, true);
        return;
      }
      if (!row.time) {
        msg.textContent = `Гол игрока №${row.scorerNum}: не заполнено время.`;
        show(msg, true);
        return;
      }
      if (row.assistIds.some((x) => x === null)) {
        msg.textContent = `Гол игрока №${row.scorerNum}: номер в П(ПАС) не найден среди отмеченных «играл».`;
        show(msg, true);
        return;
      }
      if (row.assistIds.length > 2) {
        msg.textContent = `Гол игрока №${row.scorerNum}: в П(ПАС) не больше двух номеров.`;
        show(msg, true);
        return;
      }
      const ev = {
        team_id: teamId,
        period: row.period,
        time: row.time,
        player_id: row.scorerId,
      };
      if (row.assistIds[0]) ev.assist1_player_id = row.assistIds[0];
      if (row.assistIds[1]) ev.assist2_player_id = row.assistIds[1];
      events.push(ev);
    }
  }

  const intOrNull = (v) => (String(v).trim() === "" ? null : Number.parseInt(v, 10));
  const payload = {
    score_a: intOrNull($("prScoreA").value),
    score_b: intOrNull($("prScoreB").value),
    shots_a: intOrNull($("prShotsA").value),
    shots_b: intOrNull($("prShotsB").value),
    stat_lines,
    events,
  };

  try {
    await apiFetch(`/games/${p.gameId}/protocol`, { method: "PUT", body: JSON.stringify(payload) });
    closeProtocol();
    await Promise.all([loadGames(), loadStandings()]);
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
}

/* ------------------------------ обработчики ------------------------------ */

for (const id of ["prScoreA", "prScoreB", "prShotsA", "prShotsB"]) {
  $(id).addEventListener("input", refreshDerived);
}

document.querySelectorAll("[data-add-goal]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const side = btn.dataset.addGoal;
    const tbody = side === "a" ? $("prGoalsA") : $("prGoalsB");
    tbody.appendChild(goalRow(side, null));
    refreshDerived();
  });
});

$("protocolSaveBtn").addEventListener("click", saveProtocol);
$("protocolCancelBtn").addEventListener("click", () => {
  if (window.confirm("Закрыть протокол без сохранения изменений?")) closeProtocol();
});

$("rosterAddCancelBtn").addEventListener("click", closeRosterAddModal);

let _addSearchTimer = null;
$("rosterAddSearch").addEventListener("input", () => {
  clearTimeout(_addSearchTimer);
  _addSearchTimer = setTimeout(() => {
    renderRosterAddList().catch((err) => {
      $("rosterAddMsg").textContent = err.message;
      show($("rosterAddMsg"), true);
    });
  }, 300);
});

$("rosterAddSaveBtn").addEventListener("click", async () => {
  const msg = $("rosterAddMsg");
  msg.textContent = "";
  show(msg, false);
  const list = $("rosterAddList");
  const players = [];
  list.querySelectorAll("[data-player-id]").forEach((cb) => {
    if (!cb.checked) return;
    const pid = cb.dataset.playerId;
    const numEl = list.querySelector(`[data-number-for="${pid}"]`);
    const raw = numEl ? String(numEl.value).trim() : "";
    players.push({ player_id: pid, number: raw === "" ? null : Number.parseInt(raw, 10) });
  });
  if (!players.length) {
    msg.textContent = "Никто не отмечен.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch(`/tournaments/${TOURNAMENT_ID}/roster`, {
      method: "POST",
      body: JSON.stringify({ team_id: state.addTeamId, players }),
    });
    closeRosterAddModal();
    await loadRoster();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("refreshRosterBtn").addEventListener("click", () => loadRoster().catch((e) => fail("rosterError", e)));
$("refreshGamesBtn").addEventListener("click", () => loadGames().catch((e) => fail("gamesError", e)));
$("refreshStandingsBtn").addEventListener("click", () => loadStandings().catch((e) => fail("topError", e)));

function bindScanUpload({ btnId, fileId, urlId, msgId, onDone }) {
  $(btnId).addEventListener("click", () => $(fileId).click());
  $(fileId).addEventListener("change", async () => {
    const file = $(fileId).files && $(fileId).files[0];
    if (!file) return;
    const status = $(msgId);
    status.textContent = "Загрузка…";
    show(status, true);
    $(btnId).disabled = true;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await apiFetch("/uploads/game-scan", { method: "POST", body: fd });
      $(urlId).value = data.url;
      status.textContent = "Скан загружен. Не забудьте сохранить.";
      if (onDone) onDone();
    } catch (err) {
      status.textContent = "Ошибка загрузки: " + err.message;
    } finally {
      $(btnId).disabled = false;
      $(fileId).value = "";
    }
  });
}

bindScanUpload({
  btnId: "gcScanUploadBtn", fileId: "gcScanFile",
  urlId: "gcScan", msgId: "gcScanMsg",
});
bindScanUpload({
  btnId: "geScanUploadBtn", fileId: "geScanFile",
  urlId: "geScan", msgId: "geScanMsg", onDone: renderScanPreview,
});

$("geScan").addEventListener("input", renderScanPreview);
$("gameEditCancelBtn").addEventListener("click", () => {
  if (window.confirm("Закрыть без сохранения изменений?")) closeGameEditModal();
});

$("gameEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("gameEditMsg");
  msg.textContent = "";
  show(msg, false);
  const intOrNull = (v) => (String(v).trim() === "" ? null : Number.parseInt(v, 10));
  const teamA = $("geTeamA").value;
  const teamB = $("geTeamB").value;
  if (teamA === teamB) {
    msg.textContent = "Команда не может играть сама с собой.";
    show(msg, true);
    return;
  }
  const payload = {
    team_a_id: teamA,
    team_b_id: teamB,
    date: $("geDate").value,
    time: $("geTime").value || null,
    position: intOrNull($("gePosition").value),
    score_a: intOrNull($("geScoreA").value),
    score_b: intOrNull($("geScoreB").value),
    shots_a: intOrNull($("geShotsA").value),
    shots_b: intOrNull($("geShotsB").value),
    video_url: String($("geVideoUrl").value || "").trim() || null,
    scan: String($("geScan").value || "").trim() || null,
  };
  try {
    await apiFetch(`/games/${$("geId").value}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    closeGameEditModal();
    await Promise.all([loadGames(), loadStandings()]);
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("gameCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("gameCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const intOrNull = (v) => (String(v).trim() === "" ? null : Number.parseInt(v, 10));
  const teamA = $("gcTeamA").value;
  const teamB = $("gcTeamB").value;
  if (teamA === teamB) {
    msg.textContent = "Команда не может играть сама с собой.";
    show(msg, true);
    return;
  }
  const payload = {
    team_a_id: teamA,
    team_b_id: teamB,
    date: $("gcDate").value,
    time: $("gcTime").value || null,
    score_a: intOrNull($("gcScoreA").value),
    score_b: intOrNull($("gcScoreB").value),
    shots_a: intOrNull($("gcShotsA").value),
    shots_b: intOrNull($("gcShotsB").value),
    video_url: String($("gcVideoUrl").value || "").trim() || null,
    scan: String($("gcScan").value || "").trim() || null,
    position: intOrNull($("gcPosition").value),
  };
  try {
    await apiFetch(`/tournaments/${TOURNAMENT_ID}/games`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("gameCreateForm").reset();
    show($("gcScanMsg"), false);
    renderTeamSelects();
    msg.textContent = "Матч добавлен.";
    show(msg, true);
    await Promise.all([loadGames(), loadStandings()]);
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

/* --------------------------------- запуск --------------------------------- */

(async function boot() {
  if (!TOURNAMENT_ID) {
    show($("authError"), true);
    $("authError").querySelector("h1").textContent = "Турнир не указан";
    return;
  }
  if (!localStorage.getItem(TOKEN_KEY)) {
    show($("authError"), true);
    return;
  }
  try {
    await loadTournament();
    show($("content"), true);
    renderTeamSelects();
    $("gcDate").value = state.tournament.start_date;
    await loadRoster();
    await Promise.all([loadGames(), loadStandings()]);
  } catch (err) {
    show($("content"), true);
    fail("topError", err);
  }
})();
