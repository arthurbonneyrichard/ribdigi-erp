'use client';

/**
 * What guests see: the phone menu behind the QR code and the full-screen TV board.
 * Neither needs a login. Both poll the public menu, so a change reaches every screen
 * without a new QR code or a reload.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import './digital-menu.css';

export type GuestItem = {
  id: string;
  name: string;
  description: string | null;
  price: number;
  image_version: string | null;
  available: boolean;
  featured: boolean;
  promo: string | null;
};

export type GuestMenu = {
  restaurant: { name: string; logo_version: string | null; phone: string | null; address: string | null; tagline: string | null };
  currency: string;
  theme: { accent: string; style: 'forest' | 'mist'; rotate_seconds: number };
  categories: { id: string; name: string; items: GuestItem[] }[];
  version: string;
};

export function menuPrice(value: number, currency: string): string {
  const amount = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0);
  return `${currency} ${amount}`;
}

const logoUrl = (token: string, version: string) => `/api/v1/public/menu/${token}/logo?v=${version}`;
const photoUrl = (token: string, item: GuestItem) => `/api/v1/public/menu/${token}/items/${item.id}/image?v=${item.image_version}`;

export function useGuestMenu(token: string, pollMs: number) {
  const [menu, setMenu] = useState<GuestMenu | null>(null);
  const [gone, setGone] = useState(false);
  const version = useRef('');

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/public/menu/${encodeURIComponent(token)}`, { cache: 'no-cache' });
      if (res.status === 404) {
        setGone(true);
        setMenu(null);
        version.current = '';
        return;
      }
      if (!res.ok) return;
      const body = await res.json();
      setGone(false);
      if (body?.data?.version !== version.current) {
        version.current = body.data.version;
        setMenu(body.data);
      }
    } catch {
      /* a dropped connection keeps the last menu on screen */
    }
  }, [token]);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, pollMs);
    const onVisible = () => {
      if (document.visibilityState === 'visible') void load();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load, pollMs]);

  return { menu, gone };
}

function Unavailable() {
  return (
    <main className="gmenu-gone">
      <h1>This menu is not available</h1>
      <p>Please ask a member of staff.</p>
    </main>
  );
}

