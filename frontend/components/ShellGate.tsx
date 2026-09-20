'use client';

import { usePathname } from 'next/navigation';
import Shell from './Shell';

/** Routes that render without the app chrome (sign-in and recovery). */
const AUTH_PREFIXES = ['/forgot-password', '/reset-password', '/verify-email'];

function isAuthRoute(pathname: string | null): boolean {
  const path = (pathname || '/').split('?')[0] || '/';
  if (path === '/') return true;
  return AUTH_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

/**
 * Keep one Shell mounted across dashboard navigations so the sidebar stays
 * static when moving from Platform to Staff (and other app pages).
 */
export default function ShellGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (isAuthRoute(pathname)) {
    return <>{children}</>;
  }
  return <Shell>{children}</Shell>;
}
