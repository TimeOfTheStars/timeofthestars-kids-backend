const API = "/api/admin";
const TOKEN_KEY = "admin_jwt";

const $ = (id) => document.getElementById(id);

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(t) {
  if (!t) localStorage.removeItem(TOKEN_KEY);
  else localStorage.setItem(TOKEN_KEY, t);
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function apiFetch(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  // FormData сам выставит Content-Type с boundary — не трогаем.
  if (opts.body && typeof opts.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  Object.assign(headers, authHeaders());
  const res = await fetch(`${API}${path}`, { ...opts, headers });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }
  if (!res.ok) {
    const msg = data?.detail ? (Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : String(data.detail)) : res.statusText;
    throw new Error(msg || "Ошибка запроса");
  }
  return data;
}

function show(el, on) {
  el.classList.toggle("hidden", !on);
}

function isAdmin() {
  return window.__myRole === "admin";
}

function setTab(name) {
  if (name === "users" && !isAdmin()) return;
  window.__activeTab = name;
  document.querySelectorAll(".nav-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    show(p, p.id === `tab-${name}`);
  });
  if (name === "appointments") loadAppointments();
  if (name === "services") loadServiceRequests();
  if (name === "questions") loadQuestions();
  if (name === "reviews") loadReviews();
  if (name === "news") loadNews();
  if (name === "teams") loadTeams();
  if (name === "players") loadPlayers();
  if (name === "arenas") loadArenas();
  if (name === "tournaments") loadTournaments();
  if (name === "tournament-apps") loadTournamentApps();
  if (name === "profile") loadMe();
  if (name === "users") loadAdmins();
}

function requestModalClose(closeFn) {
  if (window.confirm("Закрыть окно без сохранения изменений?")) closeFn();
}

async function confirmAndDelete({ question, request, onDone, errorTargetId }) {
  if (!window.confirm(question)) return;
  try {
    await request();
    if (onDone) await onDone();
  } catch (err) {
    const target = $(errorTargetId);
    if (target) {
      target.textContent = err.message;
      show(target, true);
    }
  }
}

function makeDeleteButton(onClick) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn danger btn-small";
  btn.textContent = "Удалить";
  btn.addEventListener("click", onClick);
  return btn;
}

async function loadMe() {
  const me = await apiFetch("/me");
  window.__myRole = me.role;
  const roleLabel = me.role === "admin" ? "admin" : "viewer";
  $("whoami").textContent = `${me.username} · ${roleLabel}`;
  document.querySelectorAll(".nav-tab-admin-only").forEach((el) => {
    show(el, me.role === "admin");
  });
  const inp = $("vkUserIdInput");
  if (inp) inp.value = me.vk_user_id != null ? String(me.vk_user_id) : "";
}

