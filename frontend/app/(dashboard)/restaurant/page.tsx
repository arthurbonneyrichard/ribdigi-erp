'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'next/navigation';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { moduleEnabledForTenant } from '../../../lib/industryModules';

type Row = Record<string, any>;

const ORDER_WORDS: Record<string, string> = {
  dine_in: 'Dine in',
  takeaway: 'Takeaway',
  delivery: 'Delivery',
  cash: 'Cash',
  card: 'Card',
  wallet: 'Wallet',
  mobile_money: 'Mobile Money',
  credit: 'Credit',
  open: 'Open',
  sent: 'In the kitchen',
  preparing: 'Preparing',
  ready: 'Ready',
  completed: 'Completed',
  cancelled: 'Cancelled',
  voided: 'Voided',
  refunded: 'Refunded',
};

function orderWord(code: unknown) {
  const key = String(code || '');
  return ORDER_WORDS[key] || key.replaceAll('_', ' ');
}

export default function RestaurantPage() {
  const tab = useSearchParams().get('tab') || 'dashboard';
  const [summary, setSummary] = useState<Row | null>(null);
  const [tables, setTables] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [kitchen, setKitchen] = useState<Row[]>([]);
  const [reports, setReports] = useState<Row | null>(null);
  const [products, setProducts] = useState<Row[]>([]);
  const [tableForm, setTableForm] = useState({ code: '', name: '', seats: '2' });
  const [orderForm, setOrderForm] = useState({
    service_mode: 'dine_in',
    payment_method: 'cash',
    product_id: '',
    quantity: '1',
    customer_name: '',
  });
  const [recipeForm, setRecipeForm] = useState({ product_id: '', ingredient_id: '', quantity: '1', name: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function refresh() {
    const [sum, tableRes, orderRes, kitchenRes, reportRes, productRes] = await Promise.all([
      api('/restaurant/summary'),
      api('/restaurant/tables'),
      api('/restaurant/orders'),
      api('/restaurant/kitchen'),
      api('/restaurant/reports'),
      api('/products'),
    ]);
    setSummary(sum?.data || null);
    setTables(tableRes?.data || []);
    setOrders(orderRes?.data || []);
    setKitchen(kitchenRes?.data || []);
    setReports(reportRes?.data || null);
    const catalog = productRes?.data;
    setProducts(Array.isArray(catalog) ? catalog : catalog?.items || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message || 'Could not load restaurant'));
  }, []);

  async function createTable(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await api('/restaurant/tables', {
        method: 'POST',
        body: JSON.stringify({
          code: tableForm.code.trim(),
          name: tableForm.name.trim(),
          seats: Number(tableForm.seats) || 2,
        }),
      });
      setTableForm({ code: '', name: '', seats: '2' });
      setMessage('Table saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save table');
    }
  }

  async function createOrder(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await api('/restaurant/orders', {
        method: 'POST',
        body: JSON.stringify({
          service_mode: orderForm.service_mode,
          payment_method: orderForm.payment_method,
          customer_name: orderForm.customer_name.trim() || null,
          lines: [{ product_id: orderForm.product_id, quantity: orderForm.quantity }],
        }),
      });
      setMessage('Order saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save order');
    }
  }

  async function act(orderId: string, action: string) {
    setError('');
    try {
      await api(`/restaurant/orders/${orderId}/${action}`, { method: 'POST' });
      setMessage(`Order ${action}`);
      await refresh();
    } catch (err: any) {
      setError(err.message || `Could not ${action} order`);
    }
  }

  async function createRecipe(event: FormEvent) {
    event.preventDefault();
    setError('');
    try {
      await api('/restaurant/recipes', {
        method: 'POST',
        body: JSON.stringify({
          product_id: recipeForm.product_id,
          name: recipeForm.name.trim() || 'Recipe',
          lines: [{ ingredient_id: recipeForm.ingredient_id, quantity: recipeForm.quantity }],
        }),
      });
      setMessage('Recipe saved');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Could not save recipe');
    }
  }

  const show = (name: string) => tab === 'dashboard' || tab === name;

  return (
    <main className="page">
      <h1>Restaurant</h1>
      <p>Dine-in, takeaway, and delivery. Kitchen tickets follow each item station. Completing an order deducts recipe ingredients.</p>
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      {show('dashboard') && summary && (
        <section className="card" aria-label="Restaurant dashboard">
          <h2>Today</h2>
          <p>Sales: {summary.sales_today}</p>
          <p>Open orders: {summary.open_orders}</p>
          <p>Kitchen queue: {summary.kitchen_backlog}</p>
          <p>Low-stock ingredients: {summary.low_stock_ingredients}</p>
          <p>Tables: {Object.entries(summary.tables || {}).map(([status, count]) => `${status} ${count}`).join(', ') || 'none'}</p>
        </section>
      )}
      {(tab === 'dashboard' || tab === 'tables') && (
        <section className="card">
          <h2>Tables</h2>
          <form onSubmit={createTable}>
            <input aria-label="Restaurant table code" value={tableForm.code} onChange={(e) => setTableForm({ ...tableForm, code: e.target.value })} required />
            <input aria-label="Restaurant table name" value={tableForm.name} onChange={(e) => setTableForm({ ...tableForm, name: e.target.value })} required />
            <input aria-label="Restaurant table seats" value={tableForm.seats} onChange={(e) => setTableForm({ ...tableForm, seats: e.target.value })} />
            <button type="submit" aria-label="Save restaurant table">Save table</button>
          </form>
          <ul>
            {tables.map((row) => (
              <li key={row.id}>{row.code} — {row.name} ({row.status})</li>
            ))}
          </ul>
        </section>
      )}
      {(tab === 'dashboard' || tab === 'orders') && (
        <section className="card">
          <h2>Orders</h2>
          <form onSubmit={createOrder}>
            <select aria-label="Restaurant service mode" value={orderForm.service_mode} onChange={(e) => setOrderForm({ ...orderForm, service_mode: e.target.value })}>
              <option value="dine_in">Dine in</option>
              <option value="takeaway">Takeaway</option>
              <option value="delivery">Delivery</option>
            </select>
            <select aria-label="Restaurant payment method" value={orderForm.payment_method} onChange={(e) => setOrderForm({ ...orderForm, payment_method: e.target.value })}>
              <option value="cash">Cash</option>
              <option value="card">Card</option>
              <option value="wallet">Wallet</option>
              <option value="mobile_money">Mobile Money</option>
              <option value="credit">Credit</option>
            </select>
            <select aria-label="Restaurant menu item" value={orderForm.product_id} onChange={(e) => setOrderForm({ ...orderForm, product_id: e.target.value })} required>
              <option value="">Menu item</option>
              {products.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
            <input aria-label="Restaurant order quantity" value={orderForm.quantity} onChange={(e) => setOrderForm({ ...orderForm, quantity: e.target.value })} />
            <input aria-label="Restaurant customer name" value={orderForm.customer_name} onChange={(e) => setOrderForm({ ...orderForm, customer_name: e.target.value })} />
            <button type="submit" aria-label="Save restaurant order">Save order</button>
          </form>
          <ul>
            {orders.map((row) => (
              <li key={row.id}>
                {row.order_number} {orderWord(row.service_mode)} {orderWord(row.status)} {row.total_amount}
                {row.status === 'open' && (
                  <button type="button" aria-label={`Send order ${row.order_number} to kitchen`} onClick={() => act(row.id, 'send')}>Send to kitchen</button>
                )}
                {row.status !== 'completed' && row.status !== 'cancelled' && row.status !== 'voided' && row.status !== 'refunded' && (
                  <button type="button" aria-label={`Complete order ${row.order_number}`} onClick={() => act(row.id, 'complete')}>Complete</button>
                )}
                {row.status !== 'completed' && row.status !== 'cancelled' && row.status !== 'voided' && row.status !== 'refunded' && (
                  <button type="button" aria-label={`Cancel order ${row.order_number}`} onClick={() => act(row.id, 'cancel')}>Cancel</button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {(tab === 'dashboard' || tab === 'kitchen') && (
        <section className="card" aria-label="Kitchen queue">
          <h2>Kitchen</h2>
          <ul>
            {kitchen.map((row) => (
              <li key={row.id}>{row.station} — {row.status}</li>
            ))}
          </ul>
        </section>
      )}
      {(tab === 'dashboard' || tab === 'recipes') && (
        <section className="card">
          <h2>Recipes</h2>
          <form onSubmit={createRecipe}>
            <input aria-label="Restaurant recipe name" value={recipeForm.name} onChange={(e) => setRecipeForm({ ...recipeForm, name: e.target.value })} />
            <select aria-label="Restaurant recipe menu item" value={recipeForm.product_id} onChange={(e) => setRecipeForm({ ...recipeForm, product_id: e.target.value })} required>
              <option value="">Menu item</option>
              {products.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
            <select aria-label="Restaurant recipe ingredient" value={recipeForm.ingredient_id} onChange={(e) => setRecipeForm({ ...recipeForm, ingredient_id: e.target.value })} required>
              <option value="">Ingredient</option>
              {products.map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
            <input aria-label="Restaurant recipe quantity" value={recipeForm.quantity} onChange={(e) => setRecipeForm({ ...recipeForm, quantity: e.target.value })} />
            <button type="submit" aria-label="Save restaurant recipe">Save recipe</button>
          </form>
        </section>
      )}
      {tab === 'dashboard' && reports && (
        <section className="card">
          <h2>Sales by service</h2>
          <ul>
            {(reports.by_service_mode || []).map((row: Row) => (
              <li key={row.service_mode}>{row.service_mode}: {row.orders} / {row.sales}</li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
