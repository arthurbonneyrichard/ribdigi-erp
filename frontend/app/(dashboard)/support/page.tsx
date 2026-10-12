'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import { api, apiFetch } from '../../../lib/api';

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

function errText(err: unknown): string {
  return err instanceof Error ? err.message : 'Request failed';
}

function when(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function HelpSupportPage() {
  const [categories, setCategories] = useState<Option[]>([]);
  const [priorities, setPriorities] = useState<string[]>(['low', 'normal', 'high', 'urgent']);
  const [rows, setRows] = useState<Ticket[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [status, setStatus] = useState('');
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

  const loadList = useCallback(async () => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (q.trim()) params.set('q', q.trim());
    const body = await api(`/support/tickets?${params.toString()}`);
    setRows(body.data?.items || []);
  }, [q, status]);

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
        setPriorities(meta.data?.priorities || priorities);
        setCategory((current) => current || cats[0]?.code || '');
        await loadList();
      } catch (err) {
        if (!cancelled) setError(errText(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadList]);

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
      await loadList();
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
      await loadList();
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
      await loadList();
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

  return (
    <div className="support-layout">
      <header>
        <h1>Help &amp; Support</h1>
        <p className="muted">Open a ticket, follow the conversation, and close it when the issue is resolved.</p>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      <div className="support-split">
        <section className="card">
          <h2>Your tickets</h2>
          <form
            className="support-filters"
            onSubmit={(event) => {
              event.preventDefault();
              loadList().catch((err) => setError(errText(err)));
            }}
          >
            <label>
              Status
              <select aria-label="Ticket status filter" value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">All</option>
                <option value="new">New</option>
                <option value="in_progress">In Progress</option>
                <option value="waiting_for_tenant">Waiting for Tenant</option>
                <option value="resolved">Resolved</option>
                <option value="closed">Closed</option>
              </select>
            </label>
            <label>
              Search
              <input aria-label="Search tickets" value={q} onChange={(event) => setQ(event.target.value)} />
            </label>
            <button className="btn" type="submit">Filter</button>
          </form>
          {loading ? <p>Loading tickets…</p> : null}
          {!loading && rows.length === 0 ? <p className="muted">No tickets yet.</p> : null}
          <div className="support-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Subject</th>
                  <th>Status</th>
                  <th>Priority</th>
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
                    <td>{row.subject}</td>
                    <td>{row.status}</td>
                    <td>{row.priority}</td>
                    <td>{when(row.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <section className="card">
          <h2>New ticket</h2>
          <form onSubmit={createTicket} className="support-layout">
            <label>
              Subject
              <input aria-label="Ticket subject" value={subject} onChange={(event) => setSubject(event.target.value)} required />
            </label>
            <label>
              Category
              <select aria-label="Ticket category" value={category} onChange={(event) => setCategory(event.target.value)} required>
                {categories.map((item) => (
                  <option key={item.code} value={item.code}>{item.label}</option>
                ))}
              </select>
            </label>
            <label>
              Priority
              <select aria-label="Ticket priority" value={priority} onChange={(event) => setPriority(event.target.value)}>
                {priorities.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label>
              Description
              <textarea aria-label="Ticket description" value={description} onChange={(event) => setDescription(event.target.value)} rows={5} required />
            </label>
            <button className="btn btn-primary" type="submit" disabled={busy} aria-label="Create support ticket">Create ticket</button>
          </form>
        </section>
      </div>
      {detail ? (
        <section className="card">
          <h2>{detail.ticket.reference}</h2>
          <p>{detail.ticket.subject}</p>
          <p className="muted">
            {detail.ticket.category_label} · {detail.ticket.priority} · {detail.ticket.status}
          </p>
          <p className="muted">
            Created {when(detail.ticket.created_at)} · Updated {when(detail.ticket.updated_at)} · Resolved {when(detail.ticket.resolved_at)} · Closed {when(detail.ticket.closed_at)}
          </p>
          <p>{detail.ticket.description}</p>
          <div className="support-thread">
            {detail.messages.length === 0 ? <p className="muted">No replies yet.</p> : null}
            {detail.messages.map((message) => (
              <article key={message.id} className="support-msg">
                <p className="muted">{message.author?.full_name || 'Support'} · {when(message.created_at)}</p>
                <p>{message.body}</p>
              </article>
            ))}
          </div>
          <h3>Attachments</h3>
          {detail.attachments.length === 0 ? <p className="muted">No attachments.</p> : null}
          <ul>
            {detail.attachments.map((file) => (
              <li key={file.id}>
                <button type="button" className="btn" aria-label={`Download ${file.filename}`} onClick={() => downloadAttachment(file)}>
                  {file.filename}
                </button>
                <span className="muted"> {file.content_type} · {file.size_bytes} bytes</span>
              </li>
            ))}
          </ul>
          <label>
            Add attachment
            <input
              aria-label="Support ticket attachment"
              type="file"
              accept=".png,.jpg,.jpeg,.pdf,.txt,image/png,image/jpeg,application/pdf,text/plain"
              onChange={(event) => uploadFile(event.target.files?.[0] || null)}
            />
          </label>
          {detail.ticket.status !== 'closed' ? (
            <form onSubmit={sendReply}>
              <label>
                Reply
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
          {detail.ticket.status === 'resolved' ? (
            <button className="btn btn-ok" type="button" disabled={busy} aria-label="Close resolved ticket" onClick={closeTicket}>
              Close ticket
            </button>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
