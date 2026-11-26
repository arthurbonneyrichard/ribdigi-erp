/**
 * Content-Security-Policy for the web app, built per request.
 *
 * Script policy: Next.js and our three small inline scripts carry a fresh nonce, so
 * 'unsafe-inline' is not needed for scripts. Styles still allow 'unsafe-inline' (inline style
 * attributes are used widely; script injection is the risk this closes).
 *
 * CSP_MODE (read by proxy.ts at run time):
 *   legacy       enforce the old policy with 'unsafe-inline' scripts. The default: nothing changes.
 *   report-only  enforce the old policy AND send the nonce policy as Report-Only, with violation reports.
 *   enforce      enforce the nonce policy only.
 */

export type CspMode = 'legacy' | 'report-only' | 'enforce';

export function cspMode(raw: string | undefined, isProduction: boolean): CspMode {
  const v = (raw || '').trim().toLowerCase();
  if (v === 'legacy' || v === 'report-only' || v === 'enforce') return v;
  return isProduction ? 'legacy' : 'report-only';
}

function analyticsOrigin(env: Record<string, string | undefined>): string {
  const src = (env.NEXT_PUBLIC_UMAMI_SRC || '').trim();
  if (!src || !(env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '').trim()) return '';
  try {
    return ` ${new URL(src).origin}`;
  } catch {
    return '';
  }
}

export const REPORT_PATH = '/api/csp-report';

const REST =
  "style-src 'self' 'unsafe-inline'; font-src 'self' data:; " +
  "img-src 'self' data: blob: https:; media-src 'self' blob:; connect-src 'self' https: wss: http://127.0.0.1:8765; frame-src 'self' https: blob:; " +
  "worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self' https:";

export function legacyPolicy(env: Record<string, string | undefined>): string {
  return `default-src 'self'; script-src 'self' 'unsafe-inline'${analyticsOrigin(env)}; ${REST}`;
}

export function noncePolicy(nonce: string, env: Record<string, string | undefined>, opts: { dev?: boolean; report?: boolean } = {}): string {
  // Dev server hot reload needs eval; production builds never do.
  const dev = opts.dev ? " 'unsafe-eval'" : '';
  const report = opts.report ? `; report-uri ${REPORT_PATH}` : '';
  return `default-src 'self'; script-src 'self' 'nonce-${nonce}'${dev}${analyticsOrigin(env)}; ${REST}${report}`;
}

export function newNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let s = '';
  for (let i = 0; i < bytes.length; i += 1) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

/** Private header the proxy uses to hand the enforced (old) policy to serve.cjs in report-only mode. */
export const ENFORCED_HANDOFF = 'x-csp-enforced';

/**
 * What to send on the response, and what Next.js should see on the request (it reads its script
 * nonce from the request's CSP header, and also copies response headers onto the request, so an
 * enforced old policy sitting in a response header would hide the nonce in report-only mode).
 * That is why report-only hands the old policy to serve.cjs, which sets it after rendering.
 */
export function cspHeaders(mode: CspMode, nonce: string, env: Record<string, string | undefined>, dev: boolean) {
  const strict = noncePolicy(nonce, env, { dev, report: mode !== 'enforce' });
  if (mode === 'enforce') {
    return { response: { 'Content-Security-Policy': strict } as Record<string, string>, request: { 'content-security-policy': strict } as Record<string, string> };
  }
  if (mode === 'legacy') {
    return { response: { 'Content-Security-Policy': legacyPolicy(env) } as Record<string, string>, request: {} as Record<string, string> };
  }
  return {
    response: { 'Content-Security-Policy-Report-Only': strict, [ENFORCED_HANDOFF]: legacyPolicy(env) } as Record<string, string>,
    request: { 'content-security-policy-report-only': strict } as Record<string, string>,
  };
}
