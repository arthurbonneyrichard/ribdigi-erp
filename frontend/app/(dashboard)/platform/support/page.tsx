'use client';

import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { api, apiFetch } from '../../../../lib/api';
import { formatWhen, type FormatPrefs } from '../../../../lib/format';
import { INDUSTRIES, INDUSTRY_LABELS } from '../../../../lib/industries';
import { getMe } from '../../../../lib/meCache';
import { useCompanyFormat } from '../../../../lib/useCompanyFormat';

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

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  in_progress: 'In progress',
  waiting_for_tenant: 'Waiting on company',
  resolved: 'Resolved',
  closed: 'Closed',
};

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Low',
  normal: 'Normal',
  high: 'High',
  urgent: 'Urgent',
};

const ACTION_LABEL: Record<string, string> = {
  support_ticket_created: 'Opened',
  support_ticket_replied: 'Public reply',
  support_ticket_internal_note: 'Staff note',
  support_ticket_resolved: 'Marked resolved',
  support_ticket_closed: 'Closed',
  support_ticket_reopened: 'Reopened',
  support_ticket_status_changed: 'Status changed',
  support_ticket_category_changed: 'Category changed',
  support_ticket_priority_changed: 'Priority changed',
  support_ticket_assigned: 'Assignee changed',
  support_ticket_attachment: 'File added',
};

function plain(map: Record<string, string>, code: string): string {
  return map[code] || code.replace(/_/g, ' ');
}

function showWhen(value: string | null | undefined, prefs: FormatPrefs | null): string {
  if (!value) return '—';
  return formatWhen(value, prefs) || '—';
}

