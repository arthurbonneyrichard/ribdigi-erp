/** Short-lived /me cache so sidebar navigations do not wait on a duplicate call. */

import { api, tenantHeaderValue } from './api';
import { rememberCurrency } from './format';

type MeBody = Awaited<ReturnType<typeof api>>;

let cached: { at: number; body: MeBody; tenant: string; key: string } | null = null;

export function meCacheKey(tenant: string, industry?: string | null): string {
  return `${tenant}::${industry || 'unset'}`;
}

function noteCurrency(body: MeBody) {
  const data = (body as { data?: { currency?: string | null } } | null)?.data;
  if (data && typeof data.currency === 'string') rememberCurrency(data.currency);
}

function industryOf(body: MeBody): string {
  const data = (body as { data?: { industry?: string | null } } | null)?.data;
  return typeof data?.industry === 'string' ? data.industry : '';
}
let inflight: Promise<MeBody> | null = null;
let inflightTenant = '';

const TTL_MS = 20_000;

function activeTenant(): string {
  if (typeof window === 'undefined') return '';
  return tenantHeaderValue(localStorage.getItem('tenant')) || '';
}

export function invalidateMeCache() {
  cached = null;
  inflight = null;
  inflightTenant = '';
}

export async function getMe(options?: { force?: boolean }): Promise<MeBody> {
  const force = Boolean(options?.force);
  const tenant = activeTenant();
  if (!force && cached && cached.tenant === tenant && Date.now() - cached.at < TTL_MS) {
    noteCurrency(cached.body);
    return cached.body;
  }
  if (!force && inflight && inflightTenant === tenant) return inflight;

  inflightTenant = tenant;
  inflight = api('/me')
    .then((body) => {
      noteCurrency(body);
      if (activeTenant() === tenant) {
        cached = { at: Date.now(), body, tenant, key: meCacheKey(tenant, industryOf(body)) };
      }
      return body;
    })
    .finally(() => {
      inflight = null;
      inflightTenant = '';
    });

  return inflight;
}
