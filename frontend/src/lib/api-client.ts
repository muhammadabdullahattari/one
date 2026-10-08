export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
    public requestId?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api/v1" : "http://127.0.0.1:8000/api/v1");

let isRefreshing = false;
let refreshSubscribers: ((ok: boolean) => void)[] = [];

function onRefreshed(ok: boolean) {
  refreshSubscribers.forEach((cb) => cb(ok));
  refreshSubscribers = [];
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: "include",
  };

  let response = await fetch(url, config);

  if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/refresh")) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (refreshRes.ok) {
          isRefreshing = false;
          onRefreshed(true);
        } else {
          isRefreshing = false;
          onRefreshed(false);
          if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            const isLocal =
              window.location.hostname === "localhost" ||
              window.location.hostname === "127.0.0.1";
            if (!isLocal) {
              window.location.href = "/login";
            }
          }
          throw new ApiError(401, "UNAUTHORIZED", "Session expired. Please log in again.");
        }
      } catch (err) {
        isRefreshing = false;
        onRefreshed(false);
        throw err;
      }
    } else {
      const ok = await new Promise<boolean>((resolve) => {
        refreshSubscribers.push(resolve);
      });
      if (!ok) {
        throw new ApiError(401, "UNAUTHORIZED", "Session expired. Please log in again.");
      }
    }

    // Retry original request with refreshed session cookie
    response = await fetch(url, config);
  }

  if (!response.ok) {
    let errorData: any = {};
    try {
      errorData = await response.json();
    } catch {
      errorData = { error: { message: response.statusText } };
    }

    const err = errorData.error || errorData;
    throw new ApiError(
      response.status,
      err.code || "API_ERROR",
      err.message || response.statusText || "An unexpected API error occurred",
      err.details,
      err.request_id || response.headers.get("x-request-id") || undefined
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const apiClient = {
  get: <T>(url: string, options?: RequestInit) =>
    request<T>(url, { ...options, method: "GET" }),
  post: <T>(url: string, body?: unknown, options?: RequestInit) =>
    request<T>(url, {
      ...options,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(url: string, body?: unknown, options?: RequestInit) =>
    request<T>(url, {
      ...options,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(url: string, options?: RequestInit) =>
    request<T>(url, { ...options, method: "DELETE" }),
};
