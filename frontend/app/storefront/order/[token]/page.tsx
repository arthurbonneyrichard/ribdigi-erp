'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { shopMoney, storefrontAssetUrl, storefrontFetch, storefrontHref } from '../../../../lib/storefrontApi';

export default function OrderStatusPage() {
  const params = useParams<{ token: string }>();
  const [order, setOrder] = useState<any>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = params.token;
    if (!token) return;
    storefrontFetch(`/storefront/orders/${token}`)
      .then((res) => setOrder(res.data))
      .catch((err) => setError(err.message || 'Order not found'));
  }, [params.token]);

  const paid = Boolean(order?.paid);
  const items = order?.items || [];

  return (
    <main className="sf-main">
      <h1>Order status</h1>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {!order && !error ? <p className="sf-muted">Loading order…</p> : null}
      {order ? (
        <section className="sf-split">
          <div>
            {(items as Array<any>).map((line, idx) => (
              <article key={`${line.product_id || idx}`} className="sf-line">
                {line.image_url ? (
                  <img className="sf-thumb" src={storefrontAssetUrl(line.image_url)} alt="" />
                ) : (
                  <div className="sf-thumb-fallback" aria-hidden>{String(line.name || 'Item').slice(0, 1)}</div>
                )}
                <div>
                  <h2>{line.name || 'Item'}</h2>
                  {line.variant_name ? <p className="sf-muted">{line.variant_name}</p> : null}
                  <p className="sf-muted">× {line.quantity}</p>
                </div>
                <p className="sf-price">{shopMoney(line.line_total, order.currency)}</p>
              </article>
            ))}
            {!items.length ? <p className="sf-muted">Keep this tracking link for your order.</p> : null}
          </div>
          <aside className="sf-summary">
            <p className="sf-chip">{order.status}</p>
            <h2>Order {order.order_number}</h2>
            <p className="sf-price">{shopMoney(order.total_amount, order.currency)}</p>
            <p className="sf-muted">
              {order.message ||
                (paid
                  ? 'Payment received. Thank you.'
                  : 'Keep this link to check your order. It shows as paid once the shop receives your payment.')}
            </p>
            <p className="sf-actions">
              <Link className="sf-btn" href={storefrontHref('/storefront')}>Back to shop</Link>
            </p>
          </aside>
        </section>
      ) : null}
    </main>
  );
}
