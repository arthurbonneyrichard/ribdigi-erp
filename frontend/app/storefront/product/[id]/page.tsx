'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { cartToken, notifyStorefrontCart, setCartToken, shopMoney, storefrontAssetUrl, storefrontFetch, storefrontHref } from '../../../../lib/storefrontApi';
import { useStorefrontShell } from '../../StorefrontShell';

type CatalogVariant = { id: string; name: string; price: number };
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

export default function StorefrontProductPage() {
  const params = useParams<{ id: string }>();
  const { currency, refreshCart } = useStorefrontShell();
  const [item, setItem] = useState<CatalogItem | null>(null);
  const [variantId, setVariantId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const id = params.id;
    if (!id) return;
    storefrontFetch(`/storefront/bootstrap?product_id=${encodeURIComponent(id)}&page_size=1`)
      .then((res) => {
        const found = (res.data?.catalog || [])[0] || null;
        setItem(found);
        setVariantId(found?.variants?.[0]?.id || '');
        if (!found) setError('This product is not published for online sale.');
      })
      .catch((err) => setError(err.message || 'This product is not available'));
  }, [params.id]);

  async function addToCart() {
    if (!item) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      let token = cartToken();
      if (!token) {
        const created = await storefrontFetch('/storefront/cart', { method: 'POST' });
        token = created.data?.token;
        if (!token) throw new Error('Could not start a cart');
        setCartToken(token);
      }
      const current = await storefrontFetch(`/storefront/cart/${token}`);
      const existing = (current.data?.items || []).find(
        (line: { product_id: string; variant_id?: string | null }) =>
          line.product_id === item.product_id && (line.variant_id || null) === (variantId || null),
      );
      await storefrontFetch(`/storefront/cart/${token}/items`, {
        method: 'POST',
        body: JSON.stringify({
          product_id: item.product_id,
          quantity: Number(existing?.quantity || 0) + 1,
          variant_id: variantId || null,
        }),
      });
      notifyStorefrontCart();
      await refreshCart();
      setMessage(`${item.name} added to cart`);
    } catch (err: any) {
      setError(err.message || 'Could not add to cart');
    } finally {
      setBusy(false);
    }
  }

  const selected = item?.variants?.find((row) => row.id === variantId);
  const price = selected?.price ?? item?.price ?? 0;

  return (
    <main className="sf-main">
      <p><Link href={storefrontHref('/storefront')}>Back to shop</Link></p>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {message ? <p className="sf-ok" role="status">{message}</p> : null}
      {!item && !error ? <p className="sf-muted">Loading product…</p> : null}
      {item ? (
        <article className="sf-split">
          <div className="sf-card">
            {item.image_url ? (
              <img className="sf-thumb" src={storefrontAssetUrl(item.image_url)} alt={item.image_alt || item.name} />
            ) : (
              <div className="sf-thumb-fallback" aria-hidden>{item.name.slice(0, 1)}</div>
            )}
          </div>
          <div className="sf-summary">
            {item.category ? <p className="sf-chip">{item.category}</p> : null}
            <h1>{item.name}</h1>
            <p className="sf-price">{shopMoney(price, currency)}</p>
            {item.description ? <p className="sf-lead">{item.description}</p> : null}
            <p className="sf-muted">{item.in_stock ? `${item.available_qty} available` : 'Out of stock'}</p>
            {item.variants?.length ? (
              <label>
                Variant
                <select
                  aria-label={`Storefront variant for ${item.name}`}
                  value={variantId}
                  onChange={(e) => setVariantId(e.target.value)}
                >
                  {item.variants.map((variant) => (
                    <option key={variant.id} value={variant.id}>
                      {variant.name} · {shopMoney(variant.price, currency)}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <div className="sf-actions">
              <button
                type="button"
                aria-label={`Add ${item.name} to cart`}
                disabled={!item.in_stock || busy}
                onClick={() => void addToCart()}
              >
                Add to cart
              </button>
              <Link className="sf-btn sf-btn-ghost" href={storefrontHref('/storefront/cart')}>Cart</Link>
            </div>
          </div>
        </article>
      ) : null}
    </main>
  );
}
