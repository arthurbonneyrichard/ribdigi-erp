'use client';

import { useEffect, useState } from 'react';
import { HOTEL_GUIDES } from '../lib/hotelGuides';

const KEY = 'ribdigi.hotelGuide.closed.';

function readClosed(id: string) {
  try {
    return window.localStorage.getItem(KEY + id) === '1';
  } catch {
    return false;
  }
}

function saveClosed(id: string, closed: boolean) {
  try {
    if (closed) window.localStorage.setItem(KEY + id, '1');
    else window.localStorage.removeItem(KEY + id);
  } catch {
    /* A blocked browser store only means the guide opens again next time. */
  }
}

/** "How this works" under a hotel feature. Open at first; stays closed once the person closes it. */
export default function HotelGuide({ id }: { id: string }) {
  const guide = HOTEL_GUIDES[id];
  const [open, setOpen] = useState(true);

  useEffect(() => {
    setOpen(!readClosed(id));
  }, [id]);

  if (!guide) return null;
  return (
    <section className={`hguide${open ? ' is-open' : ''}`} aria-label={`How this works: ${id.replace(/-/g, ' ')}`}>
      <button
        type="button"
        className="hguide-toggle"
        aria-expanded={open}
        onClick={() => {
          saveClosed(id, open);
          setOpen(!open);
        }}
      >
        <span aria-hidden="true">?</span>
        {open ? 'Hide help' : 'How this works'}
      </button>
      {open && (
        <div className="hguide-body">
          <p className="hguide-what">{guide.what}</p>
          <ol className="hguide-steps">
            {guide.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          {guide.tip ? <p className="hguide-tip">{guide.tip}</p> : null}
        </div>
      )}
    </section>
  );
}
