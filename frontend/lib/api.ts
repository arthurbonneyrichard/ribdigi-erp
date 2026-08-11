const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// Shared in-flight refresh so concurrent 401s trigger a single token refresh.
let refreshPromise: Promise<boolean> | null = null;

function clearSessionAndRedirect() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant');
  if (window.location.pathname !== '/') {
    window.location.href = '/';
  }
}

async function refreshSession(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  const refresh_token = localStorage.getItem('refresh_token');
  if (!refresh_token) return false;
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const r = await fetch(base + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token }),
          cache: 'no-store',
        });
        if (!r.ok) return false;
        const body = await r.json().catch(() => ({}));
        const data = body?.data || body;
        if (!data?.access_token) return false;
        localStorage.setItem('token', data.access_token);
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
        return true;
      } catch {
        return false;
      }
    })();
    refreshPromise.finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function api(path: string, opts: RequestInit = {}, retryOn401 = true) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (tenant) headers['X-Tenant-ID'] = tenant;

  const response = await fetch(base + path, { ...opts, headers, cache: 'no-store' });

  // Session expired: try a one-time refresh + retry, otherwise send back to login.
  // Auth endpoints are excluded so the login/2FA flow is never disrupted.
  if (response.status === 401 && retryOn401 && !path.startsWith('/auth/') && typeof window !== 'undefined') {
    const refreshed = await refreshSession();
    if (refreshed) {
      return api(path, opts, false);
    }
    clearSessionAndRedirect();
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || detail?.code || body.message || 'Request failed';
    throw new Error(message);
  }
  return body;
}
