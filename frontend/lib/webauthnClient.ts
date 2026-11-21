/** Browser-side helpers shared by every passkey / fingerprint prompt. */

export const WEBAUTHN_PROMPT_TIMEOUT_MS = 60_000;

export function webauthnSupported(): boolean {
  return typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials;
}

/** True when this device has its own fingerprint / face / PIN (Windows Hello, Touch ID, Android lock). */
export async function deviceBiometricAvailable(): Promise<boolean> {
  try {
    if (!webauthnSupported()) return false;
    const fn = (window.PublicKeyCredential as any).isUserVerifyingPlatformAuthenticatorAvailable;
    if (typeof fn !== 'function') return true; // cannot tell: let the browser decide
    return !!(await fn.call(window.PublicKeyCredential));
  } catch {
    return true;
  }
}

export const NO_BIOMETRIC_MESSAGE =
  'This device has no fingerprint, face or PIN set up for sign-in. On Windows turn on Windows Hello (Settings → Accounts → Sign-in options); on a phone set a screen lock with fingerprint or face. You can still sign in with your password.';

/** A signal that aborts after the prompt timeout, so a forgotten prompt never hangs the page. */
export function promptAbort(ms = WEBAUTHN_PROMPT_TIMEOUT_MS): { signal: AbortSignal; done: () => void } {
  const ctl = new AbortController();
  const timer = window.setTimeout(() => ctl.abort(), ms);
  return { signal: ctl.signal, done: () => window.clearTimeout(timer) };
}

/**
 * Turn the browser's WebAuthn errors into something a person can act on. The browser deliberately
 * reports "cancelled", "timed out" and "no matching passkey" as the same NotAllowedError.
 */
export function describeWebAuthnError(err: any, what: 'register' | 'signin'): string {
  const name = String(err?.name || '');
  if (name === 'AbortError') {
    return 'The fingerprint prompt timed out. Tap the button and try again, or sign in with your password.';
  }
  if (name === 'NotAllowedError') {
    return what === 'register'
      ? 'The fingerprint prompt was cancelled, timed out, or this device has no fingerprint, face or PIN set up. Set one up (Windows Hello on Windows, screen lock on a phone), then tap the button and approve the prompt within a minute.'
      : 'The prompt was cancelled or timed out, or this device does not hold your fingerprint sign-in. Try again and approve the prompt. If you enabled fingerprint on another device or browser, enable it here too (Security → Enable fingerprint / face on this device), or sign in with your password.';
  }
  if (name === 'InvalidStateError') {
    return 'Fingerprint sign-in is already set up on this device.';
  }
  if (name === 'SecurityError') {
    return 'The browser refused because the site address does not match the passkey settings. Open the site at its normal https address and try again.';
  }
  if (name === 'NotSupportedError') {
    return 'This browser or device cannot use fingerprint / passkeys. Use Chrome or Edge, or sign in with your password.';
  }
  const raw = String(err?.message || '');
  return raw || (what === 'register' ? 'Could not turn on fingerprint sign-in.' : 'Could not sign in with fingerprint. Use your password instead.');
}
