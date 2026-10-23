'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { cartToken, storefrontAssetUrl, storefrontFetch, storefrontHref } from '../../lib/storefrontApi';

export type StorefrontMeta = {
  company_name?: string;
  tagline?: string | null;
  announcement?: string | null;
  currency?: string;
  pickup_address?: string | null;
  allow_delivery?: boolean;
  allow_pickup?: boolean;
  support_email?: string | null;
  support_phone?: string | null;
  preview?: boolean;
  https_ready?: boolean;
  enabled?: boolean;
  has_logo?: boolean;
  has_banner?: boolean;
  has_favicon?: boolean;
};

type ShellContext = {
  meta: StorefrontMeta;
  currency: string;
  cartCount: number;
  ready: boolean;
  unavailable: string;
  refreshCart: () => Promise<void>;
};

const Ctx = createContext<ShellContext>({
  meta: {},
  currency: 'GHS',
  cartCount: 0,
  ready: false,
  unavailable: '',
  refreshCart: async () => undefined,
});

export function useStorefrontShell() {
  return useContext(Ctx);
}

export function previewHref(href: string) {
  return storefrontHref(href);
}

export default function StorefrontShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [meta, setMeta] = useState<StorefrontMeta>({});
  const [cartCount, setCartCount] = useState(0);
  const [ready, setReady] = useState(false);
  const [unavailable, setUnavailable] = useState('');

  const refreshCart = useCallback(async () => {
    const token = cartToken();
    if (!token) {
      setCartCount(0);
      return;
    }
    try {
      const res = await storefrontFetch(`/storefront/cart/${token}`);
      const items = res.data?.items || [];
      setCartCount(items.reduce((sum: number, line: { quantity?: number }) => sum + Number(line.quantity || 0), 0));
    } catch {
      setCartCount(0);
    }
  }, []);

  useEffect(() => {
    if (!meta.has_favicon) return;
    const link = document.querySelector('link[data-sf-favicon]') || document.createElement('link');
    link.setAttribute('rel', 'icon');
    link.setAttribute('data-sf-favicon', '1');
    link.setAttribute('href', storefrontAssetUrl('/storefront/media/favicon'));
    document.head.appendChild(link);
    return () => {
      link.remove();
    };
  }, [meta.has_favicon]);

  useEffect(() => {
    storefrontFetch('/storefront/bootstrap?page=1&page_size=1')
      .then((res) => {
        setMeta(res.data?.storefront || {});
        setUnavailable('');
      })
      .catch((err) => {
        setUnavailable(err.message || 'This store is not available');
      })
      .finally(() => setReady(true));
    void refreshCart();
    const onCart = () => {
      void refreshCart();
    };
    window.addEventListener('ribdigi-storefront-cart', onCart);
    return () => window.removeEventListener('ribdigi-storefront-cart', onCart);
  }, [refreshCart]);

  const company = meta.company_name || 'Online store';
  const currency = meta.currency || 'GHS';
  const value = useMemo(
    () => ({ meta, currency, cartCount, ready, unavailable, refreshCart }),
    [meta, currency, cartCount, ready, unavailable, refreshCart],
  );

  if (unavailable) {
    return (
      <div className="sf-shell">
        <header className="sf-bar">
          <strong className="sf-brand">Online store</strong>
        </header>
        <main className="sf-main">
          <section className="sf-empty" role="alert">
            <p className="sf-empty-title">This store is not available</p>
            <p className="sf-muted">
              {unavailable}. Check the web address, or ask the shop for its store link.
            </p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <Ctx.Provider value={value}>
      <div className="sf-shell">
        <header className="sf-bar">
          <Link href={previewHref('/storefront')} className="sf-brand-block">
            {meta.has_logo ? (
              <img className="sf-logo" src={storefrontAssetUrl('/storefront/media/logo')} alt={company} />
            ) : null}
            <span>
              <strong className="sf-brand">{company}</strong>
              {meta.tagline ? <span className="sf-tagline">{meta.tagline}</span> : null}
            </span>
          </Link>
          <nav className="sf-nav" aria-label="Storefront">
            <Link href={previewHref('/storefront')} className={pathname === '/storefront' ? 'is-active' : undefined}>
              Shop
            </Link>
            <Link href={previewHref('/storefront/cart')} className={pathname === '/storefront/cart' ? 'is-active' : undefined}>
              Cart{cartCount ? ` (${cartCount})` : ''}
            </Link>
            <Link href={previewHref('/storefront/account')} className={pathname === '/storefront/account' ? 'is-active' : undefined}>
              Account
            </Link>
            <Link href={previewHref('/storefront/policy/contact')}>Contact</Link>
          </nav>
        </header>
        {meta.preview ? (
          <p className="sf-preview" role="status">
            Preview for shop staff. Customers do not see this bar.
          </p>
        ) : null}
        {meta.announcement ? <p className="sf-announce">{meta.announcement}</p> : null}
        {children}
        <footer className="sf-foot">
          <p>{company}</p>
          <nav aria-label="Storefront policies">
            <Link href={previewHref('/storefront/policy/shipping')}>Shipping</Link>
            <Link href={previewHref('/storefront/policy/returns')}>Returns</Link>
            <Link href={previewHref('/storefront/policy/privacy')}>Privacy</Link>
            <Link href={previewHref('/storefront/policy/contact')}>Contact</Link>
          </nav>
          <p className="sf-muted">
            Your order is confirmed once the shop receives payment.
          </p>
        </footer>
      </div>
    </Ctx.Provider>
  );
}
