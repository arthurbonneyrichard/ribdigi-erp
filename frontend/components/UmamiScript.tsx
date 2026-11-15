'use client';

/**
 * Optional Umami analytics for the ERP UI.
 *
 * Off unless NEXT_PUBLIC_UMAMI_SRC and NEXT_PUBLIC_UMAMI_WEBSITE_ID are both set at frontend
 * image build time, and even then the script is added only after this browser has said yes to
 * analytics (lib/consent). Withdrawing consent stops it from loading on the next page load.
 * Query strings are excluded so reset links and other tokens are not stored.
 */
import { useEffect, useState } from 'react';
import { CONSENT_EVENT, analyticsAllowed } from '../lib/consent';

const DEFAULT_DOMAINS = 'erp.ribdigihouse.com';
const SCRIPT_ID = 'ribdigi-umami';

export default function UmamiScript() {
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    const update = () => setAllowed(analyticsAllowed());
    update();
    window.addEventListener(CONSENT_EVENT, update);
    return () => window.removeEventListener(CONSENT_EVENT, update);
  }, []);

  useEffect(() => {
    const websiteId = (process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '').trim();
    const src = (process.env.NEXT_PUBLIC_UMAMI_SRC || '').trim();
    const domains = (process.env.NEXT_PUBLIC_UMAMI_DOMAINS || DEFAULT_DOMAINS).trim();
    const existing = document.getElementById(SCRIPT_ID);
    if (!allowed || !websiteId || !src) {
      existing?.remove();
      return;
    }
    if (existing) return;
    const el = document.createElement('script');
    el.id = SCRIPT_ID;
    el.defer = true;
    el.src = src;
    el.setAttribute('data-website-id', websiteId);
    el.setAttribute('data-domains', domains);
    el.setAttribute('data-exclude-search', 'true');
    document.head.appendChild(el);
  }, [allowed]);

  return null;
}
