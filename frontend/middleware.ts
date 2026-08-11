import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Stage 87 Z1 — console boundary hardening.
 * Uses `ribdigi_principal` cookie set at login (localStorage alone is not visible here).
 */
const PUBLIC_PREFIXES = [
  '/',
  '/register',
  '/reset-password',
  '/verify-email',
];

const TENANT_ERP_PREFIXES = [
  '/dashboard',
  '/company',
  '/inventory',
  '/sales',
  '/pos',
  '/purchasing',
  '/expenses',
  '/accounting',
  '/credit',
  '/tax',
  '/stores',
  '/reports',
  '/notifications',
  '/audit',
  '/activity',
  '/backup',
  '/ai',
  '/users',
  '/admin',
];

function isPublic(path: string): boolean {
  if (path === '/') return true;
  return PUBLIC_PREFIXES.some((p) => p !== '/' && (path === p || path.startsWith(`${p}/`)));
}

function isTenantErp(path: string): boolean {
  return TENANT_ERP_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));
}

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;
  if (isPublic(path) || path.startsWith('/_next') || path.startsWith('/api')) {
    return NextResponse.next();
  }
  // Shared security surface for MFA enrollment (both principals)
  if (path === '/security' || path.startsWith('/security/')) {
    return NextResponse.next();
  }

  const principal = request.cookies.get('ribdigi_principal')?.value || '';
  if (principal === 'platform') {
    if (isTenantErp(path)) {
      return NextResponse.redirect(new URL('/platform/dashboard', request.url));
    }
  } else if (principal === 'tenant') {
    if (path === '/platform' || path.startsWith('/platform/')) {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
