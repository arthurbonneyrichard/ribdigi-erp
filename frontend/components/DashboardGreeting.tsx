'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { formatDate, formatTime } from '../lib/format';
import { getMe } from '../lib/meCache';
import { useCompanyFormat } from '../lib/useCompanyFormat';

/** Trial / active / grace state, from the retail dashboard or `/me` `subscription_status`. */
export type GreetingSubscription = {
  status?: string | null;
  trial_ends_at?: string | null;
  grace_ends_at?: string | null;
  days_remaining?: number | null;
};

function timeOfDay(hour: number): { greeting: string; sub: string; period: 'morning' | 'afternoon' | 'evening' } {
  if (hour < 12) return { greeting: 'Good morning', sub: 'A bright new day for your business.', period: 'morning' };
  if (hour < 18) return { greeting: 'Good afternoon', sub: 'Keep the momentum going strong.', period: 'afternoon' };
  return { greeting: 'Good evening', sub: "Here's how today wrapped up.", period: 'evening' };
}

function subStatus(sub?: GreetingSubscription | null) {
  const status = sub?.status;
  const days = sub?.days_remaining;
  const dayLabel = (n: number | null | undefined) => `${n ?? 0} day${(n ?? 0) === 1 ? '' : 's'} left`;
  if (status === 'active') return { label: 'Active', cls: 'st-active' };
  if (status === 'trial') return { label: `Trial · ${dayLabel(days)}`, cls: 'st-trial' };
  if (status === 'grace') return { label: `Grace · ${dayLabel(days)} · read-only`, cls: 'st-grace' };
  if (status === 'suspended') return { label: 'Suspended', cls: 'st-suspended' };
  return null;
}

function GreetMark({ period }: { period: 'morning' | 'afternoon' | 'evening' }) {
  if (period === 'morning') {
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <circle cx="12" cy="12" r="5" fill="#F4C542" />
        <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M5.6 18.4l1.6-1.6M16.8 7.2l1.6-1.6" stroke="#F4C542" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
    );
  }
  if (period === 'afternoon') {
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <circle cx="9" cy="11" r="4.2" fill="#F4C542" />
        <path d="M8 17.5c1.8-2.6 6.8-2.8 8.8 0 2.2 0 3.7-1.6 3.7-3.4S19 10.7 16.9 10.7c-.4-2.2-2.3-3.8-4.6-3.8-1.4 0-2.7.6-3.5 1.6" fill="#E8F5D8" stroke="#4AB012" strokeWidth="1.4" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d="M15.2 4.2A7.6 7.6 0 1 0 20 14.6 6.4 6.4 0 0 1 15.2 4.2Z" fill="currentColor" />
    </svg>
  );
}

function greetingClockFace(now: Date, timeFormat: string | null | undefined) {
  const hours24 = now.getHours();
  const minutes = String(now.getMinutes()).padStart(2, '0');
  if (timeFormat === '12h') {
    const h12 = hours24 % 12 || 12;
    return { hours: String(h12), minutes, meridiem: hours24 < 12 ? 'AM' : 'PM' };
  }
  return { hours: String(hours24).padStart(2, '0'), minutes, meridiem: null as string | null };
}

type GreetingProps = {
  /** Desk chip, e.g. "Bakery dashboard". "Dashboard" (retail) shows only the Dashboard chip. */
  desk: string;
  /** Store or property shown after the company name. */
  place?: string;
  /** Company name, when the page already tracks it (retail refreshes it on a company switch). */
  company?: string;
  /** The retail dashboard passes its own; desks read `/me`. */
  subscription?: GreetingSubscription | null;
  /** Extra chips after the trial / grace chip (retail: returns). */
  chips?: string[];
  /** Notices under the greeting (retail: offline, loading, error). */
  children?: ReactNode;
  /** Render the hero alone, for a page that already wraps it in `.dash`. */
  bare?: boolean;
};

