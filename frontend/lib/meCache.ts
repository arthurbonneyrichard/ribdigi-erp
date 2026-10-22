/** Short-lived /me cache so sidebar navigations do not wait on a duplicate call. */

import { api, tenantHeaderValue } from './api';
import {
  invalidateCompanyFormatCache,
  rememberCurrency,
  rememberFormatPrefs,
  type FormatPrefs,
} from './format';

type MeBody = Awaited<ReturnType<typeof api>>;

let cached: { at: number; body: MeBody; tenant: string; key: string } | null = null;

export function meCacheKey(tenant: string, industry?: string | null): string {
  return `${tenant}::${industry || 'unset'}`;
}

function noteCurrency(body: MeBody) {
  const data = (body as { data?: ({ currency?: string | null } & FormatPrefs) | null } | null)?.data;
  if (!data) return;
  if (typeof data.currency === 'string') rememberCurrency(data.currency);
  rememberFormatPrefs({
    date_format: data.date_format,
    decimal_separator: data.decimal_separator,
    thousand_separator: data.thousand_separator,
    time_format: data.time_format,
  });
}

function industryOf(body: MeBody): string {
  const data = (body as { data?: { industry?: string | null } } | null)?.data;
  return typeof data?.industry === 'string' ? data.industry : '';
}
let inflight: Promise<MeBody> | null = null;
let inflightTenant = '';
let epoch = 0;

const TTL_MS = 20_000;

function activeTenant(): string {
  if (typeof window === 'undefined') return '';
  return tenantHeaderValue(localStorage.getItem('tenant')) || '';
}

export function invalidateMeCache() {
  epoch += 1;
  cached = null;
  inflight = null;
  inflightTenant = '';
  invalidateCompanyFormatCache();
}

export async function getMe(options?: { force?: boolean }): Promise<MeBody> {
  const force = Boolean(options?.force);
  const tenant = activeTenant();
  const seen = epoch;
  if (!force && cached && cached.tenant === tenant && Date.now() - cached.at < TTL_MS) {
    noteCurrency(cached.body);
    return cached.body;
  }
  if (!force && inflight && inflightTenant === tenant) return inflight;

  inflightTenant = tenant;
  inflight = api('/me')
    .then((body) => {
      if (seen !== epoch || activeTenant() !== tenant) return body;
      noteCurrency(body);
      if (activeTenant() === tenant) {
        cached = { at: Date.now(), body, tenant, key: meCacheKey(tenant, industryOf(body)) };
      }
      return body;
    })
    .finally(() => {
      if (seen === epoch) {
        inflight = null;
        inflightTenant = '';
      }
    });

  return inflight;
}
