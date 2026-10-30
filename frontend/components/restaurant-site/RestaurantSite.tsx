'use client';

/**
 * A restaurant's public website: the menu, online food and drink orders (pickup or
 * delivery) with live tracking, and table bookings with an optional pre-order.
 * Served at /book/<slug> and /order/<slug>. Nothing is charged here; the guest pays
 * the restaurant when they collect, on delivery, or at the table.
 */

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiRoot } from '../../lib/api';
import { formatMoney } from '../../lib/format';
import './restaurant-site.css';

type MenuItem = {
  id: string;
  name: string;
  price: number;
  category: string;
  description?: string | null;
  has_image?: boolean;
  kind?: 'food' | 'drink';
};

type Site = {
  slug: string;
  company_name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  currency?: string;
  has_logo?: boolean;
  booking_open: boolean;
  ordering_open: boolean;
  delivery_zones: string[];
  service_percent?: number;
  menu: MenuItem[];
};

type Tracked = {
  id: string;
  order_number: string;
  status: string;
  status_words: string;
  service: 'pickup' | 'delivery';
  total_amount: number;
  items: { name: string; quantity: number; line_total: number }[];
};

type Panel = 'bag' | 'checkout' | 'tracking' | null;

const STEPS = [
  { key: 'open', label: 'Received' },
  { key: 'sent', label: 'In the kitchen' },
  { key: 'ready', label: 'Ready' },
  { key: 'completed', label: 'Done' },
];

const PAY = [
  { id: 'cash', label: 'Cash' },
  { id: 'mobile_money', label: 'Mobile Money' },
  { id: 'card', label: 'Card' },
] as const;

async function call(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${apiRoot()}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail;
    if (typeof detail === 'string') throw new Error(detail);
    if (Array.isArray(detail) && detail[0]?.msg) {
      const field = String(detail[0]?.loc?.slice(-1)[0] || '').replace(/_/g, ' ');
      throw new Error(field ? `Check the ${field}.` : String(detail[0].msg));
    }
    throw new Error('Something went wrong. Please try again.');
  }
  return body?.data;
}

/** "024 123 4567" → "+233241234567" for Ghana cedi restaurants; other numbers need the + code. */
function cleanPhone(raw: string, currency?: string) {
  const digits = raw.replace(/[\s\-().]/g, '');
  if (digits.startsWith('+')) return digits;
  if (digits.startsWith('00')) return `+${digits.slice(2)}`;
  if ((currency || 'GHS') === 'GHS' && /^0\d{9}$/.test(digits)) return `+233${digits.slice(1)}`;
  return digits;
}

function stepIndex(status: string) {
  if (status === 'preparing') return 1;
  const i = STEPS.findIndex((s) => s.key === status);
  return i < 0 ? 0 : i;
}

function initials(name: string) {
  const words = name.trim().split(/\s+/);
  return ((words[0]?.[0] || '') + (words[1]?.[0] || '')).toUpperCase() || 'R';
}

