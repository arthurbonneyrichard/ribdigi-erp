/** Per-user dark/light preference (browser-local). Not tenant-wide. */

export type ThemeMode = 'light' | 'dark';

/** Default dashboard theme for new users (and login when no preference). */
export const DEFAULT_THEME: ThemeMode = 'light';

const LEGACY_KEY = 'theme';
const ACTIVE_USER_KEY = 'ribdigi.theme.userId';

export function themeKeyForUser(userId: string): string {
  return `ribdigi.theme.${String(userId || '').trim()}`;
}

export function applyTheme(mode: ThemeMode): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', mode);
}

/** Apply and persist theme for one authenticated user only. */
export function writeUserTheme(userId: string, mode: ThemeMode): void {
  if (typeof localStorage === 'undefined') return;
  const id = String(userId || '').trim();
  if (!id || (mode !== 'light' && mode !== 'dark')) return;
  localStorage.setItem(themeKeyForUser(id), mode);
  localStorage.setItem(ACTIVE_USER_KEY, id);
  // Drop legacy global key so the next user on this browser cannot inherit it.
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(mode);
}

/**
 * Load theme for the signed-in user. Migrates a one-time legacy `theme` value
 * into that user's scoped key, then removes the global key.
 * New users (no saved preference) get light/white mode by default.
 */
export function loadUserTheme(userId: string): ThemeMode {
  if (typeof localStorage === 'undefined') return DEFAULT_THEME;
  const id = String(userId || '').trim();
  if (!id) {
    applyTheme(DEFAULT_THEME);
    return DEFAULT_THEME;
  }

  const scoped = localStorage.getItem(themeKeyForUser(id));
  if (scoped === 'light' || scoped === 'dark') {
    localStorage.setItem(ACTIVE_USER_KEY, id);
    applyTheme(scoped);
    return scoped;
  }

  const legacy = localStorage.getItem(LEGACY_KEY);
  if (legacy === 'light' || legacy === 'dark') {
    localStorage.setItem(themeKeyForUser(id), legacy);
    localStorage.removeItem(LEGACY_KEY);
    localStorage.setItem(ACTIVE_USER_KEY, id);
    applyTheme(legacy);
    return legacy;
  }

  // First login / no preference: white (light) dashboard by default.
  localStorage.setItem(themeKeyForUser(id), DEFAULT_THEME);
  localStorage.setItem(ACTIVE_USER_KEY, id);
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(DEFAULT_THEME);
  return DEFAULT_THEME;
}

/** After logout: forget active user and return UI to the light default. */
export function clearSessionTheme(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(ACTIVE_USER_KEY);
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(DEFAULT_THEME);
}
