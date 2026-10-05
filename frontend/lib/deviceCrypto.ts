/**
 * AES-GCM helpers for device-local secrets (auth tokens, offline queue).
 * Keys stay in IndexedDB; this is not a substitute for httpOnly cookies against XSS.
 */

const KEY_DB = 'ribdigi-device-crypto';
const KEY_STORE = 'keys';
const KEY_ID = 'aes-gcm-v1';

function openKeyDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(KEY_DB, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(KEY_STORE)) {
        req.result.createObjectStore(KEY_STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('crypto db open failed'));
  });
}

async function loadOrCreateKey(): Promise<CryptoKey> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('WebCrypto unavailable');
  }
  const db = await openKeyDb();
  const existing = await new Promise<CryptoKey | undefined>((resolve, reject) => {
    const tx = db.transaction(KEY_STORE, 'readonly');
    const req = tx.objectStore(KEY_STORE).get(KEY_ID);
    tx.oncomplete = () => {
      db.close();
      resolve(req.result as CryptoKey | undefined);
    };
    tx.onerror = () => {
      db.close();
      reject(req.error || tx.error);
    };
  });
  if (existing) return existing;
  const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, [
    'encrypt',
    'decrypt',
  ]);
  const writeDb = await openKeyDb();
  await new Promise<void>((resolve, reject) => {
    const tx = writeDb.transaction(KEY_STORE, 'readwrite');
    tx.objectStore(KEY_STORE).put(key, KEY_ID);
    tx.oncomplete = () => {
      writeDb.close();
      resolve();
    };
    tx.onerror = () => {
      writeDb.close();
      reject(tx.error);
    };
  });
  return key;
}

function bytesToB64(bytes: Uint8Array): string {
  let bin = '';
  bytes.forEach((b) => {
    bin += String.fromCharCode(b);
  });
  return btoa(bin);
}

function b64ToBytes(value: string): Uint8Array {
  const raw = atob(value);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  return copy.buffer;
}

export async function encryptJson(value: unknown): Promise<string> {
  const key = await loadOrCreateKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(JSON.stringify(value));
  const ct = new Uint8Array(
    await crypto.subtle.encrypt({ name: 'AES-GCM', iv: toArrayBuffer(iv) }, key, toArrayBuffer(encoded))
  );
  return `v1.${bytesToB64(iv)}.${bytesToB64(ct)}`;
}

export async function decryptJson<T>(blob: string): Promise<T> {
  const parts = String(blob || '').split('.');
  if (parts.length !== 3 || parts[0] !== 'v1') {
    throw new Error('Unsupported ciphertext');
  }
  const key = await loadOrCreateKey();
  const iv = b64ToBytes(parts[1]);
  const ct = b64ToBytes(parts[2]);
  const pt = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: toArrayBuffer(iv) },
    key,
    toArrayBuffer(ct)
  );
  return JSON.parse(new TextDecoder().decode(pt)) as T;
}

export function webCryptoAvailable(): boolean {
  return typeof crypto !== 'undefined' && Boolean(crypto.subtle);
}

const PASSPHRASE_ITERATIONS = 210_000;

async function passphraseKey(passphrase: string, salt: Uint8Array, iterations: number): Promise<CryptoKey> {
  const base = await crypto.subtle.importKey(
    'raw',
    toArrayBuffer(new TextEncoder().encode(passphrase)),
    'PBKDF2',
    false,
    ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt: toArrayBuffer(salt), iterations },
    base,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

export type PassphraseCiphertext = {
  alg: 'PBKDF2-SHA256/AES-GCM-256';
  iterations: number;
  salt: string;
  iv: string;
  ciphertext: string;
};

/** Portable encryption for files that leave the device (the device key is non-extractable). */
export async function encryptWithPassphrase(value: unknown, passphrase: string): Promise<PassphraseCiphertext> {
  if (!passphrase || passphrase.length < 8) throw new Error('Use a passphrase of at least 8 characters');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await passphraseKey(passphrase, salt, PASSPHRASE_ITERATIONS);
  const ct = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: toArrayBuffer(iv) },
      key,
      toArrayBuffer(new TextEncoder().encode(JSON.stringify(value)))
    )
  );
  return {
    alg: 'PBKDF2-SHA256/AES-GCM-256',
    iterations: PASSPHRASE_ITERATIONS,
    salt: bytesToB64(salt),
    iv: bytesToB64(iv),
    ciphertext: bytesToB64(ct),
  };
}

export async function decryptWithPassphrase<T>(blob: PassphraseCiphertext, passphrase: string): Promise<T> {
  const key = await passphraseKey(passphrase, b64ToBytes(blob.salt), Number(blob.iterations) || PASSPHRASE_ITERATIONS);
  try {
    const pt = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: toArrayBuffer(b64ToBytes(blob.iv)) },
      key,
      toArrayBuffer(b64ToBytes(blob.ciphertext))
    );
    return JSON.parse(new TextDecoder().decode(pt)) as T;
  } catch {
    throw new Error('Wrong passphrase or damaged backup file');
  }
}
