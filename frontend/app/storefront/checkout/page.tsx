'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';
import {
  cartToken,
  setCartToken,
  shopMoney,
  shopperToken,
  storefrontFetch,
  storefrontHref,
} from '../../../lib/storefrontApi';
import { useStorefrontShell } from '../StorefrontShell';

type Line = {
  name: string;
  quantity: number;
  line_total: number;
  variant_name?: string | null;
};

export default function CheckoutPage() {
  const router = useRouter();
  const { meta, currency, refreshCart } = useStorefrontShell();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [signedIn, setSignedIn] = useState(false);
  const [fulfillment, setFulfillment] = useState<'delivery' | 'pickup'>('delivery');
  const [address, setAddress] = useState('');
  const [lines, setLines] = useState<Line[]>([]);
  const [subtotal, setSubtotal] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (meta.allow_pickup && !meta.allow_delivery) setFulfillment('pickup');
    const token = cartToken();
    if (!token) {
      setLines([]);
      setSubtotal(0);
    } else {
      storefrontFetch(`/storefront/cart/${token}`)
        .then((res) => {
          setLines(res.data?.items || []);
          setSubtotal(Number(res.data?.subtotal || 0));
          setError('');
        })
        .catch((err: { message?: string }) => {
          setLines([]);
          setSubtotal(0);
          setError(err.message || 'Could not load cart');
        });
    }
    if (!shopperToken()) return;
    storefrontFetch('/storefront/account/me')
      .then((res) => {
        setSignedIn(true);
        setName(res.data?.name || '');
        setEmail(res.data?.email || '');
      })
      .catch(() => setSignedIn(false));
  }, [meta.allow_delivery, meta.allow_pickup]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const token = cartToken();
    if (!token || !lines.length) {
      setError('Your cart is empty.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const res = await storefrontFetch('/storefront/checkout', {
        method: 'POST',
        body: JSON.stringify({
          cart_token: token,
          guest_name: name.trim() || null,
          guest_email: email.trim() || null,
          guest_phone: phone.trim() || null,
          fulfillment,
          delivery_address: fulfillment === 'delivery' ? address.trim() || null : null,
        }),
      });
      setCartToken(null);
      await refreshCart();
      const tracking = res.data?.tracking_token;
      if (res.data?.payment?.checkout_url) {
        window.location.href = res.data.payment.checkout_url;
        return;
      }
      router.push(storefrontHref(`/storefront/order/${tracking}`));
    } catch (err: any) {
      setError(err.message || 'Checkout failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="sf-main">
      <h1>{signedIn ? 'Checkout' : 'Guest checkout'}</h1>
      <p className="sf-lead">
        {signedIn
          ? 'You are signed in, so this order is saved to your account.'
          : 'No account needed. Make one later if you want to see your past orders.'}
      </p>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {!lines.length ? (
        <section className="sf-empty" role="status">
          <p className="sf-empty-title">Your cart is empty</p>
          <p className="sf-muted">Add a published product before checking out. Stock is reserved only when you place the order.</p>
          <p className="sf-actions">
            <Link className="sf-btn" href={storefrontHref('/storefront')}>Continue shopping</Link>
          </p>
        </section>
      ) : (
        <div className="sf-split">
          <form className="sf-form" onSubmit={submit}>
            <label>
              Full name
              <input
                aria-label="Checkout customer name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required={!signedIn}
              />
            </label>
            <label>
              Email
              <input aria-label="Checkout customer email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>
              Phone
              <input
                aria-label="Checkout customer phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+233..."
              />
            </label>
            <label>
              Fulfillment
              <select aria-label="Checkout fulfillment" value={fulfillment} onChange={(e) => setFulfillment(e.target.value as 'delivery' | 'pickup')}>
                {meta.allow_delivery !== false ? <option value="delivery">Delivery</option> : null}
                {meta.allow_pickup ? <option value="pickup">Pickup</option> : null}
              </select>
            </label>
            {fulfillment === 'delivery' ? (
              <label>
                Delivery address
                <textarea aria-label="Checkout delivery address" value={address} onChange={(e) => setAddress(e.target.value)} required />
              </label>
            ) : (
              <p className="sf-muted">{meta.pickup_address ? `Pickup at ${meta.pickup_address}` : 'Pickup details are on the shipping policy.'}</p>
            )}
            <button type="submit" aria-label="Place online order" disabled={busy}>
              Place order
            </button>
          </form>
          <aside className="sf-summary">
            <h2>Order</h2>
            {lines.map((line, idx) => (
              <p key={`${line.name}-${idx}`} className="sf-muted">
                {line.name}{line.variant_name ? ` · ${line.variant_name}` : ''} × {line.quantity} · {shopMoney(line.line_total, currency)}
              </p>
            ))}
            <p className="sf-price">{shopMoney(subtotal, currency)}</p>
            <h2>Payment</h2>
            <p className="sf-muted">
              Place your order now and pay when it is delivered, or when you collect it at the shop: cash, mobile
              money or card. The shop confirms your order once your payment arrives.
            </p>
            <p className="sf-actions">
              <Link className="sf-btn sf-btn-ghost" href={storefrontHref('/storefront/cart')}>Back to cart</Link>
              <Link className="sf-btn sf-btn-ghost" href={storefrontHref('/storefront/account')}>{signedIn ? 'Account' : 'Sign in'}</Link>
            </p>
          </aside>
        </div>
      )}
    </main>
  );
}
