const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "pm_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY),
  set: (token, remember) => {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  },
};

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn);

function errorMessage(data, status) {
  if (!data) return `Request failed (${status})`;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => (d.msg || "").replace(/^Value error, /, "")).filter(Boolean).join(". ");
  }
  return `Request failed (${status})`;
}

async function request(path, { method = "GET", body, form } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  } catch {
    throw new Error("Cannot reach the server. Check that the backend is running.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new Error(errorMessage(data, res.status));
  }
  return data;
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  register: (body) => request("/auth/register", { method: "POST", body }),
  login: (body) => request("/auth/login", { method: "POST", body }),
  forgotPassword: (email) => request("/auth/forgot-password", { method: "POST", body: { email } }),
  resetPassword: (token, new_password) => request("/auth/reset-password", { method: "POST", body: { token, new_password } }),
  me: () => request("/auth/me"),
  onboard: (body) => request("/onboarding", { method: "POST", body }),
  projects: () => request("/projects"),
  createProject: (body) => request("/projects", { method: "POST", body }),
  dashboard: (project_id) => request(`/dashboard/summary${qs({ project_id })}`),
  analyze: (form) => request("/deployments/analyze", { method: "POST", form }),
  deployments: (params) => request(`/deployments${qs(params)}`),
  incidents: (params) => request(`/incidents${qs(params)}`),
  incident: (id) => request(`/incidents/${id}`),
  feedback: (id, body) => request(`/incidents/${id}/feedback`, { method: "POST", body }),
  memory: (project_id) => request(`/memory${qs({ project_id })}`),
  recall: (project_id, query) => request("/memory/recall", { method: "POST", body: { project_id, query } }),
  risk: (form) => request("/risk/analyze", { method: "POST", form }),
  chat: (body) => request("/assistant/chat", { method: "POST", body }),
  integrations: () => request("/settings/integrations"),
  updateProfile: (body) => request("/settings/profile", { method: "PATCH", body }),
  changePassword: (body) => request("/settings/change-password", { method: "POST", body }),
};
