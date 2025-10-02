// ---------- tiny DOM helpers ----------
const $ = sel => document.querySelector(sel);
const CE = (tag, props={}) => Object.assign(document.createElement(tag), props);

// ---------- Toasts ----------
function notify(text, type = "info", timeout = 4000) {
  const host = $("#toasts") || (() => {
    const d = CE("div", { id:"toasts" });
    document.body.appendChild(d);
    return d;
  })();

  const el = CE("div", { className:`toast toast--${type}` });
  const msg = CE("div", { className:"toast__msg", textContent: text });
  const btn = CE("button", { className:"toast__close", innerHTML:"&times;", title:"Закрыть" });
  btn.onclick = () => el.remove();

  el.append(msg, btn);
  host.appendChild(el);

  if (timeout > 0) setTimeout(() => { el.remove(); }, timeout);
}

// Централизованный fetch с нормальными ошибками
async function http(url, opts = {}) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    throw new Error("Сеть недоступна или соединение прервано");
  }

  // пробуем JSON, если не вышло — текст
  let data, raw = "";
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try { data = await res.json(); } catch {}
  } else {
    try { raw = await res.text(); } catch {}
  }

  if (!res.ok) {
    const detail = data?.detail || data?.message || raw || res.statusText || "Неизвестная ошибка";
    throw new Error(`${detail} (HTTP ${res.status})`);
  }
  return data ?? raw;
}

function markInvalid(el) {
  el.classList.add("input-invalid");
  setTimeout(() => el.classList.remove("input-invalid"), 1200);
}


// ---------- DOM refs ----------fv
const listEl = $("#list");

