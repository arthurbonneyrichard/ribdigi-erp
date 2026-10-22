import { NextRequest, NextResponse } from 'next/server';

const ERP_HOSTS = new Set(
  (process.env.NEXT_PUBLIC_ERP_HOSTS || 'localhost,127.0.0.1,erp.ribdigihouse.com')
    .split(',')
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean),
);

const PASS_PREFIXES = ['/_next', '/api', '/brand', '/favicon', '/icon', '/apple-icon', '/manifest', '/sw.js'];

function hostnameOf(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-host');
  const raw = (forwarded || request.headers.get('host') || '').split(',')[0].trim().toLowerCase();
  return raw.split(':')[0];
}

export function middleware(request: NextRequest) {
  const host = hostnameOf(request);
  if (!host || ERP_HOSTS.has(host)) return NextResponse.next();
  const path = request.nextUrl.pathname;
  if (PASS_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`))) {
    return NextResponse.next();
  }
  if (path === '/storefront' || path.startsWith('/storefront/')) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  url.pathname = '/storefront';
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image).*)'],
};
