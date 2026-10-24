/**
 * Company (tenant) sidebar logo loader.
 *
 * `GET /tenants/me/logo?v=<logo_version>` is cacheable for a year per version, so a
 * reload is served from the browser HTTP cache. Within the SPA one blob URL per
 * tenant+version is reused across route changes. The last version per tenant is
 * kept in localStorage (a non-secret hash) so the request can start before `/me`.
 */
import { apiRoot, getAccessToken, hydrateAuth } from './api';

const HINT_PREFIX = 'ribdigi.logoVersion.';
/** Server had a logo but sent no version (older API): fetch without `?v`. */
export const UNVERSIONED_LOGO = 'current';

const urls = new Map<string, string>();
const inflight = new Map<string, Promise<string | null>>();

function cacheKey(tenantId: string, version: string): string {
  return `${tenantId}:${version}`;
}

export function logoVersionFromMe(data: { has_logo?: boolean; logo_version?: string | null } | null | undefined): string | null {
  if (!data?.has_logo) return null;
  const v = String(data.logo_version || '').trim();
  return v || UNVERSIONED_LOGO;
}

export function logoVersionHint(tenantId: string | null): string | null {
  if (!tenantId || typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(HINT_PREFIX + tenantId) || null;
  } catch {
    return null;
  }
}

export function rememberLogoVersion(tenantId: string | null, version: string | null): void {
  if (!tenantId || typeof window === 'undefined') return;
  try {
    if (version) localStorage.setItem(HINT_PREFIX + tenantId, version);
    else localStorage.removeItem(HINT_PREFIX + tenantId);
  } catch {
    /* storage full or blocked: the logo still loads after /me */
  }
}

export function cachedCompanyLogoUrl(tenantId: string, version: string): string | null {
  return urls.get(cacheKey(tenantId, version)) || null;
}

function dropOtherVersions(tenantId: string, keep: string): void {
  Array.from(urls.keys()).forEach((key) => {
    if (key.startsWith(`${tenantId}:`) && key !== keep) {
      URL.revokeObjectURL(urls.get(key) as string);
      urls.delete(key);
    }
  });
}

export function loadCompanyLogo(tenantId: string, version: string): Promise<string | null> {
  const key = cacheKey(tenantId, version);
  const hit = urls.get(key);
  if (hit) return Promise.resolve(hit);
  const pending = inflight.get(key);
  if (pending) return pending;
  const run = (async () => {
    try {
      await hydrateAuth();
      const token = getAccessToken();
      if (!token) return null;
      const query = version === UNVERSIONED_LOGO ? '' : `?v=${encodeURIComponent(version)}`;
      const res = await fetch(`${apiRoot()}/tenants/me/logo${query}`, {
        headers: { Authorization: `Bearer ${token}`, 'X-Tenant-ID': tenantId },
        cache: 'default',
      });
      if (!res.ok) return null;
      const url = URL.createObjectURL(await res.blob());
      dropOtherVersions(tenantId, key);
      urls.set(key, url);
      return url;
    } catch {
      return null;
    } finally {
      inflight.delete(key);
    }
  })();
  inflight.set(key, run);
  return run;
}
