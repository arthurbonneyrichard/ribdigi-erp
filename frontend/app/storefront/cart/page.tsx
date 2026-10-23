'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { cartToken, notifyStorefrontCart, shopMoney, storefrontAssetUrl, storefrontFetch, storefrontHref } from '../../../lib/storefrontApi';
import { useStorefrontShell } from '../StorefrontShell';

type Line = {
  product_id: string;
  variant_id?: string | null;
  variant_name?: string | null;
  name: string;
  image_url?: string | null;
  quantity: number;
  unit_price: number;
  line_total: number;
};

export default function CartPage() {
  const { currency, refreshCart } = useStorefrontShell();
  const [lines, setLines] = useState<Line[]>([]);
  const [subtotal, setSubtotal] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  async function load() {
    const token = cartToken();
    if (!token) {
      setLines([]);
      setSubtotal(0);
      return;
    }
    try {
      const res = await storefrontFetch(`/storefront/cart/${token}`);
      setLines(res.data?.items || []);
      setSubtotal(res.data?.subtotal || 0);
      setError('');
    } catch (err: any) {
      setError(err.message || 'Could not load cart');
      setLines([]);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function setQty(line: Line, quantity: number) {
    const token = cartToken();
    if (!token) return;
    setBusy(`${line.product_id}:${line.variant_id || 'base'}`);
    setError('');
    try {
      const res = await storefrontFetch(`/storefront/cart/${token}/items`, {
        method: 'POST',
        body: JSON.stringify({
          product_id: line.product_id,
          quantity: Math.max(0, quantity),
          variant_id: line.variant_id || null,
        }),
      });
      setLines(res.data?.items || []);
      setSubtotal(res.data?.subtotal || 0);
      notifyStorefrontCart();
      await refreshCart();
    } catch (err: any) {
      setError(err.message || 'Could not update cart');
    } finally {
      setBusy('');
    }
  }

  return (
    <main className="sf-main">
      <h1>Cart</h1>
      <p className="sf-lead">Change quantities here. Stock is reserved only when you place the order.</p>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {!lines.length && !error ? (
        <section className="sf-empty" role="status">
          <p className="sf-empty-title">Your cart is empty</p>
          <p className="sf-muted">Add a published product from the shop, then return here to check out.</p>
          <p className="sf-actions"><Link className="sf-btn" href={storefrontHref('/storefront')}>Continue shopping</Link></p>
        </section>
      ) : null}
      {lines.map((line) => (
        <article key={`${line.product_id}:${line.variant_id || 'base'}`} className="sf-line">
          {line.image_url ? (
            <img className="sf-thumb" src={storefrontAssetUrl(line.image_url)} alt="" />
          ) : (
            <div className="sf-thumb-fallback" aria-hidden>{line.name.slice(0, 1)}</div>
          )}
          <div>
            <h2>{line.name}</h2>
            {line.variant_name ? <p className="sf-muted">{line.variant_name}</p> : null}
            <p className="sf-muted">{shopMoney(line.unit_price, currency)} each</p>
            <div className="sf-qty">
              <button
                type="button"
                aria-label={`Decrease ${line.name}`}
                disabled={busy === `${line.product_id}:${line.variant_id || 'base'}`}
                onClick={() => void setQty(line, line.quantity - 1)}
              >
                −
              </button>
              <input
                aria-label={`Quantity ${line.name}`}
                type="number"
                min="0"
                value={line.quantity}
                onChange={(e) => void setQty(line, Number(e.target.value || 0))}
              />
              <button
                type="button"
                aria-label={`Increase ${line.name}`}
                disabled={busy === `${line.product_id}:${line.variant_id || 'base'}`}
                onClick={() => void setQty(line, line.quantity + 1)}
              >
                +
              </button>
              <button
                type="button"
                className="sf-btn-ghost"
                aria-label={`Remove ${line.name} from cart`}
                onClick={() => void setQty(line, 0)}
              >
                Remove
              </button>
            </div>
          </div>
          <p className="sf-price">{shopMoney(line.line_total, currency)}</p>
        </article>
      ))}
      {lines.length ? (
        <section className="sf-summary">
          <h2>Subtotal {shopMoney(subtotal, currency)}</h2>
          <p className="sf-muted">You choose delivery or pickup at checkout.</p>
          <div className="sf-actions">
            <Link className="sf-btn" href={storefrontHref('/storefront/checkout')}>Go to checkout</Link>
            <Link className="sf-btn sf-btn-ghost" href={storefrontHref('/storefront')}>Continue shopping</Link>
          </div>
        </section>
      ) : null}
    </main>
  );
}
