'use client';

/**
 * Restaurant help and support: short "how do I" guides for every restaurant screen, and
 * support requests to the RIBDIGI team (the shared support desk, with restaurant topics).
 */

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Guide = { area: string; q: string; steps: string[]; href: string; go: string };

const GUIDES: Guide[] = [
  { area: 'Service', q: 'Take an order at a table', href: '/restaurant/till', go: 'Open the till', steps: ['Open the till and start your shift with the cash float.', 'Pick the table (or Takeaway / Delivery), then tap dishes to add them.', 'Tap Send to kitchen. The kitchen screen shows it straight away.'] },
  { area: 'Service', q: 'Take payment and split a bill', href: '/restaurant/bills', go: 'Open bills', steps: ['Open Bills and pick the table’s bill.', 'Choose Cash, Card or MoMo. For cash, type what the guest handed over to see the change.', 'To split, pay part of the bill one way and the rest another way.'] },
  { area: 'Service', q: 'Refund a paid bill', href: '/restaurant/orders', go: 'Open orders', steps: ['Open Orders and show all, including paid ones.', 'Open the bill and choose Refund.', 'A cash refund comes out of the open till shift, so the cash count stays right.'] },
  { area: 'Service', q: 'Open and close a till shift', href: '/restaurant/till', go: 'Open the till', steps: ['On the till, tap Shift and enter the opening float.', 'Use Cash in / Cash out for change top-ups or money taken to the bank.', 'At the end, count the cash and close. Over or short shows on End of day.'] },
  { area: 'Service', q: 'Close off the day', href: '/restaurant/day-close', go: 'Open End of day', steps: ['Open End of day.', 'Clear what it lists: shifts still open, bills not paid.', 'Print the sheet for your file.'] },
  { area: 'Kitchen', q: 'Use the kitchen screen', href: '/restaurant?tab=kitchen', go: 'Open the kitchen', steps: ['Put the Kitchen screen on a tablet in the kitchen (and one at the bar).', 'Tap a dish when it is ready; tap Bump when the whole ticket is done.', 'Tickets turn amber, then red, the longer they wait.'] },
  { area: 'Kitchen', q: 'Mark a dish sold out', href: '/restaurant/ingredients?tab=menu', go: 'Open menu items', steps: ['Open Menu items.', 'Tap Sold out next to the dish. It disappears from the till and the website.', 'Tap Put back when it is available again.'] },
  { area: 'Menu', q: 'Add a dish and its recipe', href: '/restaurant/ingredients?tab=menu', go: 'Open menu items', steps: ['Under Menu items, tap + Menu item: name, price, section, kitchen or bar.', 'Open Recipes and list the ingredients one plate uses.', 'Every sale then takes those ingredients off stock and counts the food cost.'] },
  { area: 'Menu', q: 'Record spoiled or dropped food', href: '/restaurant?tab=waste', go: 'Open waste', steps: ['Open Waste, pick the ingredient and how much.', 'Choose spoilage, damage or waste.', 'It comes off stock and the cost is booked as a running cost.'] },
  { area: 'Stock', q: 'Count stock', href: '/restaurant/ingredients', go: 'Open ingredients', steps: ['Open Ingredients and tap Count on an ingredient.', 'Type what you actually have.', 'The difference is booked as found or lost.'] },
  { area: 'Stock', q: 'Record a market run', href: '/restaurant/purchasing', go: 'Open purchasing', steps: ['Open Purchasing and tap Market run.', 'Say where you bought, pick Cash or MoMo, and list what you bought and what it cost.', 'Save: the stock goes in and the money comes off in one step.'] },
  { area: 'Stock', q: 'Order from a supplier and receive it', href: '/restaurant/purchasing', go: 'Open purchasing', steps: ['Tap + New order, or “Order them” to order everything running low.', 'Send it. When the delivery arrives, open the order and tap Receive delivery into stock.', 'What you owe then shows under Pay suppliers.'] },
  { area: 'Money', q: 'Pay a supplier', href: '/restaurant/payables', go: 'Open pay suppliers', steps: ['Open Pay suppliers and tap Pay next to the supplier.', 'Enter the amount and how you paid.', 'The oldest delivery is paid first.'] },
  { area: 'Money', q: 'Record gas, rent or another cost', href: '/restaurant/expenses', go: 'Open expenses', steps: ['Open Expenses and tap + Expense.', 'Enter the amount, pick the cost type and how you paid. Add a receipt photo if you have one.', 'Rent and wages can be Regular bills so they are recorded for you.'] },
  { area: 'Money', q: 'Bank the day’s takings', href: '/restaurant/money', go: 'Open money', steps: ['Open Money and tap Move money.', 'From Cash to your bank or MoMo account, with the amount.', 'Both balances update straight away.'] },
  { area: 'Money', q: 'See if the restaurant made money', href: '/restaurant/profit', go: 'Open profit and loss', steps: ['Open Profit and loss and pick the period.', 'Food and drink cost should usually be 28–35% of sales.', 'Compare with the period before to see what changed.'] },
  { area: 'Money', q: 'Prepare the VAT return', href: '/restaurant/tax', go: 'Open tax', steps: ['Open Tax and pick last month.', 'Check tax on bills, tax you can claim back, and tax to pay.', 'Download the GRA VAT return and enter it on the GRA portal. Add your TIN on the company profile first.'] },
  { area: 'Guests', q: 'Take orders and bookings online', href: '/restaurant?tab=booking', go: 'Open website and booking', steps: ['Open Website and booking and turn ordering and booking on.', 'Share the link, or connect your own website address.', 'Online orders land on the till and kitchen; bookings show on the booking board.'] },
  { area: 'Staff', q: 'Add a waiter or cashier', href: '/restaurant/staff', go: 'Open staff', steps: ['Open Staff and Permissions and add the person with their role.', 'Waiter: takes orders and seats guests. Restaurant Cashier: also takes payment and closes the till. Kitchen: the kitchen screen, sold out and waste. Restaurant Manager: everything, including refunds, the menu, stock and money.', 'Each person signs in with their own email and password and only sees their own screens.'] },
];