// ---------- API wrappers ----------
async function apiList()  { return http("/api/items"); }
async function apiCreate(title, description=null) {
  return http("/api/items", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ title, description })
  });
}
async function apiDelete(id) { await http(`/api/items/${id}`, { method: "DELETE" }); }
async function apiPatch(id, updates) {
  return http(`/api/items/${id}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(updates)
  });
}
async function apiPut(id, title, description) {
  return http(`/api/items/${id}`, {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ title, description })
  });
}

async function apiPing(token) {
  return http("/api/ping", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ token })
  });
}

async function apiPingStats() {
  return http("/api/ping/stats");
}

async function apiPingLast(n=100) { 
  return http(`/api/ping/last?limit=${n}`);
}

async function apiPingClear() {
  return http("/api/ping/clear", { method: "POST" });
}

// ---------- List rendering ----------
async function reload() {
  let items = [];
  try { items = await apiList(); }
  catch (e) {
    listEl.innerHTML = "";
    const li = CE("li",{ className:"muted", textContent:"Не удалось загрузить список." });
    listEl.appendChild(li);
    notify(`Ошибка загрузки списка: ${e.message}`, "error", 6000);
    return;
  }

  listEl.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    const li = CE("li",{ className:"muted", textContent:"Список пуст — добавьте первый элемент." });
    listEl.appendChild(li);
    return;
  }
  for (const it of items) listEl.appendChild(renderItem(it));
}

function renderItem(it) {
  const li = CE("li", { className:"item" });

  // view mode
  const text = CE("div", { className:"text", textContent: `ID: ${it.id} — ${it.title} — ${it.description ?? ""}` });
  const actions = CE("div", { className:"actions" });
  const btnEdit = CE("button", { textContent:"Редактировать" });
  const btnDel  = CE("button", { textContent:"Удалить" });

  btnDel.onclick = async () => {
    try { await apiDelete(it.id); notify("Удалено", "success", 1500); reload(); }
    catch (e) { notify(`Удаление не удалось: ${e.message}`, "error", 6000); }
  };
  btnEdit.onclick = () => enterEdit(li, it);

  actions.append(btnEdit, btnDel);
  li.append(text, actions);
  return li;
}

function enterEdit(li, it) {
  li.classList.add("editing");
  li.innerHTML = "";

  const editor = CE("div", { className:"editor" });
  const titleInput = CE("input", { type:"text", value: it.title, placeholder:"Заголовок (≤ 200 символов)" });
  const descInput  = CE("input", { type:"text", value: it.description ?? "", placeholder:"Описание (необязательно)" });

  const hint = CE("div", { className:"hint", textContent:"Сохранить можно частично (PATCH) или полностью (PUT)." });
  const spacer = CE("div", { className:"spacer" });

  const btnSavePatch = CE("button", { textContent:"Сохранить (PATCH)" });
  const btnSavePut   = CE("button", { textContent:"Сохранить (PUT)" });
  const btnCancel    = CE("button", { textContent:"Отмена" });

  function disableAll(disabled=true) {
    [titleInput, descInput, btnSavePatch, btnSavePut, btnCancel].forEach(el => el.disabled = disabled);
  }

  btnSavePatch.onclick = async () => {
    const updates = {};
    const newTitle = titleInput.value.trim();
    const newDesc  = descInput.value.trim();

    if (newTitle !== it.title && newTitle !== "") updates.title = newTitle;
    if ((it.description ?? "") !== newDesc)       updates.description = newDesc === "" ? null : newDesc;

    if (Object.keys(updates).length === 0) { notify("Нет изменений", "warn", 2000); return; }

    disableAll(true);
    try { await apiPatch(it.id, updates); notify("Сохранено (PATCH)", "success", 2000); reload(); }
    catch (e) { notify(`Ошибка PATCH: ${e.message}`, "error", 6000); disableAll(false); }
  };

  btnSavePut.onclick = async () => {
    const newTitle = titleInput.value.trim();
    const newDesc  = descInput.value.trim();
    if (newTitle === "") { notify("Заголовок обязателен для PUT", "warn", 3000); return; }

    disableAll(true);
    try { await apiPut(it.id, newTitle, newDesc === "" ? null : newDesc); notify("Сохранено (PUT)", "success", 2000); reload(); }
    catch (e) { notify(`Ошибка PUT: ${e.message}`, "error", 6000); disableAll(false); }
  };

  btnCancel.onclick = () => { li.replaceWith(renderItem(it)); };

  editor.append(titleInput, descInput, hint, spacer, btnSavePatch, btnSavePut, btnCancel);
  li.append(editor);
}

// ---------- create & controls ----------
$("#add").onclick = async () => {
  const titleEl = $("#title");
  const descEl  = $("#desc");
  const title   = titleEl.value.trim();
  const descRaw = descEl.value.trim();

  // оба поля пустые — отдельное уведомление
  if (!title && !descRaw) {
    notify("Поля пустые: заполните хотя бы «Название».", "warn", 3000);
    markInvalid(titleEl);
    markInvalid(descEl);
    titleEl.focus();
    return;
  }

  // заголовок обязателен по API
  if (!title) {
    notify("Введите «Название» — это обязательное поле.", "warn", 3000);
    markInvalid(titleEl);
    titleEl.focus();
    return;
  }

  const description = descRaw || null;

  try {
    await apiCreate(title, description);
    titleEl.value = "";
    descEl.value  = "";
    notify("Добавлено", "success", 1500);
    reload();
  } catch (e) {
    notify(`Ошибка создания: ${e.message}`, "error", 6000);
  }
};

function rndToken(n=8) {
  const alphabet = "abcdefghijklmnopqrstuvwxyz0123456789";
  let s=""; for (let i=0;i<n;i++) s+=alphabet[Math.floor(Math.random()*alphabet.length)];
  return s;
}
const tokenEl = $("#tokenInput");
$("#tokenRnd").onclick = () => { tokenEl.value = rndToken(10); };

$("#clearPingStats").onclick = async () => {
  // простое подтверждение, чтобы случайно не стереть
  if (!confirm("Точно очистить всю статистику по IP/AS?")) return;

  const btn = $("#clearPingStats");
  btn.disabled = true;
  try {
    const r = await apiPingClear();
    notify(`Очищено записей: ${r.deleted}`, "success", 2500);
    // обновим виджеты статистики и таблицу
    await loadPingStats();
  } catch (e) {
    notify(`Не удалось очистить: ${e.message}`, "error", 6000);
  } finally {
    btn.disabled = false;
  }
};

$("#tokenSend").onclick = async () => {
  const t = tokenEl.value.trim();
  if (!t) {
    notify("Введите токен", "warn", 2500);
    tokenEl.classList.add("input-invalid");
    setTimeout(()=>tokenEl.classList.remove("input-invalid"), 1200);
    tokenEl.focus();
    return;
  }
  try {
    const r = await apiPing(t);  // теперь ответ содержит r.duplicate
    const name = r.as_name ? ` (${r.as_name})` : "";
    const pref = r.prefix ? `, ${r.prefix}` : "";
    if (r.duplicate) {
      notify(`IP уже есть в базе: ${r.ip} → AS${r.asn ?? "?"}${name}${pref}. Новая запись не добавлена.`, "warn", 5000);
    } else {
      notify(`Записано: ${r.ip} → AS${r.asn ?? "?"}${name}${pref}`, "success", 3000);
    }
  } catch (e) {
    notify(`Ping не удался: ${e.message}`, "error", 6000);
  }
};

async function loadPingStats() {
  try {
    const stats = await apiPingStats();
    $("#pingSummary").textContent = `Всего пингов: ${stats.total_hits}, уникальных IP: ${stats.unique_ips}`;

    const top = $("#pingTop"); top.innerHTML = "";
    for (const row of stats.top) {
      const name = row.as_name ? ` (${row.as_name})` : "";
      top.appendChild(CE("li", { textContent: `AS${row.asn ?? "?"}${name} — ${row.count}` }));
    }

    const tbody = $("#pingTable tbody"); tbody.innerHTML = "";
    const last = await apiPingLast(100);
    for (const r of last) {
      const tr = CE("tr");
      tr.append(
        CE("td", { textContent: r.when }),
        CE("td", { textContent: r.token }),
        CE("td", { textContent: r.ip }),
        CE("td", { textContent: r.asn ?? "" }),
        CE("td", { textContent: r.as_name ?? "" }),
        CE("td", { textContent: r.prefix ?? "" }),
        CE("td", { textContent: r.user_agent ?? "" }),
      );
      tbody.appendChild(tr);
    }

    notify("Статистика по токенам обновлена", "success", 1500);
  } catch (e) {
    notify(`Ошибка загрузки статистики: ${e.message}`, "error", 6000);
  }
}
$("#loadPingStats").onclick = loadPingStats;

// Читаем ответ fetch() потоком и обновляем прогресс
async function fetchWithProgress(url, onProgress) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const total = parseInt(res.headers.get("content-length") || "0", 10);
  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let received = 0;
  let text = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    text += decoder.decode(value, { stream: true });
    if (total) onProgress(Math.round(received * 100 / total));
  }
  text += decoder.decode();
  if (!total) onProgress(100);
  return text;
}

// Разбор delegated-ripencc-latest для ASN RU
function parseRipeDelegated(text) {
  const lines = text.split(/\r?\n/);
  const perDay = new Map(); // YYYYMMDD -> count
  for (const ln of lines) {
    if (!ln || ln[0] === '#') continue;
    const parts = ln.split('|');
    if (parts.length < 7) continue;
    const [registry, cc, type, start, value, date, status] = parts;
    if (type !== 'asn') continue;
    if (cc !== 'RU') continue;
    const st = (status || '').toLowerCase();
    if (st !== 'allocated' && st !== 'assigned') continue;

    const count = parseInt(value, 10);
    if (!Number.isFinite(count)) continue;
    if (!/^\d{8}$/.test(date)) continue;

    perDay.set(date, (perDay.get(date) || 0) + count);
  }

  // агрегация по годам
  const perYear = new Map(); // YYYY -> count
  for (const [d, cnt] of perDay) {
    const y = d.slice(0, 4);
    perYear.set(y, (perYear.get(y) || 0) + cnt);
  }

  const years = Array.from(perYear.keys()).sort();
  const perYearArr = years.map(y => perYear.get(y));
  let cum = 0;
  const cumulative = years.map(y => { cum += perYear.get(y); return cum; });

  return { years, perYear: perYearArr, cumulative, total: cum };
}

let ripeChart = null;
function renderRipeChart(data) {
  const ctx = document.getElementById('ripeChart').getContext('2d');
  if (ripeChart) ripeChart.destroy();
  ripeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.years,
      datasets: [
        { label: 'Выделено за год', data: data.perYear, fill: false, tension: 0.2 },
        { label: 'Накопительный итог', data: data.cumulative, fill: false, tension: 0.2 }
      ]
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'bottom' } },
      scales: { y: { beginAtZero: true } }
    }
  });
}

async function ensureRipe(force=false) {
  const r = await fetch(`/api/ripe/ensure?force=${force ? 'true' : 'false'}`, { method: 'POST' });
  if (!r.ok) throw new Error('ensure failed');
  return r.json();
}

const ripeBar  = document.getElementById('ripeBar');
const ripeInfo = document.getElementById('ripeInfo');

document.getElementById('ripeLoad').onclick = async () => {
  try {
    ripeBar.value = 0;
    const info = await ensureRipe(false);
    const text = await fetchWithProgress('/api/ripe/file', v => ripeBar.value = v);
    const parsed = parseRipeDelegated(text);
    renderRipeChart(parsed);
    const mb = info.size ? (info.size / 1024 / 1024).toFixed(2) : '?';
    ripeInfo.textContent = `Размер файла: ${mb} MB. Всего выдано ASN (RU): ${parsed.total}.`;
    notify('График построен', 'success', 2000);
  } catch (e) {
    notify('Ошибка RIPE: ' + e.message, 'error', 6000);
  }
};

document.getElementById('ripeForce').onclick = async () => {
  try {
    ripeBar.value = 0;
    await ensureRipe(true);
    notify('Файл переcкачан на сервер', 'success', 2000);
  } catch (e) {
    notify('Не удалось перескачать: ' + e.message, 'error', 6000);
  }
};

// first load
reload();
