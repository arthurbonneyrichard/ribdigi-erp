'use client';

/**
 * Gym back office screens: Growth (leads, campaigns, member feedback), Setup (branches, door rules,
 * door devices, cards and portal links), Insights (rule-based, not a language model) and My work
 * (the trainer's own view). Each part loads on its own, so a role that may not see one still sees the rest.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { printPaymentReceipt } from '../../../lib/receiptPrint';
import { api, apiFetch } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const when = (v?: string) => (v ? new Date(`${v}Z`).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '');
const today = () => new Date().toISOString().slice(0, 10);
const get = async (path: string) => {
  try {
    return (await api(path))?.data ?? null;
  } catch {
    return null;
  }
};

function useRunner(reload: () => Promise<void>) {
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const run = useCallback(async (path: string, body: object | null, done: string) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await api(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
      setNotice(done);
      await reload();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }, [reload]);
  return { error, notice, busy, run, setError };
}

function Msg({ error, notice }: { error: string; notice: string }) {
  return (
    <>
      {error ? <p className="gm-error" role="alert">{error}</p> : null}
      {notice ? <p className="gm-ok" role="status">{notice}</p> : null}
    </>
  );
}

// --- Growth ---------------------------------------------------------------------------------

export function GrowthTab({ members }: { members: Row[] }) {
  const [part, setPart] = useState('leads');
  const [leads, setLeads] = useState<Row[]>([]);
  const [due, setDue] = useState<Row[]>([]);
  const [report, setReport] = useState<Row | null>(null);
  const [campaigns, setCampaigns] = useState<Row[]>([]);
  const [feedback, setFeedback] = useState<Row[]>([]);
  const [recipients, setRecipients] = useState<Row[] | null>(null);
  const [auto, setAuto] = useState('');
  const [lf, setLf] = useState({ full_name: '', phone: '', email: '', source: 'walk_in', consent: false });
  const [cf, setCf] = useState({ name: '', channel: 'sms', audience: 'active', kind: 'marketing', subject: '', message: '' });
  const [fix, setFix] = useState<Record<string, string>>({});
  const load = useCallback(async () => {
    setLeads((await get('/gym/leads')) || []);
    setDue((await get('/gym/leads/follow-ups')) || []);
    setReport(await get('/gym/reports/leads'));
    setCampaigns((await get('/gym/campaigns')) || []);
    setFeedback((await get('/gym/feedback?status=open')) || []);
    setAuto(((await get('/gym/reminders/auto')) || {}).reminder_channels || '');
  }, []);
  useEffect(() => { void load(); }, [load]);
  const { error, notice, busy, run } = useRunner(load);

  return (
    <div className="gm-floor">
      <Msg error={error} notice={notice} />
      <div className="gm-row" role="tablist" aria-label="Growth">
        {[['leads', 'Leads'], ['campaigns', 'Campaigns'], ['feedback', `Feedback (${feedback.length})`]].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={part === id} className={part === id ? 'gm-primary' : ''} onClick={() => setPart(id)}>{label}</button>
        ))}
      </div>

      {part === 'leads' ? (
        <>
          {report ? <p className="gm-muted">Last 90 days: {report.total} leads, {report.converted} joined ({report.conversion_rate}%). Trials: {report.trials}, {report.trial_conversion_rate}% joined.</p> : null}
          {due.length ? <p className="gm-error">{due.length} follow-up{due.length === 1 ? '' : 's'} due: {due.map((d) => d.full_name).join(', ')}</p> : null}
          <section className="gm-box" aria-label="Add lead">
            <h2>Add a lead</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={lf.full_name} onChange={(e) => setLf({ ...lf, full_name: e.target.value })} aria-label="Lead name" /></label>
              <label><span>Phone</span><input value={lf.phone} onChange={(e) => setLf({ ...lf, phone: e.target.value })} aria-label="Lead phone" placeholder="+233..." /></label>
              <label><span>Email</span><input value={lf.email} onChange={(e) => setLf({ ...lf, email: e.target.value })} aria-label="Lead email" /></label>
              <label><span>Where from</span>
                <select value={lf.source} onChange={(e) => setLf({ ...lf, source: e.target.value })} aria-label="Lead source">
                  {['walk_in', 'referral', 'social', 'website', 'event', 'phone', 'other'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                </select></label>
              <label><input type="checkbox" checked={lf.consent} onChange={(e) => setLf({ ...lf, consent: e.target.checked })} aria-label="Lead agreed to offers" /> Agreed to receive offers</label>
              <button type="button" className="gm-primary" disabled={busy || !lf.full_name.trim() || !(lf.phone.trim() || lf.email.trim())}
                onClick={async () => {
                  const body: Record<string, unknown> = { full_name: lf.full_name.trim(), source: lf.source, marketing_consent: lf.consent };
                  if (lf.phone.trim()) body.phone = lf.phone.replace(/[\s-]/g, '');
                  if (lf.email.trim()) body.email = lf.email.trim();
                  if (await run('/gym/leads', body, 'Lead added')) setLf({ full_name: '', phone: '', email: '', source: 'walk_in', consent: false });
                }}>Add lead</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Leads">
            <table>
              <thead><tr><th>Name</th><th>Contact</th><th>Source</th><th>Status</th><th>Follow up</th><th /></tr></thead>
              <tbody>
                {leads.map((l) => (
                  <tr key={l.id}>
                    <td>{l.full_name}</td><td>{l.phone || l.email}</td><td>{String(l.source).replace('_', ' ')}</td><td>{l.status}{l.trial_ends_on ? ` (to ${l.trial_ends_on})` : ''}</td><td>{l.next_follow_up || ''}</td>
                    <td className="gm-row">
                      {['new', 'contacted', 'trial'].includes(l.status) ? (
                        <>
                          <button type="button" onClick={() => void run(`/gym/leads/${l.id}`, { status: 'contacted', next_follow_up: new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10) }, 'Saved')}>Contacted</button>
                          <button type="button" onClick={() => void run(`/gym/leads/${l.id}`, { status: 'trial', trial_days: 3 }, 'Trial started')}>Start trial</button>
                          <button type="button" className="gm-ok-btn" onClick={() => void run(`/gym/leads/${l.id}/convert`, null, 'Now a member. Sell their first plan at the till.')}>Make member</button>
                          <button type="button" className="gm-danger" onClick={() => void run(`/gym/leads/${l.id}`, { status: 'lost' }, 'Marked lost')}>Lost</button>
                        </>
                      ) : null}
                    </td>
                  </tr>
                ))}
                {leads.length === 0 ? <tr><td colSpan={6} className="gm-muted">No leads yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {part === 'campaigns' ? (
        <>
          <p className="gm-muted">Offers go only to people who agreed to them, and never to anyone who unsubscribed. Messages use your company&apos;s own SMS and email settings. WhatsApp is not connected.</p>
          <section className="gm-box" aria-label="New campaign">
            <h2>New campaign</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={cf.name} onChange={(e) => setCf({ ...cf, name: e.target.value })} aria-label="Campaign name" /></label>
              <label><span>Send by</span>
                <select value={cf.channel} onChange={(e) => setCf({ ...cf, channel: e.target.value })} aria-label="Campaign channel"><option value="sms">SMS</option><option value="email">Email</option></select></label>
              <label><span>To</span>
                <select value={cf.audience} onChange={(e) => setCf({ ...cf, audience: e.target.value, kind: e.target.value === 'expiring' ? cf.kind : 'marketing' })} aria-label="Campaign audience">
                  <option value="active">Active members</option><option value="expiring">Plan ends within 7 days</option><option value="lapsed">Lapsed members</option><option value="leads">Open leads</option>
                </select></label>
              {cf.audience === 'expiring' ? (
                <label><span>Kind</span>
                  <select value={cf.kind} onChange={(e) => setCf({ ...cf, kind: e.target.value })} aria-label="Campaign kind"><option value="service">Renewal reminder</option><option value="marketing">Offer</option></select></label>
              ) : null}
              {cf.channel === 'email' ? <label><span>Subject</span><input value={cf.subject} onChange={(e) => setCf({ ...cf, subject: e.target.value })} aria-label="Campaign subject" /></label> : null}
              <label><span>Message (use {'{name}'})</span><textarea value={cf.message} onChange={(e) => setCf({ ...cf, message: e.target.value })} aria-label="Campaign message" /></label>
              <button type="button" className="gm-primary" disabled={busy || !cf.name.trim() || !cf.message.trim() || (cf.channel === 'email' && !cf.subject.trim())}
                onClick={async () => {
                  const body: Record<string, unknown> = { name: cf.name.trim(), channel: cf.channel, audience: cf.audience, kind: cf.kind, message: cf.message.trim() };
                  if (cf.channel === 'email') body.subject = cf.subject.trim();
                  if (await run('/gym/campaigns', body, 'Saved as a draft. Review it, then send.')) setCf({ ...cf, name: '', message: '', subject: '' });
                }}>Save draft</button>
            </div>
          </section>
          <p className="gm-row">
            <label><span>Send renewal reminders automatically each morning </span>
              <select value={auto} onChange={(e) => void run('/gym/reminders/auto', { channels: e.target.value }, 'Saved')} aria-label="Automatic renewal reminders">
                <option value="">Off</option><option value="sms">By SMS</option><option value="email">By email</option><option value="both">By SMS and email</option>
              </select></label>
          </p>
          <p className="gm-row">
            <button type="button" disabled={busy} onClick={() => { if (window.confirm('Send a renewal reminder by SMS to everyone whose plan ends within 7 days?')) void run('/gym/reminders/run', { channel: 'sms' }, 'Reminders sent'); }}>Send renewal reminders by SMS</button>
            <button type="button" disabled={busy} onClick={() => { if (window.confirm('Send a renewal reminder by email to everyone whose plan ends within 7 days?')) void run('/gym/reminders/run', { channel: 'email' }, 'Reminders sent'); }}>Send renewal reminders by email</button>
          </p>
          <section className="gm-box gm-scroll" aria-label="Campaigns">
            <table>
              <thead><tr><th>Name</th><th>To</th><th>Status</th><th>Result</th><th /></tr></thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td><td>{c.channel} · {c.audience}</td><td>{c.status}</td>
                    <td>{Object.entries(c.counts || {}).map(([k, v]) => `${v} ${k}`).join(', ')}</td>
                    <td className="gm-row">
                      {c.status === 'draft' ? <button type="button" className="gm-primary" disabled={busy} onClick={() => { if (window.confirm(`Send "${c.name}" now?`)) void run(`/gym/campaigns/${c.id}/send`, null, 'Campaign sent'); }}>Send</button> : null}
                      {c.counts?.failed ? <button type="button" onClick={() => void run(`/gym/campaigns/${c.id}/retry`, null, 'Retried')}>Retry failed</button> : null}
                      {c.status === 'sent' ? <button type="button" onClick={async () => setRecipients(await get(`/gym/campaigns/${c.id}/recipients`))}>Who</button> : null}
                    </td>
                  </tr>
                ))}
                {campaigns.length === 0 ? <tr><td colSpan={5} className="gm-muted">No campaigns yet.</td></tr> : null}
              </tbody>
            </table>
            {recipients ? <p className="gm-muted">{recipients.map((r) => `${r.address} (${r.status}${r.detail ? `: ${r.detail}` : ''})`).join('; ')}</p> : null}
          </section>
        </>
      ) : null}

      {part === 'feedback' ? (
        <section className="gm-box gm-scroll" aria-label="Member feedback">
          <table>
            <thead><tr><th>When</th><th>Member</th><th>Kind</th><th>Message</th><th /></tr></thead>
            <tbody>
              {feedback.map((f) => (
                <tr key={f.id}>
                  <td>{when(f.date)}</td><td>{f.member_name}</td><td>{f.kind}{f.rating ? ` ${f.rating}/5` : ''}</td><td>{f.message}</td>
                  <td className="gm-row">
                    <input value={fix[f.id] || ''} onChange={(e) => setFix({ ...fix, [f.id]: e.target.value })} aria-label={`Resolution for ${f.member_name}`} placeholder="What was done" />
                    <button type="button" disabled={busy || (fix[f.id] || '').trim().length < 3} onClick={() => void run(`/gym/feedback/${f.id}/close`, { resolution: fix[f.id].trim() }, 'Closed')}>Close</button>
                  </td>
                </tr>
              ))}
              {feedback.length === 0 ? <tr><td colSpan={5} className="gm-muted">Nothing open.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
      <span hidden>{members.length}</span>
    </div>
  );
}

// --- Setup ----------------------------------------------------------------------------------

export function SetupTab({ members, plans }: { members: Row[]; plans: Row[] }) {
  const [part, setPart] = useState('branches');
  const [branches, setBranches] = useState<Row[]>([]);
  const [devices, setDevices] = useState<Row[]>([]);
  const [attention, setAttention] = useState<Row[]>([]);
  const [trainers, setTrainers] = useState<Row[]>([]);
  const [report, setReport] = useState<Row[]>([]);
  const [bf, setBf] = useState({ code: '', name: '' });
  const [df, setDf] = useState({ name: '', kind: 'qr_scanner', branch_id: '' });
  const [rules, setRules] = useState<Record<string, { start: string; end: string; days: string; scope: string }>>({});
  const [memberId, setMemberId] = useState('');
  const [issued, setIssued] = useState<Row | null>(null);
  const [credKind, setCredKind] = useState('qr');
  const [credToken, setCredToken] = useState('');
  const [scan, setScan] = useState({ token: '', branch_id: '' });
  const [scanResult, setScanResult] = useState<Row | null>(null);
  const [link, setLink] = useState('');
  const [files, setFiles] = useState<Row[]>([]);
  const [fileKind, setFileKind] = useState('photo');
  const [trainerUser, setTrainerUser] = useState<Record<string, string>>({});
  const [facilities, setFacilities] = useState<Row[]>([]);
  const [fbookings, setFbookings] = useState<Row[]>([]);
  const [ff, setFf] = useState({ name: '', kind: 'sauna', capacity: '2', open_time: '06:00', close_time: '22:00', max_minutes: '60' });
  const [fbook, setFbook] = useState({ facility_id: '', member_id: '', when: '', minutes: '30' });
  const [commission, setCommission] = useState<Row | null>(null);
  const [pct, setPct] = useState<Record<string, string>>({});
  const [payRef, setPayRef] = useState<Record<string, string>>({});
  const load = useCallback(async () => {
    setBranches((await get('/gym/branches')) || []);
    setDevices((await get('/gym/devices')) || []);
    setAttention((await get('/gym/door/attention')) || []);
    setTrainers((await get('/gym/trainers')) || []);
    setReport((await get('/gym/reports/branches')) || []);
    setFacilities((await get('/gym/facilities')) || []);
    setFbookings((await get('/gym/facility-bookings')) || []);
    setCommission(await get('/gym/reports/commissions'));
  }, []);
  useEffect(() => { void load(); }, [load]);
  const { error, notice, busy, run, setError } = useRunner(load);
  useEffect(() => {
    if (!memberId) { setFiles([]); return; }
    void (async () => setFiles((await get(`/gym/members/${memberId}/files`)) || []))();
  }, [memberId, notice]);

  async function upload(file: File) {
    const form = new FormData();
    form.append('kind', fileKind);
    form.append('file', file);
    try {
      await api(`/gym/members/${memberId}/files`, { method: 'POST', body: form });
      setFiles((await get(`/gym/members/${memberId}/files`)) || []);
    } catch (err) { setError(problem(err)); }
  }
  async function openFile(id: string) {
    try {
      const res = await apiFetch(`/gym/files/${id}`);
      if (!res.ok) throw new Error('Could not open the file');
      window.open(URL.createObjectURL(await res.blob()), '_blank', 'noopener');
    } catch (err) { setError(problem(err)); }
  }
  async function removeFile(id: string) {
    try {
      await api(`/gym/files/${id}`, { method: 'DELETE' });
      setFiles((await get(`/gym/members/${memberId}/files`)) || []);
    } catch (err) { setError(problem(err)); }
  }
  async function printCard() {
    try {
      const res = await apiFetch(`/gym/members/${memberId}/card`, { method: 'POST' });
      if (!res.ok) throw new Error('Could not make the card');
      const url = URL.createObjectURL(new Blob([await res.text()], { type: 'text/html' }));
      window.open(url, '_blank', 'noopener');
    } catch (err) { setError(problem(err)); }
  }
  const activeBranches = branches.filter((b) => b.is_active);

  return (
    <div className="gm-floor">
      <Msg error={error} notice={notice} />
      <div className="gm-row" role="tablist" aria-label="Setup">
        {[['branches', 'Branches'], ['rules', 'Plan door rules'], ['door', 'Cards, codes and links'], ['devices', `Door devices${attention.length ? ` (${attention.length} to check)` : ''}`], ['trainers', 'Trainer logins'], ['facilities', 'Facilities'], ['pay', 'Trainer pay']].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={part === id} className={part === id ? 'gm-primary' : ''} onClick={() => setPart(id)}>{label}</button>
        ))}
      </div>

      {part === 'branches' ? (
        <>
          <section className="gm-box" aria-label="Add branch">
            <h2>Add a branch</h2>
            <p className="gm-muted">A gym with one site does not need this.</p>
            <div className="gm-form">
              <label><span>Code</span><input value={bf.code} onChange={(e) => setBf({ ...bf, code: e.target.value })} aria-label="Branch code" /></label>
              <label><span>Name</span><input value={bf.name} onChange={(e) => setBf({ ...bf, name: e.target.value })} aria-label="Branch name" /></label>
              <button type="button" className="gm-primary" disabled={busy || !bf.code.trim() || !bf.name.trim()} onClick={async () => { if (await run('/gym/branches', { code: bf.code.trim(), name: bf.name.trim() }, 'Branch added')) setBf({ code: '', name: '' }); }}>Add branch</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Branches">
            <table>
              <thead><tr><th>Code</th><th>Name</th><th>Visits (30 days)</th><th>Home members</th><th /></tr></thead>
              <tbody>
                {branches.map((b) => {
                  const r = report.find((x) => x.branch_id === b.id) || {};
                  return (
                    <tr key={b.id}>
                      <td>{b.code}</td><td>{b.name}{b.is_active ? '' : ' (closed)'}</td><td>{r.visits ?? 0}</td><td>{r.home_members ?? 0}</td>
                      <td><button type="button" onClick={() => void run(`/gym/branches/${b.id}/active`, { is_active: !b.is_active }, 'Saved')}>{b.is_active ? 'Close' : 'Reopen'}</button></td>
                    </tr>
                  );
                })}
                {branches.length === 0 ? <tr><td colSpan={5} className="gm-muted">No branches.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {part === 'rules' ? (
        <section className="gm-box gm-scroll" aria-label="Plan door rules">
          <p className="gm-muted">Leave times empty for all day. Days: 1 Monday to 7 Sunday, comma separated. Times are the company&apos;s local time.</p>
          <table>
            <thead><tr><th>Plan</th><th>From</th><th>To</th><th>Days</th><th>Branches</th><th /></tr></thead>
            <tbody>
              {plans.map((p) => {
                const v = rules[p.id] || { start: p.access_start || '', end: p.access_end || '', days: (p.access_days || []).join(','), scope: p.branch_scope || 'all' };
                const set = (patch: object) => setRules({ ...rules, [p.id]: { ...v, ...patch } });
                return (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td><input value={v.start} onChange={(e) => set({ start: e.target.value })} placeholder="06:00" aria-label={`${p.name} opens`} style={{ width: 80 }} /></td>
                    <td><input value={v.end} onChange={(e) => set({ end: e.target.value })} placeholder="22:00" aria-label={`${p.name} closes`} style={{ width: 80 }} /></td>
                    <td><input value={v.days} onChange={(e) => set({ days: e.target.value })} placeholder="1,2,3,4,5" aria-label={`${p.name} days`} style={{ width: 110 }} /></td>
                    <td><select value={v.scope} onChange={(e) => set({ scope: e.target.value })} aria-label={`${p.name} branches`}><option value="all">Any branch</option><option value="home">Home branch only</option></select></td>
                    <td><button type="button" disabled={busy} onClick={() => void run(`/gym/plans/${p.id}/access`, {
                      access_start: v.start.trim() || null, access_end: v.end.trim() || null,
                      access_days: v.days.trim() ? v.days.split(',').map((x) => Number(x.trim())) : [], branch_scope: v.scope,
                    }, 'Door rules saved')}>Save</button></td>
                  </tr>
                );
              })}
              {plans.length === 0 ? <tr><td colSpan={6} className="gm-muted">No plans yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {part === 'door' ? (
        <>
          <section className="gm-box" aria-label="Scan a code">
            <h2>Scan a code</h2>
            <p className="gm-muted">Click the box and scan with a handheld reader (it types the code and presses Enter), or paste a code.</p>
            <div className="gm-form">
              <label><span>Code</span><input value={scan.token} onChange={(e) => setScan({ ...scan, token: e.target.value })} aria-label="Scanned code" autoComplete="off"
                onKeyDown={async (e) => { if (e.key === 'Enter' && scan.token.trim().length >= 4) { const r = await run('/gym/check-ins/scan', { token: scan.token.trim(), branch_id: scan.branch_id || undefined }, ''); setScanResult(r && r !== true ? r : null); setScan({ ...scan, token: '' }); } }} /></label>
              {activeBranches.length ? (
                <label><span>This door is at</span>
                  <select value={scan.branch_id} onChange={(e) => setScan({ ...scan, branch_id: e.target.value })} aria-label="Door branch"><option value="">Not set</option>{activeBranches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
              ) : null}
            </div>
            {scanResult ? <p className={scanResult.allowed ? 'gm-ok' : 'gm-error'} role="status">{scanResult.message}</p> : null}
          </section>
          <section className="gm-box" aria-label="Member cards and links">
            <h2>Cards, codes and links</h2>
            <div className="gm-form">
              <label><span>Member</span>
                <select value={memberId} onChange={(e) => { setMemberId(e.target.value); setIssued(null); setLink(''); }} aria-label="Credential member"><option value="">Choose</option>{members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></label>
              <label><span>Type</span>
                <select value={credKind} onChange={(e) => setCredKind(e.target.value)} aria-label="Credential type">{['qr', 'card', 'rfid', 'nfc', 'barcode'].map((k) => <option key={k} value={k}>{k.toUpperCase()}</option>)}</select></label>
              {credKind !== 'qr' ? <label><span>Card number (scan it)</span><input value={credToken} onChange={(e) => setCredToken(e.target.value)} aria-label="Card number" /></label> : null}
              <button type="button" disabled={busy || !memberId || (credKind !== 'qr' && credToken.trim().length < 4)}
                onClick={async () => { const r = await run('/gym/credentials', { member_id: memberId, kind: credKind, token: credKind !== 'qr' ? credToken.trim() : undefined }, 'Shown once below'); if (r && r !== true) { setIssued(r); setCredToken(''); } }}>Issue {credKind === 'qr' ? 'code' : 'card'}</button>
              <button type="button" disabled={busy || !memberId}
                onClick={async () => { const r = await run(`/gym/members/${memberId}/portal-link`, {}, 'Link ready below'); if (r && r !== true) setLink(`${window.location.origin}/gym-member?t=${r.token}`); }}>Make member portal link</button>
              <button type="button" className="gm-danger" disabled={busy || !memberId} onClick={() => void run(`/gym/members/${memberId}/portal-link/revoke`, null, 'Link cancelled')}>Cancel their link</button>
            </div>
            {issued ? (
              <div>
                <p>Shown once. Give it to {issued.member_name} now.</p>
                {issued.qr_png ? <img src={issued.qr_png} alt={`Door QR code for ${issued.member_name}`} width={180} height={180} /> : null}
                <p><code style={{ wordBreak: 'break-all' }}>{issued.token}</code></p>
              </div>
            ) : null}
            {memberId ? (
              <div className="gm-form">
                <button type="button" disabled={busy} onClick={() => { if (window.confirm('Print a new card? Any earlier printed card for this member will stop opening the door.')) void printCard(); }}>Print membership card</button>
                <label><span>File type</span>
                  <select value={fileKind} onChange={(e) => setFileKind(e.target.value)} aria-label="Member file type"><option value="photo">Photo</option><option value="id_document">ID</option><option value="waiver">Signed waiver</option><option value="progress_photo">Progress photo</option></select></label>
                <label><span>File (image or PDF)</span><input type="file" accept="image/png,image/jpeg,image/webp,application/pdf" aria-label="Member file" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ''; }} /></label>
              </div>
            ) : null}
            {files.length ? <ul>{files.map((f) => <li key={f.id}>{f.kind.replace('_', ' ')}: <button type="button" onClick={() => void openFile(f.id)}>{f.filename}</button>{' '}<button type="button" className="gm-danger" onClick={() => { if (window.confirm('Remove this file?')) void removeFile(f.id); }}>Remove</button></li>)}</ul> : null}
            {link ? <p>Member portal link (shown once, expires in 30 days): <code style={{ wordBreak: 'break-all' }}>{link}</code></p> : null}
          </section>
        </>
      ) : null}

      {part === 'devices' ? (
        <>
          <p className="gm-muted">A reader or turnstile stays &ldquo;not yet tested on real hardware&rdquo; until someone marks it tested after trying it at the door. Offline scans are checked again when they sync; ones that cannot be trusted show below.</p>
          <section className="gm-box" aria-label="Add device">
            <div className="gm-form">
              <label><span>Name</span><input value={df.name} onChange={(e) => setDf({ ...df, name: e.target.value })} aria-label="Device name" /></label>
              <label><span>Type</span>
                <select value={df.kind} onChange={(e) => setDf({ ...df, kind: e.target.value })} aria-label="Device type">{['qr_scanner', 'barcode_scanner', 'rfid_reader', 'nfc_reader', 'fingerprint', 'face', 'turnstile'].map((k) => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}</select></label>
              <button type="button" className="gm-primary" disabled={busy || !df.name.trim()} onClick={async () => { if (await run('/gym/devices', { name: df.name.trim(), kind: df.kind, branch_id: df.branch_id || undefined }, 'Device added')) setDf({ ...df, name: '' }); }}>Add device</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Devices">
            <table>
              <thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Last seen</th><th /></tr></thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id}><td>{d.name}</td><td>{String(d.kind).replace('_', ' ')}</td><td>{d.status}</td><td>{when(d.last_seen_at)}</td>
                    <td><button type="button" onClick={() => void run(`/gym/devices/${d.id}/verified`, { verified: !d.verified }, 'Saved')}>{d.verified ? 'Mark untested' : 'Mark tested on hardware'}</button></td></tr>
                ))}
                {devices.length === 0 ? <tr><td colSpan={5} className="gm-muted">No devices.</td></tr> : null}
              </tbody>
            </table>
          </section>
          <section className="gm-box gm-scroll" aria-label="Scans to check">
            <h2>Scans to check</h2>
            <table>
              <thead><tr><th>When</th><th>Result</th><th>Why</th><th /></tr></thead>
              <tbody>
                {attention.map((a) => (
                  <tr key={a.id}><td>{when(a.occurred_at)}</td><td>{a.outcome}</td><td>{a.message}</td><td><button type="button" onClick={() => void run(`/gym/door/attention/${a.id}/reviewed`, null, 'Reviewed')}>Reviewed</button></td></tr>
                ))}
                {attention.length === 0 ? <tr><td colSpan={4} className="gm-muted">Nothing to check.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {part === 'facilities' ? (
        <>
          <section className="gm-box" aria-label="Add facility">
            <h2>Add a facility</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={ff.name} onChange={(e) => setFf({ ...ff, name: e.target.value })} aria-label="Facility name" /></label>
              <label><span>Type</span>
                <select value={ff.kind} onChange={(e) => setFf({ ...ff, kind: e.target.value })} aria-label="Facility type">{['sauna', 'pool', 'studio', 'court', 'steam_room', 'other'].map((k) => <option key={k} value={k}>{k.replace('_', ' ')}</option>)}</select></label>
              <label><span>Places at once</span><input type="number" min="1" value={ff.capacity} onChange={(e) => setFf({ ...ff, capacity: e.target.value })} aria-label="Facility capacity" /></label>
              <label><span>Opens</span><input value={ff.open_time} onChange={(e) => setFf({ ...ff, open_time: e.target.value })} aria-label="Facility opens" style={{ width: 80 }} /></label>
              <label><span>Closes</span><input value={ff.close_time} onChange={(e) => setFf({ ...ff, close_time: e.target.value })} aria-label="Facility closes" style={{ width: 80 }} /></label>
              <label><span>Longest booking (min)</span><input type="number" min="15" value={ff.max_minutes} onChange={(e) => setFf({ ...ff, max_minutes: e.target.value })} aria-label="Facility longest booking" /></label>
              <button type="button" className="gm-primary" disabled={busy || !ff.name.trim()} onClick={async () => { if (await run('/gym/facilities', { name: ff.name.trim(), kind: ff.kind, capacity: Number(ff.capacity), open_time: ff.open_time, close_time: ff.close_time, max_minutes: Number(ff.max_minutes) }, 'Facility added')) setFf({ ...ff, name: '' }); }}>Add facility</button>
            </div>
          </section>
          <section className="gm-box" aria-label="Book a facility">
            <h2>Book a slot</h2>
            <div className="gm-form">
              <label><span>Facility</span>
                <select value={fbook.facility_id} onChange={(e) => setFbook({ ...fbook, facility_id: e.target.value })} aria-label="Booking facility"><option value="">Choose</option>{facilities.filter((f) => f.is_active).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
              <label><span>Member</span>
                <select value={fbook.member_id} onChange={(e) => setFbook({ ...fbook, member_id: e.target.value })} aria-label="Booking member"><option value="">Choose</option>{members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></label>
              <label><span>When</span><input type="datetime-local" value={fbook.when} onChange={(e) => setFbook({ ...fbook, when: e.target.value })} aria-label="Booking time" /></label>
              <label><span>Minutes</span><input type="number" min="15" value={fbook.minutes} onChange={(e) => setFbook({ ...fbook, minutes: e.target.value })} aria-label="Booking minutes" /></label>
              <button type="button" className="gm-primary" disabled={busy || !fbook.facility_id || !fbook.member_id || !fbook.when}
                onClick={async () => { if (await run(`/gym/facilities/${fbook.facility_id}/book`, { member_id: fbook.member_id, starts_at: new Date(fbook.when).toISOString().slice(0, 19), minutes: Number(fbook.minutes) }, 'Booked')) setFbook({ ...fbook, when: '' }); }}>Book</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Facilities and bookings">
            <table>
              <thead><tr><th>Facility</th><th>Hours</th><th>Places</th><th /></tr></thead>
              <tbody>
                {facilities.map((f) => <tr key={f.id}><td>{f.name}{f.is_active ? '' : ' (closed)'}</td><td>{f.open_time} to {f.close_time}</td><td>{f.capacity}</td>
                  <td><button type="button" onClick={() => void run(`/gym/facilities/${f.id}/active`, { is_active: !f.is_active }, 'Saved')}>{f.is_active ? 'Close' : 'Reopen'}</button></td></tr>)}
                {facilities.length === 0 ? <tr><td colSpan={4} className="gm-muted">No facilities.</td></tr> : null}
              </tbody>
            </table>
            <table>
              <thead><tr><th>When</th><th>Facility</th><th>Member</th><th>Status</th><th /></tr></thead>
              <tbody>
                {fbookings.map((b) => <tr key={b.id}><td>{when(b.starts_at)}</td><td>{b.facility}</td><td>{b.member_name}</td><td>{b.status.replace('_', ' ')}</td>
                  <td className="gm-row">{b.status === 'booked' ? (<>
                    <button type="button" onClick={() => void run(`/gym/facility-bookings/${b.id}`, { status: 'attended' }, 'Saved')}>Came</button>
                    <button type="button" onClick={() => void run(`/gym/facility-bookings/${b.id}`, { status: 'no_show' }, 'Saved')}>Did not come</button>
                    <button type="button" className="gm-danger" onClick={() => void run(`/gym/facility-bookings/${b.id}`, { status: 'cancelled' }, 'Cancelled')}>Cancel</button></>) : null}</td></tr>)}
                {fbookings.length === 0 ? <tr><td colSpan={5} className="gm-muted">No bookings coming up.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {part === 'pay' ? (
        <section className="gm-box gm-scroll" aria-label="Trainer pay">
          <p className="gm-muted">A trainer earns their percent of the session price listed on their profile each time a session is marked done. This is a record for payroll: marking it paid does not move money or post to the books.</p>
          <table>
            <thead><tr><th>Trainer</th><th>Percent</th><th>Sessions (30 days)</th><th>Owed</th><th>Paid</th><th /></tr></thead>
            <tbody>
              {trainers.map((t) => {
                const r = (commission?.trainers || []).find((x: Row) => x.trainer_id === t.id) || { sessions: 0, accrued: 0, paid: 0 };
                return (
                  <tr key={t.id}>
                    <td>{t.full_name}</td>
                    <td className="gm-row"><input type="number" min="0" max="100" step="0.5" value={pct[t.id] ?? String(t.commission_pct ?? 0)} onChange={(e) => setPct({ ...pct, [t.id]: e.target.value })} aria-label={`Commission percent for ${t.full_name}`} style={{ width: 80 }} />
                      <button type="button" disabled={busy} onClick={() => void run(`/gym/trainers/${t.id}/commission`, { commission_pct: Number(pct[t.id] ?? t.commission_pct ?? 0) }, 'Saved')}>Save</button></td>
                    <td>{r.sessions}</td><td>{r.accrued}</td><td>{r.paid}</td>
                    <td className="gm-row">{r.accrued > 0 ? (<>
                      <input value={payRef[t.id] || ''} onChange={(e) => setPayRef({ ...payRef, [t.id]: e.target.value })} placeholder="Payroll or transfer reference" aria-label={`Pay reference for ${t.full_name}`} />
                      <button type="button" disabled={busy || (payRef[t.id] || '').trim().length < 2} onClick={() => { const end = today(); const start = commission?.start_date || end; if (window.confirm(`Mark ${r.accrued} as paid to ${t.full_name}?`)) void run('/gym/commissions/pay', { trainer_id: t.id, start_date: start, end_date: end, reference: payRef[t.id].trim() }, 'Marked as paid'); }}>Mark paid</button></>) : null}</td>
                  </tr>
                );
              })}
              {trainers.length === 0 ? <tr><td colSpan={6} className="gm-muted">No trainers.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {part === 'trainers' ? (
        <section className="gm-box gm-scroll" aria-label="Trainer logins">
          <p className="gm-muted">Link a trainer to their staff login (paste the user id from Staff) so they get My work. They then see only their own sessions and members.</p>
          <table>
            <thead><tr><th>Trainer</th><th>Linked login</th><th /></tr></thead>
            <tbody>
              {trainers.map((t) => (
                <tr key={t.id}><td>{t.full_name}</td>
                  <td><input value={trainerUser[t.id] ?? ''} onChange={(e) => setTrainerUser({ ...trainerUser, [t.id]: e.target.value })} placeholder="user id" aria-label={`Login for ${t.full_name}`} /></td>
                  <td className="gm-row">
                    <button type="button" disabled={busy || !(trainerUser[t.id] || '').trim()} onClick={() => void run(`/gym/trainers/${t.id}/link-user`, { user_id: trainerUser[t.id].trim() }, 'Linked')}>Link</button>
                    <button type="button" className="gm-danger" onClick={() => void run(`/gym/trainers/${t.id}/link-user`, { user_id: null }, 'Unlinked')}>Unlink</button>
                  </td></tr>
              ))}
              {trainers.length === 0 ? <tr><td colSpan={3} className="gm-muted">No trainers.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

// --- Insights -------------------------------------------------------------------------------

export function InsightsTab() {
  const [status, setStatus] = useState<Row | null>(null);
  const [summary, setSummary] = useState<Row | null>(null);
  const [risk, setRisk] = useState<Row | null>(null);
  const [att, setAtt] = useState<Row | null>(null);
  const [eq, setEq] = useState<Row | null>(null);
  const [assets, setAssets] = useState<Row | null>(null);
  const [ratings, setRatings] = useState<Row[] | null>(null);
  const load = useCallback(async () => {
    setAssets(await get('/gym/reports/equipment-assets'));
    setRatings(await get('/gym/reports/trainer-ratings'));
    const s = await get('/gym/insights/status');
    setStatus(s);
    if (s?.insights_enabled) {
      setSummary(await get('/gym/insights/summary'));
      setRisk(await get('/gym/insights/churn-risk'));
      setAtt(await get('/gym/insights/attendance'));
      setEq(await get('/gym/insights/equipment'));
    } else {
      setSummary(null); setRisk(null); setAtt(null); setEq(null);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const { error, notice, busy, run } = useRunner(load);

  return (
    <div className="gm-floor">
      <Msg error={error} notice={notice} />
      <p className="gm-muted">{status?.note || 'Calculated from your own records with fixed rules. Not generated by a language model.'} Nothing leaves your system.</p>
      <p><button type="button" disabled={busy || !status} onClick={() => void run('/gym/insights/status', { insights_enabled: !status?.insights_enabled }, 'Saved')}>{status?.insights_enabled ? 'Switch insights off' : 'Switch insights on'}</button></p>
      {status && !status.insights_enabled ? <p>Insights are off.</p> : null}
      {summary ? (
        <section className="gm-box" aria-label="Summary">
          <h2>Last 30 days</h2>
          <ul>{summary.bullets.map((b: string) => <li key={b}>{b}</li>)}</ul>
        </section>
      ) : null}
      {risk ? (
        <section className="gm-box gm-scroll" aria-label="Members who may leave">
          <h2>Members who may leave ({risk.total_at_risk})</h2>
          <table>
            <thead><tr><th>Member</th><th>Risk</th><th>Why</th><th>Suggested next step</th></tr></thead>
            <tbody>
              {risk.items.map((r: Row) => <tr key={r.member_id}><td>{r.member_name}</td><td>{r.level} ({r.score})</td><td>{r.reasons.join('; ')}</td><td>{r.suggested_action}</td></tr>)}
              {risk.items.length === 0 ? <tr><td colSpan={4} className="gm-muted">No one stands out.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
      {att ? (
        <section className="gm-box" aria-label="Attendance">
          <h2>Attendance</h2>
          <ul>{att.notes.map((n: string) => <li key={n}>{n}</li>)}</ul>
          <p className="gm-muted">{Object.entries(att.by_weekday).map(([d, n]) => `${d} ${n}`).join(' · ')}</p>
        </section>
      ) : null}
      {eq ? (
        <section className="gm-box" aria-label="Equipment">
          <h2>Equipment to look at</h2>
          <ul>{eq.items.map((e: Row) => <li key={e.equipment_id}><strong>{e.name}</strong>: {e.flags.join('; ')}</li>)}</ul>
          {eq.items.length === 0 ? <p className="gm-muted">Nothing stands out.</p> : null}
        </section>
      ) : null}
      {assets ? (
        <section className="gm-box gm-scroll" aria-label="Equipment value">
          <h2>Equipment value (as of {assets.as_of})</h2>
          <p className="gm-muted">{assets.note}</p>
          <table>
            <thead><tr><th>Equipment</th><th>Status</th><th>Cost</th><th>Depreciation</th><th>Book value</th></tr></thead>
            <tbody>
              {assets.items.map((i: Row) => <tr key={i.id || i.name}><td>{i.name}</td><td>{i.status}</td><td>{i.purchase_cost ?? ''}</td><td>{i.accumulated_depreciation ?? ''}</td><td>{i.book_value ?? ''}</td></tr>)}
              {assets.items.length === 0 ? <tr><td colSpan={5} className="gm-muted">No equipment recorded.</td></tr> : null}
            </tbody>
            <tfoot><tr><th colSpan={2}>Total</th><th>{assets.total_cost}</th><th>{assets.total_depreciation}</th><th>{assets.total_book_value}</th></tr></tfoot>
          </table>
        </section>
      ) : null}
      {ratings ? (
        <section className="gm-box gm-scroll" aria-label="Trainer ratings">
          <h2>Trainer ratings</h2>
          <table>
            <thead><tr><th>Trainer</th><th>Average</th><th>Ratings</th></tr></thead>
            <tbody>
              {ratings.map((r: Row) => <tr key={r.trainer_id}><td>{r.trainer}</td><td>{r.average}</td><td>{r.ratings}</td></tr>)}
              {ratings.length === 0 ? <tr><td colSpan={3} className="gm-muted">No member ratings yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

// --- My work (trainer) ----------------------------------------------------------------------

export function MyWorkTab() {
  const [me, setMe] = useState<Row | null>(null);
  const [sessions, setSessions] = useState<Row[]>([]);
  const [members, setMembers] = useState<Row[]>([]);
  const [programmes, setProgrammes] = useState<Row[]>([]);
  const [missing, setMissing] = useState(false);
  const load = useCallback(async () => {
    const m = await get('/gym/trainer-portal/me');
    setMissing(!m);
    setMe(m);
    if (m) {
      setSessions((await get('/gym/trainer-portal/sessions')) || []);
      setMembers((await get('/gym/trainer-portal/members')) || []);
      setProgrammes((await get('/gym/trainer-portal/programmes')) || []);
    }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const { error, notice, busy, run } = useRunner(load);
  if (missing) return <p className="gm-muted">Your login is not linked to a trainer profile yet. Ask a manager to link it in Setup.</p>;
  return (
    <div className="gm-floor">
      <Msg error={error} notice={notice} />
      {me ? <p>{me.members} members · {me.upcoming_sessions} sessions coming up{me.average_rating ? ` · rated ${me.average_rating}/5 (${me.ratings})` : ''}</p> : null}
      <section className="gm-box gm-scroll" aria-label="My sessions">
        <h2>My sessions</h2>
        <table>
          <thead><tr><th>When</th><th>Member</th><th>Status</th><th /></tr></thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}><td>{when(s.starts_at)}</td><td>{s.member_name}</td><td>{String(s.status).replace('_', ' ')}</td>
                <td className="gm-row">{s.status === 'booked' ? (<>
                  <button type="button" disabled={busy} onClick={() => void run(`/gym/trainer-portal/sessions/${s.id}`, { status: 'completed' }, 'Saved')}>Done</button>
                  <button type="button" disabled={busy} onClick={() => void run(`/gym/trainer-portal/sessions/${s.id}`, { status: 'no_show' }, 'Saved')}>Did not come</button>
                </>) : null}</td></tr>
            ))}
            {sessions.length === 0 ? <tr><td colSpan={4} className="gm-muted">No sessions.</td></tr> : null}
          </tbody>
        </table>
      </section>
      <section className="gm-box" aria-label="My members">
        <h2>My members</h2>
        <ul>{members.map((m) => <li key={m.id}>{m.full_name} · {m.state}{m.plan_name ? ` · ${m.plan_name}` : ''}{m.ends_on ? ` until ${m.ends_on}` : ''}</li>)}</ul>
        {members.length === 0 ? <p className="gm-muted">No members yet.</p> : null}
      </section>
      <section className="gm-box" aria-label="My programmes">
        <h2>My programmes</h2>
        <ul>{programmes.map((p) => <li key={p.id}>{p.name} for {p.member_name} ({p.status})</li>)}</ul>
        {programmes.length === 0 ? <p className="gm-muted">None.</p> : null}
      </section>
      <span hidden>{today()}</span>
    </div>
  );
}

// --- Shop -----------------------------------------------------------------------------------

const PAY = [['cash', 'Cash'], ['mobile_money', 'Mobile Money'], ['card', 'Card'], ['bank_transfer', 'Bank transfer']];

export function ShopTab({ members }: { members: Row[] }) {
  const [part, setPart] = useState('sell');
  const [products, setProducts] = useState<Row[] | null>(null);
  const [sales, setSales] = useState<Row[]>([]);
  const [bills, setBills] = useState<Row[]>([]);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [method, setMethod] = useState('cash');
  const [member, setMember] = useState('');
  const [receipt, setReceipt] = useState<Row | null>(null);
  const [pf, setPf] = useState({ name: '', price: '', reorder: '0' });
  const [stock, setStock] = useState<Record<string, { qty: string; cost: string; how: string; supplier: string }>>({});
  const [refundQty, setRefundQty] = useState<Record<string, string>>({});
  const [refundHow, setRefundHow] = useState('cash');
  const load = useCallback(async () => {
    setProducts(await get('/gym/shop/products'));
    setSales((await get('/gym/shop/sales')) || []);
    setBills((await get('/gym/shop/bills')) || []);
  }, []);
  useEffect(() => { void load(); }, [load]);
  const { error, notice, busy, run } = useRunner(load);
  const active = (products || []).filter((p) => p.is_active);
  const lines = Object.entries(cart).filter(([, q]) => q > 0);
  const total = lines.reduce((sum, [id, q]) => sum + q * Number(products?.find((p) => p.id === id)?.price || 0), 0);

  return (
    <div className="gm-floor">
      <Msg error={error} notice={notice} />
      <div className="gm-row" role="tablist" aria-label="Shop">
        {[['sell', 'Sell'], ['products', 'Products and stock'], ['sales', 'Sales and refunds'], ['bills', `Supplier bills${bills.filter((b) => b.status === 'open').length ? ` (${bills.filter((b) => b.status === 'open').length} open)` : ''}`]].map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={part === id} className={part === id ? 'gm-primary' : ''} onClick={() => setPart(id)}>{label}</button>
        ))}
      </div>

      {part === 'sell' ? (
        <section className="gm-box" aria-label="Sell">
          <p className="gm-muted">Needs an open till (Members screen). Tax is added by the company&apos;s tax setting.</p>
          <table>
            <thead><tr><th>Product</th><th>Price</th><th>In stock</th><th>Qty</th></tr></thead>
            <tbody>
              {active.map((p) => (
                <tr key={p.id}><td>{p.name}{p.low ? ' (low)' : ''}</td><td>{p.price}</td><td>{p.stock_qty}</td>
                  <td><input type="number" min="0" max={p.stock_qty} value={cart[p.id] || ''} onChange={(e) => setCart({ ...cart, [p.id]: Math.max(0, Number(e.target.value)) })} aria-label={`Quantity of ${p.name}`} style={{ width: 70 }} /></td></tr>
              ))}
              {active.length === 0 ? <tr><td colSpan={4} className="gm-muted">No products yet. A manager adds them under Products and stock.</td></tr> : null}
            </tbody>
          </table>
          <div className="gm-form">
            <label><span>Member (optional)</span>
              <select value={member} onChange={(e) => setMember(e.target.value)} aria-label="Shop member"><option value="">Walk-in</option>{members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></label>
            <label><span>Paid by</span>
              <select value={method} onChange={(e) => setMethod(e.target.value)} aria-label="Shop payment method">{PAY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <button type="button" className="gm-primary" disabled={busy || lines.length === 0}
              onClick={async () => {
                const r = await run('/gym/shop/sales', { items: lines.map(([product_id, quantity]) => ({ product_id, quantity })), method, member_id: member || undefined }, 'Sold');
                if (r && r !== true) { printPaymentReceipt('gym_sale', r.id); setReceipt(r); setCart({}); }
              }}>Charge about {total.toFixed(2)}</button>
          </div>
          {receipt ? <p role="status">Sale {receipt.sale_number}: {receipt.total} by {String(receipt.method).replace('_', ' ')} ({receipt.lines.map((l: Row) => `${l.quantity} x ${l.name}`).join(', ')})</p> : null}
        </section>
      ) : null}

      {part === 'products' && products ? (
        <>
          <section className="gm-box" aria-label="Add product">
            <h2>Add a product</h2>
            <div className="gm-form">
              <label><span>Name</span><input value={pf.name} onChange={(e) => setPf({ ...pf, name: e.target.value })} aria-label="Product name" /></label>
              <label><span>Price</span><input type="number" min="0" step="0.01" value={pf.price} onChange={(e) => setPf({ ...pf, price: e.target.value })} aria-label="Product price" /></label>
              <label><span>Warn when stock is at</span><input type="number" min="0" value={pf.reorder} onChange={(e) => setPf({ ...pf, reorder: e.target.value })} aria-label="Product reorder level" /></label>
              <button type="button" className="gm-primary" disabled={busy || !pf.name.trim() || pf.price === ''} onClick={async () => { if (await run('/gym/shop/products', { name: pf.name.trim(), price: Number(pf.price), reorder_level: Number(pf.reorder || 0) }, 'Product added')) setPf({ name: '', price: '', reorder: '0' }); }}>Add product</button>
            </div>
          </section>
          <section className="gm-box gm-scroll" aria-label="Products">
            <p className="gm-muted">Buying stock for cash, Mobile Money, card or transfer is paid from the open till. &quot;On credit&quot; makes a supplier bill you pay later.</p>
            <table>
              <thead><tr><th>Product</th><th>Price</th><th>Stock</th><th>Cost</th><th>Buy stock</th><th /></tr></thead>
              <tbody>
                {products.map((p) => {
                  const v = stock[p.id] || { qty: '', cost: '', how: 'cash', supplier: '' };
                  const set = (patch: object) => setStock({ ...stock, [p.id]: { ...v, ...patch } });
                  return (
                    <tr key={p.id}>
                      <td>{p.name}{p.is_active ? '' : ' (off sale)'}</td><td>{p.price}</td><td>{p.stock_qty}{p.low ? ' (low)' : ''}</td><td>{p.cost}</td>
                      <td className="gm-row">
                        <input type="number" min="1" value={v.qty} onChange={(e) => set({ qty: e.target.value })} placeholder="Qty" aria-label={`Quantity to buy of ${p.name}`} style={{ width: 70 }} />
                        <input type="number" min="0" step="0.01" value={v.cost} onChange={(e) => set({ cost: e.target.value })} placeholder="Cost each" aria-label={`Unit cost of ${p.name}`} style={{ width: 90 }} />
                        <select value={v.how} onChange={(e) => set({ how: e.target.value })} aria-label={`How ${p.name} was paid`}>{[...PAY, ['credit', 'On credit']].map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
                        {v.how === 'credit' ? <input value={v.supplier} onChange={(e) => set({ supplier: e.target.value })} placeholder="Supplier" aria-label={`Supplier of ${p.name}`} /> : null}
                        <button type="button" disabled={busy || !v.qty || !v.cost || (v.how === 'credit' && !v.supplier.trim())}
                          onClick={async () => { if (await run(`/gym/shop/products/${p.id}/restock`, { quantity: Number(v.qty), unit_cost: Number(v.cost), method: v.how, supplier_name: v.how === 'credit' ? v.supplier.trim() : undefined }, 'Stock added')) setStock({ ...stock, [p.id]: { ...v, qty: '', cost: '' } }); }}>Add stock</button>
                      </td>
                      <td><button type="button" onClick={() => void run(`/gym/shop/products/${p.id}`, { is_active: !p.is_active }, 'Saved')}>{p.is_active ? 'Take off sale' : 'Put on sale'}</button></td>
                    </tr>
                  );
                })}
                {products.length === 0 ? <tr><td colSpan={6} className="gm-muted">No products yet.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {part === 'sales' ? (
        <section className="gm-box gm-scroll" aria-label="Sales">
          <p className="gm-muted">A refund is a manager&apos;s decision. It puts the stock back, reverses the sale and pays the customer from the open till.</p>
          <label><span>Refund paid by </span>
            <select value={refundHow} onChange={(e) => setRefundHow(e.target.value)} aria-label="Refund method">{PAY.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <table>
            <thead><tr><th>Sale</th><th>When</th><th>Total</th><th>Items</th></tr></thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id}><td>{s.sale_number}</td><td>{when(s.date)}</td><td>{s.total}</td>
                  <td>{s.lines.map((l: Row) => {
                    const key = `${s.id}:${l.product_id}`;
                    return (
                      <span key={key} className="gm-row">{l.quantity} x {l.name}{l.refundable < l.quantity ? ` (${l.quantity - l.refundable} refunded)` : ''}{' '}
                        {l.refundable > 0 ? (<>
                          <input type="number" min="1" max={l.refundable} value={refundQty[key] || ''} onChange={(e) => setRefundQty({ ...refundQty, [key]: e.target.value })} aria-label={`Refund quantity of ${l.name} on ${s.sale_number}`} style={{ width: 60 }} />
                          <button type="button" className="gm-danger" disabled={busy || !refundQty[key]} onClick={() => { if (window.confirm(`Refund ${refundQty[key]} x ${l.name}?`)) void run(`/gym/shop/sales/${s.id}/refund`, { items: [{ product_id: l.product_id, quantity: Number(refundQty[key]) }], method: refundHow }, 'Refunded'); }}>Refund</button></>) : null}
                      </span>
                    );
                  })}</td></tr>
              ))}
              {sales.length === 0 ? <tr><td colSpan={4} className="gm-muted">No sales yet.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}

      {part === 'bills' ? (
        <section className="gm-box gm-scroll" aria-label="Supplier bills">
          <table>
            <thead><tr><th>Bill</th><th>Supplier</th><th>Product</th><th>Amount</th><th>Due</th><th>Status</th><th /></tr></thead>
            <tbody>
              {bills.map((b) => (
                <tr key={b.id}><td>{b.bill_number}</td><td>{b.supplier}</td><td>{b.quantity} x {b.product}</td><td>{b.amount}</td><td>{b.due_on || ''}{b.overdue ? ' (overdue)' : ''}</td><td>{b.status}</td>
                  <td>{b.status === 'open' ? <button type="button" className="gm-primary" disabled={busy} onClick={() => { if (window.confirm(`Pay ${b.amount} to ${b.supplier} from the open till?`)) void run(`/gym/shop/bills/${b.id}/pay`, { method: 'cash' }, 'Bill paid'); }}>Pay in cash</button> : null}</td></tr>
              ))}
              {bills.length === 0 ? <tr><td colSpan={7} className="gm-muted">No supplier bills.</td></tr> : null}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
