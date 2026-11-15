/**
 * Cookie and tracking consent for this browser.
 *
 * Only one optional category exists: analytics (Umami page statistics), and only when it is
 * configured at build time. Everything else the site keeps in the browser is needed to work
 * (sign-in, theme, the till's offline sales queue) and needs no consent.
 *
 * The choice is stored on this device with a version and a time, and can be changed at any
 * time from Cookie settings. Raising CONSENT_VERSION asks everyone again.
 */
export const CONSENT_VERSION = '2026-11-15';
const KEY = 'ribdigi:consent';
export const CONSENT_EVENT = 'ribdigi:consent-change';

export type ConsentChoice = {
  version: string;
  analytics: boolean;
  decided_at: string;
};

export function analyticsConfigured(): boolean {
  return Boolean(
    (process.env.NEXT_PUBLIC_UMAMI_SRC || '').trim() && (process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '').trim(),
  );
}

/** Optional categories that actually exist on this build. Empty means no banner is needed. */
export function optionalCategories(): Array<'analytics'> {
  return analyticsConfigured() ? ['analytics'] : [];
}

export function readConsent(): ConsentChoice | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ConsentChoice;
    if (!parsed || parsed.version !== CONSENT_VERSION) return null;
    return { version: parsed.version, analytics: parsed.analytics === true, decided_at: String(parsed.decided_at || '') };
  } catch {
    return null;
  }
}

export function saveConsent(choice: { analytics: boolean }): ConsentChoice {
  const value: ConsentChoice = {
    version: CONSENT_VERSION,
    analytics: choice.analytics === true,
    decided_at: new Date().toISOString(),
  };
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // Private windows can refuse storage; the choice then lasts for this page only.
  }
  try {
    window.dispatchEvent(new CustomEvent(CONSENT_EVENT, { detail: value }));
  } catch {
    // ignore
  }
  return value;
}

export function analyticsAllowed(): boolean {
  return analyticsConfigured() && readConsent()?.analytics === true;
}

export function openCookieSettings(): void {
  try {
    window.dispatchEvent(new CustomEvent('ribdigi:open-cookie-settings'));
  } catch {
    // ignore
  }
}
