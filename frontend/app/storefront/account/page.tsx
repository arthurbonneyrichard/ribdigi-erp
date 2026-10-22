'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState } from 'react';
import { setShopperToken, shopMoney, shopperToken, storefrontFetch, storefrontHref } from '../../../lib/storefrontApi';
import { useStorefrontShell } from '../StorefrontShell';

export default function StorefrontAccountPage() {
  const { currency } = useStorefrontShell();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orders, setOrders] = useState<any[]>([]);
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState('');

  async function loadHistory() {
    if (!shopperToken()) {
      setSignedIn(false);
      setOrders([]);
      return;
    }
    try {
      const res = await storefrontFetch('/storefront/account/orders');
      setSignedIn(true);
      setOrders(res.data?.orders || []);
      setName(res.data?.shopper?.name || '');
    } catch {
      setShopperToken(null);
      setSignedIn(false);
      setOrders([]);
    }
  }

  useEffect(() => {
    void loadHistory();
  }, []);

  async function register(e?: FormEvent) {
    e?.preventDefault();
    setError('');
    try {
      const res = await storefrontFetch('/storefront/account/register', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), email: email.trim(), password }),
      });
      setShopperToken(res.data?.session_token || null);
      setPassword('');
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'Could not create account');
    }
  }

  async function login(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const res = await storefrontFetch('/storefront/account/login', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      });
      setShopperToken(res.data?.session_token || null);
      setPassword('');
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'Could not sign in');
    }
  }

  async function logout() {
    await storefrontFetch('/storefront/account/logout', { method: 'POST' }).catch(() => undefined);
    setShopperToken(null);
    setSignedIn(false);
    setOrders([]);
  }

  return (
    <main className="sf-main">
      <h1>Customer account</h1>
      <p className="sf-lead">This login is for the online store only. It is not ERP staff access.</p>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {signedIn ? (
        <>
          <section className="sf-summary">
            <p>Signed in as {name || email}</p>
            <div className="sf-actions">
              <button type="button" aria-label="Sign out of storefront" onClick={() => void logout()}>
                Sign out
              </button>
            </div>
          </section>
          <h2>Order history</h2>
          {!orders.length ? (
            <section className="sf-empty" role="status">
              <p className="sf-empty-title">No orders yet</p>
              <p className="sf-muted">Place an order from the shop. Payment stays unpaid until a signed webhook or staff collection.</p>
            </section>
          ) : null}
          {orders.map((order) => (
            <article key={order.id} className="sf-card">
              <Link href={storefrontHref(`/storefront/order/${order.tracking_token}`)}>
                <h2>{order.order_number}</h2>
                <p className="sf-muted">{order.status} · {shopMoney(order.total_amount, order.currency || currency)}</p>
              </Link>
            </article>
          ))}
        </>
      ) : (
        <form className="sf-form" onSubmit={login}>
          <label>
            Name
            <input aria-label="Storefront account name" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Email
            <input aria-label="Storefront account email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input aria-label="Storefront account password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <div className="sf-actions">
            <button type="submit" aria-label="Sign in to storefront">Sign in</button>
            <button type="button" aria-label="Create storefront account" onClick={() => void register()}>
              Create account
            </button>
          </div>
        </form>
      )}
    </main>
  );
}