async function loadAppointments() {
  $("listError").textContent = "";
  show($("listError"), false);
  const rows = $("rows");
  rows.innerHTML = "";
  const data = await apiFetch("/appointments?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="6" class="muted">Пока нет заявок</td></tr>`;
    return;
  }
  for (const a of data) {
    const tr = document.createElement("tr");
    const dt = new Date(a.created_at);
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="Телефон">${escapeHtml(a.phone)}</td>
      <td data-label="Родитель">${escapeHtml(a.parent_name)}</td>
      <td data-label="Ребёнок">${escapeHtml(a.child_name)}</td>
      <td data-label="Возраст">${escapeHtml(String(a.child_age))}</td>
    `;
    const tdAction = document.createElement("td");
    tdAction.setAttribute("data-label", "Действие");
    tdAction.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить эту заявку?",
          request: () => apiFetch(`/appointments/${a.id}`, { method: "DELETE" }),
          onDone: loadAppointments,
          errorTargetId: "listError",
        }),
      ),
    );
    tr.appendChild(tdAction);
    rows.appendChild(tr);
  }
}

async function loadServiceRequests() {
  $("svcError").textContent = "";
  show($("svcError"), false);
  const rows = $("svcRows");
  rows.innerHTML = "";
  const data = await apiFetch("/service-requests?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="7" class="muted">Пока нет заявок на услуги</td></tr>`;
    return;
  }
  for (const s of data) {
    const tr = document.createElement("tr");
    const dt = new Date(s.created_at);
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="Услуга">${escapeHtml(s.service)}</td>
      <td data-label="Телефон">${escapeHtml(s.phone)}</td>
      <td data-label="Родитель">${escapeHtml(s.parent_name)}</td>
      <td data-label="Ребёнок">${escapeHtml(s.child_name)}</td>
      <td data-label="Возраст">${escapeHtml(String(s.child_age))}</td>
    `;
    const tdAction = document.createElement("td");
    tdAction.setAttribute("data-label", "Действие");
    tdAction.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить эту заявку на услугу?",
          request: () => apiFetch(`/service-requests/${s.id}`, { method: "DELETE" }),
          onDone: loadServiceRequests,
          errorTargetId: "svcError",
        }),
      ),
    );
    tr.appendChild(tdAction);
    rows.appendChild(tr);
  }
}

async function loadQuestions() {
  $("qError").textContent = "";
  show($("qError"), false);
  const rows = $("qRows");
  rows.innerHTML = "";
  const data = await apiFetch("/questions?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="5" class="muted">Пока нет вопросов</td></tr>`;
    return;
  }
  for (const q of data) {
    const tr = document.createElement("tr");
    const dt = new Date(q.created_at);
    const questionText = q.question ? String(q.question) : "";
    const questionCell = questionText
      ? escapeHtml(questionText.length > 300 ? questionText.slice(0, 300) + "…" : questionText)
      : '<span class="muted">—</span>';
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="ФИО">${escapeHtml(q.full_name)}</td>
      <td data-label="Контакт">${escapeHtml(q.contact)}</td>
      <td data-label="Вопрос">${questionCell}</td>
    `;
    const tdAction = document.createElement("td");
    tdAction.setAttribute("data-label", "Действие");
    tdAction.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить этот вопрос?",
          request: () => apiFetch(`/questions/${q.id}`, { method: "DELETE" }),
          onDone: loadQuestions,
          errorTargetId: "qError",
        }),
      ),
    );
    tr.appendChild(tdAction);
    rows.appendChild(tr);
  }
}

async function loadAdmins() {
  $("adminsListError").textContent = "";
  show($("adminsListError"), false);
  const rows = $("adminRows");
  rows.innerHTML = "";
  const data = await apiFetch("/admins?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="6" class="muted">Нет записей</td></tr>`;
    return;
  }
  for (const u of data) {
    const tr = document.createElement("tr");
    const dt = new Date(u.created_at);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = "Изменить";
    btn.addEventListener("click", () => openEditModal(u));
    const tdAct = document.createElement("td");
    tdAct.appendChild(btn);
    tr.innerHTML = `
      <td>${escapeHtml(u.username)}</td>
      <td>${escapeHtml(u.role)}</td>
      <td>${u.vk_user_id != null ? escapeHtml(String(u.vk_user_id)) : "—"}</td>
      <td>${u.is_active ? "да" : "нет"}</td>
      <td>${dt.toLocaleString()}</td>
    `;
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

async function loadReviews() {
  $("reviewsError").textContent = "";
  show($("reviewsError"), false);
  const rows = $("reviewRows");
  rows.innerHTML = "";
  const data = await apiFetch("/reviews?limit=500");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="7" class="muted">Пока нет отзывов</td></tr>`;
    return;
  }
  for (const r of data) {
    const tr = document.createElement("tr");
    const photoCell = r.author_photo_url
      ? `<img src="${escapeHtml(r.author_photo_url)}" alt="" class="review-avatar" />`
      : '<span class="muted">—</span>';
    const preview = r.text.length > 200 ? r.text.slice(0, 200) + "…" : r.text;
    tr.innerHTML = `
      <td data-label="Фото">${photoCell}</td>
      <td data-label="Автор">${escapeHtml(r.author_name)}</td>
      <td data-label="Текст" class="review-text">${escapeHtml(preview)}</td>
      <td data-label="Поз.">${escapeHtml(String(r.position))}</td>
      <td data-label="Видим">${r.is_visible ? "да" : "нет"}</td>
      <td data-label="VK id">${r.vk_comment_id != null ? escapeHtml(String(r.vk_comment_id)) : "—"}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openReviewEditModal(r));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить этот отзыв?",
          request: () => apiFetch(`/reviews/${r.id}`, { method: "DELETE" }),
          onDone: loadReviews,
          errorTargetId: "reviewsError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function openReviewEditModal(r) {
  $("reUserId").value = r.id;
  $("reAuthor").value = r.author_name;
  $("rePhoto").value = r.author_photo_url || "";
  $("reText").value = r.text;
  $("rePosition").value = String(r.position);
  $("reVisible").checked = !!r.is_visible;
  $("reviewEditMsg").textContent = "";
  show($("reviewEditMsg"), false);
  show($("reviewEditModal"), true);
  $("reviewEditModal").setAttribute("aria-hidden", "false");
}

function closeReviewEditModal() {
  show($("reviewEditModal"), false);
  $("reviewEditModal").setAttribute("aria-hidden", "true");
}

async function loadNews() {
  $("newsError").textContent = "";
  show($("newsError"), false);
  const rows = $("newsRows");
  rows.innerHTML = "";
  const data = await apiFetch("/news?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="6" class="muted">Пока нет новостей</td></tr>`;
    return;
  }
  for (const n of data) {
    const tr = document.createElement("tr");
    const imgCell = n.image
      ? `<img src="${escapeHtml(n.image)}" alt="" class="news-thumb" />`
      : '<span class="muted">—</span>';
    const preview = n.excerpt.length > 220 ? n.excerpt.slice(0, 220) + "…" : n.excerpt;
    const safeUrl = escapeHtml(n.url);
    tr.innerHTML = `
      <td data-label="Картинка">${imgCell}</td>
      <td data-label="Текст" class="review-text">${escapeHtml(preview)}</td>
      <td data-label="Поз.">${escapeHtml(String(n.position))}</td>
      <td data-label="Видим">${n.is_visible ? "да" : "нет"}</td>
      <td data-label="Ссылка"><a href="${safeUrl}" target="_blank" rel="noopener noreferrer">VK ${n.vk_owner_id}_${n.vk_post_id}</a></td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openNewsEditModal(n));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить эту новость?",
          request: () => apiFetch(`/news/${n.id}`, { method: "DELETE" }),
          onDone: loadNews,
          errorTargetId: "newsError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function openNewsEditModal(n) {
  $("neId").value = n.id;
  $("neUrl").value = n.url;
  $("neImage").value = n.image || "";
  $("neExcerpt").value = n.excerpt || "";
  $("nePosition").value = String(n.position);
  $("neVisible").checked = !!n.is_visible;
  $("newsEditMsg").textContent = "";
  show($("newsEditMsg"), false);
  show($("newsEditModal"), true);
  $("newsEditModal").setAttribute("aria-hidden", "false");
}

function closeNewsEditModal() {
  show($("newsEditModal"), false);
  $("newsEditModal").setAttribute("aria-hidden", "true");
}

// SVG/GIF не трогаем: первое — векторное, второе — теряет анимацию при canvas-перерисовке.
const _UNCOMPRESSIBLE_TYPES = new Set(["image/svg+xml", "image/gif"]);

function _loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}

async function compressImage(file, { maxDim = 1920, quality = 0.85 } = {}) {
  if (!file.type.startsWith("image/")) return file;
  if (_UNCOMPRESSIBLE_TYPES.has(file.type)) return file;

  let img;
  try {
    img = await _loadImage(file);
  } catch {
    return file;
  }

  const ratio = Math.min(maxDim / img.width, maxDim / img.height, 1);
  // Маленькие лёгкие файлы не пережимаем (< 256 KB и в пределах maxDim).
  if (ratio === 1 && file.size < 256 * 1024) return file;

  const width = Math.round(img.width * ratio);
  const height = Math.round(img.height * ratio);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0, width, height);

  // PNG с прозрачностью сохраняем как PNG (toBlob с image/png игнорирует quality),
  // остальное — в JPEG для максимального сжатия.
  const outputType = file.type === "image/png" ? "image/png" : "image/jpeg";
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, outputType, quality));
  if (!blob || blob.size >= file.size) return file;

  // Имя сохраняем — серверу важно только content-type.
  return new File([blob], file.name, { type: outputType, lastModified: Date.now() });
}

async function uploadTeamLogo(file) {
  const compressed = await compressImage(file, { maxDim: 512, quality: 0.9 });
  const fd = new FormData();
  fd.append("file", compressed);
  const data = await apiFetch("/uploads/team-logo", { method: "POST", body: fd });
  return data.url;
}

async function uploadPlayerPhoto(file) {
  const compressed = await compressImage(file, { maxDim: 800, quality: 0.9 });
  const fd = new FormData();
  fd.append("file", compressed);
  const data = await apiFetch("/uploads/player-photo", { method: "POST", body: fd });
  return data.url;
}

function bindLogoUpload({ urlInputId, fileInputId, buttonId, statusId, uploader = uploadTeamLogo, okText = "Логотип загружен." }) {
  const fileInput = $(fileInputId);
  const urlInput = $(urlInputId);
  const btn = $(buttonId);
  const statusEl = statusId ? $(statusId) : null;
  if (!fileInput || !urlInput || !btn) return;
  btn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (statusEl) {
      statusEl.textContent = "Загрузка…";
      statusEl.classList.remove("hidden");
    }
    btn.disabled = true;
    try {
      const url = await uploader(file);
      urlInput.value = url;
      if (statusEl) statusEl.textContent = okText;
    } catch (err) {
      if (statusEl) statusEl.textContent = "Ошибка загрузки: " + err.message;
    } finally {
      btn.disabled = false;
      fileInput.value = "";
    }
  });
}

// ---------- Teams ----------

window.__teamsCache = [];

function teamLabel(team) {
  // Для пикера в турнире: показываем описание, если задано, иначе название,
  // и добавляем город — без него одноимённые команды не различить.
  if (!team) return "";
  const desc = team.description ? String(team.description).trim() : "";
  const base = desc || team.name;
  const city = team.city ? String(team.city).trim() : "";
  return city ? `${base} (${city})` : base;
}

async function loadTeams() {
  $("teamsError").textContent = "";
  show($("teamsError"), false);
  const rows = $("teamRows");
  rows.innerHTML = "";
  const data = await apiFetch("/teams?limit=500");
  window.__teamsCache = data;
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="12" class="muted">Команд пока нет</td></tr>`;
    return;
  }
  for (const t of data) {
    const tr = document.createElement("tr");
    const logoCell = t.logo
      ? `<img src="${escapeHtml(t.logo)}" alt="" class="team-logo" />`
      : '<span class="muted">—</span>';
    const descRaw = t.description ? String(t.description) : "";
    const descPreview = descRaw.length > 140 ? descRaw.slice(0, 140) + "…" : descRaw;
    const descCell = descPreview ? escapeHtml(descPreview) : '<span class="muted">—</span>';
    // Звёздочка = значение вписано руками и не пересчитывается по матчам.
    const manual = new Set(t.manual_fields || []);
    const stat = (field) => {
      const v = t.stats ? t.stats[field] : 0;
      return manual.has(field)
        ? `<span title="Вписано руками, расчёт: ${t.computed ? t.computed[field] : 0}"><b>${v}</b>*</span>`
        : String(v);
    };
    tr.innerHTML = `
      <td data-label="Лого">${logoCell}</td>
      <td data-label="Название">${escapeHtml(t.name)}</td>
      <td data-label="Город">${t.city ? escapeHtml(t.city) : '<span class="muted">—</span>'}</td>
      <td data-label="Т">${stat("tournaments")}</td>
      <td data-label="И">${stat("games")}</td>
      <td data-label="В">${stat("wins")}</td>
      <td data-label="Н">${stat("draws")}</td>
      <td data-label="П">${stat("losses")}</td>
      <td data-label="Заб">${stat("goals_for")}</td>
      <td data-label="Проп">${stat("goals_against")}</td>
      <td data-label="О">${t.stats ? t.stats.points : 0}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openTeamEditModal(t));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: `Удалить команду «${t.name}»? Из турниров она тоже исчезнет.`,
          request: () => apiFetch(`/teams/${t.id}`, { method: "DELETE" }),
          onDone: async () => {
            await loadTeams();
            if (window.__activeTab === "tournaments") await loadTournaments();
          },
          errorTargetId: "teamsError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function openTeamEditModal(t) {
  $("teId").value = t.id;
  $("teName").value = t.name;
  $("teCity").value = t.city || "";
  $("teLogo").value = t.logo || "";
  $("teDescription").value = t.description || "";
  // Пустое поле = «считать автоматически», поэтому в placeholder кладём расчёт.
  // Сырые manual_* в ответе не приходят, но они и не нужны: если поле помечено
  // ручным, его вписанное значение и есть действующее в stats.
  const manualSet = new Set(t.manual_fields || []);
  for (const [field, inputId] of Object.entries(TEAM_STAT_INPUTS)) {
    const el = $(inputId);
    el.value = manualSet.has(field) ? String(t.stats[field]) : "";
    el.placeholder = `по матчам: ${t.computed ? t.computed[field] : 0}`;
  }
  const c = t.computed || {};
  $("teStatsHint").textContent =
    `По матчам: турниров ${c.tournaments ?? 0}, игр ${c.games ?? 0}, ` +
    `${c.wins ?? 0}-${c.draws ?? 0}-${c.losses ?? 0}, ` +
    `шайбы ${c.goals_for ?? 0}-${c.goals_against ?? 0}, очки ${c.points ?? 0}.`;
  $("teamEditMsg").textContent = "";
  show($("teamEditMsg"), false);
  show($("teamEditModal"), true);
  $("teamEditModal").setAttribute("aria-hidden", "false");
}

function closeTeamEditModal() {
  show($("teamEditModal"), false);
  $("teamEditModal").setAttribute("aria-hidden", "true");
}

// Поле статистики команды → id инпута в модалке правки.
const TEAM_STAT_INPUTS = {
  tournaments: "teManualTournaments",
  games: "teManualGames",
  wins: "teManualWins",
  draws: "teManualDraws",
  losses: "teManualLosses",
  goals_for: "teManualGoalsFor",
  goals_against: "teManualGoalsAgainst",
};

// ---------- Players ----------

window.__playersCache = [];

const POSITION_LABELS = { "вратарь": "вратарь", "защитник": "защитник", "нападающий": "нападающий" };

async function loadPlayers() {
  $("playersError").textContent = "";
  show($("playersError"), false);
  const rows = $("playerRows");
  rows.innerHTML = "";
  const q = String($("playerSearch").value || "").trim();
  const path = q ? `/players?limit=500&search=${encodeURIComponent(q)}` : "/players?limit=500";
  const data = await apiFetch(path);
  window.__playersCache = data;
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="5" class="muted">${q ? "Ничего не найдено" : "Игроков пока нет"}</td></tr>`;
    return;
  }
  for (const pl of data) {
    const tr = document.createElement("tr");
    const photoCell = pl.photo
      ? `<img src="${escapeHtml(pl.photo)}" alt="" class="team-logo" />`
      : '<span class="muted">—</span>';
    tr.innerHTML = `
      <td data-label="Фото">${photoCell}</td>
      <td data-label="ФИО">${escapeHtml(pl.full_name)}</td>
      <td data-label="Дата рождения">${pl.birth_date ? escapeHtml(fmtDate(pl.birth_date)) : '<span class="muted">—</span>'}</td>
      <td data-label="Амплуа">${pl.position ? escapeHtml(POSITION_LABELS[pl.position] || pl.position) : '<span class="muted">—</span>'}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openPlayerEditModal(pl));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: `Удалить игрока «${pl.full_name}»? Вся его статистика по всем турнирам тоже исчезнет.`,
          request: () => apiFetch(`/players/${pl.id}`, { method: "DELETE" }),
          onDone: loadPlayers,
          errorTargetId: "playersError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function openPlayerEditModal(pl) {
  $("peId").value = pl.id;
  $("peName").value = pl.full_name;
  $("peBirthDate").value = pl.birth_date || "";
  $("pePosition").value = pl.position || "";
  $("pePhoto").value = pl.photo || "";
  $("playerEditMsg").textContent = "";
  show($("playerEditMsg"), false);
  show($("playerEditModal"), true);
  $("playerEditModal").setAttribute("aria-hidden", "false");
}

function closePlayerEditModal() {
  show($("playerEditModal"), false);
  $("playerEditModal").setAttribute("aria-hidden", "true");
}

// ---------- Arenas ----------

window.__arenasCache = [];

async function loadArenas() {
  $("arenasError").textContent = "";
  show($("arenasError"), false);
  const rows = $("arenaRows");
  rows.innerHTML = "";
  const data = await apiFetch("/arenas?limit=500");
  window.__arenasCache = data;
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="5" class="muted">Арен пока нет</td></tr>`;
    return;
  }
  for (const a of data) {
    const tr = document.createElement("tr");
    const mapCell = a.url
      ? `<a href="${escapeHtml(a.url)}" target="_blank" rel="noopener">открыть</a>`
      : '<span class="muted">—</span>';
    tr.innerHTML = `
      <td data-label="Название">${escapeHtml(a.name)}</td>
      <td data-label="Город">${a.city ? escapeHtml(a.city) : '<span class="muted">—</span>'}</td>
      <td data-label="Адрес">${a.address ? escapeHtml(a.address) : '<span class="muted">—</span>'}</td>
      <td data-label="Карта">${mapCell}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openArenaEditModal(a));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: `Удалить арену «${a.name}»? Не получится, если она используется в турнирах.`,
          request: () => apiFetch(`/arenas/${a.id}`, { method: "DELETE" }),
          onDone: loadArenas,
          errorTargetId: "arenasError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function openArenaEditModal(a) {
  $("aeId").value = a.id;
  $("aeName").value = a.name;
  $("aeUrl").value = a.url || "";
  $("aeAddress").value = a.address || "";
  $("aeCity").value = a.city || "";
  $("arenaEditMsg").textContent = "";
  show($("arenaEditMsg"), false);
  show($("arenaEditModal"), true);
  $("arenaEditModal").setAttribute("aria-hidden", "false");
}

function closeArenaEditModal() {
  show($("arenaEditModal"), false);
  $("arenaEditModal").setAttribute("aria-hidden", "true");
}

function renderArenaSelect(selectedId) {
  const sel = $("toArenaId");
  if (!sel) return;
  sel.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = (window.__arenasCache || []).length
    ? "Выберите арену…"
    : "(нет арен — создайте на вкладке «Арены»)";
  sel.appendChild(placeholder);
  for (const a of window.__arenasCache || []) {
    const opt = document.createElement("option");
    opt.value = a.id;
    const cityHint = a.city ? ` · ${a.city}` : "";
    opt.textContent = `${a.name}${cityHint}`;
    if (selectedId && a.id === selectedId) opt.selected = true;
    sel.appendChild(opt);
  }
}

// ---------- Tournaments ----------

window.__editingTeams = []; // [{team_id, photo}] — порядок + per-tournament фото

async function uploadTeamPhoto(file) {
  const compressed = await compressImage(file, { maxDim: 1920, quality: 0.85 });
  const fd = new FormData();
  fd.append("file", compressed);
  const data = await apiFetch("/uploads/team-photo", { method: "POST", body: fd });
  return data.url;
}

function fmtDate(iso) {
  if (!iso) return "";
  return iso; // YYYY-MM-DD уже читаемо
}

async function loadTournaments() {
  $("tournamentsError").textContent = "";
  show($("tournamentsError"), false);
  const rows = $("tournamentRows");
  rows.innerHTML = "";
  // Команды и арены нужны для модалки — подтянем их параллельно
  const [tournaments, teams, arenas] = await Promise.all([
    apiFetch("/tournaments?limit=200"),
    apiFetch("/teams?limit=500"),
    apiFetch("/arenas?limit=500"),
  ]);
  window.__teamsCache = teams;
  window.__arenasCache = arenas;
  if (!tournaments.length) {
    rows.innerHTML = `<tr><td colspan="7" class="muted">Турниров пока нет</td></tr>`;
    return;
  }
  for (const t of tournaments) {
    const tr = document.createElement("tr");
    const startT = t.start_time ? String(t.start_time).slice(0, 5) : "";
    const endT = t.end_time ? String(t.end_time).slice(0, 5) : "";
    let timeSuffix = "";
    if (startT && endT) timeSuffix = ` · ${startT}–${endT}`;
    else if (startT) timeSuffix = ` · ${startT}`;
    else if (endT) timeSuffix = ` · до ${endT}`;
    const dates = `${fmtDate(t.start_date)} — ${fmtDate(t.end_date)}${timeSuffix}`;
    const arenaName = t.arena && t.arena.name ? t.arena.name : "";
    const arenaCell = t.arena && t.arena.url
      ? `<a href="${escapeHtml(t.arena.url)}" target="_blank" rel="noopener">${escapeHtml(arenaName)}</a>`
      : escapeHtml(arenaName);
    tr.innerHTML = `
      <td data-label="Название">${escapeHtml(t.title)}</td>
      <td data-label="Категория">${escapeHtml(t.age_category)}${t.birth_year ? ` · ${t.birth_year}` : ""}</td>
      <td data-label="Даты">${escapeHtml(dates)}</td>
      <td data-label="Арена">${arenaCell}</td>
      <td data-label="Команд">${(t.teams || []).length}</td>
      <td data-label="Видим">${t.is_visible ? "да" : "нет"}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    const statsLink = document.createElement("a");
    statsLink.className = "btn";
    statsLink.href = `/admin/tournament.html?id=${encodeURIComponent(t.id)}`;
    statsLink.textContent = "Статистика";
    tdAct.appendChild(statsLink);
    tdAct.appendChild(document.createTextNode(" "));
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn";
    editBtn.textContent = "Изменить";
    editBtn.addEventListener("click", () => openTournamentEditModal(t));
    tdAct.appendChild(editBtn);
    tdAct.appendChild(document.createTextNode(" "));
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: `Удалить турнир «${t.title}»?`,
          request: () => apiFetch(`/tournaments/${t.id}`, { method: "DELETE" }),
          onDone: loadTournaments,
          errorTargetId: "tournamentsError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

function renderTeamPicker() {
  const sel = $("toTeamSelect");
  sel.innerHTML = "";
  const chosen = new Set(window.__editingTeams.map((x) => x.team_id));
  const available = (window.__teamsCache || []).filter((t) => !chosen.has(t.id));
  if (!available.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(все команды уже добавлены)";
    opt.disabled = true;
    sel.appendChild(opt);
  } else {
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Выберите команду…";
    sel.appendChild(placeholder);
    for (const t of available) {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = teamLabel(t);
      sel.appendChild(opt);
    }
  }

  const list = $("toTeamList");
  list.innerHTML = "";
  for (let i = 0; i < window.__editingTeams.length; i++) {
    const entry = window.__editingTeams[i];
    const team = (window.__teamsCache || []).find((x) => x.id === entry.team_id);
    const li = document.createElement("li");
    li.className = "team-list-item";

    const head = document.createElement("div");
    head.className = "team-list-head";
    const label = document.createElement("span");
    label.textContent = team ? teamLabel(team) : `(удалена) ${entry.team_id}`;
    head.appendChild(label);

    const actions = document.createElement("span");
    actions.className = "team-list-actions";
    const up = document.createElement("button");
    up.type = "button";
    up.className = "btn btn-small";
    up.textContent = "↑";
    up.disabled = i === 0;
    up.addEventListener("click", () => {
      [window.__editingTeams[i - 1], window.__editingTeams[i]] = [window.__editingTeams[i], window.__editingTeams[i - 1]];
      renderTeamPicker();
    });
    const down = document.createElement("button");
    down.type = "button";
    down.className = "btn btn-small";
    down.textContent = "↓";
    down.disabled = i === window.__editingTeams.length - 1;
    down.addEventListener("click", () => {
      [window.__editingTeams[i + 1], window.__editingTeams[i]] = [window.__editingTeams[i], window.__editingTeams[i + 1]];
      renderTeamPicker();
    });
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "btn btn-small danger";
    rm.textContent = "×";
    rm.addEventListener("click", () => {
      window.__editingTeams.splice(i, 1);
      renderTeamPicker();
    });
    actions.appendChild(up);
    actions.appendChild(down);
    actions.appendChild(rm);
    head.appendChild(actions);

    // Превью + кнопки в одну компактную строку. Размер зашит инлайн —
    // на случай, если у клиента закэширована старая styles.css.
    const photoRow = document.createElement("div");
    photoRow.className = "row gap team-photo-row";

    const thumbBox = document.createElement("div");
    thumbBox.className = "team-photo-thumb";
    thumbBox.style.cssText =
      "width:40px;height:40px;flex:0 0 40px;border-radius:6px;overflow:hidden;background:var(--border);display:flex;align-items:center;justify-content:center;font-size:0.75rem;color:var(--muted);";
    if (entry.photo) {
      const thumb = document.createElement("img");
      thumb.alt = "";
      thumb.src = entry.photo;
      thumb.style.cssText = "width:100%;height:100%;object-fit:cover;display:block;cursor:pointer;";
      thumb.title = "Открыть в полный размер";
      thumb.addEventListener("click", () => window.open(entry.photo, "_blank", "noopener"));
      thumbBox.appendChild(thumb);
    } else {
      thumbBox.textContent = "—";
    }

    const uploadBtn = document.createElement("button");
    uploadBtn.type = "button";
    uploadBtn.className = "btn btn-small";
    uploadBtn.textContent = entry.photo ? "Заменить" : "Загрузить";
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/*";
    fileInput.hidden = true;
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      uploadBtn.disabled = true;
      uploadBtn.textContent = "…";
      try {
        const url = await uploadTeamPhoto(file);
        window.__editingTeams[i].photo = url;
        renderTeamPicker();
      } catch (err) {
        uploadBtn.disabled = false;
        uploadBtn.textContent = "Загрузить";
        window.alert("Ошибка загрузки: " + err.message);
      } finally {
        fileInput.value = "";
      }
    });
    uploadBtn.addEventListener("click", () => fileInput.click());

    const clearBtn = document.createElement("button");
    clearBtn.type = "button";
    clearBtn.className = "btn btn-small danger";
    clearBtn.textContent = "×";
    clearBtn.title = "Убрать фото";
    clearBtn.disabled = !entry.photo;
    clearBtn.addEventListener("click", () => {
      window.__editingTeams[i].photo = null;
      renderTeamPicker();
    });

    photoRow.appendChild(thumbBox);
    photoRow.appendChild(uploadBtn);
    photoRow.appendChild(clearBtn);
    photoRow.appendChild(fileInput);

    li.appendChild(head);
    li.appendChild(photoRow);
    list.appendChild(li);
  }
}

function openTournamentEditModal(t) {
  $("toId").value = t ? t.id : "";
  $("tournamentEditTitle").textContent = t ? "Редактировать турнир" : "Новый турнир";
  $("toTitle").value = t ? t.title : "";
  $("toAge").value = t ? t.age_category : "";
  $("toBirthYear").value = t && t.birth_year ? t.birth_year : "";
  $("toStart").value = t ? t.start_date : "";
  $("toEnd").value = t ? t.end_date : "";
  // start_time/end_time приходят как "HH:MM" из API — input type=time принимает as-is.
  $("toStartTime").value = t && t.start_time ? t.start_time.slice(0, 5) : "";
  $("toEndTime").value = t && t.end_time ? t.end_time.slice(0, 5) : "";
  renderArenaSelect(t && t.arena ? t.arena.id : "");
  $("toSeason").value = t && t.season ? t.season : "";
  $("toDescription").value = t && t.description ? t.description : "";
  $("toUrl").value = t && t.url ? t.url : "";
  $("toRecordingsUrl").value = t && t.recordings_url ? t.recordings_url : "";
  $("toGameFormat").value = t && t.game_format ? t.game_format : "";
  $("toPeriodMinutes").value = t && t.period_minutes != null ? String(t.period_minutes) : "";
  $("toPeriodsCount").value = t && t.periods_count != null ? String(t.periods_count) : "";
  $("toPosition").value = t ? String(t.position) : "0";
  $("toVisible").checked = t ? !!t.is_visible : true;
  window.__editingTeams = t && Array.isArray(t.teams)
    ? t.teams.map((x) => ({ team_id: x.id, photo: x.photo || null }))
    : [];
  renderTeamPicker();
  $("tournamentEditMsg").textContent = "";
  show($("tournamentEditMsg"), false);
  show($("tournamentEditModal"), true);
  $("tournamentEditModal").setAttribute("aria-hidden", "false");
}

function closeTournamentEditModal() {
  show($("tournamentEditModal"), false);
  $("tournamentEditModal").setAttribute("aria-hidden", "true");
}

function openEditModal(u) {
  $("edUserId").value = u.id;
  $("edUsername").value = u.username;
  $("edPassword").value = "";
  $("edVkId").value = u.vk_user_id != null ? String(u.vk_user_id) : "";
  $("edRole").value = u.role;
  $("edActive").checked = u.is_active;
  $("editMsg").textContent = "";
  show($("editMsg"), false);
  show($("editModal"), true);
  $("editModal").setAttribute("aria-hidden", "false");
}

function closeEditModal() {
  show($("editModal"), false);
  $("editModal").setAttribute("aria-hidden", "true");
}

function intOrNull(raw) {
  const v = String(raw ?? "").trim();
  if (!v) return null;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function showDashboard() {
  show($("loginPanel"), false);
  show($("dashPanel"), true);
  show($("userBar"), true);
}

function showLogin() {
  show($("dashPanel"), false);
  show($("userBar"), false);
  show($("loginPanel"), true);
  window.__myRole = null;
}

document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
});

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const username = String(fd.get("username") || "").trim();
  const password = String(fd.get("password") || "");
  show($("loginError"), false);
  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.statusText);
    setToken(data.access_token);
    showDashboard();
    await loadMe();
    setTab("appointments");
  } catch (err) {
    $("loginError").textContent = err.message || "Ошибка входа";
    show($("loginError"), true);
  }
});

$("logoutBtn").addEventListener("click", () => {
  setToken(null);
  showLogin();
});

$("refreshAppointmentsBtn").addEventListener("click", async () => {
  try {
    await loadAppointments();
  } catch (err) {
    $("listError").textContent = err.message;
    show($("listError"), true);
  }
});

$("refreshServicesBtn").addEventListener("click", async () => {
  try {
    await loadServiceRequests();
  } catch (err) {
    $("svcError").textContent = err.message;
    show($("svcError"), true);
  }
});

$("refreshQuestionsBtn").addEventListener("click", async () => {
  try {
    await loadQuestions();
  } catch (err) {
    $("qError").textContent = err.message;
    show($("qError"), true);
  }
});

$("refreshAdminsBtn").addEventListener("click", async () => {
  try {
    await loadAdmins();
  } catch (err) {
    $("adminsListError").textContent = err.message;
    show($("adminsListError"), true);
  }
});

function bindDeleteAll({ btnId, msgId, path, confirmText, reload }) {
  const btn = $(btnId);
  if (!btn) return;
  btn.addEventListener("click", async () => {
    const msg = $(msgId);
    msg.textContent = "";
    show(msg, false);
    if (!window.confirm(confirmText)) return;
    btn.disabled = true;
    try {
      const res = await apiFetch(path, { method: "DELETE" });
      msg.textContent = `Удалено: ${res.deleted}.`;
      show(msg, true);
      if (reload) await reload();
    } catch (err) {
      msg.textContent = err.message;
      show(msg, true);
    } finally {
      btn.disabled = false;
    }
  });
}

bindDeleteAll({
  btnId: "deleteAllAppointmentsBtn",
  msgId: "deleteAllAppointmentsMsg",
  path: "/appointments",
  confirmText: "Удалить ВСЕ заявки? Действие необратимо.",
  reload: () => loadAppointments(),
});
bindDeleteAll({
  btnId: "deleteAllServicesBtn",
  msgId: "deleteAllServicesMsg",
  path: "/service-requests",
  confirmText: "Удалить ВСЕ заявки на услуги? Действие необратимо.",
  reload: () => loadServiceRequests(),
});
bindDeleteAll({
  btnId: "deleteAllQuestionsBtn",
  msgId: "deleteAllQuestionsMsg",
  path: "/questions",
  confirmText: "Удалить ВСЕ вопросы? Действие необратимо.",
  reload: () => loadQuestions(),
});
bindDeleteAll({
  btnId: "deleteAllReviewsBtn",
  msgId: "deleteAllReviewsMsg",
  path: "/reviews",
  confirmText: "Удалить ВСЕ отзывы? Действие необратимо.",
  reload: () => loadReviews(),
});
bindDeleteAll({
  btnId: "deleteAllNewsBtn",
  msgId: "deleteAllNewsMsg",
  path: "/news",
  confirmText: "Удалить ВСЕ новости? Действие необратимо.",
  reload: () => loadNews(),
});
bindDeleteAll({
  btnId: "deleteAllTeamsBtn",
  msgId: "deleteAllTeamsMsg",
  path: "/teams",
  confirmText: "Удалить ВСЕ команды? Они также исчезнут из всех турниров.",
  reload: async () => {
    await loadTeams();
    if (window.__activeTab === "tournaments") await loadTournaments();
  },
});
bindDeleteAll({
  btnId: "deleteAllTournamentsBtn",
  msgId: "deleteAllTournamentsMsg",
  path: "/tournaments",
  confirmText: "Удалить ВСЕ турниры? Действие необратимо.",
  reload: () => loadTournaments(),
});

$("vkForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const raw = String($("vkUserIdInput").value || "").trim();
  const msg = $("vkMsg");
  msg.textContent = "";
  show(msg, false);
  if (!raw) {
    msg.textContent = "Введите числовой VK user_id или нажмите «Отвязать».";
    show(msg, true);
    return;
  }
  const n = parseInt(raw, 10);
  if (Number.isNaN(n) || n < 1) {
    msg.textContent = "Некорректный VK user_id.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch("/me/vk", { method: "PATCH", body: JSON.stringify({ vk_user_id: n }) });
    msg.textContent = "Сохранено.";
    show(msg, true);
    await loadMe();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("vkClearBtn").addEventListener("click", async () => {
  const msg = $("vkMsg");
  msg.textContent = "";
  show(msg, false);
  try {
    await apiFetch("/me/vk", { method: "PATCH", body: JSON.stringify({ vk_user_id: null }) });
    msg.textContent = "VK отвязан.";
    show(msg, true);
    await loadMe();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("adminForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const username = String(fd.get("username") || "").trim();
  const password = String(fd.get("password") || "");
  const role = String(fd.get("role") || "viewer");
  const vkRaw = String(fd.get("vk_user_id") || "").trim();
  const payload = { username, password, role };
  if (vkRaw) {
    const v = parseInt(vkRaw, 10);
    if (!Number.isNaN(v) && v > 0) payload.vk_user_id = v;
  }
  const msg = $("adminMsg");
  msg.textContent = "";
  show(msg, false);
  try {
    await apiFetch("/admins", { method: "POST", body: JSON.stringify(payload) });
    msg.textContent = "Пользователь создан.";
    show(msg, true);
    e.target.reset();
    await loadAdmins();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("refreshReviewsBtn").addEventListener("click", async () => {
  try {
    await loadReviews();
  } catch (err) {
    $("reviewsError").textContent = err.message;
    show($("reviewsError"), true);
  }
});

$("syncReviewsBtn").addEventListener("click", async () => {
  const msg = $("reviewsSyncMsg");
  msg.textContent = "";
  show(msg, false);
  $("syncReviewsBtn").disabled = true;
  try {
    const res = await apiFetch("/reviews/sync", { method: "POST" });
    msg.textContent = `Получено из VK: ${res.fetched}, добавлено новых: ${res.created}, уже было: ${res.skipped_existing}, пустых пропущено: ${res.skipped_empty}.`;
    show(msg, true);
    await loadReviews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  } finally {
    $("syncReviewsBtn").disabled = false;
  }
});

$("reviewCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("reviewCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const author_name = String($("rcAuthor").value || "").trim();
  const text = String($("rcText").value || "").trim();
  const photo = String($("rcPhoto").value || "").trim();
  const positionRaw = String($("rcPosition").value || "0").trim();
  const position = Number.parseInt(positionRaw, 10);
  if (!author_name || !text) {
    msg.textContent = "Заполните автора и текст.";
    show(msg, true);
    return;
  }
  const payload = {
    author_name,
    text,
    author_photo_url: photo || null,
    position: Number.isFinite(position) && position >= 0 ? position : 0,
    is_visible: $("rcVisible").checked,
  };
  try {
    await apiFetch("/reviews", { method: "POST", body: JSON.stringify(payload) });
    msg.textContent = "Отзыв добавлен.";
    show(msg, true);
    e.target.reset();
    $("rcVisible").checked = true;
    $("rcPosition").value = "0";
    await loadReviews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("reviewEditCancelBtn").addEventListener("click", () => requestModalClose(closeReviewEditModal));
$("reviewEditModal").addEventListener("click", (e) => {
  if (e.target === $("reviewEditModal")) requestModalClose(closeReviewEditModal);
});

$("reviewEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("reUserId").value;
  const msg = $("reviewEditMsg");
  msg.textContent = "";
  show(msg, false);
  const author_name = String($("reAuthor").value || "").trim();
  const text = String($("reText").value || "").trim();
  const photo = String($("rePhoto").value || "").trim();
  const positionRaw = String($("rePosition").value || "0").trim();
  const position = Number.parseInt(positionRaw, 10);
  if (!author_name || !text) {
    msg.textContent = "Заполните автора и текст.";
    show(msg, true);
    return;
  }
  const payload = {
    author_name,
    text,
    author_photo_url: photo || null,
    position: Number.isFinite(position) && position >= 0 ? position : 0,
    is_visible: $("reVisible").checked,
  };
  try {
    await apiFetch(`/reviews/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    closeReviewEditModal();
    await loadReviews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("refreshNewsBtn").addEventListener("click", async () => {
  try {
    await loadNews();
  } catch (err) {
    $("newsError").textContent = err.message;
    show($("newsError"), true);
  }
});

$("syncNewsBtn").addEventListener("click", async () => {
  const msg = $("newsSyncMsg");
  msg.textContent = "";
  show(msg, false);
  $("syncNewsBtn").disabled = true;
  try {
    const res = await apiFetch("/news/sync", { method: "POST" });
    msg.textContent = `Получено из VK: ${res.fetched}, добавлено новых: ${res.created}, уже было: ${res.skipped_existing}, пропущено по фильтру: ${res.skipped_filtered}, пустых: ${res.skipped_empty}.`;
    show(msg, true);
    await loadNews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  } finally {
    $("syncNewsBtn").disabled = false;
  }
});

$("newsCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("newsCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const url = String($("ncUrl").value || "").trim();
  if (!url) {
    msg.textContent = "Вставьте ссылку на пост.";
    show(msg, true);
    return;
  }
  const positionRaw = String($("ncPosition").value || "0").trim();
  const position = Number.parseInt(positionRaw, 10);
  const payload = {
    url,
    position: Number.isFinite(position) && position >= 0 ? position : 0,
    is_visible: $("ncVisible").checked,
  };
  const submitBtn = e.target.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  try {
    await apiFetch("/news", { method: "POST", body: JSON.stringify(payload) });
    msg.textContent = "Импортировано.";
    show(msg, true);
    e.target.reset();
    $("ncVisible").checked = true;
    $("ncPosition").value = "0";
    await loadNews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  } finally {
    submitBtn.disabled = false;
  }
});

$("newsEditCancelBtn").addEventListener("click", () => requestModalClose(closeNewsEditModal));
$("newsEditModal").addEventListener("click", (e) => {
  if (e.target === $("newsEditModal")) requestModalClose(closeNewsEditModal);
});

$("newsEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("neId").value;
  const msg = $("newsEditMsg");
  msg.textContent = "";
  show(msg, false);
  const url = String($("neUrl").value || "").trim();
  const excerpt = String($("neExcerpt").value || "").trim();
  const image = String($("neImage").value || "").trim();
  const positionRaw = String($("nePosition").value || "0").trim();
  const position = Number.parseInt(positionRaw, 10);
  if (!url) {
    msg.textContent = "Ссылка обязательна.";
    show(msg, true);
    return;
  }
  const payload = {
    url,
    excerpt,
    image: image || null,
    position: Number.isFinite(position) && position >= 0 ? position : 0,
    is_visible: $("neVisible").checked,
  };
  try {
    await apiFetch(`/news/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    closeNewsEditModal();
    await loadNews();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("neRefreshBtn").addEventListener("click", async () => {
  const id = $("neId").value;
  const msg = $("newsEditMsg");
  msg.textContent = "";
  show(msg, false);
  if (!id) return;
  $("neRefreshBtn").disabled = true;
  try {
    const updated = await apiFetch(`/news/${id}/refresh`, { method: "POST" });
    $("neImage").value = updated.image || "";
    $("neExcerpt").value = updated.excerpt || "";
    msg.textContent = "Обновлено из VK.";
    show(msg, true);
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  } finally {
    $("neRefreshBtn").disabled = false;
  }
});

// ---------- Teams handlers ----------

$("refreshTeamsBtn").addEventListener("click", async () => {
  try { await loadTeams(); }
  catch (err) { $("teamsError").textContent = err.message; show($("teamsError"), true); }
});

$("teamCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("teamCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const name = String($("tcName").value || "").trim();
  const city = String($("tcCity").value || "").trim();
  const logo = String($("tcLogo").value || "").trim();
  const description = String($("tcDescription").value || "").trim();
  if (!name) {
    msg.textContent = "Название обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch("/teams", {
      method: "POST",
      body: JSON.stringify({
        name,
        city: city || null,
        logo: logo || null,
        description: description || null,
      }),
    });
    msg.textContent = "Команда добавлена.";
    show(msg, true);
    e.target.reset();
    await loadTeams();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("teamEditCancelBtn").addEventListener("click", () => requestModalClose(closeTeamEditModal));
$("teamEditModal").addEventListener("click", (e) => {
  if (e.target === $("teamEditModal")) requestModalClose(closeTeamEditModal);
});

$("teamEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("teId").value;
  const msg = $("teamEditMsg");
  msg.textContent = "";
  show(msg, false);
  const name = String($("teName").value || "").trim();
  const city = String($("teCity").value || "").trim();
  const logo = String($("teLogo").value || "").trim();
  const description = String($("teDescription").value || "").trim();
  // Пустое поле → null, то есть «вернуться к расчёту».
  const manualPayload = {};
  for (const [field, inputId] of Object.entries(TEAM_STAT_INPUTS)) {
    manualPayload[`manual_${field}`] = intOrNull($(inputId).value);
  }
  if (!name) {
    msg.textContent = "Название обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch(`/teams/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name,
        city: city || null,
        logo: logo || null,
        description: description || null,
        ...manualPayload,
      }),
    });
    closeTeamEditModal();
    await loadTeams();
    if (window.__activeTab === "tournaments") await loadTournaments();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

// ---------- Tournaments handlers ----------

$("refreshTournamentsBtn").addEventListener("click", async () => {
  try { await loadTournaments(); }
  catch (err) { $("tournamentsError").textContent = err.message; show($("tournamentsError"), true); }
});

$("newTournamentBtn").addEventListener("click", async () => {
  try {
    const [teams, arenas] = await Promise.all([
      window.__teamsCache && window.__teamsCache.length
        ? Promise.resolve(window.__teamsCache)
        : apiFetch("/teams?limit=500"),
      apiFetch("/arenas?limit=500"),
    ]);
    window.__teamsCache = teams;
    window.__arenasCache = arenas;
    if (!arenas.length) {
      $("tournamentsError").textContent = "Сначала добавьте хотя бы одну арену во вкладке «Арены».";
      show($("tournamentsError"), true);
      return;
    }
    openTournamentEditModal(null);
  } catch (err) {
    $("tournamentsError").textContent = err.message;
    show($("tournamentsError"), true);
  }
});

$("toAddTeamBtn").addEventListener("click", () => {
  const sel = $("toTeamSelect");
  const tid = sel.value;
  if (!tid) return;
  if (!window.__editingTeams.some((x) => x.team_id === tid)) {
    window.__editingTeams.push({ team_id: tid, photo: null });
  }
  renderTeamPicker();
});

$("tournamentEditCancelBtn").addEventListener("click", () => requestModalClose(closeTournamentEditModal));
$("tournamentEditModal").addEventListener("click", (e) => {
  if (e.target === $("tournamentEditModal")) requestModalClose(closeTournamentEditModal);
});

$("tournamentEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("tournamentEditMsg");
  msg.textContent = "";
  show(msg, false);
  const id = $("toId").value;
  const title = String($("toTitle").value || "").trim();
  const age_category = String($("toAge").value || "").trim();
  const start_date = $("toStart").value;
  const end_date = $("toEnd").value;
  const start_time = $("toStartTime").value || null;
  const end_time = $("toEndTime").value || null;
  const arena_id = String($("toArenaId").value || "").trim();
  if (!title || !age_category || !start_date || !end_date || !arena_id) {
    msg.textContent = "Заполните обязательные поля: название, категория, даты, арена.";
    show(msg, true);
    return;
  }
  if (end_date < start_date) {
    msg.textContent = "Дата окончания раньше начала.";
    show(msg, true);
    return;
  }
  const birth_year = String($("toBirthYear").value || "").trim() || null;
  const positionRaw = String($("toPosition").value || "0").trim();
  const position = Number.parseInt(positionRaw, 10);
  const payload = {
    title,
    age_category,
    birth_year,
    start_date,
    end_date,
    start_time,
    end_time,
    arena_id,
    season: String($("toSeason").value || "").trim() || null,
    description: String($("toDescription").value || "").trim() || null,
    url: String($("toUrl").value || "").trim() || null,
    recordings_url: String($("toRecordingsUrl").value || "").trim() || null,
    game_format: String($("toGameFormat").value || "").trim() || null,
    period_minutes: intOrNull($("toPeriodMinutes").value),
    periods_count: intOrNull($("toPeriodsCount").value),
    position: Number.isFinite(position) && position >= 0 ? position : 0,
    is_visible: $("toVisible").checked,
    teams: window.__editingTeams.map((x) => ({ team_id: x.team_id, photo: x.photo })),
  };
  try {
    if (id) {
      await apiFetch(`/tournaments/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    } else {
      await apiFetch("/tournaments", { method: "POST", body: JSON.stringify(payload) });
    }
    closeTournamentEditModal();
    await loadTournaments();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("editCancelBtn").addEventListener("click", () => requestModalClose(closeEditModal));
$("editModal").addEventListener("click", (e) => {
  if (e.target === $("editModal")) requestModalClose(closeEditModal);
});

$("editAdminForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("edUserId").value;
  const username = String($("edUsername").value || "").trim();
  const password = String($("edPassword").value || "");
  const vkRaw = String($("edVkId").value || "").trim();
  const role = String($("edRole").value || "viewer");
  const msg = $("editMsg");
  msg.textContent = "";
  show(msg, false);
  if (!username) {
    msg.textContent = "Укажите логин.";
    show(msg, true);
    return;
  }
  let vk_user_id = null;
  if (vkRaw !== "") {
    const v = parseInt(vkRaw, 10);
    if (Number.isNaN(v) || v < 1) {
      msg.textContent = "Некорректный VK user_id.";
      show(msg, true);
      return;
    }
    vk_user_id = v;
  }
  const payload = {
    username,
    role,
    is_active: $("edActive").checked,
    vk_user_id,
  };
  if (password) payload.password = password;
  try {
    await apiFetch(`/admins/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
    closeEditModal();
    await loadAdmins();
    await loadMe();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

// ---------- Tournament applications ----------

async function loadTournamentApps() {
  await Promise.all([loadTaPlayers(), loadTaTeams()]);
}

async function loadTaPlayers() {
  $("taPlayersError").textContent = "";
  show($("taPlayersError"), false);
  const rows = $("taPlayerRows");
  rows.innerHTML = "";
  const data = await apiFetch("/tournament-applications/players?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="6" class="muted">Пока нет заявок игроков</td></tr>`;
    return;
  }
  for (const a of data) {
    const tr = document.createElement("tr");
    const dt = new Date(a.created_at);
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="Родитель">${escapeHtml(a.parent_name)}</td>
      <td data-label="Ребёнок">${escapeHtml(a.child_name)}</td>
      <td data-label="Возраст">${escapeHtml(String(a.child_age))}</td>
      <td data-label="Телефон">${escapeHtml(a.phone)}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить эту заявку?",
          request: () => apiFetch(`/tournament-applications/players/${a.id}`, { method: "DELETE" }),
          onDone: loadTaPlayers,
          errorTargetId: "taPlayersError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

async function loadTaTeams() {
  $("taTeamsError").textContent = "";
  show($("taTeamsError"), false);
  const rows = $("taTeamRows");
  rows.innerHTML = "";
  const data = await apiFetch("/tournament-applications/teams?limit=200");
  if (!data.length) {
    rows.innerHTML = `<tr><td colspan="8" class="muted">Пока нет заявок команд</td></tr>`;
    return;
  }
  for (const a of data) {
    const tr = document.createElement("tr");
    const dt = new Date(a.created_at);
    const comment = a.comment ? String(a.comment) : "";
    const commentPreview = comment.length > 160 ? comment.slice(0, 160) + "…" : comment;
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="Команда">${escapeHtml(a.team_name)}</td>
      <td data-label="Город">${escapeHtml(a.city)}</td>
      <td data-label="Категория">${escapeHtml(a.age_category)}</td>
      <td data-label="Тренер">${escapeHtml(a.coach_name)}</td>
      <td data-label="Телефон">${escapeHtml(a.phone)}</td>
      <td data-label="Комментарий">${commentPreview ? escapeHtml(commentPreview) : '<span class="muted">—</span>'}</td>
    `;
    const tdAct = document.createElement("td");
    tdAct.setAttribute("data-label", "Действие");
    tdAct.appendChild(
      makeDeleteButton(() =>
        confirmAndDelete({
          question: "Удалить эту заявку?",
          request: () => apiFetch(`/tournament-applications/teams/${a.id}`, { method: "DELETE" }),
          onDone: loadTaTeams,
          errorTargetId: "taTeamsError",
        }),
      ),
    );
    tr.appendChild(tdAct);
    rows.appendChild(tr);
  }
}

$("refreshTaPlayersBtn").addEventListener("click", async () => {
  try { await loadTaPlayers(); }
  catch (err) { $("taPlayersError").textContent = err.message; show($("taPlayersError"), true); }
});

$("refreshTaTeamsBtn").addEventListener("click", async () => {
  try { await loadTaTeams(); }
  catch (err) { $("taTeamsError").textContent = err.message; show($("taTeamsError"), true); }
});

bindDeleteAll({
  btnId: "deleteAllTaPlayersBtn",
  msgId: "deleteAllTaPlayersMsg",
  path: "/tournament-applications/players",
  confirmText: "Удалить ВСЕ заявки игроков? Действие необратимо.",
  reload: () => loadTaPlayers(),
});
bindDeleteAll({
  btnId: "deleteAllTaTeamsBtn",
  msgId: "deleteAllTaTeamsMsg",
  path: "/tournament-applications/teams",
  confirmText: "Удалить ВСЕ заявки команд? Действие необратимо.",
  reload: () => loadTaTeams(),
});

bindLogoUpload({
  urlInputId: "tcLogo",
  fileInputId: "tcLogoFile",
  buttonId: "tcLogoUploadBtn",
  statusId: "tcLogoMsg",
});
bindLogoUpload({
  urlInputId: "teLogo",
  fileInputId: "teLogoFile",
  buttonId: "teLogoUploadBtn",
  statusId: "teLogoMsg",
});

// ---------- Players handlers ----------

bindLogoUpload({
  urlInputId: "pcPhoto",
  fileInputId: "pcPhotoFile",
  buttonId: "pcPhotoUploadBtn",
  statusId: "pcPhotoMsg",
  uploader: uploadPlayerPhoto,
  okText: "Фото загружено.",
});
bindLogoUpload({
  urlInputId: "pePhoto",
  fileInputId: "pePhotoFile",
  buttonId: "pePhotoUploadBtn",
  statusId: "pePhotoMsg",
  uploader: uploadPlayerPhoto,
  okText: "Фото загружено.",
});

$("refreshPlayersBtn").addEventListener("click", async () => {
  try { await loadPlayers(); }
  catch (err) { $("playersError").textContent = err.message; show($("playersError"), true); }
});

let _playerSearchTimer = null;
$("playerSearch").addEventListener("input", () => {
  clearTimeout(_playerSearchTimer);
  _playerSearchTimer = setTimeout(async () => {
    try { await loadPlayers(); }
    catch (err) { $("playersError").textContent = err.message; show($("playersError"), true); }
  }, 300);
});

$("playerCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("playerCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const full_name = String($("pcName").value || "").trim();
  if (!full_name) {
    msg.textContent = "ФИО обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch("/players", {
      method: "POST",
      body: JSON.stringify({
        full_name,
        birth_date: $("pcBirthDate").value || null,
        position: $("pcPosition").value || null,
        photo: String($("pcPhoto").value || "").trim() || null,
      }),
    });
    $("playerCreateForm").reset();
    show($("pcPhotoMsg"), false);
    msg.textContent = "Игрок добавлен.";
    show(msg, true);
    await loadPlayers();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("playerEditCancelBtn").addEventListener("click", () => requestModalClose(closePlayerEditModal));

$("playerEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("playerEditMsg");
  msg.textContent = "";
  show(msg, false);
  const full_name = String($("peName").value || "").trim();
  if (!full_name) {
    msg.textContent = "ФИО обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch(`/players/${$("peId").value}`, {
      method: "PATCH",
      body: JSON.stringify({
        full_name,
        birth_date: $("peBirthDate").value || null,
        position: $("pePosition").value || null,
        photo: String($("pePhoto").value || "").trim() || null,
      }),
    });
    closePlayerEditModal();
    await loadPlayers();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

// ---------- Arenas handlers ----------

$("refreshArenasBtn").addEventListener("click", async () => {
  try { await loadArenas(); }
  catch (err) { $("arenasError").textContent = err.message; show($("arenasError"), true); }
});

$("arenaCreateForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("arenaCreateMsg");
  msg.textContent = "";
  show(msg, false);
  const name = String($("acName").value || "").trim();
  const url = String($("acUrl").value || "").trim();
  const address = String($("acAddress").value || "").trim();
  const city = String($("acCity").value || "").trim();
  if (!name) {
    msg.textContent = "Название обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch("/arenas", {
      method: "POST",
      body: JSON.stringify({
        name,
        url: url || null,
        address: address || null,
        city: city || null,
      }),
    });
    msg.textContent = "Арена добавлена.";
    show(msg, true);
    e.target.reset();
    await loadArenas();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

$("arenaEditCancelBtn").addEventListener("click", () => requestModalClose(closeArenaEditModal));
$("arenaEditModal").addEventListener("click", (e) => {
  if (e.target === $("arenaEditModal")) requestModalClose(closeArenaEditModal);
});

$("arenaEditForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = $("aeId").value;
  const msg = $("arenaEditMsg");
  msg.textContent = "";
  show(msg, false);
  const name = String($("aeName").value || "").trim();
  const url = String($("aeUrl").value || "").trim();
  const address = String($("aeAddress").value || "").trim();
  const city = String($("aeCity").value || "").trim();
  if (!name) {
    msg.textContent = "Название обязательно.";
    show(msg, true);
    return;
  }
  try {
    await apiFetch(`/arenas/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name,
        url: url || null,
        address: address || null,
        city: city || null,
      }),
    });
    closeArenaEditModal();
    await loadArenas();
    if (window.__activeTab === "tournaments") await loadTournaments();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
});

(async function boot() {
  window.__activeTab = "appointments";
  if (!getToken()) return;
  try {
    showDashboard();
    await loadMe();
    setTab("appointments");
  } catch {
    setToken(null);
    showLogin();
  }
})();
