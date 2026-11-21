import { NextRequest, NextResponse } from 'next/server';
import { cspHeaders, cspMode, newNonce } from './lib/csp';

const ERP_HOSTS = new Set(
  (process.env.NEXT_PUBLIC_ERP_HOSTS || 'localhost,127.0.0.1,erp.ribdigihouse.com')
    .split(',')
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean),
);

const PASS_PREFIXES = ['/_next', '/api', '/brand', '/fonts', '/favicon', '/icon', '/apple-icon', '/manifest', '/sw.js'];

function hostnameOf(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-host');
  const raw = (forwarded || request.headers.get('host') || '').split(',')[0].trim().toLowerCase();
  return raw.split(':')[0];
}

/** Per-request nonce for scripts. Next.js reads it from the request's CSP header and stamps its own scripts. */
function withCsp(request: NextRequest, rewriteTo?: URL): NextResponse {
  const nonce = newNonce();
  const mode = cspMode(process.env.CSP_MODE, process.env.NODE_ENV === 'production');
  const { response, request: cspRequest } = cspHeaders(mode, nonce, process.env, process.env.NODE_ENV !== 'production');
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-nonce', nonce);
  for (const [name, value] of Object.entries(cspRequest)) requestHeaders.set(name, value);
  const init = { request: { headers: requestHeaders } };
  const res = rewriteTo ? NextResponse.rewrite(rewriteTo, init) : NextResponse.next(init);
  for (const [name, value] of Object.entries(response)) res.headers.set(name, value);
  return res;
}

export function proxy(request: NextRequest) {
  // Image optimizer is disabled (next.config images.unoptimized); refuse its endpoint outright.
  if (request.nextUrl.pathname.startsWith('/_next/image')) {
    return new NextResponse(null, { status: 404 });
  }
  const host = hostnameOf(request);
  if (!host || ERP_HOSTS.has(host)) return withCsp(request);
  const path = request.nextUrl.pathname;
  if (PASS_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) {
    return withCsp(request);
  }
  for (const open of ['/storefront', '/book', '/order', '/menu', '/stay', '/gym-member']) {
    if (path === open || path.startsWith(`${open}/`)) return withCsp(request);
  }
  const url = request.nextUrl.clone();
  url.pathname = '/storefront';
  return withCsp(request, url);
}

export const config = {
  matcher: ['/((?!_next/static).*)'],
};