function todayLocal(offsetDays = 0) {
  const d = new Date(Date.now() + offsetDays * 86400000);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const TIMES = Array.from({ length: 27 }, (_, i) => {
  const minutes = 9 * 60 + i * 30; // 09:00 to 22:00
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
});

export default function RestaurantSite({ slug, focus }: { slug: string; focus: 'menu' | 'book' }) {
  const [site, setSite] = useState<Site | null>(null);
  const [loadError, setLoadError] = useState('');
  const [category, setCategory] = useState('');
  const [search, setSearch] = useState('');
  const [bag, setBag] = useState<Record<string, number>>({});
  const [panel, setPanel] = useState<Panel>(null);
  const [tracked, setTracked] = useState<Tracked | null>(null);
  const bookRef = useRef<HTMLElement | null>(null);
  const menuRef = useRef<HTMLElement | null>(null);
  const bagKey = `rsite.bag.${slug}`;
  const trackKey = `rsite.track.${slug}`;

  const money = useCallback((v: unknown) => formatMoney(Number(v || 0), null, site?.currency || 'GHS'), [site?.currency]);

  useEffect(() => {
    if (!slug) return;
    call(`/public/restaurant-site/${encodeURIComponent(slug)}`)
      .then((data) => setSite(data))
      .catch((err: Error) => setLoadError(err.message));
    try {
      const saved = JSON.parse(localStorage.getItem(bagKey) || '{}');
      if (saved && typeof saved === 'object') setBag(saved);
      const last = localStorage.getItem(trackKey);
      if (last) {
        call(`/public/restaurant-site/${encodeURIComponent(slug)}/order/${encodeURIComponent(last)}`)
          .then((data) => {
            if (data && !['completed', 'cancelled', 'voided', 'refunded'].includes(data.status)) setTracked(data);
          })
          .catch(() => undefined);
      }
    } catch {
      /* a private window has no storage; the bag simply starts empty */
    }
  }, [slug, bagKey, trackKey]);

  useEffect(() => {
    try {
      localStorage.setItem(bagKey, JSON.stringify(bag));
    } catch {
      /* ignore */
    }
  }, [bag, bagKey]);

  useEffect(() => {
    if (!site) return;
    const target = focus === 'book' && site.booking_open ? bookRef.current : null;
    if (target) window.setTimeout(() => target.scrollIntoView({ behavior: 'smooth', block: 'start' }), 200);
  }, [site, focus]);

  // Live tracking: refresh the order every 15 seconds until it is done.
  useEffect(() => {
    if (!tracked || ['completed', 'cancelled', 'voided', 'refunded'].includes(tracked.status)) return;
    const timer = window.setInterval(() => {
      call(`/public/restaurant-site/${encodeURIComponent(slug)}/order/${encodeURIComponent(tracked.id)}`)
        .then((data) => data && setTracked(data))
        .catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [tracked, slug]);

  const menu = site?.menu || [];
  const categories = useMemo(() => {
    const seen: string[] = [];
    for (const item of menu) if (!seen.includes(item.category)) seen.push(item.category);
    return seen;
  }, [menu]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return menu.filter(
      (item) =>
        (!category || item.category === category) &&
        (!q || `${item.name} ${item.description || ''}`.toLowerCase().includes(q)),
    );
  }, [menu, category, search]);

  const grouped = useMemo(() => {
    const out: { name: string; items: MenuItem[] }[] = [];
    for (const item of shown) {
      let group = out.find((g) => g.name === item.category);
      if (!group) {
        group = { name: item.category, items: [] };
        out.push(group);
      }
      group.items.push(item);
    }
    return out;
  }, [shown]);

  const bagLines = useMemo(
    () =>
      Object.entries(bag)
        .map(([id, qty]) => ({ item: menu.find((m) => m.id === id), qty }))
        .filter((l): l is { item: MenuItem; qty: number } => Boolean(l.item) && l.qty > 0),
    [bag, menu],
  );
  const bagCount = bagLines.reduce((n, l) => n + l.qty, 0);
  const bagTotal = bagLines.reduce((sum, l) => sum + l.qty * Number(l.item.price || 0), 0);

  function setQty(id: string, qty: number) {
    setBag((current) => {
      const next = { ...current };
      if (qty <= 0) delete next[id];
      else next[id] = Math.min(40, qty);
      return next;
    });
  }

  function imageUrl(item: MenuItem) {
    return `${apiRoot()}/public/restaurant-site/${encodeURIComponent(slug)}/menu/${encodeURIComponent(item.id)}/image`;
  }

  if (loadError) {
    return (
      <div className="rsite">
        <div className="rs-closed">
          <div className="rs-closed-mark" aria-hidden>
            ✕
          </div>
          <h1>This page is not open</h1>
          <p>{loadError}</p>
        </div>
      </div>
    );
  }

  if (!site) {
    return (
      <div className="rsite">
        <div className="rs-closed" aria-busy="true">
          <p>Opening the menu…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rsite">
      <header className="rs-top">
        <a className="rs-brand" href="#top" aria-label={`${site.company_name} home`}>
          {site.has_logo ? (
            <img src={`${apiRoot()}/public/restaurant-site/${encodeURIComponent(slug)}/logo`} alt="" />
          ) : (
            <span className="rs-mono" aria-hidden>
              {initials(site.company_name)}
            </span>
          )}
          <strong>{site.company_name}</strong>
        </a>
        <nav className="rs-links" aria-label="Sections">
          <a href="#menu">Menu</a>
          {site.booking_open ? <a href="#book">Book a table</a> : null}
          {site.phone ? <a href={`tel:${site.phone}`}>Call</a> : null}
        </nav>
        {site.ordering_open ? (
          <button type="button" className="rs-bag-btn" aria-label={`Open your bag, ${bagCount} items`} onClick={() => setPanel('bag')}>
            Your bag <span>{bagCount}</span>
          </button>
        ) : null}
      </header>

      <section className="rs-hero" id="top">
        <div className="rs-hero-text">
          <p className="rs-kicker">
            {site.ordering_open && site.booking_open
              ? 'Order online · Book a table'
              : site.ordering_open
                ? 'Order online'
                : 'Book a table'}
          </p>
          <h1>{site.company_name}</h1>
          <p className="rs-lede">
            {site.ordering_open
              ? 'Fresh food and cold drinks, ready for pickup or brought to your door.'
              : 'Have a look at the menu and save yourself a table.'}
            {site.booking_open ? ' Coming to eat with us? Book your table in a minute.' : ''}
          </p>
          <div className="rs-hero-cta">
            <button
              type="button"
              className="rs-btn rs-btn-main"
              onClick={() => menuRef.current?.scrollIntoView({ behavior: 'smooth' })}
            >
              {site.ordering_open ? 'Order food & drinks' : 'See the menu'}
            </button>
            {site.booking_open ? (
              <button
                type="button"
                className="rs-btn rs-btn-ghost"
                onClick={() => bookRef.current?.scrollIntoView({ behavior: 'smooth' })}
              >
                Book a table
              </button>
            ) : null}
          </div>
          <ul className="rs-facts">
            {site.ordering_open ? <li>Pickup & delivery</li> : null}
            <li>Pay when you get your food</li>
            {site.address ? <li>{site.address}</li> : null}
          </ul>
        </div>
        <div className="rs-hero-art" aria-hidden>
          {menu
            .filter((m) => m.has_image)
            .slice(0, 3)
            .map((m, i) => (
              <img key={m.id} className={`rs-plate p${i}`} src={imageUrl(m)} alt="" />
            ))}
          {menu.filter((m) => m.has_image).length === 0 ? (
            <div className="rs-hero-badge">
              <span>{menu.length}</span>
              dishes & drinks
            </div>
          ) : null}
        </div>
      </section>

      {tracked ? (
        <button type="button" className="rs-track-strip" onClick={() => setPanel('tracking')}>
          <span className="rs-pulse" aria-hidden />
          Order {tracked.order_number}: <strong>{tracked.status_words}</strong>
          <span className="rs-track-link">Follow your order →</span>
        </button>
      ) : null}

      <section className="rs-menu" id="menu" ref={menuRef} aria-label="Menu">
        <div className="rs-menu-head">
          <h2>Menu</h2>
          <input
            className="rs-search"
            type="search"
            placeholder="Search the menu"
            aria-label="Search the menu"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {!site.ordering_open ? (
          <p className="rs-note">Online orders are closed right now. {site.booking_open ? 'You can still book a table.' : ''}</p>
        ) : null}
        <div className="rs-cats" role="tablist" aria-label="Menu sections">
          <button type="button" role="tab" aria-selected={!category} className={!category ? 'on' : ''} onClick={() => setCategory('')}>
            All
          </button>
          {categories.map((c) => (
            <button key={c} type="button" role="tab" aria-selected={category === c} className={category === c ? 'on' : ''} onClick={() => setCategory(c)}>
              {c}
            </button>
          ))}
        </div>

        {grouped.length === 0 ? <p className="rs-note">{menu.length ? 'Nothing matches that search.' : 'The menu is being prepared. Check back soon.'}</p> : null}
        {grouped.map((group) => (
          <div key={group.name} className="rs-group">
            <h3>{group.name}</h3>
            <div className="rs-grid">
              {group.items.map((item) => {
                const qty = bag[item.id] || 0;
                return (
                  <article key={item.id} className={`rs-dish${qty ? ' in' : ''}`}>
                    <div className={`rs-dish-pic${item.has_image ? '' : ' noimg'}`}>
                      {item.has_image ? (
                        <img src={imageUrl(item)} alt={item.name} loading="lazy" />
                      ) : (
                        <span className={`rs-dish-mono ${item.kind || 'food'}`} aria-hidden>
                          {item.name.slice(0, 1)}
                        </span>
                      )}
                      {item.kind === 'drink' ? <span className="rs-tag">Drink</span> : null}
                    </div>
                    <div className="rs-dish-body">
                      <h4>{item.name}</h4>
                      {item.description ? <p>{item.description}</p> : null}
                      <div className="rs-dish-foot">
                        <strong>{money(item.price)}</strong>
                        {site.ordering_open ? (
                          qty ? (
                            <div className="rs-step" aria-label={`${item.name} in your bag`}>
                              <button type="button" aria-label={`One less ${item.name}`} onClick={() => setQty(item.id, qty - 1)}>
                                −
                              </button>
                              <span>{qty}</span>
                              <button type="button" aria-label={`One more ${item.name}`} onClick={() => setQty(item.id, qty + 1)}>
                                +
                              </button>
                            </div>
                          ) : (
                            <button type="button" className="rs-add" aria-label={`Add ${item.name}`} onClick={() => setQty(item.id, 1)}>
                              Add +
                            </button>
                          )
                        ) : null}
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        ))}
      </section>

      {site.booking_open ? (
        <section className="rs-book" id="book" ref={bookRef} aria-label="Book a table">
          <BookingForm site={site} bagLines={bagLines} money={money} onBooked={(preOrdered) => preOrdered && setBag({})} />
        </section>
      ) : null}

      <footer className="rs-foot">
        <div>
          <strong>{site.company_name}</strong>
          {site.address ? <p>{site.address}</p> : null}
          <p>
            {site.phone ? <a href={`tel:${site.phone}`}>{site.phone}</a> : null}
            {site.phone && site.email ? ' · ' : ''}
            {site.email ? <a href={`mailto:${site.email}`}>{site.email}</a> : null}
          </p>
        </div>
        <p className="rs-powered">Online ordering by RIBDIGI ERP</p>
      </footer>

      {site.ordering_open && bagCount > 0 && !panel ? (
        <button type="button" className="rs-float" onClick={() => setPanel('bag')}>
          <span>{bagCount} in your bag</span>
          <strong>View bag · {money(bagTotal)}</strong>
        </button>
      ) : null}

      {panel ? (
        <div className="rs-scrim" role="dialog" aria-modal="true" aria-label="Your order" onClick={() => setPanel(null)}>
          <aside className="rs-sheet" onClick={(e) => e.stopPropagation()}>
            {panel === 'bag' ? (
              <BagPanel
                lines={bagLines}
                total={bagTotal}
                money={money}
                servicePercent={Number(site.service_percent || 0)}
                onQty={setQty}
                onClose={() => setPanel(null)}
                onCheckout={() => setPanel('checkout')}
              />
            ) : null}
            {panel === 'checkout' ? (
              <CheckoutPanel
                site={site}
                lines={bagLines}
                total={bagTotal}
                money={money}
                onBack={() => setPanel('bag')}
                onPlaced={(order) => {
                  setTracked(order);
                  setBag({});
                  try {
                    localStorage.setItem(trackKey, order.id);
                  } catch {
                    /* ignore */
                  }
                  setPanel('tracking');
                }}
              />
            ) : null}
            {panel === 'tracking' && tracked ? <TrackingPanel order={tracked} money={money} site={site} onClose={() => setPanel(null)} /> : null}
          </aside>
        </div>
      ) : null}
    </div>
  );
}

function BagPanel({
  lines,
  total,
  money,
  servicePercent,
  onQty,
  onClose,
  onCheckout,
}: {
  lines: { item: MenuItem; qty: number }[];
  total: number;
  money: (v: unknown) => string;
  servicePercent: number;
  onQty: (id: string, qty: number) => void;
  onClose: () => void;
  onCheckout: () => void;
}) {
  return (
    <>
      <div className="rs-sheet-head">
        <h2>Your bag</h2>
        <button type="button" className="rs-x" aria-label="Close bag" onClick={onClose}>
          ✕
        </button>
      </div>
      {lines.length === 0 ? (
        <p className="rs-note">Your bag is empty. Add something from the menu.</p>
      ) : (
        <ul className="rs-lines">
          {lines.map(({ item, qty }) => (
            <li key={item.id}>
              <div>
                <strong>{item.name}</strong>
                <span>{money(item.price)} each</span>
              </div>
              <div className="rs-step small">
                <button type="button" aria-label={`One less ${item.name}`} onClick={() => onQty(item.id, qty - 1)}>
                  −
                </button>
                <span>{qty}</span>
                <button type="button" aria-label={`One more ${item.name}`} onClick={() => onQty(item.id, qty + 1)}>
                  +
                </button>
              </div>
              <b>{money(qty * Number(item.price || 0))}</b>
            </li>
          ))}
        </ul>
      )}
      <div className="rs-total">
        <span>Food & drinks</span>
        <strong>{money(total)}</strong>
      </div>
      <p className="rs-small">
        {servicePercent > 0 ? `Tax and a ${servicePercent}% service charge are` : 'Tax is'} added by the restaurant. You pay
        when you get your food.
      </p>
      <button type="button" className="rs-btn rs-btn-main rs-wide" disabled={!lines.length} onClick={onCheckout}>
        Continue
      </button>
    </>
  );
}

function CheckoutPanel({
  site,
  lines,
  total,
  money,
  onBack,
  onPlaced,
}: {
  site: Site;
  lines: { item: MenuItem; qty: number }[];
  total: number;
  money: (v: unknown) => string;
  onBack: () => void;
  onPlaced: (order: Tracked) => void;
}) {
  const [service, setService] = useState<'pickup' | 'delivery'>('pickup');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [zone, setZone] = useState('');
  const [readyBy, setReadyBy] = useState('');
  const [payWith, setPayWith] = useState<'cash' | 'mobile_money' | 'card'>('cash');
  const [allergy, setAllergy] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function place(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (!name.trim()) return setError('Add your name.');
    const tel = cleanPhone(phone, site.currency);
    if (!/^\+\d{8,15}$/.test(tel)) return setError('Add a phone number the restaurant can call, like 024 123 4567.');
    if (service === 'delivery' && address.trim().length < 3) return setError('Add the delivery address.');
    if (allergy.trim() && allergy.trim().length < 2) return setError('Describe the allergy in a few words.');
    setBusy(true);
    try {
      const order = await call(`/public/restaurant-site/${encodeURIComponent(site.slug)}/order`, {
        method: 'POST',
        body: JSON.stringify({
          service,
          customer_name: name.trim(),
          phone: tel,
          pay_with: payWith,
          ready_by: service === 'pickup' && readyBy ? readyBy : null,
          delivery_address: service === 'delivery' ? address.trim() : null,
          delivery_zone: service === 'delivery' && zone ? zone : null,
          allergy: allergy.trim() || null,
          notes: notes.trim() || null,
          lines: lines.map((l) => ({ product_id: l.item.id, quantity: l.qty })),
        }),
      });
      onPlaced(order);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Your order did not go through. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={place} className="rs-form">
      <div className="rs-sheet-head">
        <button type="button" className="rs-back" onClick={onBack}>
          ← Bag
        </button>
        <h2>How do you want it?</h2>
      </div>
      <div className="rs-choice" role="radiogroup" aria-label="Pickup or delivery">
        <button type="button" role="radio" aria-checked={service === 'pickup'} className={service === 'pickup' ? 'on' : ''} onClick={() => setService('pickup')}>
          <strong>Pickup</strong>
          <span>Collect it yourself</span>
        </button>
        <button type="button" role="radio" aria-checked={service === 'delivery'} className={service === 'delivery' ? 'on' : ''} onClick={() => setService('delivery')}>
          <strong>Delivery</strong>
          <span>We bring it to you</span>
        </button>
      </div>
      <label>
        <span>Your name</span>
        <input aria-label="Your name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        <span>Phone</span>
        <input aria-label="Your phone" inputMode="tel" autoComplete="tel" placeholder="024 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      {service === 'delivery' ? (
        <>
          <label>
            <span>Delivery address</span>
            <input aria-label="Delivery address" autoComplete="street-address" placeholder="House number, street, area, landmark" value={address} onChange={(e) => setAddress(e.target.value)} />
          </label>
          {site.delivery_zones.length ? (
            <label>
              <span>Area</span>
              <select aria-label="Delivery area" value={zone} onChange={(e) => setZone(e.target.value)}>
                <option value="">Choose your area</option>
                {site.delivery_zones.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </>
      ) : (
        <label>
          <span>Pickup time (optional)</span>
          <select aria-label="Pickup time" value={readyBy} onChange={(e) => setReadyBy(e.target.value)}>
            <option value="">As soon as it is ready</option>
            {TIMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="rs-field">
        <span>You will pay with</span>
        <div className="rs-pay" role="radiogroup" aria-label="Payment">
          {PAY.map((p) => (
            <button key={p.id} type="button" role="radio" aria-checked={payWith === p.id} className={payWith === p.id ? 'on' : ''} onClick={() => setPayWith(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <label>
        <span>Allergies (optional)</span>
        <input aria-label="Allergies" placeholder="e.g. peanuts" value={allergy} maxLength={80} onChange={(e) => setAllergy(e.target.value)} />
      </label>
      <label>
        <span>Note for the kitchen (optional)</span>
        <input aria-label="Note for the kitchen" placeholder="Extra pepper, no onions…" value={notes} maxLength={300} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div className="rs-total">
        <span>
          {lines.reduce((n, l) => n + l.qty, 0)} {lines.reduce((n, l) => n + l.qty, 0) === 1 ? 'item' : 'items'}
        </span>
        <strong>{money(total)}</strong>
      </div>
      {error ? (
        <p className="rs-error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="rs-btn rs-btn-main rs-wide" aria-label="Place order" disabled={busy}>
        {busy ? 'Sending your order…' : 'Place order'}
      </button>
      <p className="rs-small">Nothing is charged now. {service === 'pickup' ? 'Pay when you collect.' : 'Pay when it arrives.'}</p>
    </form>
  );
}

function TrackingPanel({
  order,
  money,
  site,
  onClose,
}: {
  order: Tracked;
  money: (v: unknown) => string;
  site: Site;
  onClose: () => void;
}) {
  const at = stepIndex(order.status);
  const stopped = ['cancelled', 'voided', 'refunded'].includes(order.status);
  return (
    <>
      <div className="rs-sheet-head">
        <h2>Order {order.order_number}</h2>
        <button type="button" className="rs-x" aria-label="Close order" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="rs-thanks">
        <div className="rs-tick" aria-hidden>
          {stopped ? '!' : '✓'}
        </div>
        <p>
          {stopped
            ? `This order was ${order.status_words.toLowerCase()}. Please call the restaurant.`
            : order.status === 'ready'
              ? order.service === 'pickup'
                ? 'Your food is ready. Come and collect it.'
                : 'Your food is ready and on its way.'
              : 'Thank you! The restaurant has your order.'}
        </p>
      </div>
      {!stopped ? (
        <ol className="rs-steps" aria-label="Order progress">
          {STEPS.map((step, i) => (
            <li key={step.key} className={i < at ? 'done' : i === at ? 'now' : ''}>
              <span className="dot" aria-hidden />
              {step.key === 'ready' && order.service === 'delivery' ? 'Ready, on its way' : step.label}
            </li>
          ))}
        </ol>
      ) : null}
      <ul className="rs-lines plain">
        {order.items.map((item, i) => (
          <li key={`${item.name}-${i}`}>
            <div>
              <strong>
                {Number(item.quantity)}× {item.name}
              </strong>
            </div>
            <b>{money(item.line_total)}</b>
          </li>
        ))}
      </ul>
      <div className="rs-total">
        <span>To pay (tax included)</span>
        <strong>{money(order.total_amount)}</strong>
      </div>
      <p className="rs-small">
        This page updates by itself.{site.phone ? ' Questions? ' : ''}
        {site.phone ? <a href={`tel:${site.phone}`}>Call {site.phone}</a> : null}
      </p>
    </>
  );
}

function BookingForm({
  site,
  bagLines,
  money,
  onBooked,
}: {
  site: Site;
  bagLines: { item: MenuItem; qty: number }[];
  money: (v: unknown) => string;
  onBooked: (preOrdered: boolean) => void;
}) {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [party, setParty] = useState(2);
  const [date, setDate] = useState(todayLocal());
  const [time, setTime] = useState('19:00');
  const [notes, setNotes] = useState('');
  const [preOrder, setPreOrder] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<{ number: string; when: string } | null>(null);

  async function book(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (!name.trim()) return setError('Add your name.');
    const tel = cleanPhone(phone, site.currency);
    if (!/^\+\d{8,15}$/.test(tel)) return setError('Add a phone number the restaurant can call, like 024 123 4567.');
    const when = `${date}T${time}`;
    if (new Date(when).getTime() < Date.now() - 60000) return setError('Pick a time that is still ahead.');
    setBusy(true);
    try {
      const row = await call(`/public/restaurant-site/${encodeURIComponent(site.slug)}/book`, {
        method: 'POST',
        body: JSON.stringify({
          guest_name: name.trim(),
          phone: tel,
          party_size: party,
          booked_for: when,
          notes: notes.trim() || null,
          pre_order: preOrder ? bagLines.slice(0, 12).map((l) => ({ product_id: l.item.id, quantity: l.qty })) : [],
        }),
      });
      const nice = new Date(when).toLocaleString([], { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
      setDone({ number: row?.booking_number || '', when: nice });
      onBooked(preOrder && bagLines.length > 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The booking did not go through. Try again.');
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="rs-book-card rs-book-done">
        <div className="rs-tick" aria-hidden>
          ✓
        </div>
        <h2>Table requested</h2>
        <p>
          {party} {party === 1 ? 'guest' : 'guests'} · {done.when}
        </p>
        <p className="rs-small">
          Booking {done.number}. The restaurant will call {name.split(' ')[0] || 'you'} if anything changes.
        </p>
        <button type="button" className="rs-btn rs-btn-ghost" onClick={() => setDone(null)}>
          Book another table
        </button>
      </div>
    );
  }

  return (
    <div className="rs-book-wrap">
      <div className="rs-book-intro">
        <p className="rs-kicker">Eat with us</p>
        <h2>Book a table</h2>
        <p>Tell us when you are coming and how many you are. We keep a table ready for you.</p>
        {bagLines.length ? (
          <p className="rs-small">Already chose dishes? Tick “have my food ready” and the kitchen will expect you.</p>
        ) : null}
      </div>
      <form className="rs-book-card rs-form" onSubmit={book}>
        <div className="rs-two">
          <label>
            <span>Your name</span>
            <input aria-label="Booking name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            <span>Phone</span>
            <input aria-label="Booking phone" inputMode="tel" autoComplete="tel" placeholder="024 123 4567" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
        </div>
        <div className="rs-field">
          <span>How many people?</span>
          <div className="rs-party" role="radiogroup" aria-label="Party size">
            {[1, 2, 3, 4, 5, 6, 8, 10].map((n) => (
              <button key={n} type="button" role="radio" aria-checked={party === n} className={party === n ? 'on' : ''} onClick={() => setParty(n)}>
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="rs-two">
          <label>
            <span>Day</span>
            <input aria-label="Booking day" type="date" min={todayLocal()} max={todayLocal(90)} value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label>
            <span>Time</span>
            <select aria-label="Booking time" value={time} onChange={(e) => setTime(e.target.value)}>
              {TIMES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          <span>Anything we should know? (optional)</span>
          <input aria-label="Booking note" placeholder="Birthday, high chair, window seat…" value={notes} maxLength={300} onChange={(e) => setNotes(e.target.value)} />
        </label>
        {bagLines.length ? (
          <label className="rs-check">
            <input type="checkbox" aria-label="Have my food ready" checked={preOrder} onChange={(e) => setPreOrder(e.target.checked)} />
            <span>
              Have my food ready ({bagLines.reduce((n, l) => n + l.qty, 0)}{' '}
              {bagLines.reduce((n, l) => n + l.qty, 0) === 1 ? 'item' : 'items'},{' '}
              {money(bagLines.reduce((s, l) => s + l.qty * Number(l.item.price || 0), 0))}). Pay at the table.
            </span>
          </label>
        ) : null}
        {error ? (
          <p className="rs-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" className="rs-btn rs-btn-main rs-wide" aria-label="Request a table" disabled={busy}>
          {busy ? 'Sending…' : 'Request a table'}
        </button>
      </form>
    </div>
  );
}
