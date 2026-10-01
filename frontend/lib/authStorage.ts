/**
 * Access/refresh tokens live in memory + encrypted IndexedDB.
 * They are never written to localStorage. Tenant id (UUID only) may stay in localStorage
 * for the X-Tenant-ID header.
 */

import { decryptJson, encryptJson, webCryptoAvailable } from './deviceCrypto';

const AUTH_DB = 'ribdigi-session-auth';
const AUTH_STORE = 'kv';
const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';

let accessMem: string | null = null;
let refreshMem: string | null = null;
let hydrated = false;
let hydratePromise: Promise<void> | null = null;

function openAuthDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(AUTH_DB, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(AUTH_STORE)) {
        req.result.createObjectStore(AUTH_STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('auth db open failed'));
  });
}

async function idbGet(key: string): Promise<string | null> {
  try {
    const db = await openAuthDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(AUTH_STORE, 'readonly');
      const req = tx.objectStore(AUTH_STORE).get(key);
      req.onsuccess = () => resolve((req.result as string | undefined) || null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null;
  }
}

async function idbPut(key: string, value: string): Promise<void> {
  const db = await openAuthDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(AUTH_STORE, 'readwrite');
    tx.objectStore(AUTH_STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbDel(key: string): Promise<void> {
  try {
    const db = await openAuthDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(AUTH_STORE, 'readwrite');
      tx.objectStore(AUTH_STORE).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* ignore */
  }
}

async function persistSecret(key: string, raw: string | null): Promise<void> {
  if (!raw) {
    await idbDel(key);
    return;
  }
  if (webCryptoAvailable()) {
    await idbPut(key, await encryptJson(raw));
    return;
  }
  await idbPut(key, raw);
}

async function readSecret(key: string): Promise<string | null> {
  const blob = await idbGet(key);
  if (!blob) return null;
  if (blob.startsWith('v1.') && webCryptoAvailable()) {
    try {
      return await decryptJson<string>(blob);
    } catch {
      return null;
    }
  }
  return blob;
}

function stealLegacyLocalStorageTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === 'undefined') return { access: null, refresh: null };
  const access = localStorage.getItem('token');
  const refresh = localStorage.getItem('refresh_token');
  if (access) localStorage.removeItem('token');
  if (refresh) localStorage.removeItem('refresh_token');
  return { access, refresh };
}

export function getAccessTokenSync(): string | null {
  return accessMem;
}

export function getRefreshTokenSync(): string | null {
  return refreshMem;
}

export async function hydrateAuth(): Promise<void> {
  if (hydrated) return;
  if (hydratePromise) return hydratePromise;
  hydratePromise = (async () => {
    const legacy = stealLegacyLocalStorageTokens();
    accessMem = (await readSecret(ACCESS_KEY)) || legacy.access;
    refreshMem = (await readSecret(REFRESH_KEY)) || legacy.refresh;
    if (legacy.access) await persistSecret(ACCESS_KEY, accessMem);
    if (legacy.refresh) await persistSecret(REFRESH_KEY, refreshMem);
    hydrated = true;
  })().finally(() => {
    hydratePromise = null;
  });
  return hydratePromise;
}

export async function setAuthTokens(access: string, refresh?: string | null): Promise<void> {
  accessMem = access || null;
  if (refresh !== undefined) refreshMem = refresh || null;
  hydrated = true;
  await persistSecret(ACCESS_KEY, accessMem);
  if (refresh !== undefined) await persistSecret(REFRESH_KEY, refreshMem);
}

export async function clearAuthTokens(): Promise<void> {
  accessMem = null;
  refreshMem = null;
  hydrated = true;
  await idbDel(ACCESS_KEY);
  await idbDel(REFRESH_KEY);
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
  }
}
