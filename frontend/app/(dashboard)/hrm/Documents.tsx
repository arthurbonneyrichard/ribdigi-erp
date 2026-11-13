'use client';

/**
 * Staff documents. HR files documents on a person's record or company policies for everyone;
 * staff open theirs and accept by typing their full name. Confidential files are for HR
 * managers only. The server decides who may see what (hrm_documents).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api, apiFetch } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const KINDS = [
  ['contract', 'Contract'], ['id_copy', 'ID copy'], ['certificate', 'Certificate'],
  ['letter', 'Letter'], ['policy', 'Policy'], ['other', 'Other'],
] as const;
const kindWord = (k: string) => KINDS.find(([id]) => id === k)?.[1] || k;
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : '');

async function openFile(id: string) {
  const res = await apiFetch(`/hrm/documents/${id}/file`);
  if (!res.ok) throw new Error('This file could not be opened.');
  const url = URL.createObjectURL(await res.blob());
  window.open(url, '_blank', 'noopener');
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

async function postForm(path: string, form: FormData) {
  const res = await apiFetch(path, { method: 'POST', body: form });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.message || 'The file was not saved.');
  }
  return body;
}

function Uploader({ path, allowConfidential, ackDefault, onDone }: { path: string; allowConfidential: boolean; ackDefault: boolean; onDone: (m: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [kind, setKind] = useState(ackDefault ? 'policy' : 'contract');
  const [ack, setAck] = useState(ackDefault);
  const [secret, setSecret] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return (
    <div className="hr-row">
      <input type="file" accept="application/pdf,image/*" aria-label="Document file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <input placeholder="Title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} aria-label="Document title" />
      <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Document kind">
        {KINDS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
      <label><input type="checkbox" checked={ack} disabled={secret} onChange={(e) => setAck(e.target.checked)} aria-label="Staff must accept it" /> Staff must accept it</label>
      {allowConfidential ? (
        <label><input type="checkbox" checked={secret} onChange={(e) => { setSecret(e.target.checked); if (e.target.checked) setAck(false); }} aria-label="Confidential, HR managers only" /> Confidential (HR managers only)</label>
      ) : null}
      <button
        type="button" className="hr-primary" disabled={busy || !file || title.trim().length < 2}
        onClick={async () => {
          if (!file) return;
          setBusy(true);
          setError('');
          try {
            const form = new FormData();
            form.append('file', file);
            form.append('title', title.trim());
            form.append('kind', kind);
            form.append('needs_ack', String(ack));
            if (allowConfidential) form.append('confidential', String(secret));
            await postForm(path, form);
            setFile(null);
            setTitle('');
            onDone('Document filed.');
          } catch (err) {
            setError(problem(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        File it
      </button>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
    </div>
  );
}

function DocTable({ rows, onArchive, showAccepted }: { rows: Row[]; onArchive: (id: string) => void; showAccepted: (row: Row) => React.ReactNode }) {
  return (
    <table>
      <thead><tr><th>Title</th><th>Kind</th><th>Filed</th><th>Accepted</th><th /></tr></thead>
      <tbody>
        {rows.map((d) => (
          <tr key={d.id}>
            <td>{d.title}{d.confidential ? <><br /><small className="hr-bad">Confidential</small></> : null}{d.archived ? <><br /><small className="hr-muted">Archived</small></> : null}</td>
            <td>{kindWord(d.kind)}</td><td>{day(d.created_at)}</td>
            <td>{d.needs_ack ? showAccepted(d) : <span className="hr-muted">Not needed</span>}</td>
            <td>
              <div className="hr-row">
                <button type="button" aria-label={`Open ${d.title}`} onClick={() => void openFile(d.id).catch(() => undefined)}>Open</button>
                {!d.archived ? <button type="button" aria-label={`Archive ${d.title}`} onClick={() => onArchive(d.id)}>Archive</button> : null}
              </div>
            </td>
          </tr>
        ))}
        {rows.length === 0 ? <tr><td colSpan={5} className="hr-muted">Nothing filed yet.</td></tr> : null}
      </tbody>
    </table>
  );
}

/** HR side: files on one person's record, and company policies. */
export function StaffFiles({ people, canConfidential }: { people: Row[]; canConfidential: boolean }) {
  const [who, setWho] = useState('');
  const [files, setFiles] = useState<Row[]>([]);
  const [policies, setPolicies] = useState<Row[]>([]);
  const [readers, setReaders] = useState<Record<string, Row[]>>({});
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setPolicies((await api('/hrm/documents'))?.data || []);
      setFiles(who ? (await api(`/hrm/employees/${who}/documents`))?.data || [] : []);
    } catch (err) {
      setError(problem(err));
    }
  }, [who]);
  useEffect(() => {
    void load();
  }, [load]);

  async function archive(id: string) {
    try {
      await api(`/hrm/documents/${id}/archive`, { method: 'POST', body: '{}' });
      setNotice('Archived.');
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }
  const done = (msg: string) => {
    setNotice(msg);
    void load();
  };

  return (
    <>
      <section className="hr-box hr-scroll" aria-label="Staff documents">
        <div className="hr-cardhead"><h2>Documents on a staff file</h2></div>
        {notice ? <p className="hr-ok" role="status">{notice}</p> : null}
        {error ? <p className="hr-bad" role="alert">{error}</p> : null}
        <div className="hr-row">
          <select value={who} onChange={(e) => setWho(e.target.value)} aria-label="Documents for">
            <option value="">Choose who</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
          </select>
        </div>
        {who ? (
          <>
            <Uploader path={`/hrm/employees/${who}/documents`} allowConfidential={canConfidential} ackDefault={false} onDone={done} />
            <DocTable rows={files} onArchive={archive} showAccepted={(d) => (d.accepted?.length ? `Yes, ${day(d.accepted[0].at)}` : 'Not yet')} />
          </>
        ) : null}
      </section>
      <section className="hr-box hr-scroll" aria-label="Company policies">
        <div className="hr-cardhead"><h2>Company policies and handbooks</h2></div>
        <p className="hr-muted">Everyone with a staff record sees these. Staff accept by typing their full name; it is a record that they read it, not a legal signature.</p>
        <Uploader path="/hrm/documents" allowConfidential={false} ackDefault onDone={done} />
        <DocTable
          rows={policies}
          onArchive={archive}
          showAccepted={(d) => (
            <button
              type="button" aria-label={`Who accepted ${d.title}`}
              onClick={async () => setReaders({ ...readers, [d.id]: (await api(`/hrm/documents/${d.id}/accepted`))?.data || [] })}
            >
              {readers[d.id] ? `${readers[d.id].filter((r) => r.accepted_at).length} of ${readers[d.id].length}` : 'See who'}
            </button>
          )}
        />
        {Object.entries(readers).map(([id, rows]) => {
          const waiting = rows.filter((r) => !r.accepted_at);
          const doc = policies.find((p) => p.id === id);
          return doc && waiting.length ? <p key={id} className="hr-muted">{doc.title}: not accepted yet by {waiting.map((r) => r.name).join(', ')}.</p> : null;
        })}
      </section>
    </>
  );
}

