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
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
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
  if (name === "profile") loadMe();
  if (name === "users") loadAdmins();
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
    rows.innerHTML = `<tr><td colspan="4" class="muted">Пока нет вопросов</td></tr>`;
    return;
  }
  for (const q of data) {
    const tr = document.createElement("tr");
    const dt = new Date(q.created_at);
    tr.innerHTML = `
      <td data-label="Дата">${dt.toLocaleString()}</td>
      <td data-label="ФИО">${escapeHtml(q.full_name)}</td>
      <td data-label="Телефон">${escapeHtml(q.phone)}</td>
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

$("deleteAllBtn").addEventListener("click", async () => {
  const msg = $("deleteAllMsg");
  msg.textContent = "";
  show(msg, false);
  if (!window.confirm("Удалить вообще все заявки, заявки на услуги и вопросы? Действие необратимо.")) return;
  try {
    const res = await apiFetch("/requests/all", { method: "DELETE" });
    msg.textContent = `Удалено: заявки ${res.appointments}, услуги ${res.service_requests}, вопросы ${res.questions}.`;
    show(msg, true);
    if (window.__activeTab === "appointments") await loadAppointments();
    if (window.__activeTab === "services") await loadServiceRequests();
    if (window.__activeTab === "questions") await loadQuestions();
  } catch (err) {
    msg.textContent = err.message;
    show(msg, true);
  }
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

$("reviewEditCancelBtn").addEventListener("click", closeReviewEditModal);
$("reviewEditModal").addEventListener("click", (e) => {
  if (e.target === $("reviewEditModal")) closeReviewEditModal();
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

$("editCancelBtn").addEventListener("click", closeEditModal);
$("editModal").addEventListener("click", (e) => {
  if (e.target === $("editModal")) closeEditModal();
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
