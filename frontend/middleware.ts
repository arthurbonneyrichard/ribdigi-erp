import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Stage 87 Z1 + SEC-M5 Phase D — console boundary.
 *
 * Phase D: do **not** trust the legacy JS-writable `ribdigi_principal` cookie
 * as an auth or console boundary (it was UX-only and forgeable). Principal and
 * console routing are enforced by authenticated `GET /me` in Shell /
 * PlatformShell plus backend platform-vs-tenant checks.
 *
 * Middleware only clears a stale principal cookie when present so it cannot
 * linger as a misleading signal.
 */
const PUBLIC_PREFIXES = [
  '/',
  '/register',
  '/reset-password',
  '/verify-email',
];

function isPublic(path: string): boolean {
  if (path === '/') return true;
  return PUBLIC_PREFIXES.some((p) => p !== '/' && (path === p || path.startsWith(`${p}/`)));
}

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (isPublic(path) || path.startsWith('/_next') || path.startsWith('/api')) {
    return NextResponse.next();
  }

  const res = NextResponse.next();
  if (request.cookies.has('ribdigi_principal')) {
    res.cookies.set({
      name: 'ribdigi_principal',
      value: '',
      path: '/',
      maxAge: 0,
    });
  }
  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
