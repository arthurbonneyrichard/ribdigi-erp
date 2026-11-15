import type { Metadata } from 'next';
import LegalDoc from '../LegalDoc';
import CookieSettingsButton from '../../../components/CookieSettingsButton';
import { analyticsConfigured } from '../../../lib/consent';

export const metadata: Metadata = {
  title: 'Cookie Policy · RIBDIGI ERP',
};

export default function CookiesPage() {
  return (
    <LegalDoc title="Cookie Policy">
      <p>
        Effective 15 November 2026. RIBDIGI ERP does not set cookies. It keeps a few things in your browser&apos;s
        own storage (local storage) on this device so the app works. This page lists all of them. There is no
        advertising, no cross-site tracking and no third-party cookies.
      </p>

      <h2>Essential storage (always on)</h2>
      <p>The site cannot work without these, so they need no consent and cannot be switched off.</p>
      <ul>
        <li><strong>Sign-in:</strong> your sign-in tokens and the company you are signed in to. Removed when you sign out.</li>
        <li><strong>Security:</strong> the time of your last activity, so an idle session signs out; till lock and kiosk state.</li>
        <li>
          <strong>Till offline queue:</strong> sales taken while the internet is down, kept until they are sent, on
          the device that took them only.
        </li>
        <li><strong>Online shop:</strong> the cart and, if you signed in as a shopper, that sign-in, on a company&apos;s online shop on that device.</li>
      </ul>

      <h2>Preference storage (always on)</h2>
      <p>
        Your light or dark theme, the menu&apos;s open or closed state, the store you last picked, and the choice you
        make on this page. They only remember what you chose, are never sent to anyone, and you can remove them by
        clearing this site&apos;s data in your browser.
      </p>

      <h2>Analytics (only with your consent)</h2>
      <p>
        Ribdigi House can turn on Umami, a privacy-friendly page counter that it runs itself. It uses no cookies, does
        not record the part of the address after &quot;?&quot; (where reset links and similar tokens live), and does
        not collect your name or email. It loads only after you say yes in the cookie banner or in Cookie settings,
        and stops when you withdraw that consent.{' '}
        {analyticsConfigured()
          ? 'It is turned on for this site, so you are asked before it loads.'
          : 'It is currently turned off, so no banner is shown.'}
      </p>

      <h2>How long it stays</h2>
      <p>
        Session items (such as sign-in) end when you sign out or the session expires. Preferences, your cookie choice
        and the offline queue stay until you change them, the queue is sent, or you clear the site&apos;s data. Your
        cookie choice is saved with the date and the version of this policy; if the policy changes in a way that
        needs a new choice, you are asked again.
      </p>

      <h2>Changing your choice</h2>
      <p>
        Use the button below or the &quot;Cookie settings&quot; link at the foot of any page. You can also clear this
        site&apos;s data in your browser settings, which removes everything listed here and signs you out.
      </p>
      <CookieSettingsButton />

      <h2>Font</h2>
      <p>
        The site&apos;s font (Plus Jakarta Sans) is served from our own server, so loading a page does not contact any
        font service.
      </p>
    </LegalDoc>
  );
}
