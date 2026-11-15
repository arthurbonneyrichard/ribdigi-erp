'use client';

import Link from 'next/link';
import { openCookieSettings } from '../lib/consent';

/** Links to every policy, plus Cookie settings. Used on sign-in screens, legal pages and the app footer. */
export default function LoginLegalLinks({ className = 'login-legal' }: { className?: string }) {
  return (
    <nav className={className} aria-label="Legal">
      <Link href="/legal/terms">Terms of Service</Link>
      <Link href="/legal/privacy">Privacy Policy</Link>
      <Link href="/legal/refunds">Refund Policy</Link>
      <Link href="/legal/cookies">Cookie Policy</Link>
      <button type="button" className="legal-link-btn" onClick={openCookieSettings}>
        Cookie settings
      </button>
    </nav>
  );
}
