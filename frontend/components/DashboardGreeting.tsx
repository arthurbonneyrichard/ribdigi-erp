'use client';

import { useEffect, useMemo, useState } from 'react';
import { formatDate, formatTime } from '../lib/format';
import { getMe } from '../lib/meCache';
import { useCompanyFormat } from '../lib/useCompanyFormat';

function timeOfDay(hour: number): { greeting: string; sub: string; period: 'morning' | 'afternoon' | 'evening' } {
  if (hour < 12) return { greeting: 'Good morning', sub: 'A bright new day for your business.', period: 'morning' };
  if (hour < 18) return { greeting: 'Good afternoon', sub: 'Keep the momentum going strong.', period: 'afternoon' };
  return { greeting: 'Good evening', sub: "Here's how today wrapped up.", period: 'evening' };
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

/** Same morning / afternoon / evening hero as the retail company dashboard. */
export default function DashboardGreeting({ desk, place }: { desk: string; place?: string }) {
  const [now, setNow] = useState<Date | null>(null);
  const [signedInName, setSignedInName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const formatPrefs = useCompanyFormat();

  useEffect(() => {
    getMe()
      .then((r) => {
        setSignedInName(String(r.data?.full_name || '').trim());
        setCompanyName(String(r.data?.company_name || '').trim());
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

  const tod = useMemo(() => timeOfDay(now ? now.getHours() : 9), [now]);
  const dateLabel = useMemo(() => (now ? formatDate(now, formatPrefs) : ''), [now, formatPrefs]);
  const timeLabel = useMemo(() => (now ? formatTime(now, formatPrefs) : ''), [now, formatPrefs]);
  const clockFace = useMemo(
    () => (now ? greetingClockFace(now, formatPrefs?.time_format) : null),
    [now, formatPrefs],
  );
  const placeLabel = (place || '').trim();
  const metaPlace = placeLabel && placeLabel !== companyName ? placeLabel : '';

  return (
    <div className="dash" style={{ marginBottom: 16 }}>
      <section className="dash-hero" data-period={tod.period} aria-label="Dashboard greeting">
        <div className="sun" aria-hidden="true" />
        <div className="cloud" aria-hidden="true" />
        <div className="cloud c2" aria-hidden="true" />
        <div className="dash-hero-top">
          {(companyName || metaPlace) && (
            <p className="greet-meta">
              {companyName || 'Company'}
              {metaPlace ? ` · ${metaPlace}` : ''}
            </p>
          )}
        </div>
        <div className="greet-row">
          <div className="greet-copy">
            <h1 className="greet">
              <span className="greet-hello">{tod.greeting}</span>
              {signedInName ? <span className="greet-name">{signedInName}</span> : null}
              <span className="wave" aria-hidden="true">
                <GreetMark period={tod.period} />
              </span>
            </h1>
            <p className="greet-sub">{tod.sub}</p>
            <p className="greet-date">{[dateLabel, desk].filter(Boolean).join(' · ')}</p>
          </div>
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
      </section>
    </div>
  );
}