const STATUS_WORDS: Record<string, string> = {
  new: 'Sent',
  in_progress: 'Being worked on',
  waiting_for_tenant: 'Waiting for you',
  resolved: 'Solved',
  closed: 'Closed',
};

function when(value: unknown) {
  if (!value) return '';
  const d = new Date(String(value));
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}

export default function RestaurantHelpPage() {
  const [search, setSearch] = useState('');
  const [openGuide, setOpenGuide] = useState<string | null>(null);
  const [tickets, setTickets] = useState<Row[]>([]);
  const [topics, setTopics] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [sheet, setSheet] = useState<{ kind: 'new' } | { kind: 'ticket'; id: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [meta, list] = await Promise.all([api('/support/categories'), api('/support/tickets?limit=50')]);
      setTopics(meta?.data?.categories || []);
      setTickets(list?.data?.items || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(() => {
    const words = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return GUIDES;
    return GUIDES.filter((g) => words.every((w) => `${g.area} ${g.q} ${g.steps.join(' ')}`.toLowerCase().includes(w)));
  }, [search]);
  const areas = Array.from(new Set(shown.map((g) => g.area)));
  const waiting = tickets.filter((t) => t.status === 'waiting_for_tenant').length;
  const open = tickets.filter((t) => t.status !== 'closed' && t.status !== 'resolved');

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Help</h1>
          <p>Quick answers for every part of the restaurant, and a line to the RIBDIGI support team.</p>
        </div>
        <div className="rd-head-actions">
          <button type="button" className="rd-primary" aria-label="Ask support for help" onClick={() => setSheet({ kind: 'new' })}>
            Ask support
          </button>
        </div>
      </header>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}
      {waiting ? (
        <div className="rd-close-status" role="status">
          <strong>Support is waiting for your answer on {waiting} {waiting === 1 ? 'request' : 'requests'}.</strong>
        </div>
      ) : null}

      <input className="rd-search rd-help-search" type="search" placeholder="How do I… (refund, split a bill, VAT, market run)" aria-label="Search help" value={search} onChange={(e) => setSearch(e.target.value)} />

      <div className="rd-help">
        {areas.map((area) => (
          <section key={area} className="rd-panel">
            <div className="rd-panel-head">
              <h2>{area}</h2>
            </div>
            <ul className="rd-guides">
              {shown
                .filter((g) => g.area === area)
                .map((g) => {
                  const expanded = openGuide === g.q || Boolean(search.trim());
                  return (
                    <li key={g.q} className={expanded ? 'open' : ''}>
                      <button type="button" className="rd-guide-q" aria-expanded={expanded} onClick={() => setOpenGuide(openGuide === g.q ? null : g.q)}>
                        {g.q}
                      </button>
                      {expanded ? (
                        <div className="rd-guide-a">
                          <ol>
                            {g.steps.map((step) => (
                              <li key={step}>{step}</li>
                            ))}
                          </ol>
                          <Link href={g.href}>{g.go} →</Link>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
            </ul>
          </section>
        ))}
        {!shown.length ? (
          <div className="rd-empty">
            <strong>No guide for that yet</strong>
            <button type="button" className="rd-link" onClick={() => setSheet({ kind: 'new' })}>Ask support instead →</button>
          </div>
        ) : null}
      </div>

      <section className="rd-panel">
        <div className="rd-panel-head">
          <h2>Your support requests</h2>
          <small>{open.length ? `${open.length} open` : 'Nothing open'}</small>
        </div>
        <div className="rd-list rd-list-flat" aria-label="Support requests">
          {tickets.length === 0 ? (
            <div className="rd-empty">
              <strong>No requests yet</strong>Stuck on something? Tap Ask support and we will reply here.
            </div>
          ) : null}
          {tickets.map((t) => (
            <button key={t.id} type="button" className="rd-row" aria-label={`Open support request ${t.reference}`} onClick={() => setSheet({ kind: 'ticket', id: t.id })}>
              <span className="when">{when(t.updated_at || t.created_at)}</span>
              <span className="who">
                <strong>{t.subject}</strong>
                <small>
                  {t.reference} · {t.category_label}
                </small>
              </span>
              <span className={`rd-pill ${t.status === 'waiting_for_tenant' ? 'wait' : t.status === 'closed' || t.status === 'resolved' ? 'grey' : ''}`}>
                {STATUS_WORDS[t.status] || t.status}
              </span>
              <span className="amt" />
            </button>
          ))}
        </div>
      </section>

      {sheet?.kind === 'new' ? (
        <NewRequestSheet
          topics={topics}
          onClose={() => setSheet(null)}
          onDone={async (ticket) => {
            setNotice(`Request ${ticket?.reference || ''} sent. Support replies here.`);
            await load();
            setSheet(ticket?.id ? { kind: 'ticket', id: ticket.id } : null);
          }}
        />
      ) : null}
      {sheet?.kind === 'ticket' ? <TicketSheet id={sheet.id} onClose={() => setSheet(null)} onChanged={load} /> : null}
    </div>
  );
}

function NewRequestSheet({ topics, onClose, onDone }: { topics: Row[]; onClose: () => void; onDone: (ticket: Row | null) => Promise<void> }) {
  const [topic, setTopic] = useState('');
  const [subject, setSubject] = useState('');
  const [what, setWhat] = useState('');
  const [urgent, setUrgent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const help = topics.find((t) => t.code === topic)?.help;

  async function send() {
    if (!topic) return setError('Pick what it is about.');
    if (subject.trim().length < 2) return setError('Give it a short title.');
    if (what.trim().length < 2) return setError('Say what happened.');
    setBusy(true);
    setError('');
    try {
      const res = await api('/support/tickets', {
        method: 'POST',
        body: JSON.stringify({ subject: subject.trim(), description: what.trim(), category: topic, priority: urgent ? 'urgent' : 'normal' }),
      });
      const ticket = res?.data?.ticket || null;
      if (file && ticket?.id) {
        const form = new FormData();
        form.append('file', file);
        await api(`/support/tickets/${ticket.id}/attachments`, { method: 'POST', body: form });
      }
      await onDone(ticket);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label="Ask support" onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>Ask support</h2>
            <p>The RIBDIGI team replies here, usually the same working day.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <span className="rd-field-label">What is it about?</span>
        <div className="rd-chips" role="radiogroup" aria-label="Support topic">
          {topics.map((t) => (
            <button key={t.code} type="button" role="radio" aria-checked={topic === t.code} className={topic === t.code ? 'on' : ''} onClick={() => setTopic(t.code)}>
              {t.label}
            </button>
          ))}
        </div>
        {help ? <p className="rd-hint-line">{help}</p> : null}
        <div className="rd-form-grid">
          <label className="rd-span">
            <span>Short title</span>
            <input aria-label="Support request title" placeholder="Kitchen screen not showing new orders" value={subject} onChange={(e) => setSubject(e.target.value)} />
          </label>
          <label className="rd-span">
            <span>What happened?</span>
            <textarea aria-label="What happened" rows={5} placeholder="What you did, what you expected, and what you saw instead." value={what} onChange={(e) => setWhat(e.target.value)} />
          </label>
          <label className="rd-span">
            <span>Screenshot or photo (optional)</span>
            <input aria-label="Support screenshot" type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </label>
          <label className="rd-check rd-span">
            <input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} aria-label="Urgent: service is stopped" />
            <span>Urgent: we cannot serve or take payment</span>
          </label>
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Send support request" disabled={busy} onClick={() => void send()}>
            {busy ? 'Sending…' : 'Send'}
          </button>
        </div>
      </aside>
    </div>
  );
}

function TicketSheet({ id, onClose, onChanged }: { id: string; onClose: () => void; onChanged: () => Promise<void> }) {
  const [detail, setDetail] = useState<Row | null>(null);
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setDetail((await api(`/support/tickets/${id}`))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<Row | null>) {
    setBusy(true);
    setError('');
    try {
      const next = await fn();
      if (next) setDetail(next);
      await onChanged();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const ticket: Row = detail?.ticket || {};
  const messages: Row[] = (detail?.messages || []).filter((msg: Row) => msg.visibility !== 'internal');
  const closed = ticket.status === 'closed';

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={`Support request ${ticket.reference || ''}`} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{ticket.subject || 'Support request'}</h2>
            <p>
              {ticket.reference} · {ticket.category_label} · {STATUS_WORDS[ticket.status] || ticket.status}
            </p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        {detail ? (
          <ul className="rd-thread" aria-label="Messages">
            <li className="mine">
              <small>You · {when(ticket.created_at)}</small>
              <p>{ticket.description}</p>
            </li>
            {messages.map((msg) => {
              // Support staff hold platform roles; everyone else is someone at this restaurant.
              const role = String(msg.author?.role || '');
              const mine = role !== 'super_admin' && !role.startsWith('platform');
              return (
                <li key={msg.id} className={mine ? 'mine' : 'them'}>
                  <small>
                    {msg.author?.full_name || (mine ? 'You' : 'RIBDIGI support')} · {when(msg.created_at)}
                  </small>
                  <p>{msg.body}</p>
                </li>
              );
            })}
            {(detail.attachments || []).map((a: Row) => (
              <li key={a.id} className="file">
                <small>📎 {a.filename}</small>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rd-empty">Loading…</div>
        )}
        {!closed ? (
          <div className="rd-form-grid">
            <label className="rd-span">
              <span>Reply</span>
              <textarea aria-label="Reply to support" rows={3} value={reply} onChange={(e) => setReply(e.target.value)} />
            </label>
          </div>
        ) : (
          <p className="rd-hint-line">This request is closed. Ask support again if the problem comes back.</p>
        )}
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        {!closed ? (
          <div className="rd-actions">
            <button
              type="button"
              aria-label="Close support request"
              disabled={busy}
              onClick={() => void act(async () => (await api(`/support/tickets/${id}/close`, { method: 'POST' }))?.data || null)}
            >
              It is sorted, close it
            </button>
            <button
              type="button"
              className="rd-primary"
              aria-label="Send reply"
              disabled={busy || !reply.trim()}
              onClick={() =>
                void act(async () => {
                  const res = await api(`/support/tickets/${id}/replies`, { method: 'POST', body: JSON.stringify({ body: reply.trim() }) });
                  setReply('');
                  return res?.data || null;
                })
              }
            >
              Send reply
            </button>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