/** The one morning / afternoon / evening greeting every dashboard uses, retail and every desk. */
export default function DashboardGreeting({ desk, place, company, subscription, chips, children, bare }: GreetingProps) {
  const [now, setNow] = useState<Date | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [meSubscription, setMeSubscription] = useState<GreetingSubscription | null>(null);
  const formatPrefs = useCompanyFormat();

  useEffect(() => {
    getMe()
      .then((r) => {
        setCompanyName(String(r.data?.company_name || r.data?.tenant?.company_name || '').trim());
        setMeSubscription((r.data?.subscription_status as GreetingSubscription | undefined) || null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    let intervalId = 0;
    const delay = 60_000 - (Date.now() % 60_000);
    const timeoutId = window.setTimeout(() => {
      tick();
      intervalId = window.setInterval(tick, 60_000);
    }, delay);
    return () => {
      window.clearTimeout(timeoutId);
      window.clearInterval(intervalId);
    };
  }, []);

  const sub = subscription !== undefined ? subscription : meSubscription;
  const status = subStatus(sub);
  const tod = useMemo(() => timeOfDay(now ? now.getHours() : 9), [now]);
  const dateLabel = useMemo(() => (now ? formatDate(now, formatPrefs) : ''), [now, formatPrefs]);
  const dayName = useMemo(() => (now ? now.toLocaleDateString('en-GB', { weekday: 'long' }) : ''), [now]);
  const timeLabel = useMemo(() => (now ? formatTime(now, formatPrefs) : ''), [now, formatPrefs]);
  const clockFace = useMemo(
    () => (now ? greetingClockFace(now, formatPrefs?.time_format) : null),
    [now, formatPrefs],
  );
  const shownCompany = company !== undefined ? company.trim() : companyName;
  const placeLabel = (place || '').trim();
  const metaPlace = placeLabel && placeLabel !== shownCompany ? placeLabel : '';
  const deskLabel = (desk || '').trim();
  const chipList = [
    dayName,
    dateLabel,
    deskLabel && deskLabel !== 'Dashboard' ? deskLabel : '',
    sub?.status === 'trial' && sub?.trial_ends_at ? `Trial ends ${formatDate(sub.trial_ends_at, formatPrefs)}` : '',
    sub?.status === 'grace' && sub?.grace_ends_at ? `Grace period ends ${formatDate(sub.grace_ends_at, formatPrefs)}` : '',
    ...(chips || []),
  ].filter(Boolean);

  const hero = (
    <section className="dash-hero desk-greet" data-period={tod.period} aria-label="Dashboard greeting">
      <div className="sun" aria-hidden="true" />
      <div className="cloud" aria-hidden="true" />
      <div className="cloud c2" aria-hidden="true" />
      <div className="dash-hero-top">
        {status && (
          <span className={`status-pill ${status.cls}`}>
            <span className="st-dot" aria-hidden="true" /> {status.label}
          </span>
        )}
        {(shownCompany || metaPlace) && (
          <p className="greet-meta">
            {shownCompany || 'Company'}
            {metaPlace ? ` · ${metaPlace}` : ''}
          </p>
        )}
      </div>
      <div className="greet-row">
        <div className="greet-copy">
          <h1 className="greet">
            <span className="greet-hello">{tod.greeting}</span>
            <span className="wave" aria-hidden="true">
              <GreetMark period={tod.period} />
            </span>
          </h1>
          <p className="greet-sub">{tod.sub}</p>
          <p className="greet-date">
            {chipList.map((chip, i) => (
              <span className="greet-chip" key={`${i}-${chip}`}>
                {chip}
              </span>
            ))}
            <span className="greet-chip is-desk">Dashboard</span>
          </p>
        </div>
        <div className="greet-side">
          {timeLabel && clockFace ? (
            <div className="greet-clock">
              <span className="greet-clock-kicker" aria-hidden="true">Local time</span>
              <time
                className="greet-time"
                dateTime={now ? now.toISOString() : undefined}
                aria-label={`Dashboard greeting time, ${timeLabel}`}
              >
                <span className="greet-face" aria-hidden="true">
                  <span className="greet-digit">{clockFace.hours}</span>
                  <span className="greet-colon">:</span>
                  <span className="greet-digit">{clockFace.minutes}</span>
                </span>
                {clockFace.meridiem ? (
                  <span className="greet-meridiem" aria-hidden="true">{clockFace.meridiem}</span>
                ) : null}
              </time>
            </div>
          ) : null}
        </div>
      </div>
      {children}
    </section>
  );

  if (bare) return hero;
  return (
    <div className="dash" style={{ marginBottom: 16 }}>
      {hero}
    </div>
  );
}
