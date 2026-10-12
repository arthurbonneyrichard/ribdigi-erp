'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, apiFetch } from '../../../../lib/api';
import { INDUSTRIES, INDUSTRY_LABELS } from '../../../../lib/industries';
import { getMe } from '../../../../lib/meCache';

type Option = { code: string; label: string };
type Staff = { id: string; full_name: string; email: string; role: string };
type Ticket = {
  id: string;
  reference: string;
  subject: string;
  description: string;
  category: string;
  category_label: string;
  priority: string;
  status: string;
  assignee_user_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  tenant?: { company_name?: string; slug?: string; industry?: string; status?: string; email?: string; phone?: string } | null;
};
type Message = { id: string; visibility: string; body: string; created_at: string | null; author?: { full_name?: string } | null };
type EventRow = { id: string; action: string; created_at: string | null; before?: unknown; after?: unknown; actor?: { full_name?: string } | null };
type Attachment = { id: string; filename: string; content_type: string; size_bytes: number };
type Detail = {
  ticket: Ticket;
  messages: Message[];
  attachments: Attachment[];
  events: EventRow[];
  tenant?: Ticket['tenant'];
  allowed_categories?: Option[];
};
type Counts = { new: number; in_progress: number; waiting_for_tenant: number; resolved: number; failed_notifications: number };
type Recipient = {
  id: string;
  email: string;
  is_active: boolean;
  last_test_status: string | null;
  last_test_error: string | null;
  latest_delivery?: { status?: string; last_error?: string | null; event_type?: string } | null;
};
type Delivery = { id: string; recipient_email: string; event_type: string; status: string; attempts: number; last_error: string | null; subject: string };

const EMAIL_RE =
  /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+$/;
const NOTIFY_ROLES = new Set(['super_admin', 'platform_owner', 'platform_admin']);

function normalizeEmail(value: string): string | null {
  const compact = value.replace(/\s+/g, '');
  if (!compact || compact.length > 254 || !EMAIL_RE.test(compact)) return null;
  return compact.toLowerCase();
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'Request failed';
}

