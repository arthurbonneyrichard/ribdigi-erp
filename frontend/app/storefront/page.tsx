'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { cartToken, notifyStorefrontCart, setCartToken, shopMoney, storefrontAssetUrl, storefrontFetch, storefrontHref } from '../../lib/storefrontApi';
import { useStorefrontShell } from './StorefrontShell';

type CatalogVariant = {
  id: string;
  name: string;
  sku?: string | null;
  price: number;
};

type CatalogItem = {
  product_id: string;
  name: string;
  price: number;
  available_qty: number;
  in_stock: boolean;
  description?: string | null;
  category?: string | null;
  image_url?: string | null;
  image_alt?: string | null;
  variants?: CatalogVariant[];
};

export default function StorefrontHome() {
  const { meta, currency, refreshCart } = useStorefrontShell();
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [variantByProduct, setVariantByProduct] = useState<Record<string, string>>({});
  const pageSize = 12;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setQ(qInput.trim());
    }, 250);
    return () => window.clearTimeout(timer);
  }, [qInput]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    if (category) params.set('category', category);
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    storefrontFetch(`/storefront/bootstrap?${params.toString()}`)
      .then((res) => {
        setItems(res.data?.catalog || []);
        setCategories(res.data?.categories || []);
        setTotal(Number(res.data?.total || 0));
        setError('');
      })
      .catch((err) => setError(err.message || 'This store is not available'));
  }, [q, category, page]);

  async function addToCart(item: CatalogItem) {
    setBusy(item.product_id);
    setError('');
    setMessage('');
    try {
      let token = cartToken();
      if (!token) {
        const created = await storefrontFetch('/storefront/cart', { method: 'POST' });
        const createdToken = created.data?.token;
        if (typeof createdToken !== 'string' || !createdToken) {
          throw new Error('Could not start a cart');
        }
        token = createdToken;
        setCartToken(createdToken);
      }
      const variantId = variantByProduct[item.product_id] || item.variants?.[0]?.id || null;
      const current = await storefrontFetch(`/storefront/cart/${token}`);
      const existing = (current.data?.items || []).find(
        (line: { product_id: string; variant_id?: string | null }) =>
          line.product_id === item.product_id && (line.variant_id || null) === variantId,
      );
      await storefrontFetch(`/storefront/cart/${token}/items`, {
        method: 'POST',
        body: JSON.stringify({
          product_id: item.product_id,
          quantity: Number(existing?.quantity || 0) + 1,
          variant_id: variantId,
        }),
      });
      notifyStorefrontCart();
      await refreshCart();
      setMessage(`${item.name} added to cart`);
    } catch (err: any) {
      setError(err.message || 'Could not add to cart');
    } finally {
      setBusy(null);
    }
  }

  const pages = Math.max(1, Math.ceil(total / pageSize));
  const company = meta.company_name || 'Online store';

  return (
    <main className="sf-main">
      <section className={meta.has_banner ? 'sf-hero has-banner' : 'sf-hero'}>
        {meta.has_banner ? (
          <img className="sf-hero-banner" src={storefrontAssetUrl('/storefront/media/banner')} alt="" />
        ) : null}
        <div className="sf-hero-copy">
          <h1>{company}</h1>
          <p>{meta.tagline || 'Shop published products from this company. A checkout return does not mark an order paid.'}</p>
        </div>
      </section>
      <div className="sf-filters">
        <label>
          Search
          <input
            aria-label="Storefront search"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Search published products"
          />
        </label>
        <label>
          Category
          <select
            aria-label="Storefront category"
            value={category}
            onChange={(e) => {
              setPage(1);
              setCategory(e.target.value);
            }}
          >
            <option value="">All categories</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {message ? <p className="sf-ok" role="status">{message}</p> : null}
      {!items.length && !error ? (
        <section className="sf-empty" role="status">
          <p className="sf-empty-title">
            {q || category ? 'No products match this search' : 'No products are published for this store yet'}
          </p>
          <p className="sf-muted">
            {q || category
              ? 'Clear the search or choose another category.'
              : 'A staff member opts products in from Online store. Nothing is sold until it is published.'}
          </p>
        </section>
      ) : null}
      <div className="sf-grid">
        {items.map((item) => (
          <article className="sf-card" key={item.product_id}>
            <Link href={storefrontHref(`/storefront/product/${item.product_id}`)}>
              {item.image_url ? (
                <img className="sf-thumb" src={storefrontAssetUrl(item.image_url)} alt={item.image_alt || item.name} />
              ) : (
                <div className="sf-thumb-fallback" aria-hidden>{item.name.slice(0, 1)}</div>
              )}
              <h2>{item.name}</h2>
            </Link>
            {item.category ? <p className="sf-chip">{item.category}</p> : null}
            {item.description ? <p className="sf-muted">{item.description}</p> : null}
            <p className="sf-price">{shopMoney(item.price, currency)}</p>
            {item.variants?.length ? (
              <label>
                Variant
                <select
                  aria-label={`Storefront variant for ${item.name}`}
                  value={variantByProduct[item.product_id] || item.variants[0].id}
                  onChange={(e) =>
                    setVariantByProduct((current) => ({ ...current, [item.product_id]: e.target.value }))
                  }
                >
                  {item.variants.map((variant) => (
                    <option key={variant.id} value={variant.id}>
                      {variant.name} · {shopMoney(variant.price, currency)}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <p className="sf-muted">{item.in_stock ? `${item.available_qty} available` : 'Out of stock'}</p>
            <div className="sf-actions">
              <button
                type="button"
                aria-label={`Add ${item.name} to cart`}
                disabled={!item.in_stock || busy === item.product_id}
                onClick={() => addToCart(item)}
              >
                Add to cart
              </button>
              <Link className="sf-btn sf-btn-ghost" href={storefrontHref(`/storefront/product/${item.product_id}`)}>
                View
              </Link>
            </div>
          </article>
        ))}
      </div>
      {pages > 1 ? (
        <p className="sf-actions">
          <button
            type="button"
            aria-label="Previous catalog page"
            disabled={page <= 1}
            onClick={() => setPage((n) => Math.max(1, n - 1))}
          >
            Previous
          </button>
          <span className="sf-muted">
            Page {page} of {pages}
          </span>
          <button
            type="button"
            aria-label="Next catalog page"
            disabled={page >= pages}
            onClick={() => setPage((n) => n + 1)}
          >
            Next
          </button>
        </p>
      ) : null}
    </main>
  );
}
