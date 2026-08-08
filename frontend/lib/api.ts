const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function api(path: string, opts: RequestInit = {}) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (tenant) headers['X-Tenant-ID'] = tenant;

  const response = await fetch(base + path, { ...opts, headers, cache: 'no-store' });
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
