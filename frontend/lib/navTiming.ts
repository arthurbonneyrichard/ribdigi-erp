/** Lightweight first vs repeat navigation timings (devtools console). */

const SEEN_PREFIX = 'ribdigi-nav-seen:';

export function markPageLoad(route: string, kind: 'first' | 'repeat', ms: number) {
  if (typeof window === 'undefined') return;
  const rounded = Math.round(ms);
  try {
    console.info(`[ribdigi-nav] ${route} ${kind}=${rounded}ms`);
  } catch {
    /* ignore */
  }
  try {
    const key = `ribdigi-nav-last:${route}`;
    sessionStorage.setItem(key, JSON.stringify({ kind, ms: rounded, at: Date.now() }));
  } catch {
    /* ignore quota / private mode */
  }
}

export function pageLoadStarted(route: string): () => void {
  const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
  let seen = false;
  try {
    seen = sessionStorage.getItem(SEEN_PREFIX + route) === '1';
  } catch {
    seen = false;
  }
  return () => {
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
    markPageLoad(route, seen ? 'repeat' : 'first', now - t0);
    try {
      sessionStorage.setItem(SEEN_PREFIX + route, '1');
    } catch {
      /* ignore */
    }
  };
}
