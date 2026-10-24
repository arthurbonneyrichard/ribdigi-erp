'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api, apiFetch } from '../../../lib/api';
import { formatWhen, type FormatPrefs } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';

type Option = { code: string; label: string };
type Ticket = {
  id: string;
  reference: string;
  subject: string;
  description: string;
  category: string;
  category_label: string;
  priority: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
};
type Message = { id: string; visibility: string; body: string; created_at: string | null; author?: { full_name?: string } | null };
type Attachment = { id: string; filename: string; content_type: string; size_bytes: number };
type Detail = { ticket: Ticket; messages: Message[]; attachments: Attachment[] };
type StatusCounts = Record<'new' | 'in_progress' | 'waiting_for_tenant' | 'resolved' | 'closed', number>;

const STATUS_LABEL: Record<string, string> = {
  new: 'New',
  in_progress: 'In progress',
  waiting_for_tenant: 'Waiting on you',
  resolved: 'Resolved',
  closed: 'Closed',
};

const PRIORITY_LABEL: Record<string, string> = {
  low: 'Low',
  normal: 'Normal',
  high: 'High',
  urgent: 'Urgent',
};

const STATUS_ORDER = ['new', 'in_progress', 'waiting_for_tenant', 'resolved', 'closed'] as const;

const TOPIC_HELP: Record<string, string> = {
  account_login: 'Signing in, your password, and which screens your role can open.',
  pos_sales: 'Till sales and receipts, or quotations and invoices when this company uses a sales desk.',
  inventory_stock: 'Products on hand, stock movements, and what is available to sell.',
  purchases_suppliers: 'Suppliers, purchase orders, goods received, supplier bills, and returns.',
  finance_reports: 'Accounts, expenses, and the reports for this company.',
  printing_barcode_receipt: 'Printers, barcode labels, and sale receipts.',
  settings_configuration: 'Company settings, including the business type already saved for this company.',
  bug_other: 'A problem that is not covered by the topics above.',
};

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'Request failed';
}

function plain(map: Record<string, string>, code: string): string {
  return map[code] || code.replace(/_/g, ' ');
}

function showWhen(value: string | null | undefined, prefs: FormatPrefs | null): string {
  if (!value) return '—';
  return formatWhen(value, prefs) || '—';
}

