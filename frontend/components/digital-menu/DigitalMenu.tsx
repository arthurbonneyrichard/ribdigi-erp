'use client';

/**
 * What guests see: the phone menu behind the QR code and the full-screen TV board.
 * Neither needs a login. Both poll the public menu, so a change reaches every screen
 * without a new QR code or a reload.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePageIcon } from '../../lib/usePageIcon';
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
  restaurant: { name: string; logo_version: string | null; favicon_version?: string | null; phone: string | null; address: string | null; tagline: string | null };
  currency: string;
  banner?: { version: string | null; position: 'top' | 'footer' };
  theme: { accent: string; primary?: string | null; background?: string | null; board_background?: string | null; pattern?: 'food' | 'dots' | 'none'; style: 'forest' | 'mist'; rotate_seconds: number };
  categories: { id: string; name: string; items: GuestItem[] }[];
  version: string;
};

const lum = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};
const contrast = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};
const readable = (bg: string) => (contrast(bg, '#FFFFFF') >= contrast(bg, '#10211B') ? '#FFFFFF' : '#10211B');
const HEX = /^#[0-9A-Fa-f]{6}$/;

/** The restaurant's own colours. Text colours are picked for contrast, so any colour stays readable. */
const DEFAULT_ACCENT = '#4AB012';

/** The accent is still the stock green when the restaurant has not chosen one; then it follows their own colours. */
function accentFor(theme: GuestMenu['theme']): string {
  const own = (c?: string | null) => (c && HEX.test(c) ? c : null);
  const primary = own(theme.primary);
  const background = own(theme.background);
  if (theme.accent.toUpperCase() !== DEFAULT_ACCENT || (!primary && !background)) return theme.accent;
  if (primary && (!background || contrast(primary, background) >= 3)) return primary;
  return readable(background || primary || '#FFFFFF');
}

export function menuColorVars(theme: GuestMenu['theme']): React.CSSProperties {
  const accent = accentFor(theme);
  const vars: Record<string, string> = { '--menu-accent': accent };
  vars['--menu-on-accent'] = readable(accent);
  if (theme.primary && HEX.test(theme.primary)) {
    vars['--menu-primary'] = theme.primary;
    vars['--menu-on-primary'] = readable(theme.primary);
  }
  if (theme.background && HEX.test(theme.background)) {
    const bg = theme.background;
    vars['--menu-bg'] = bg;
    vars['--menu-ink'] = readable(bg);
    vars['--menu-card'] = readable(bg) === '#FFFFFF' ? 'rgba(255,255,255,.08)' : '#FFFFFF';
    // Prices use the accent when it reads on the background, otherwise the text colour.
    vars['--menu-price'] = contrast(accent, bg) >= 3 ? accent : readable(bg);
  }
  return vars as React.CSSProperties;
}

/** TV board colours: background, card colour and text, each picked for contrast. */
export function boardColorVars(theme: GuestMenu['theme']): React.CSSProperties {
  const vars: Record<string, string> = { ...(menuColorVars(theme) as Record<string, string>) };
  const mist = theme.style === 'mist';
  const own = [theme.board_background, theme.background].find((c) => c && HEX.test(c));
  const bg = own || (mist ? '#F5FAF0' : '#001A0E');
  const panel = theme.primary && HEX.test(theme.primary) ? theme.primary : mist ? '#FFFFFF' : '#003D1F';
  const ink = readable(bg);
  const onPanel = readable(panel);
  vars['--bg'] = bg;
  vars['--panel'] = panel;
  vars['--ink'] = ink;
  vars['--soft'] = ink === '#FFFFFF' ? '#D6E3D8' : '#4D5D56';
  vars['--on-panel'] = onPanel;
  vars['--on-panel-soft'] = onPanel === '#FFFFFF' ? '#D6E3D8' : '#4D5D56';
  vars['--menu-price'] = contrast(accentFor(theme), panel) >= 3 ? accentFor(theme) : onPanel;
  return vars as React.CSSProperties;
}

export function menuPrice(value: number, currency: string): string {
  const amount = new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value || 0);
  return `${currency} ${amount}`;
}

const faviconUrl = (token: string, version: string) => `/api/v1/public/menu/${token}/favicon?v=${version}`;
const logoUrl = (token: string, version: string) => `/api/v1/public/menu/${token}/logo?v=${version}`;
const bannerUrl = (token: string, version: string) => `/api/v1/public/menu/${token}/banner?v=${version}`;
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
  logoSrc,
  bannerSrc,
}: {
  menu: GuestMenu;
  token?: string;
  photo?: (item: GuestItem) => React.ReactNode;
  /** Staff preview only: images loaded with the staff session instead of the public link. */
  logoSrc?: string;
  bannerSrc?: string;
}) {
  const { restaurant, currency, categories, theme } = menu;
  const [active, setActive] = useState(categories[0]?.id || '');
  const featured = useMemo(() => categories.flatMap((c) => c.items).filter((i) => i.featured && i.available), [categories]);

  function jump(id: string) {
    setActive(id);
    document.getElementById(`gmenu-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  const bannerPos = menu.banner?.position || 'top';
  const bannerHref = bannerSrc || (token && menu.banner?.version ? bannerUrl(token, menu.banner.version) : '');
  const logoHref = logoSrc || (token && restaurant.logo_version ? logoUrl(token, restaurant.logo_version) : '');
  const banner =
    bannerHref ? (
      <img className={`gmenu-banner is-${bannerPos}`} src={bannerHref} alt={`${restaurant.name} banner`} decoding="async" />
    ) : null;

  const image = (item: GuestItem) => {
    if (photo) return photo(item);
    if (!token || !item.image_version) return null;
    return <img src={photoUrl(token, item)} alt="" loading="lazy" decoding="async" />;
  };

  return (
    <div className={`gmenu pat-${theme.pattern || 'food'}`} style={menuColorVars(theme)}>
      {banner && bannerPos === 'top' ? banner : null}
      <header className="gmenu-head">
        {logoHref ? <img className="gmenu-logo" src={logoHref} alt={`${restaurant.name} logo`} /> : null}
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

      {banner && bannerPos === 'footer' ? banner : null}
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
  usePageIcon(menu?.restaurant.favicon_version ? faviconUrl(token, menu.restaurant.favicon_version) : null, menu ? `${menu.restaurant.name} menu` : null);
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
  usePageIcon(menu?.restaurant.favicon_version ? faviconUrl(token, menu.restaurant.favicon_version) : null, menu ? `${menu.restaurant.name} menu board` : null);
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
    <div className={`gboard is-${theme.style} has-colours pat-${theme.pattern || 'food'}`} style={boardColorVars(theme)}>
      <header className="gboard-head">
        <div className="gboard-brand">
          {restaurant.logo_version ? (
            <img
              className="gboard-logo"
              src={logoUrl(token, restaurant.logo_version)}
              alt={`${restaurant.name} logo`}
              onError={(e) => ((e.currentTarget as HTMLImageElement).style.display = 'none')}
            />
          ) : null}
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
            page.items.some((item) => item.image_version) ? ' is-list' : ' is-text'
          }`}
        >
          {page.items.map((item) => (
            <article key={item.id} className={`gboard-item${item.available ? '' : ' is-out'}`}>
              {item.image_version ? (
                <div className="gboard-photo">
                  <img src={photoUrl(token, item)} alt="" decoding="async" />
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
