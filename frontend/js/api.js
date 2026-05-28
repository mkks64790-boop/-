export const API_BASE = window.location.origin;

function normalizeError(detail) {
  if (!detail) return "请求失败";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(normalizeError).join("；");
  if (detail.error) return detail.error;
  if (detail.detail) return normalizeError(detail.detail);
  if (detail.errors && Array.isArray(detail.errors)) {
    return detail.errors.map(item => item.check || item.detail || JSON.stringify(item)).join("；");
  }
  try {
    return JSON.stringify(detail, null, 2);
  } catch {
    return String(detail);
  }
}

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  let payload = null;
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else {
    payload = await response.text();
  }
  if (!response.ok) {
    throw new ApiError(normalizeError(payload?.detail ?? payload), response.status, payload);
  }
  return payload;
}

export async function getJSON(path) {
  return request(path, { method: "GET" });
}

export async function postJSON(path, body = {}) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function postForm(path, formData) {
  return request(path, {
    method: "POST",
    body: formData,
  });
}

export function toErrorMessage(error) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}
