const API_BASE = "";

function getToken() {
  return localStorage.getItem("rs_token");
}

function setAuth(data) {
  localStorage.setItem("rs_token", data.access_token);
  localStorage.setItem("rs_user_type", data.user_type);
  localStorage.setItem("rs_username", data.username);
}

function clearAuth() {
  localStorage.removeItem("rs_token");
  localStorage.removeItem("rs_user_type");
  localStorage.removeItem("rs_username");
}

function isLoggedIn() {
  return !!getToken();
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, { ...options, headers });

  if (res.status === 401) {
    clearAuth();
    window.location.href = "/";
    return;
  }

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Ошибка запроса");
  return data;
}

async function apiGet(path) {
  return apiFetch(path, { method: "GET" });
}

async function apiPost(path, body) {
  return apiFetch(path, { method: "POST", body: JSON.stringify(body) });
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
}

function starsHtml(rating, max = 5) {
  let html = "";
  for (let i = 1; i <= max; i++) {
    html += `<span class="${i <= rating ? "text-yellow-400" : "text-gray-300"}">★</span>`;
  }
  return html;
}

function platformLabel(key) {
  const map = {
    wb: "Wildberries", ozon: "Ozon", ym: "Яндекс.Маркет",
    gmaps: "Google Maps", "2gis": "2ГИС", zoon: "Zoon",
    ratescan: "РейтСкан",
  };
  return map[key] || key;
}

function platformColor(key) {
  const map = {
    wb: "bg-purple-100 text-purple-700",
    ozon: "bg-blue-100 text-blue-700",
    ym: "bg-yellow-100 text-yellow-700",
    gmaps: "bg-green-100 text-green-700",
    "2gis": "bg-emerald-100 text-emerald-700",
    zoon: "bg-orange-100 text-orange-700",
    ratescan: "bg-indigo-100 text-indigo-700",
  };
  return map[key] || "bg-gray-100 text-gray-700";
}

function sentimentIcon(s) {
  if (s === "positive") return '<span class="text-green-500">▲</span>';
  if (s === "negative") return '<span class="text-red-500">▼</span>';
  return '<span class="text-gray-400">■</span>';
}

function showToast(msg, type = "success") {
  const el = document.createElement("div");
  el.className = `fixed bottom-6 right-6 z-50 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-medium transition-all
    ${type === "success" ? "bg-green-600" : "bg-red-600"}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