export default function SupportDeskPage() {
  const prefs = useCompanyFormat();
  const ticketRef = useRef<HTMLElement | null>(null);
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

  useEffect(() => {
    if (!detail) return;
    if (window.matchMedia('(max-width: 1099px)').matches) {
      ticketRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [detail?.ticket.id]);

  function pickStatus(next: string) {
    setStatus((current) => (current === next ? '' : next));
  }

  function clearFilters() {
    setQ('');
    setStatus('');
    setPriority('');
    setCategory('');
    setIndustry('');
    setAssignee('');
    setFromDate('');
    setToDate('');
  }

  function personName(id: string | null): string {
    if (!id) return 'Unassigned';
    return staff.find((person) => person.id === id)?.full_name || 'Assigned';
  }

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

  const allowedCategories = detail
    ? (detail.allowed_categories?.length ? detail.allowed_categories : categories)
    : [];
  const categoryChoices = detail && allowedCategories.some((item) => item.code === draftCategory)
    ? allowedCategories
    : detail
      ? [...allowedCategories, { code: draftCategory, label: detail.ticket.category_label || draftCategory }]
      : [];

  return (
    <div className="plat desk">
      <header className="plat-hero">
        <div>
          <p className="plat-kicker">Software owner</p>
          <h1>Support Desk</h1>
          <p className="plat-sub">Work company tickets here. A public reply goes to the company. A staff note stays on this desk.</p>
        </div>
      </header>
      {error ? <p className="plat-msg desk-alert" role="alert">{error}</p> : null}
      {queueError ? <p className="plat-msg desk-alert" role="alert">{queueError}</p> : null}
      {notice ? <p className="plat-msg" role="status">{notice}</p> : null}
      {loading ? <p className="muted">Loading support desk…</p> : null}
      <div className="plat-stats">
        <button className={`plat-stat${status === 'new' ? ' is-on' : ''}`} type="button" aria-pressed={status === 'new'} onClick={() => pickStatus('new')}><span>New</span><strong>{counts?.new ?? '—'}</strong></button>
        <button className={`plat-stat${status === 'in_progress' ? ' is-on' : ''}`} type="button" aria-pressed={status === 'in_progress'} onClick={() => pickStatus('in_progress')}><span>In progress</span><strong>{counts?.in_progress ?? '—'}</strong></button>
        <button className={`plat-stat${status === 'waiting_for_tenant' ? ' is-on' : ''}`} type="button" aria-pressed={status === 'waiting_for_tenant'} onClick={() => pickStatus('waiting_for_tenant')}><span>Waiting on company</span><strong>{counts?.waiting_for_tenant ?? '—'}</strong></button>
        <button className={`plat-stat ok${status === 'resolved' ? ' is-on' : ''}`} type="button" aria-pressed={status === 'resolved'} onClick={() => pickStatus('resolved')}><span>Resolved</span><strong>{counts?.resolved ?? '—'}</strong></button>
        <button
          className="plat-stat bad"
          type="button"
          aria-label="Show failed notifications"
          onClick={() => {
            deliveriesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }}
        >
          <span>Failed email</span>
          <strong>{counts?.failed_notifications ?? '—'}</strong>
        </button>
      </div>
      <section className="plat-panel desk-filters">
        <div className="desk-panel-head"><h2>Filters</h2></div>
        <form className="support-filters" onSubmit={applyFilters}>
          <label><span>Reference or company</span><input aria-label="Search tickets" value={q} onChange={(event) => setQ(event.target.value)} /></label>
          <label><span>Status</span>
            <select aria-label="Desk status filter" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All</option>
              <option value="new">New</option>
              <option value="in_progress">In progress</option>
              <option value="waiting_for_tenant">Waiting on company</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <label><span>Priority</span>
            <select aria-label="Desk priority filter" value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="">All</option>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          <label><span>Industry</span>
            <select aria-label="Desk industry filter" value={industry} onChange={(event) => setIndustry(event.target.value)}>
              <option value="">All</option>
              {INDUSTRIES.map((code) => <option key={code} value={code}>{INDUSTRY_LABELS[code] || code}</option>)}
            </select>
          </label>
          <label><span>Category</span>
            <select aria-label="Desk category filter" value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">All</option>
              {categories.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
            </select>
          </label>
          <label><span>Assignee</span>
            <select aria-label="Desk assignee filter" value={assignee} onChange={(event) => setAssignee(event.target.value)}>
              <option value="">All</option>
              <option value="unassigned">Unassigned</option>
              {staff.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
            </select>
          </label>
          <label><span>From</span><input aria-label="Desk from date" type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} /></label>
          <label><span>To</span><input aria-label="Desk to date" type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} /></label>
          <div className="desk-filter-actions">
            <button className="btn btn-primary" type="submit">Apply filters</button>
            <button className="btn" type="button" aria-label="Clear ticket filters" onClick={clearFilters}>Clear</button>
          </div>
        </form>
      </section>
      <div className="desk-split">
      <section className="plat-panel desk-queue">
        <div className="desk-panel-head">
          <h2>Queue</h2>
          {ticketTotal > 0 ? <p className="muted">Showing {rows.length} of {ticketTotal}</p> : null}
        </div>
        {!loading && ticketTotal === 0 ? <p className="muted">No tickets match these filters.</p> : null}
        <div className="support-table-wrap">
          <table>
            <colgroup>
              <col className="desk-col-ticket" />
              <col className="desk-col-company" />
              <col className="desk-col-status" />
              <col className="desk-col-priority" />
              <col className="desk-col-person" />
              <col className="desk-col-when" />
            </colgroup>
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Company</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Assignee</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={detail?.ticket.id === row.id ? 'is-selected' : undefined}>
                  <td>
                    <button className="desk-ref" type="button" aria-label={`Open ticket ${row.reference}`} onClick={() => openTicket(row.id).catch((err) => setError(errText(err)))}>
                      {row.reference}
                    </button>
                    <span className="desk-subject">{row.subject}</span>
                  </td>
                  <td>
                    <span className="plat-co">{row.tenant?.company_name || row.tenant?.slug || '—'}</span>
                    <span className="desk-meta">{INDUSTRY_LABELS[row.tenant?.industry || ''] || row.tenant?.industry || '—'} · {row.category_label || row.category}</span>
                  </td>
                  <td><span className={`desk-badge ${row.status}`}>{plain(STATUS_LABEL, row.status)}</span></td>
                  <td><span className={`desk-badge ${row.priority}`}>{plain(PRIORITY_LABEL, row.priority)}</span></td>
                  <td>{personName(row.assignee_user_id)}</td>
                  <td>{showWhen(row.updated_at, prefs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length < ticketTotal ? (
          <button className="btn" type="button" disabled={busy} onClick={() => loadMore()}>Load more tickets</button>
        ) : null}
      </section>
      <section className={`plat-panel desk-ticket${detail ? '' : ' is-empty'}`} ref={ticketRef}>
        {detail ? (
          <>
          <div className="desk-ticket-head">
            <div>
              <p className="desk-kicker">{detail.ticket.reference}</p>
              <h2>{detail.ticket.subject}</h2>
            </div>
            <button className="btn" type="button" aria-label="Hide ticket" onClick={() => setDetail(null)}>Hide</button>
          </div>
          <p className="desk-description">{detail.ticket.description}</p>
          <div className="desk-facts">
            <span><small>Company</small><strong>{detail.tenant?.company_name || 'Company'}</strong></span>
            <span><small>Workspace</small>{detail.tenant?.slug || '—'}</span>
            <span><small>Industry</small>{INDUSTRY_LABELS[detail.tenant?.industry || ''] || detail.tenant?.industry || '—'}</span>
            <span><small>Status</small>{detail.tenant?.status ? `${detail.tenant.status.charAt(0).toUpperCase()}${detail.tenant.status.slice(1).replace(/_/g, ' ')}` : '—'}</span>
            <span><small>Email</small>{detail.tenant?.email || '—'}</span>
            <span><small>Phone</small>{detail.tenant?.phone || '—'}</span>
            <span><small>Opened</small>{showWhen(detail.ticket.created_at, prefs)}</span>
            <span><small>Resolved</small>{showWhen(detail.ticket.resolved_at, prefs)}</span>
            <span><small>Closed</small>{showWhen(detail.ticket.closed_at, prefs)}</span>
          </div>
          <div className="support-filters">
            <label><span>Status</span>
              <select aria-label="Ticket status" value={draftStatus} onChange={(event) => setDraftStatus(event.target.value)}>
                <option value="new">New</option>
                <option value="in_progress">In progress</option>
                <option value="waiting_for_tenant">Waiting on company</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </label>
            <label><span>Priority</span>
              <select aria-label="Ticket priority" value={draftPriority} onChange={(event) => setDraftPriority(event.target.value)}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>
            <label><span>Category</span>
              <select aria-label="Ticket category" value={draftCategory} onChange={(event) => setDraftCategory(event.target.value)}>
                {categoryChoices.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
              </select>
            </label>
            <label><span>Assignee</span>
              <select aria-label="Ticket assignee" value={draftAssignee} onChange={(event) => setDraftAssignee(event.target.value)}>
                <option value="">Unassigned</option>
                {staff.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}
              </select>
            </label>
            <div className="desk-filter-actions">
              <button className="btn btn-primary" type="button" disabled={busy} aria-label="Save ticket changes" onClick={saveTicket}>Save</button>
              <button className="btn btn-danger" type="button" disabled={busy} aria-label="Close ticket" onClick={() => closeOrReopen('close')}>Close</button>
              <button className="btn btn-ok" type="button" disabled={busy} aria-label="Reopen ticket" onClick={() => closeOrReopen('reopen')}>Reopen</button>
            </div>
          </div>
          <h3>Conversation</h3>
          {detail.messages.length === 0 ? <p className="muted">No replies yet.</p> : null}
          <div className="support-thread">
            {detail.messages.map((message) => (
              <article key={message.id} className={message.visibility === 'internal' ? 'support-msg internal' : 'support-msg'}>
                <p className="muted">{message.visibility === 'internal' ? 'Staff note' : 'Public reply'} · {message.author?.full_name || 'User'} · {showWhen(message.created_at, prefs)}</p>
                <p>{message.body}</p>
              </article>
            ))}
          </div>
          <div className="desk-compose">
            <form onSubmit={sendReply}>
              <label><span>Reply to the company</span><textarea aria-label="Public reply" value={reply} onChange={(event) => setReply(event.target.value)} rows={4} placeholder="This is emailed to the company." /></label>
              <button className="btn btn-primary" type="submit" disabled={busy}>Send public reply</button>
            </form>
            <form onSubmit={sendNote}>
              <label><span>Note for staff</span><textarea aria-label="Internal note" value={note} onChange={(event) => setNote(event.target.value)} rows={4} placeholder="Only people on this desk can see this." /></label>
              <button className="btn" type="submit" disabled={busy}>Save internal note</button>
            </form>
          </div>
          <details className="desk-fold">
            <summary>Attachments ({detail.attachments.length})</summary>
            {detail.attachments.length === 0 ? <p className="muted">No files on this ticket.</p> : (
              <ul className="desk-files">
                {detail.attachments.map((file) => (
                  <li key={file.id}>
                    <button className="btn" type="button" aria-label={`Download ${file.filename}`} onClick={() => downloadAttachment(file)}>{file.filename}</button>
                  </li>
                ))}
              </ul>
            )}
          </details>
          <details className="desk-fold">
            <summary>History ({detail.events.length})</summary>
            <div className="support-table-wrap">
              <table>
                <thead><tr><th>When</th><th>Action</th><th>Actor</th></tr></thead>
                <tbody>
                  {detail.events.map((event) => (
                    <tr key={event.id}><td>{showWhen(event.created_at, prefs)}</td><td>{plain(ACTION_LABEL, event.action)}</td><td>{event.actor?.full_name || '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          </>
        ) : (
          <div className="desk-empty">
            <h2>Choose a ticket</h2>
            <p>Open a reference in the queue. Reply in public when the company should see it. Save a staff note when they should not.</p>
          </div>
        )}
      </section>
      </div>
      {canNotify ? (
        <section className="plat-panel desk-people">
          <div className="desk-panel-head"><h2>Who gets ticket email</h2></div>
          <p className="muted">Active recipients are emailed when a company needs support. This page does not store mail-server passwords.</p>
          {emailWarning ? <p role="status">{emailWarning}</p> : null}
          <form className="desk-inline" onSubmit={addRecipient}>
            <label><span>Email</span><input aria-label="New support recipient" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} placeholder="name@company.com" /></label>
            <div className="desk-filter-actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>Add recipient</button>
            </div>
          </form>
          {recipientNote ? <p role="alert">{recipientNote}</p> : recipients.length === 0 ? <p className="muted">No recipients yet.</p> : null}
          <div className="support-table-wrap">
            <table>
              <colgroup>
                <col className="desk-col-email" />
                <col className="desk-col-flag" />
                <col className="desk-col-delivery" />
                <col className="desk-col-test" />
                <col className="desk-col-actions" />
              </colgroup>
              <thead>
                <tr><th>Email</th><th>Active</th><th>Latest delivery</th><th>Last test</th><th>Actions</th></tr>
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
                      <div className="desk-row-actions">
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
      <section className="plat-panel desk-mail" ref={deliveriesRef} id="support-deliveries">
        <div className="desk-panel-head"><h2>Email still to send</h2></div>
        <p className="muted">These messages stay queued until email is sent. Retry uses the same delivery and does not create a second email.</p>
        {mailNote ? <p role="alert">{mailNote}</p> : deliveries.length === 0 ? <p className="muted">No pending or failed notifications.</p> : null}
        <div className="support-table-wrap">
          <table>
            <colgroup>
              <col className="desk-col-email" />
              <col className="desk-col-delivery" />
              <col className="desk-col-flag" />
              <col className="desk-col-flag" />
              <col />
              <col className="desk-col-flag" />
            </colgroup>
            <thead><tr><th>Recipient</th><th>Event</th><th>Status</th><th>Attempts</th><th>Error</th><th>Actions</th></tr></thead>
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
