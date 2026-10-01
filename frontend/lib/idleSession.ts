/** Client idle tracking. Stores only a timestamp — never tokens — in localStorage for cross-tab activity. */

export const LAST_ACTIVITY_KEY = 'ribdigi:lastActivity';
export const IDLE_WARN_LEAD_MS = 60_000;
export const ACTIVITY_THROTTLE_MS = 1_000;

export const ACTIVITY_EVENTS = [
  'mousedown',
  'keydown',
  'click',
  'touchstart',
  'input',
  'change',
  'submit',
  'wheel',
  'scroll',
] as const;

let lastWriteMs = 0;

export function readLastActivity(now = Date.now()): number {
  if (typeof window === 'undefined') return now;
  try {
    const raw = Number(localStorage.getItem(LAST_ACTIVITY_KEY) || 0);
    if (Number.isFinite(raw) && raw > 0) return raw;
  } catch {
    /* ignore quota / private mode */
  }
  return now;
}

export function bumpLastActivity(now = Date.now()): number {
  if (typeof window === 'undefined') return now;
  if (now - lastWriteMs < ACTIVITY_THROTTLE_MS) return readLastActivity(now);
  lastWriteMs = now;
  try {
    localStorage.setItem(LAST_ACTIVITY_KEY, String(now));
  } catch {
    /* ignore */
  }
  return now;
}

export function warnLeadMs(timeoutMs: number): number {
  return Math.min(IDLE_WARN_LEAD_MS, Math.max(15_000, Math.round(timeoutMs / 6)));
}

export function remainingIdleMs(timeoutMs: number, now = Date.now(), last = readLastActivity()): number {
  return last + timeoutMs - now;
}

export function shouldWarnIdle(timeoutMs: number, now = Date.now(), last = readLastActivity()): boolean {
  const left = remainingIdleMs(timeoutMs, now, last);
  return left > 0 && left <= warnLeadMs(timeoutMs);
}

export function isIdleExpired(timeoutMs: number, now = Date.now(), last = readLastActivity()): boolean {
  return now - last >= timeoutMs;
}

/** Reset throttle so tests (and Stay signed in) write immediately. */
export function resetIdleWriteThrottle() {
  lastWriteMs = 0;
}