function when(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function SupportDeskPage() {
  const [canNotify, setCanNotify] = useState(false);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [categories, setCategories] = useState<Option[]>([]);
  const [staff, setStaff] = useState<Staff[]>([]);
  const [rows, setRows] = useState<Ticket[]>([]);
  const [ticketTotal, setTicketTotal] = useState(0);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [category, setCategory] = useState('');
  const [industry, setIndustry] = useState('');
  const [assignee, setAssignee] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [reply, setReply] = useState('');
  const [note, setNote] = useState('');
  const [draftStatus, setDraftStatus] = useState('');
  const [draftPriority, setDraftPriority] = useState('');
  const [draftCategory, setDraftCategory] = useState('');
  const [draftAssignee, setDraftAssignee] = useState('');
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [emailWarning, setEmailWarning] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [editId, setEditId] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const deliveriesRef = useRef<HTMLElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [queueError, setQueueError] = useState('');
  const [mailNote, setMailNote] = useState('');
  const [recipientNote, setRecipientNote] = useState('');
  const [notice, setNotice] = useState('');

  const ticketQuery = useCallback((offset = 0) => {
    const params = new URLSearchParams();
    if (q.trim()) params.set('q', q.trim());
    if (status) params.set('status', status);
    if (priority) params.set('priority', priority);
    if (category) params.set('category', category);
    if (industry) params.set('industry', industry);
    if (assignee) params.set('assignee', assignee);
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    if (offset > 0) params.set('offset', String(offset));
    return params;
  }, [assignee, category, fromDate, industry, priority, q, status, toDate]);

  const loadList = useCallback(async () => {
    const body = await api(`/support/desk/tickets?${ticketQuery(0).toString()}`);
    const items = body.data?.items || [];
    setRows(items);
    setTicketTotal(typeof body.data?.total === 'number' ? body.data.total : items.length);
  }, [ticketQuery]);

  const loadCounts = useCallback(async () => {
    const body = await api('/support/desk/counts');
    setCounts(body.data);
  }, []);

  const openTicket = useCallback(async (id: string) => {
    const body = await api(`/support/desk/tickets/${id}`);
    const next = body.data as Detail;
    setDetail(next);
    setDraftStatus(next.ticket.status);
    setDraftPriority(next.ticket.priority);
    setDraftCategory(next.ticket.category);
    setDraftAssignee(next.ticket.assignee_user_id || '');
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await getMe();
        const role = me.data?.role || '';
        if (cancelled) return;
        setCanNotify(NOTIFY_ROLES.has(role));
        if (!NOTIFY_ROLES.has(role)) return;
        const rec = await api('/support/desk/recipients');
        if (cancelled) return;
        setRecipients(rec.data?.recipients || []);
        setEmailWarning(rec.data?.email?.warning || '');
      } catch (err) {
        if (!cancelled) setRecipientNote(errText(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [meta, people] = await Promise.all([
          api('/support/desk/categories'),
          api('/support/desk/staff'),
        ]);
        if (cancelled) return;
        setCategories(meta.data?.categories || []);
        setStaff(people.data || []);
      } catch (err) {
        if (!cancelled) setError(errText(err));
      }
      try {
        await loadCounts();
      } catch (err) {
        if (!cancelled) setError(errText(err));
      }
      try {
        const mail = await api('/support/desk/deliveries?status=actionable');
        if (!cancelled) {
          setDeliveries(mail.data?.items || []);
          setMailNote('');
        }
      } catch (err) {
        if (!cancelled) setMailNote(errText(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadCounts]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        await loadList();
        if (!cancelled) setQueueError('');
      } catch (err) {
        if (!cancelled) setQueueError(errText(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadList]);

  async function applyFilters(event: FormEvent) {
    event.preventDefault();
    setQueueError('');
    try {
      await loadList();
    } catch (err) {
      setQueueError(errText(err));
    }
  }

  async function loadMore() {
    setBusy(true);
    setQueueError('');
    try {
      const body = await api(`/support/desk/tickets?${ticketQuery(rows.length).toString()}`);
      const more = body.data?.items || [];
      setRows((current) => [...current, ...more]);
      if (typeof body.data?.total === 'number') setTicketTotal(body.data.total);
    } catch (err) {
      setQueueError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(event: FormEvent) {
    event.preventDefault();
    if (!detail || !reply.trim()) {
      setError('Write a public reply before sending.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/tickets/${detail.ticket.id}/replies`, {
        method: 'POST',
        body: JSON.stringify({ body: reply.trim() }),
      });
      setReply('');
      setDetail(body.data);
      setNotice('Public reply sent.');
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function sendNote(event: FormEvent) {
    event.preventDefault();
    if (!detail || !note.trim()) {
      setError('Write an internal note before saving.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/tickets/${detail.ticket.id}/notes`, {
        method: 'POST',
        body: JSON.stringify({ body: note.trim() }),
      });
      setNote('');
      setDetail(body.data);
      setNotice('Internal note saved. Tenants are not emailed.');
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveTicket() {
    if (!detail) return;
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/tickets/${detail.ticket.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: draftStatus,
          priority: draftPriority,
          category: draftCategory,
          assignee_user_id: draftAssignee || null,
        }),
      });
      setDetail(body.data);
      setNotice('Ticket updated.');
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function closeOrReopen(kind: 'close' | 'reopen') {
    if (!detail) return;
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/tickets/${detail.ticket.id}/${kind}`, { method: 'POST' });
      setDetail(body.data);
      setDraftStatus(body.data?.ticket?.status || draftStatus);
      setNotice(kind === 'close' ? 'Ticket closed.' : 'Ticket reopened.');
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadAttachment(file: Attachment) {
    if (!detail) return;
    const response = await apiFetch(`/support/tickets/${detail.ticket.id}/attachments/${file.id}`);
    if (!response.ok) {
      setError('Could not download that attachment.');
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = file.filename || 'attachment';
    link.click();
    URL.revokeObjectURL(url);
  }

  async function addRecipient(event: FormEvent) {
    event.preventDefault();
    const email = normalizeEmail(newEmail);
    if (!email) {
      setError('Enter a valid email address.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api('/support/desk/recipients', { method: 'POST', body: JSON.stringify({ email }) });
      setNewEmail('');
      const rec = await api('/support/desk/recipients');
      setRecipients(rec.data?.recipients || []);
      setEmailWarning(rec.data?.email?.warning || '');
      setNotice('Recipient added.');
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveRecipient(row: Recipient) {
    const email = normalizeEmail(editId === row.id ? editEmail : row.email);
    if (!email) {
      setError('Enter a valid email address.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api(`/support/desk/recipients/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ email }),
      });
      setEditId('');
      const rec = await api('/support/desk/recipients');
      setRecipients(rec.data?.recipients || []);
      setNotice('Recipient updated.');
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecipient(row: Recipient) {
    setBusy(true);
    setError('');
    try {
      await api(`/support/desk/recipients/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !row.is_active }),
      });
      const rec = await api('/support/desk/recipients');
      setRecipients(rec.data?.recipients || []);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeRecipient(row: Recipient) {
    setBusy(true);
    setError('');
    try {
      await api(`/support/desk/recipients/${row.id}`, { method: 'DELETE' });
      const rec = await api('/support/desk/recipients');
      setRecipients(rec.data?.recipients || []);
      setNotice('Recipient removed.');
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function testRecipient(row: Recipient) {
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/recipients/${row.id}/test-email`, { method: 'POST' });
      const rec = await api('/support/desk/recipients');
      setRecipients(rec.data?.recipients || []);
      setEmailWarning(body.data?.warning || rec.data?.email?.warning || '');
      setNotice(`Test email ${body.data?.delivery?.status || 'processed'} for ${row.email}.`);
      const mail = await api('/support/desk/deliveries?status=all');
      setDeliveries(mail.data?.items || []);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function retryDelivery(row: Delivery) {
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/desk/deliveries/${row.id}/retry`, { method: 'POST' });
      setNotice(`Retry ${body.data?.resent ? 'sent' : 'checked'} for ${row.recipient_email}.`);
      const mail = await api('/support/desk/deliveries?status=actionable');
      setDeliveries(mail.data?.items || []);
      await loadCounts();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="support-layout">
      <header>
        <h1>Support Desk</h1>
        <p className="muted">Cross-company tickets, public replies, and internal notes.</p>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {queueError ? <p role="alert">{queueError}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {loading ? <p>Loading support desk…</p> : null}
      <div className="stat-grid">
        <button className="stat" type="button" onClick={() => setStatus('new')}><span>New</span><strong>{counts?.new ?? '—'}</strong></button>
        <button className="stat" type="button" onClick={() => setStatus('in_progress')}><span>In Progress</span><strong>{counts?.in_progress ?? '—'}</strong></button>
        <button className="stat" type="button" onClick={() => setStatus('waiting_for_tenant')}><span>Waiting for Tenant</span><strong>{counts?.waiting_for_tenant ?? '—'}</strong></button>
        <button className="stat" type="button" onClick={() => setStatus('resolved')}><span>Resolved</span><strong>{counts?.resolved ?? '—'}</strong></button>
        <button
          className="stat"
          type="button"
          aria-label="Show failed notifications"
          onClick={() => {
            deliveriesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
        >
          <span>Failed Notifications</span>
          <strong>{counts?.failed_notifications ?? '—'}</strong>
        </button>
      </div>
      <section className="card">
        <form className="support-filters" onSubmit={applyFilters}>
          <label>Reference or company<input aria-label="Search tickets" value={q} onChange={(event) => setQ(event.target.value)} /></label>
          <label>Status
            <select aria-label="Desk status filter" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All</option>
              <option value="new">New</option>
              <option value="in_progress">In Progress</option>
              <option value="waiting_for_tenant">Waiting for Tenant</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <label>Priority
            <select aria-label="Desk priority filter" value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">All</option>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          <label>Industry
            <select aria-label="Desk industry filter" value={industry} onChange={(event) => setIndustry(event.target.value)}>
              <option value="">All</option>
              {INDUSTRIES.map((code) => <option key={code} value={code}>{INDUSTRY_LABELS[code] || code}</option>)}
            </select>
          </label>
          <label>Category
            <select aria-label="Desk category filter" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">All</option>
              {categories.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
            </select>
          </label>
          <label>Assignee
            <select aria-label="Desk assignee filter" value={assignee} onChange={(event) => setAssignee(event.target.value)}>
              <option value="">All</option>
              <option value="unassigned">Unassigned</option>
              {staff.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
            </select>
          </label>
          <label>From<input aria-label="Desk from date" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label>
          <label>To<input aria-label="Desk to date" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>
          <button className="btn btn-primary" type="submit">Apply filters</button>
        </form>
        {!loading && ticketTotal === 0 ? <p className="muted">No tickets match these filters.</p> : null}
        {ticketTotal > 0 ? <p className="muted">Showing {rows.length} of {ticketTotal}.</p> : null}
        <div className="support-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Company</th>
                <th>Industry</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Category</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <button className="btn" type="button" aria-label={`Open ticket ${row.reference}`} onClick={() => openTicket(row.id).catch((err) => setError(errText(err)))}>
                      {row.reference}
                    </button>
                  </td>
                  <td>{row.tenant?.company_name || row.tenant?.slug || '—'}</td>
                  <td>{INDUSTRY_LABELS[row.tenant?.industry || ''] || row.tenant?.industry || '—'}</td>
                  <td>{row.subject}</td>
                  <td>{row.status}</td>
                  <td>{row.priority}</td>
                  <td>{row.category_label || row.category}</td>
                  <td>{when(row.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length < ticketTotal ? (
          <button className="btn" type="button" disabled={busy} onClick={() => loadMore()}>Load more tickets</button>
        ) : null}
      </section>
      {detail ? (
        <section className="card">
          <h2>{detail.ticket.reference}</h2>
          <p>{detail.ticket.subject}</p>
          <p>{detail.ticket.description}</p>
          <p className="muted">
            {detail.tenant?.company_name} · {detail.tenant?.slug} · {detail.tenant?.industry} · {detail.tenant?.status}
            {detail.tenant?.email ? ` · ${detail.tenant.email}` : ''}
            {detail.tenant?.phone ? ` · ${detail.tenant.phone}` : ''}
          </p>
          <p className="muted">Created {when(detail.ticket.created_at)} · Resolved {when(detail.ticket.resolved_at)} · Closed {when(detail.ticket.closed_at)}</p>
          <div className="support-filters">
            <label>Status
              <select aria-label="Ticket status" value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
                <option value="new">New</option>
                <option value="in_progress">In Progress</option>
                <option value="waiting_for_tenant">Waiting for Tenant</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </label>
            <label>Priority
              <select aria-label="Ticket priority" value={draftPriority} onChange={(event) => setDraftPriority(event.target.value)}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>
            <label>Category
              <select aria-label="Ticket category" value={draftCategory} onChange={(event) => setDraftCategory(event.target.value)}>
                {(() => {
                  const allowed = detail.allowed_categories?.length ? detail.allowed_categories : categories;
                  const choices = allowed.some((item) => item.code === draftCategory)
                    ? allowed
                    : [...allowed, { code: draftCategory, label: detail.ticket.category_label || draftCategory }];
                  return choices.map((item) => <option key={item.code} value={item.code}>{item.label}</option>);
                })()}
              </select>
            </label>
            <label>Assignee
              <select aria-label="Ticket assignee" value={draftAssignee} onChange={(event) => setDraftAssignee(event.target.value)}>
                <option value="">Unassigned</option>
                {staff.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
              </select>
            </label>
            <button className="btn btn-primary" type="button" disabled={busy} aria-label="Save ticket changes" onClick={saveTicket}>Save</button>
            <button className="btn btn-danger" type="button" disabled={busy} aria-label="Close ticket" onClick={() => closeOrReopen('close')}>Close</button>
            <button className="btn btn-ok" type="button" disabled={busy} aria-label="Reopen ticket" onClick={() => closeOrReopen('reopen')}>Reopen</button>
          </div>
          <h3>Conversation</h3>
          <div className="support-thread">
            {detail.messages.map((message) => (
              <article key={message.id} className={message.visibility === 'internal' ? 'support-msg internal' : 'support-msg'}>
                <p className="muted">{message.visibility === 'internal' ? 'Internal note' : 'Public'} · {message.author?.full_name || 'User'} · {when(message.created_at)}</p>
                <p>{message.body}</p>
              </article>
            ))}
          </div>
          <form onSubmit={sendReply}>
            <label>Public reply<textarea aria-label="Public reply" value={reply} onChange={(event) => setReply(event.target.value)} rows={3} /></label>
            <button className="btn btn-primary" type="submit" disabled={busy}>Send public reply</button>
          </form>
          <form onSubmit={sendNote}>
            <label>Internal note<textarea aria-label="Internal note" value={note} onChange={(event) => setNote(event.target.value)} rows={3} /></label>
            <button className="btn" type="submit" disabled={busy}>Save internal note</button>
          </form>
          <h3>Attachments</h3>
          <ul>
            {detail.attachments.map((file) => (
              <li key={file.id}>
                <button className="btn" type="button" aria-label={`Download ${file.filename}`} onClick={() => downloadAttachment(file)}>{file.filename}</button>
              </li>
            ))}
          </ul>
          <h3>History</h3>
          <div className="support-table-wrap">
            <table>
              <thead><tr><th>When</th><th>Action</th><th>Actor</th></tr></thead>
              <tbody>
                {detail.events.map((event) => (
                  <tr key={event.id}><td>{when(event.created_at)}</td><td>{event.action}</td><td>{event.actor?.full_name || '—'}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      {canNotify ? (
        <section className="card">
          <h2>Ticket notification settings</h2>
          <p className="muted">Active recipients are emailed when a company needs support. This page does not store mail-server passwords.</p>
          {emailWarning ? <p role="status">{emailWarning}</p> : null}
          <form className="support-filters" onSubmit={addRecipient}>
            <label>Email<input aria-label="New support recipient" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} /></label>
            <button className="btn btn-primary" type="submit" disabled={busy}>Add recipient</button>
          </form>
          {recipientNote ? <p role="alert">{recipientNote}</p> : recipients.length === 0 ? <p className="muted">No recipients yet.</p> : null}
          <div className="support-table-wrap">
            <table>
              <thead>
                <tr><th>Email</th><th>Active</th><th>Latest delivery</th><th>Last test</th><th></th></tr>
              </thead>
              <tbody>
                {recipients.map((row) => (
                  <tr key={row.id}>
                    <td>
                      {editId === row.id ? (
                        <input aria-label={`Edit recipient ${row.email}`} value={editEmail} onChange={(event) => setEditEmail(event.target.value)} />
                      ) : row.email}
                    </td>
                    <td>{row.is_active ? 'Active' : 'Inactive'}</td>
                    <td>{row.latest_delivery?.status || '—'} {row.latest_delivery?.last_error || ''}</td>
                    <td>{row.last_test_status || '—'} {row.last_test_error || ''}</td>
                    <td>
                      {editId === row.id ? (
                        <button className="btn btn-ok" type="button" aria-label={`Save recipient ${row.email}`} onClick={() => saveRecipient(row)}>Save</button>
                      ) : (
                        <button className="btn" type="button" aria-label={`Edit recipient ${row.email}`} onClick={() => { setEditId(row.id); setEditEmail(row.email); }}>Edit</button>
                      )}
                      <button className="btn" type="button" aria-label={`${row.is_active ? 'Deactivate' : 'Activate'} recipient ${row.email}`} onClick={() => toggleRecipient(row)}>
                        {row.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button className="btn btn-danger" type="button" aria-label={`Remove recipient ${row.email}`} onClick={() => removeRecipient(row)}>Remove</button>
                      <button className="btn" type="button" aria-label={`Send test email to ${row.email}`} onClick={() => testRecipient(row)}>Send test email</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <section className="card" ref={deliveriesRef} id="support-deliveries">
        <h2>Pending and failed deliveries</h2>
        <p className="muted">These messages stay queued until email is sent. Retry uses the same delivery and does not create a second email.</p>
        {mailNote ? <p role="alert">{mailNote}</p> : deliveries.length === 0 ? <p className="muted">No pending or failed notifications.</p> : null}
        <div className="support-table-wrap">
          <table>
            <thead><tr><th>Recipient</th><th>Event</th><th>Status</th><th>Attempts</th><th>Error</th><th></th></tr></thead>
            <tbody>
              {deliveries.map((row) => (
                <tr key={row.id}>
                  <td>{row.recipient_email}</td>
                  <td>{row.event_type}</td>
                  <td>{row.status}</td>
                  <td>{row.attempts}</td>
                  <td>{row.last_error || '—'}</td>
                  <td><button className="btn" type="button" aria-label={`Retry delivery to ${row.recipient_email}`} onClick={() => retryDelivery(row)}>Retry</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