/** Staff side, under My HR. */
export function MyDocuments() {
  const [rows, setRows] = useState<Row[]>([]);
  const [typed, setTyped] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      setRows((await api('/hrm/me/documents'))?.data || []);
    } catch {
      setRows([]);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  if (rows.length === 0) return null;
  return (
    <section className="hr-box hr-scroll" aria-label="My documents">
      <div className="hr-cardhead"><h2>My documents</h2></div>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      <table>
        <thead><tr><th>Title</th><th>Kind</th><th /></tr></thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id}>
              <td>{d.title}{d.company_wide ? <><br /><small className="hr-muted">For all staff</small></> : null}</td>
              <td>{kindWord(d.kind)}</td>
              <td>
                <div className="hr-row">
                  <button type="button" aria-label={`Open ${d.title}`} onClick={() => void openFile(d.id).catch((e) => setError(problem(e)))}>Open</button>
                  {d.needs_ack && !d.accepted_at ? (
                    <>
                      <input placeholder="Type your full name" value={typed[d.id] || ''} onChange={(e) => setTyped({ ...typed, [d.id]: e.target.value })} aria-label={`Type your full name to accept ${d.title}`} />
                      <button
                        type="button" className="hr-primary" disabled={(typed[d.id] || '').trim().length < 2}
                        onClick={async () => {
                          setError('');
                          try {
                            await api(`/hrm/me/documents/${d.id}/accept`, { method: 'POST', body: JSON.stringify({ typed_name: typed[d.id] }) });
                            await load();
                          } catch (err) {
                            setError(problem(err));
                          }
                        }}
                      >
                        I have read and accept it
                      </button>
                    </>
                  ) : d.accepted_at ? <span className="hr-muted">Accepted {day(d.accepted_at)}</span> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
