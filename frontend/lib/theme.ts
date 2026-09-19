/** Per-user dark/light preference (browser-local). Not tenant-wide. */

export type ThemeMode = 'light' | 'dark';

const LEGACY_KEY = 'theme';
const ACTIVE_USER_KEY = 'ribdigi.theme.userId';

export function themeKeyForUser(userId: string): string {
  return `ribdigi.theme.${String(userId || '').trim()}`;
}

export function applyTheme(mode: ThemeMode): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', mode);
}

function systemTheme(): ThemeMode {
  return 'light';
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
 */
export function loadUserTheme(userId: string): ThemeMode {
  if (typeof localStorage === 'undefined') return 'light';
  const id = String(userId || '').trim();
  if (!id) return systemTheme();

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

  const mode = 'light';
  localStorage.setItem(themeKeyForUser(id), mode);
  localStorage.setItem(ACTIVE_USER_KEY, id);
  applyTheme(mode);
  return mode;
}

/** After logout: forget the active user and return the login page to the white theme. */
export function clearSessionTheme(): void {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem(ACTIVE_USER_KEY);
  localStorage.removeItem(LEGACY_KEY);
  applyTheme(systemTheme());
}