export function GuestMenuView({
  menu,
  token,
  photo,
}: {
  menu: GuestMenu;
  token?: string;
  photo?: (item: GuestItem) => React.ReactNode;
}) {
  const { restaurant, currency, categories, theme } = menu;
  const [active, setActive] = useState(categories[0]?.id || '');
  const featured = useMemo(() => categories.flatMap((c) => c.items).filter((i) => i.featured && i.available), [categories]);

  function jump(id: string) {
    setActive(id);
    document.getElementById(`gmenu-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const image = (item: GuestItem) => {
    if (photo) return photo(item);
    if (!token || !item.image_version) return null;
    return <img src={photoUrl(token, item)} alt="" loading="lazy" decoding="async" />;
  };

  return (
    <div className="gmenu" style={{ '--menu-accent': theme.accent } as React.CSSProperties}>
      <header className="gmenu-head">
        {token && restaurant.logo_version ? (
          <img className="gmenu-logo" src={logoUrl(token, restaurant.logo_version)} alt={`${restaurant.name} logo`} />
        ) : null}
        <h1>{restaurant.name}</h1>
        {restaurant.tagline ? <p>{restaurant.tagline}</p> : null}
      </header>

      {categories.length > 1 ? (
        <nav className="gmenu-nav" aria-label="Menu categories">
          {categories.map((c) => (
            <button key={c.id} type="button" className={active === c.id ? 'on' : ''} onClick={() => jump(c.id)}>
              {c.name}
            </button>
          ))}
        </nav>
      ) : null}

      <main className="gmenu-body">
        {categories.length === 0 ? <p className="gmenu-empty">The menu is being updated. Please ask a member of staff.</p> : null}

        {featured.length > 0 ? (
          <section aria-label="Featured dishes">
            <h2>Featured</h2>
            <div className="gmenu-featured">
              {featured.map((item) => {
                const picture = image(item);
                return (
                  <article key={item.id} className="gmenu-feature">
                    {picture ? <div className="gmenu-feature-photo">{picture}</div> : null}
                    <div className="gmenu-feature-copy">
                      {item.promo ? <span className="gmenu-promo">{item.promo}</span> : null}
                      <h3>{item.name}</h3>
                      <strong>{menuPrice(item.price, currency)}</strong>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}

        {categories.map((category) => (
          <section key={category.id} id={`gmenu-${category.id}`} className="gmenu-section">
            <h2>{category.name}</h2>
            {category.items.map((item) => {
              const picture = image(item);
              return (
                <article key={item.id} className={`gmenu-item${item.available ? '' : ' is-out'}`}>
                  {picture ? <div className="gmenu-photo">{picture}</div> : null}
                  <div className="gmenu-copy">
                    <h3>
                      {item.name}
                      {item.promo ? <span className="gmenu-promo">{item.promo}</span> : null}
                    </h3>
                    {item.description ? <p>{item.description}</p> : null}
                    <div className="gmenu-price-row">
                      <strong>{menuPrice(item.price, currency)}</strong>
                      {item.available ? null : <span className="gmenu-out">Unavailable</span>}
                    </div>
                  </div>
                </article>
              );
            })}
          </section>
        ))}
      </main>

      {restaurant.phone || restaurant.address ? (
        <footer className="gmenu-foot">
          {restaurant.address ? <span>{restaurant.address}</span> : null}
          {restaurant.phone ? <a href={`tel:${restaurant.phone}`}>{restaurant.phone}</a> : null}
        </footer>
      ) : null}
    </div>
  );
}

export function GuestMenuPage({ token }: { token: string }) {
  const { menu, gone } = useGuestMenu(token, 60_000);
  if (gone) return <Unavailable />;
  if (!menu) return <div className="gmenu-loading" role="status" aria-label="Loading the menu" />;
  return <GuestMenuView menu={menu} token={token} />;
}

type BoardPage = { title: string; items: GuestItem[] };

const ITEMS_PER_PAGE = 8;

function boardPages(menu: GuestMenu): BoardPage[] {
  const pages: BoardPage[] = [];
  const featured = menu.categories.flatMap((c) => c.items).filter((i) => i.featured && i.available);
  if (featured.length > 0) pages.push({ title: 'Featured', items: featured.slice(0, ITEMS_PER_PAGE) });
  for (const category of menu.categories) {
    for (let start = 0; start < category.items.length; start += ITEMS_PER_PAGE) {
      pages.push({ title: category.name, items: category.items.slice(start, start + ITEMS_PER_PAGE) });
    }
  }
  return pages;
}

export function MenuBoardPage({ token }: { token: string }) {
  const { menu, gone } = useGuestMenu(token, 20_000);
  const [index, setIndex] = useState(0);
  const [full, setFull] = useState(false);
  const pages = useMemo(() => (menu ? boardPages(menu) : []), [menu]);
  const seconds = Math.max(5, menu?.theme.rotate_seconds || 12);

  useEffect(() => {
    if (pages.length < 2) return;
    const id = window.setInterval(() => setIndex((i) => i + 1), seconds * 1000);
    return () => window.clearInterval(id);
  }, [pages.length, seconds]);

  useEffect(() => {
    const onChange = () => setFull(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // A TV screen must not fall asleep in the middle of service.
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null;
    const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<{ release: () => Promise<void> }> } };
    nav.wakeLock?.request('screen').then((l) => (lock = l)).catch(() => undefined);
    return () => {
      void lock?.release().catch(() => undefined);
    };
  }, []);

  if (gone) return <Unavailable />;
  if (!menu) return <div className="gmenu-loading gboard-loading" role="status" aria-label="Loading the menu" />;
  const page = pages.length ? pages[index % pages.length] : null;
  const { restaurant, currency, theme } = menu;

  return (
    <div className={`gboard is-${theme.style}`} style={{ '--menu-accent': theme.accent } as React.CSSProperties}>
      <header className="gboard-head">
        <div className="gboard-brand">
          {restaurant.logo_version ? <img src={logoUrl(token, restaurant.logo_version)} alt="" /> : null}
          <div>
            <h1>{restaurant.name}</h1>
            {restaurant.tagline ? <p>{restaurant.tagline}</p> : null}
          </div>
        </div>
        {page ? <h2 className="gboard-title">{page.title}</h2> : null}
      </header>

      {page ? (
        <main
          key={`${page.title}-${index}`}
          className={`gboard-grid count-${Math.min(page.items.length, ITEMS_PER_PAGE)}${
            page.items.some((item) => item.image_version) ? '' : ' is-text'
          }`}
        >
          {page.items.map((item) => (
            <article key={item.id} className={`gboard-item${item.available ? '' : ' is-out'}`}>
              {item.image_version ? (
                <div className="gboard-photo">
                  <img src={photoUrl(token, item)} alt="" />
                </div>
              ) : null}
              <div className="gboard-copy">
                {item.promo ? <span className="gmenu-promo">{item.promo}</span> : null}
                <h3>{item.name}</h3>
                {item.description ? <p>{item.description}</p> : null}
                <strong>{item.available ? menuPrice(item.price, currency) : 'Unavailable'}</strong>
              </div>
            </article>
          ))}
        </main>
      ) : (
        <main className="gboard-empty">The menu is being updated.</main>
      )}

      {pages.length > 1 ? (
        <div className="gboard-dots" aria-hidden>
          {pages.map((p, i) => (
            <span key={`${p.title}-${i}`} className={i === index % pages.length ? 'on' : ''} />
          ))}
        </div>
      ) : null}

      {!full ? (
        <button
          type="button"
          className="gboard-full"
          onClick={() => void document.documentElement.requestFullscreen?.().catch(() => undefined)}
        >
          Full screen
        </button>
      ) : null}
    </div>
  );
}
