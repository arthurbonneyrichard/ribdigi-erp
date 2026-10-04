/** Short-lived /me cache so sidebar navigations do not wait on a duplicate call. */

import { api } from './api';

type MeBody = Awaited<ReturnType<typeof api>>;

let cached: { at: number; body: MeBody } | null = null;
let inflight: Promise<MeBody> | null = null;

const TTL_MS = 20_000;

export function invalidateMeCache() {
  cached = null;
  inflight = null;
}

export async function getMe(options?: { force?: boolean }): Promise<MeBody> {
  const force = Boolean(options?.force);
  if (!force && cached && Date.now() - cached.at < TTL_MS) {
    return cached.body;
  }
  if (!force && inflight) return inflight;

  inflight = api('/me')
    .then((body) => {
      cached = { at: Date.now(), body };
      return body;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}
