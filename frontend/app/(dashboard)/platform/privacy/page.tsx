'use client';

/**
 * Owner console: data deletion requests from every company.
 * Approving a personal request deletes that sign-in at once. Approving a company request marks it
 * approved; finish it with Tenants -> Delete after the company has downloaded its data, then mark it done.
 */
import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import PageHeader from '../../../../components/PageHeader';
import EmptyState from '../../../../components/EmptyState';
import { Tabs, Tag } from '../../../../components/PlatformUi';
import { api } from '../../../../lib/api';
import { formatWhen } from '../../../../lib/format';

type Row = {
  id: string;
  scope: 'my_account' | 'company';
  status: 'pending' | 'approved' | 'rejected' | 'completed' | 'cancelled';
  company_name?: string | null;
  company_slug?: string | null;
  requester_email?: string | null;
  requester_name?: string | null;
  reason?: string | null;
  decision_note?: string | null;
  created_at?: string | null;
  decided_at?: string | null;
};

const TABS = [
  { key: 'pending', label: 'Waiting' },
  { key: 'approved', label: 'Approved' },
  { key: 'all', label: 'All' },
];

const TONE: Record<Row['status'], 'ok' | 'info' | 'warn' | 'bad' | 'none'> = {
  pending: 'warn',
  approved: 'info',
  completed: 'ok',
  rejected: 'bad',
  cancelled: 'none',
};

const STATUS_WORDS: Record<Row['status'], string> = {
  pending: 'Waiting',
  approved: 'Approved',
  completed: 'Done',
  rejected: 'Refused',
  cancelled: 'Cancelled',
};

export default function PlatformPrivacyPage() {
  const [tab, setTab] = useState('pending');
  const [rows, setRows] = useState<Row[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    const q = tab === 'all' ? '' : `?status=${tab}`;
    try {
      const r = await api(`/platform/privacy/deletion-requests${q}`);
      setRows(Array.isArray(r?.data) ? r.data : []);
    } catch (err: any) {
      setError(err?.message || 'Could not load requests');
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  async function decide(row: Row, decision: 'approve' | 'reject' | 'complete') {
    const note = (notes[row.id] || '').trim();
    if (decision === 'reject' && !note) {
      setError('Write why the request is refused; the person will be told.');
      return;
    }
    if (decision === 'approve' && row.scope === 'my_account') {
      const ok = window.confirm(
        `Delete the sign-in account ${row.requester_email || ''} at ${row.company_name || 'this company'} now? This cannot be undone.`,
      );
      if (!ok) return;
    }
    setBusy(row.id);
    setError('');
    setMessage('');
    try {
      const r = await api(`/platform/privacy/deletion-requests/${encodeURIComponent(row.id)}/decide`, {
        method: 'POST',
        body: JSON.stringify({ decision, note: note || null }),
      });
      setMessage(r?.message || 'Saved');
      await load();
    } catch (err: any) {
      setError(err?.message || 'Could not save the decision');
    } finally {
      setBusy('');
    }
  }

  return (
    <div className="plat">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Privacy requests"
        subtitle="Requests to delete a person's account or a whole company. Check who is asking, refuse with a reason, or approve."
        subtitleClassName="plat-sub"
      />
      {error ? <p className="erp-banner err" role="alert">{error}</p> : null}
      {message ? <p className="erp-banner ok" role="status">{message}</p> : null}
      <Tabs tabs={TABS} active={tab} onChange={setTab} label="Request status" />
      <div className="plat-panel">
        <div className="plat-panel-head">
          <h2>{TABS.find((t) => t.key === tab)?.label} requests</h2>
        </div>
        {rows.length === 0 ? (
          <EmptyState title="No requests here" />
        ) : (
          <div className="plat-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Sent</th>
                  <th scope="col">Company</th>
                  <th scope="col">Who</th>
                  <th scope="col">What</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Status</th>
                  <th scope="col">Decision</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{formatWhen(row.created_at) || '—'}</td>
                    <td className="plat-co">{row.company_name || row.company_slug || '—'}</td>
                    <td>
                      {row.requester_name || '—'}
                      <div className="muted">{row.requester_email}</div>
                    </td>
                    <td>{row.scope === 'company' ? 'Whole company' : 'Own account'}</td>
                    <td>{row.reason || <span className="muted">None given</span>}</td>
                    <td>
                      <Tag tone={TONE[row.status]}>{STATUS_WORDS[row.status]}</Tag>
                      {row.decision_note ? <div className="muted">{row.decision_note}</div> : null}
                    </td>
                    <td>
                      {row.status === 'pending' ? (
                        <div className="plat-stack">
                          <input
                            aria-label={`Note for ${row.requester_email || 'request'}`}
                            placeholder="Note (needed to refuse)"
                            value={notes[row.id] || ''}
                            maxLength={1000}
                            onChange={(e) => setNotes((n) => ({ ...n, [row.id]: e.target.value }))}
                          />
                          <div>
                            <button type="button" className="btn-ok" disabled={busy === row.id} onClick={() => decide(row, 'approve')}>
                              Approve
                            </button>{' '}
                            <button type="button" className="btn-danger" disabled={busy === row.id} onClick={() => decide(row, 'reject')}>
                              Refuse
                            </button>
                          </div>
                        </div>
                      ) : row.status === 'approved' && row.scope === 'company' ? (
                        <div className="plat-stack">
                          <span className="muted">
                            Let the company download its data, then delete it in{' '}
                            <Link href={`/platform/tenants?q=${encodeURIComponent(row.company_slug || '')}`}>Tenants</Link>.
                          </span>
                          <button type="button" className="btn-ok" disabled={busy === row.id} onClick={() => decide(row, 'complete')}>
                            Mark done
                          </button>
                        </div>
                      ) : (
                        <span className="muted">{formatWhen(row.decided_at) || '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