export default function HelpSupportPage() {
  const prefs = useCompanyFormat();
  const [categories, setCategories] = useState<Option[]>([]);
  const [priorities, setPriorities] = useState<string[]>(['low', 'normal', 'high', 'urgent']);
  const [rows, setRows] = useState<Ticket[]>([]);
  const [ticketTotal, setTicketTotal] = useState(0);
  const [counts, setCounts] = useState<StatusCounts | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [status, setStatus] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [q, setQ] = useState('');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState('normal');
  const [reply, setReply] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [guideBusy, setGuideBusy] = useState(false);
  const [guideError, setGuideError] = useState('');

  const loadList = useCallback(async () => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (priorityFilter) params.set('priority', priorityFilter);
    if (categoryFilter) params.set('category', categoryFilter);
    if (q.trim()) params.set('q', q.trim());
    const body = await api(`/support/tickets?${params.toString()}`);
    setRows(body.data?.items || []);
    setTicketTotal(Number(body.data?.total || 0));
  }, [categoryFilter, priorityFilter, q, status]);

  const loadCounts = useCallback(async () => {
    const body = await api('/support/tickets?limit=100');
    const items: Ticket[] = body.data?.items || [];
    const total = Number(body.data?.total || 0);
    if (total > items.length) {
      setCounts(null);
      return;
    }
    const next: StatusCounts = { new: 0, in_progress: 0, waiting_for_tenant: 0, resolved: 0, closed: 0 };
    for (const row of items) {
      if (row.status in next) next[row.status as keyof StatusCounts] += 1;
    }
    setCounts(next);
  }, []);

  const openTicket = useCallback(async (id: string) => {
    const body = await api(`/support/tickets/${id}`);
    setDetail(body.data);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const meta = await api('/support/categories');
        if (cancelled) return;
        const cats: Option[] = meta.data?.categories || [];
        setCategories(cats);
        setPriorities(meta.data?.priorities || ['low', 'normal', 'high', 'urgent']);
        setCategory((current) => current || cats[0]?.code || '');
        await Promise.all([loadList(), loadCounts()]);
      } catch (err) {
        if (!cancelled) setError(errText(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadCounts, loadList]);

  function pickStatus(next: string) {
    setStatus((current) => (current === next ? '' : next));
  }

  function clearFilters() {
    setStatus('');
    setPriorityFilter('');
    setCategoryFilter('');
    setQ('');
  }

  async function createTicket(event: FormEvent) {
    event.preventDefault();
    setError('');
    setNotice('');
    if (subject.trim().length < 2 || description.trim().length < 2 || !category) {
      setError('Subject, description, and category are required.');
      return;
    }
    setBusy(true);
    try {
      const body = await api('/support/tickets', {
        method: 'POST',
        body: JSON.stringify({
          subject: subject.trim(),
          description: description.trim(),
          category,
          priority,
        }),
      });
      setSubject('');
      setDescription('');
      setNotice(`Ticket ${body.data?.ticket?.reference || ''} created.`);
      setDetail(body.data);
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function sendReply(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    if (!reply.trim()) {
      setError('Write a reply before sending.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/tickets/${detail.ticket.id}/replies`, {
        method: 'POST',
        body: JSON.stringify({ body: reply.trim() }),
      });
      setReply('');
      setDetail(body.data);
      setNotice('Reply sent.');
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function closeTicket() {
    if (!detail) return;
    setBusy(true);
    setError('');
    try {
      const body = await api(`/support/tickets/${detail.ticket.id}/close`, { method: 'POST' });
      setDetail(body.data);
      setNotice('Ticket closed.');
      await Promise.all([loadList(), loadCounts()]);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(file: File | null) {
    if (!detail || !file) return;
    setBusy(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      await api(`/support/tickets/${detail.ticket.id}/attachments`, { method: 'POST', body: form });
      await openTicket(detail.ticket.id);
      setNotice('Attachment saved.');
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function downloadAttachment(attachment: Attachment) {
    if (!detail) return;
    setError('');
    try {
      const response = await apiFetch(
        `/support/tickets/${detail.ticket.id}/attachments/${attachment.id}`
      );
      if (!response.ok) {
        setError('Could not download that attachment.');
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = attachment.filename || 'attachment';
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(errText(err));
    }
  }

  async function openGuide() {
    setGuideError('');
    setGuideBusy(true);
    try {
      const response = await apiFetch('/staff-guide');
      const type = (response.headers.get('content-type') || '').toLowerCase();
      if (!response.ok || !type.includes('pdf')) {
        let detail = 'Could not open the guide.';
        try {
          const body = await response.json();
          const raw = body?.detail;
          if (typeof raw === 'string') detail = raw;
          else if (raw?.message) detail = String(raw.message);
        } catch {
          if (response.status === 401) detail = 'Sign in required';
          if (response.status === 403) detail = 'You do not have permission to open the guide.';
        }
        setGuideError(detail);
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'RIBDIGI-ERP-Customer-User-Guide.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setGuideError('Could not open the guide.');
    } finally {
      setGuideBusy(false);
    }
  }

  return (
    <div className="plat desk help">
      <PageHeader
        className="plat-hero"
        kicker="Help"
        kickerClassName="plat-kicker"
        title="Help & Support"
        subtitle="Find a topic, open the guide, or send a ticket if you still need help."
        subtitleClassName="plat-sub"
        actions={
          <button type="button" className="btn btn-primary" onClick={() => void openGuide()} disabled={guideBusy} aria-label="Open staff guide">
            {guideBusy ? 'Opening the guide…' : 'Open the guide'}
          </button>
        }
      />
      {guideError ? <p className="plat-msg desk-alert" role="alert">{guideError}</p> : null}
      <section className="plat-panel" aria-label="Help topics">
        <div className="desk-panel-head"><h2>Help topics</h2><p className="muted">Pick a topic to start a ticket about it.</p></div>
        {categories.length === 0 ? (
          <p className="muted">Topics appear here once this page has loaded your company.</p>
        ) : (
          <div className="help-topics">
            {categories.map((item) => (
              <button
                key={item.code}
                type="button"
                className="help-topic"
                aria-label={`Ask about ${item.label}`}
                onClick={() => {
                  setCategory(item.code);
                  setDetail(null);
                  window.setTimeout(() => {
                    document.getElementById('help-new-ticket')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    (document.querySelector('[aria-label="Ticket subject"]') as HTMLInputElement | null)?.focus({ preventScroll: true });
                  }, 50);
                }}
              >
                <b>{item.label}</b>
                <span>{TOPIC_HELP[item.code] || 'Covers this part of the product for your company.'}</span>
                <small>Ask about this →</small>
              </button>
            ))}
          </div>
        )}
      </section>
      {error ? <p className="plat-msg desk-alert" role="alert">{error}</p> : null}
      {notice ? <p className="plat-msg" role="status">{notice}</p> : null}
      {loading ? <p className="muted">Loading tickets…</p> : null}
      <div className="plat-stats">
        {STATUS_ORDER.map((code) => (
          <button
            key={code}
            className={`plat-stat${code === 'resolved' ? ' ok' : ''}${status === code ? ' is-on' : ''}`}
            type="button"
            aria-pressed={status === code}
            onClick={() => pickStatus(code)}
          >
            <span>{STATUS_LABEL[code]}</span>
            <strong>{counts ? counts[code] : '—'}</strong>
          </button>
        ))}
      </div>
      <section className="plat-panel desk-filters">
        <div className="desk-panel-head"><h2>Filters</h2></div>
        <form
          className="support-filters"
          onSubmit={(event) => {
            event.preventDefault();
            loadList().catch((err) => setError(errText(err)));
          }}
        >
          <label>
            <span>Reference or subject</span>
            <input aria-label="Search tickets" value={q} onChange={(event) => setQ(event.target.value)} />
          </label>
          <label>
            <span>Status</span>
            <select aria-label="Ticket status filter" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All</option>
              {STATUS_ORDER.map((code) => <option key={code} value={code}>{STATUS_LABEL[code]}</option>)}
            </select>
          </label>
          <label>
            <span>Priority</span>
            <select aria-label="Ticket priority filter" value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
              <option value="">All</option>
              {priorities.map((item) => <option key={item} value={item}>{plain(PRIORITY_LABEL, item)}</option>)}
            </select>
          </label>
          <label>
            <span>Category</span>
            <select aria-label="Ticket category filter" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
              <option value="">All</option>
              {categories.map((item) => <option key={item.code} value={item.code}>{item.label}</option>)}
            </select>
          </label>
          <div className="desk-filter-actions">
            <button className="btn btn-primary" type="submit">Apply filters</button>
            <button className="btn" type="button" aria-label="Clear ticket filters" onClick={clearFilters}>Clear</button>
          </div>
        </form>
      </section>
      <div className="desk-split">
        <section className="plat-panel desk-queue">
          <div className="desk-panel-head">
            <h2>Your tickets</h2>
            {ticketTotal > 0 ? <p className="muted">Showing {rows.length} of {ticketTotal}</p> : null}
          </div>
          {!loading && ticketTotal === 0 ? <p className="muted">No tickets match these filters.</p> : null}
          <div className="support-table-wrap">
            <table>
              <colgroup>
                <col className="help-col-ticket" />
                <col className="help-col-category" />
                <col className="help-col-status" />
                <col className="help-col-priority" />
                <col className="help-col-when" />
              </colgroup>
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Priority</th>
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
                    <td><span className="plat-co">{row.category_label || row.category}</span></td>
                    <td><span className={`desk-badge ${row.status}`}>{plain(STATUS_LABEL, row.status)}</span></td>
                    <td><span className={`desk-badge ${row.priority}`}>{plain(PRIORITY_LABEL, row.priority)}</span></td>
                    <td>{showWhen(row.updated_at, prefs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="plat-panel desk-ticket">
          {detail ? (
            <>
              <div className="desk-ticket-head">
                <div>
                  <p className="desk-kicker">{detail.ticket.reference}</p>
                  <h2>{detail.ticket.subject}</h2>
                </div>
                <button className="btn" type="button" aria-label="New ticket" onClick={() => setDetail(null)}>New ticket</button>
              </div>
              <p className="desk-description">{detail.ticket.description}</p>
              <div className="desk-facts">
                <span><small>Category</small>{detail.ticket.category_label || detail.ticket.category}</span>
                <span><small>Priority</small>{plain(PRIORITY_LABEL, detail.ticket.priority)}</span>
                <span><small>Status</small>{plain(STATUS_LABEL, detail.ticket.status)}</span>
                <span><small>Opened</small>{showWhen(detail.ticket.created_at, prefs)}</span>
                <span><small>Updated</small>{showWhen(detail.ticket.updated_at, prefs)}</span>
                <span><small>Resolved</small>{showWhen(detail.ticket.resolved_at, prefs)}</span>
                <span><small>Closed</small>{showWhen(detail.ticket.closed_at, prefs)}</span>
              </div>
              <h3>Conversation</h3>
              <div className="support-thread">
                {detail.messages.length === 0 ? <p className="muted">No replies yet.</p> : null}
                {detail.messages.map((message) => (
                  <article key={message.id} className="support-msg">
                    <p className="muted">{message.author?.full_name || 'Support'} · {showWhen(message.created_at, prefs)}</p>
                    <p>{message.body}</p>
                  </article>
                ))}
              </div>
              <div className="desk-compose">
                <label>
                  <span>Add a file</span>
                  <input
                    aria-label="Support ticket attachment"
                    type="file"
                    accept=".png,.jpg,.jpeg,.pdf,.txt,image/png,image/jpeg,application/pdf,text/plain"
                    onChange={(event) => uploadFile(event.target.files?.[0] || null)}
                  />
                </label>
                {detail.attachments.length === 0 ? <p className="muted">No attachments.</p> : (
                  <ul className="desk-files">
                    {detail.attachments.map((file) => (
                      <li key={file.id}>
                        <button type="button" className="btn" aria-label={`Download ${file.filename}`} onClick={() => downloadAttachment(file)}>
                          {file.filename}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {detail.ticket.status !== 'closed' ? (
                  <form onSubmit={sendReply}>
                    <label>
                      <span>Reply</span>
                      <textarea aria-label="Ticket reply" value={reply} onChange={(event) => setReply(event.target.value)} rows={4} />
                    </label>
                    {detail.ticket.status === 'resolved' ? (
                      <p className="muted">A reply sends this ticket back to support.</p>
                    ) : null}
                    <button className="btn btn-primary" type="submit" disabled={busy} aria-label="Send ticket reply">Send reply</button>
                  </form>
                ) : (
                  <p className="muted">This ticket is closed. Ask support to reopen it if you still need help.</p>
                )}
                {detail.ticket.status !== 'closed' ? (
                  <button className="btn btn-ok" type="button" disabled={busy} aria-label="Close ticket" onClick={closeTicket}>
                    Close ticket
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <div className="desk-ticket-head">
                <div>
                  <p className="desk-kicker">New</p>
                  <h2>New ticket</h2>
                </div>
              </div>
              <form id="help-new-ticket" onSubmit={createTicket} className="desk-compose">
                <label>
                  <span>Subject</span>
                  <input aria-label="Ticket subject" value={subject} onChange={(event) => setSubject(event.target.value)} required />
                </label>
                <div className="support-filters">
                  <label>
                    <span>Category</span>
                    <select aria-label="Ticket category" value={category} onChange={(event) => setCategory(event.target.value)} required>
                      {categories.map((item) => (
                        <option key={item.code} value={item.code}>{item.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Priority</span>
                    <select aria-label="Ticket priority" value={priority} onChange={(event) => setPriority(event.target.value)}>
                      {priorities.map((item) => (
                        <option key={item} value={item}>{plain(PRIORITY_LABEL, item)}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  <span>Description</span>
                  <textarea aria-label="Ticket description" value={description} onChange={(event) => setDescription(event.target.value)} rows={5} required />
                </label>
                <button className="btn btn-primary" type="submit" disabled={busy} aria-label="Create support ticket">Create ticket</button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
