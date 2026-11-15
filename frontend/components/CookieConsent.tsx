'use client';

/**
 * Cookie consent banner and settings dialog.
 *
 * The banner appears only when this build has an optional category (analytics) and the browser
 * has not chosen yet. "Accept all", "Reject non-essential" and "Customize" look the same and sit
 * side by side, so saying no is as easy as saying yes. The settings dialog opens from any
 * "Cookie settings" link (openCookieSettings) and from /legal/cookies.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { optionalCategories, readConsent, saveConsent } from '../lib/consent';
import './cookie-consent.css';

export default function CookieConsent() {
  const [bannerOpen, setBannerOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  const [saved, setSaved] = useState<string>('');
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const hasOptional = optionalCategories().length > 0;

  useEffect(() => {
    const current = readConsent();
    setAnalytics(current?.analytics === true);
    setSaved(current?.decided_at || '');
    setBannerOpen(hasOptional && !current);
    const open = () => {
      returnFocus.current = document.activeElement as HTMLElement | null;
      const now = readConsent();
      setAnalytics(now?.analytics === true);
      setSaved(now?.decided_at || '');
      setDialogOpen(true);
    };
    window.addEventListener('ribdigi:open-cookie-settings', open);
    return () => window.removeEventListener('ribdigi:open-cookie-settings', open);
  }, [hasOptional]);

  const close = useCallback(() => {
    setDialogOpen(false);
    window.setTimeout(() => returnFocus.current?.focus?.(), 0);
  }, []);

  useEffect(() => {
    if (!dialogOpen) return;
    const node = dialogRef.current;
    node?.querySelector<HTMLElement>('input, button')?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
        return;
      }
      if (e.key !== 'Tab' || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>('button, input, a[href]')).filter((el) => !el.hasAttribute('disabled'));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [dialogOpen, close]);

  function decide(value: boolean) {
    const choice = saveConsent({ analytics: value });
    setAnalytics(choice.analytics);
    setSaved(choice.decided_at);
    setBannerOpen(false);
  }

  function customize() {
    returnFocus.current = document.activeElement as HTMLElement | null;
    setBannerOpen(false);
    setDialogOpen(true);
  }

  return (
    <>
      {bannerOpen ? (
        <section className="cc-banner" role="region" aria-label="Cookie choices">
          <p className="cc-text">
            We use storage that the site needs to work, such as keeping you signed in. With your permission we also
            count page visits with privacy-friendly analytics. No advertising or cross-site tracking.{' '}
            <a href="/legal/cookies">Cookie Policy</a>
          </p>
          <div className="cc-actions">
            <button type="button" className="cc-btn" onClick={() => decide(true)}>Accept all</button>
            <button type="button" className="cc-btn" onClick={() => decide(false)}>Reject non-essential</button>
            <button type="button" className="cc-btn" onClick={customize}>Customize</button>
          </div>
        </section>
      ) : null}
      {dialogOpen ? (
        <div className="cc-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
          <div className="cc-dialog" role="dialog" aria-modal="true" aria-labelledby="cc-title" ref={dialogRef}>
            <h2 id="cc-title">Cookie settings</h2>
            <fieldset className="cc-cat">
              <legend>Essential</legend>
              <label className="cc-row">
                <input type="checkbox" checked disabled aria-describedby="cc-essential-help" />
                <span>Always on</span>
              </label>
              <p id="cc-essential-help" className="cc-help">
                Sign-in, security, your theme and menu choices, and the till&apos;s offline sales queue. The site does not
                work without them, so they cannot be switched off.
              </p>
            </fieldset>
            <fieldset className="cc-cat">
              <legend>Analytics</legend>
              {hasOptional ? (
                <>
                  <label className="cc-row">
                    <input
                      type="checkbox"
                      checked={analytics}
                      onChange={(e) => setAnalytics(e.target.checked)}
                      aria-describedby="cc-analytics-help"
                    />
                    <span>Allow page visit counts</span>
                  </label>
                  <p id="cc-analytics-help" className="cc-help">
                    Umami, run by Ribdigi House. Counts pages viewed, without cookies, without the address bar&apos;s
                    query part and without your name or email. Off unless you switch it on.
                  </p>
                </>
              ) : (
                <p className="cc-help">This site has no analytics turned on, so there is nothing to allow.</p>
              )}
            </fieldset>
            <fieldset className="cc-cat">
              <legend>Advertising</legend>
              <p className="cc-help">None. The site has no advertising or cross-site tracking.</p>
            </fieldset>
            {saved ? <p className="cc-help">Last saved {new Date(saved).toLocaleString()}.</p> : null}
            <div className="cc-actions">
              {hasOptional ? (
                <>
                  <button type="button" className="cc-btn" onClick={() => { decide(analytics); close(); }}>Save choices</button>
                  <button type="button" className="cc-btn" onClick={() => { decide(false); close(); }}>Reject non-essential</button>
                </>
              ) : null}
              <button type="button" className="cc-btn" onClick={close}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
