'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import DeskIcon from '../../../../components/DeskIcon';
import PageHeader from '../../../../components/PageHeader';
import { Tag, timeAgo } from '../../../../components/PlatformUi';
import { api } from '../../../../lib/api';
import './email-center.css';

type Preview = {
  recipient_count: number;
  company_count: number;
  sample: { email: string; company_name: string }[];
  too_many: boolean;
  max_recipients: number;
};

type HistoryRow = {
  id: string;
  created_at?: string | null;
  subject?: string | null;
  body_preview?: string | null;
  filters?: { statuses?: string[]; industries?: string[]; packages?: string[]; include_company_email?: boolean };
  recipient_count: number;
  company_count: number;
  sent_by?: string | null;
  status: 'sending' | 'finished';
  sent?: number | null;
  failed?: number | null;
  failures?: { email: string; reason: string }[];
};

type Option = { value: string; label: string };

const STATUSES: Option[] = [
  { value: 'trial', label: 'Trial' },
  { value: 'active', label: 'Active' },
  { value: 'grace', label: 'Grace' },
  { value: 'suspended', label: 'Suspended' },
];

const INDUSTRIES: Option[] = [
  { value: 'retail', label: 'Retail' },
  { value: 'hotel', label: 'Hotel' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'bakery', label: 'Bakery' },
  { value: 'fmcg', label: 'FMCG' },
  { value: 'gym', label: 'Gym' },
  { value: 'hrm', label: 'HRM' },
  { value: 'pharmacy', label: 'Pharmacy' },
];

const PACKAGES: Option[] = [
  { value: 'trial', label: 'Trial' },
  { value: 'starter', label: 'Starter' },
  { value: 'professional', label: 'Professional' },
  { value: 'enterprise', label: 'Enterprise' },
];

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

function labelsFor(values: string[] | undefined, options: Option[]) {
  return (values || []).map((v) => options.find((o) => o.value === v)?.label || v);
}

function audienceWords(filters: HistoryRow['filters']) {
  const parts = [
    ...labelsFor(filters?.statuses, STATUSES),
    ...labelsFor(filters?.industries, INDUSTRIES),
    ...labelsFor(filters?.packages, PACKAGES),
  ];
  return parts.length ? parts.join(', ') : 'All companies';
}

function ChipGroup({
  legend,
  options,
  value,
  onChange,
}: {
  legend: string;
  options: Option[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset className="ec-chips">
      <legend>{legend}</legend>
      <div className="ec-chip-row">
        <button
          type="button"
          className={`ec-chip${value.length === 0 ? ' is-on' : ''}`}
          aria-pressed={value.length === 0}
          onClick={() => onChange([])}
        >
          Any
        </button>
        {options.map((opt) => {
          const on = value.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              className={`ec-chip${on ? ' is-on' : ''}`}
              aria-pressed={on}
              aria-label={`${legend}: ${opt.label}`}
              onClick={() => onChange(on ? value.filter((v) => v !== opt.value) : [...value, opt.value])}
            >
              {on ? <DeskIcon name="check" size={14} /> : null}
              {opt.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function EmailCenterPage() {
  const [statuses, setStatuses] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [packages, setPackages] = useState<string[]>([]);
  const [includeCompanyEmail, setIncludeCompanyEmail] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [testTo, setTestTo] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [mode, setMode] = useState<string>('');
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const audience = useMemo(
    () => ({ statuses, industries, packages, include_company_email: includeCompanyEmail }),
    [statuses, industries, packages, includeCompanyEmail],
  );

  const loadHistory = useCallback(async () => {
    try {
      const res = await api('/platform/email/history');
      setHistory(res?.data || []);
    } catch (err: any) {
      setError(err.message || 'Could not load sent emails');
    }
  }, []);

  useEffect(() => {
    api('/platform/email/status')
      .then((res) => setMode(res?.data?.mode || ''))
      .catch((err) => setError(err.message || 'Could not open the email center'));
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    let live = true;
    setPreviewing(true);
    const timer = window.setTimeout(() => {
      api('/platform/email/preview', { method: 'POST', body: JSON.stringify(audience) })
        .then((res) => live && setPreview(res?.data || null))
        .catch((err) => live && setError(err.message || 'Could not count recipients'))
        .finally(() => live && setPreviewing(false));
    }, 250);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [audience]);

  // While a send is still going out, check back for its result.
  useEffect(() => {
    if (!history.some((row) => row.status === 'sending')) return;
    const timer = window.setInterval(loadHistory, 4000);
    return () => window.clearInterval(timer);
  }, [history, loadHistory]);

  const subjectOk = subject.trim().length >= 2;
  const bodyOk = body.trim().length >= 2;
  const count = preview?.recipient_count || 0;
  const canSend = subjectOk && bodyOk && count > 0 && !preview?.too_many && !busy;
  const mailOff = mode === 'disabled';

  async function sendTest() {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await api('/platform/email/test', {
        method: 'POST',
        body: JSON.stringify({ subject: subject.trim(), body: body.trim(), to: testTo.trim() || null }),
      });
      setMessage(res?.message || 'Test email sent.');
    } catch (err: any) {
      setError(err.message || 'The test email was not sent');
    } finally {
      setBusy(false);
    }
  }

  async function sendNow() {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await api('/platform/email/send', {
        method: 'POST',
        body: JSON.stringify({ ...audience, subject: subject.trim(), body: body.trim(), confirm: true }),
      });
      setMessage(res?.message || 'Sending.');
      setConfirming(false);
      setSubject('');
      setBody('');
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'The email was not sent');
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="plat ec">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Email center"
        subtitle="Write once to the companies that use Ribdigi ERP. Each person gets their own copy, so nobody sees anyone else's address."
        subtitleClassName="plat-sub"
      />

      {mailOff && (
        <p className="ec-banner ec-banner-warn" role="status">
          <DeskIcon name="alert" size={18} />
          <span>Platform email is turned off. Turn email on and set the SMTP settings for Ribdigi House before sending.</span>
        </p>
      )}
      {mode === 'console' && (
        <p className="ec-banner ec-banner-warn" role="status">
          <DeskIcon name="alert" size={18} />
          <span>No SMTP server is set, so messages are only written to the server log. Live sending needs SMTP settings.</span>
        </p>
      )}
      {error && (
        <p className="ec-banner ec-banner-bad" role="alert">
          <DeskIcon name="alert" size={18} />
          <span>{error}</span>
        </p>
      )}
      {message && (
        <p className="ec-banner ec-banner-ok" role="status">
          <DeskIcon name="check" size={18} />
          <span>{message}</span>
        </p>
      )}

      <div className="ec-grid">
        <section className="plat-panel ec-panel" aria-label="Who gets it">
          <div className="ec-panel-head">
            <span className="ec-ico"><DeskIcon name="users" size={20} /></span>
            <h2>Who gets it</h2>
          </div>
          <ChipGroup legend="Status" options={STATUSES} value={statuses} onChange={setStatuses} />
          <ChipGroup legend="Business type" options={INDUSTRIES} value={industries} onChange={setIndustries} />
          <ChipGroup legend="Plan" options={PACKAGES} value={packages} onChange={setPackages} />
          <label className="ec-check">
            <input
              type="checkbox"
              aria-label="Also send to each company's own email"
              checked={includeCompanyEmail}
              onChange={(event) => setIncludeCompanyEmail(event.target.checked)}
            />
            <span>Also send to each company&apos;s own email address, not just its admins</span>
          </label>

          <div className={`ec-count${preview?.too_many ? ' is-bad' : ''}`} aria-live="polite">
            <strong>{previewing && !preview ? '…' : count}</strong>
            <span>
              {preview
                ? `${count === 1 ? 'person' : 'people'} at ${plural(preview.company_count, 'company', 'companies')}`
                : 'people'}
            </span>
          </div>
          {preview?.too_many && (
            <p className="ec-note ec-note-bad">One send can reach at most {preview.max_recipients} people. Narrow the filters.</p>
          )}
          {preview && preview.sample.length > 0 && (
            <ul className="ec-sample" aria-label="Some of the people who get it">
              {preview.sample.map((row) => (
                <li key={row.email}>
                  <span className="ec-sample-name">{row.company_name}</span>
                  <span className="ec-sample-mail">{row.email}</span>
                </li>
              ))}
              {count > preview.sample.length && <li className="ec-sample-more">and {count - preview.sample.length} more</li>}
            </ul>
          )}
          {preview && count === 0 && <p className="ec-note">No company admins match these filters.</p>}
        </section>

        <section className="plat-panel ec-panel" aria-label="Message">
          <div className="ec-panel-head">
            <span className="ec-ico"><DeskIcon name="mail" size={20} /></span>
            <h2>Message</h2>
          </div>
          <label className="ec-field">
            <span>Subject</span>
            <input
              aria-label="Email subject"
              value={subject}
              maxLength={200}
              placeholder="New: Reports on the Starter plan"
              onChange={(event) => setSubject(event.target.value)}
            />
          </label>
          <label className="ec-field">
            <span>Message</span>
            <textarea
              aria-label="Email message"
              value={body}
              rows={11}
              maxLength={20000}
              placeholder={'Hello {company_name},\n\nWrite your news here. Leave a blank line between paragraphs.'}
              onChange={(event) => setBody(event.target.value)}
            />
          </label>
          <p className="ec-note">
            Type <code>{'{company_name}'}</code> in the subject or message and each company sees its own name. The
            Ribdigi House logo and a line saying why they got the email are added for you.
          </p>

          <div className="ec-test">
            <label className="ec-field">
              <span>Send a test to</span>
              <input
                aria-label="Test email address"
                type="email"
                value={testTo}
                placeholder="Your own email"
                onChange={(event) => setTestTo(event.target.value)}
              />
            </label>
            <button type="button" aria-label="Send test email" disabled={!subjectOk || !bodyOk || busy || mailOff} onClick={sendTest}>
              Send test
            </button>
          </div>

          <div className="ec-actions">
            <button
              type="button"
              className="list-btn-primary ec-send"
              aria-label="Send bulk email"
              disabled={!canSend || mailOff}
              onClick={() => setConfirming(true)}
            >
              <DeskIcon name="send" size={18} />
              <span>{count ? `Send to ${plural(count, 'person', 'people')}` : 'Send'}</span>
            </button>
          </div>
        </section>
      </div>

      <section className="plat-panel ec-panel" aria-label="Sent emails">
        <div className="ec-panel-head">
          <span className="ec-ico"><DeskIcon name="clock" size={20} /></span>
          <h2>Sent emails</h2>
        </div>
        {!history.length ? (
          <p className="ec-note">Nothing sent yet. Your sends appear here with how many went out.</p>
        ) : (
          <ul className="ec-history">
            {history.map((row) => (
              <li key={row.id}>
                <div className="ec-history-main">
                  <strong>{row.subject}</strong>
                  <span className="ec-history-meta">
                    {audienceWords(row.filters)} · {plural(row.recipient_count, 'person', 'people')} ·{' '}
                    {timeAgo(row.created_at)}
                    {row.sent_by ? ` · by ${row.sent_by}` : ''}
                  </span>
                  {row.failures && row.failures.length > 0 && (
                    <details className="ec-fail">
                      <summary>Show who did not get it</summary>
                      <ul>
                        {row.failures.map((f) => (
                          <li key={f.email}>
                            {f.email}: {f.reason}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
                <div className="ec-history-state">
                  {row.status === 'sending' ? (
                    <Tag tone="info">Sending…</Tag>
                  ) : row.failed ? (
                    <Tag tone="warn">{`${row.sent} sent, ${row.failed} failed`}</Tag>
                  ) : (
                    <Tag tone="ok">{`${row.sent} sent`}</Tag>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {confirming && (
        <div className="ec-modal-back" role="presentation" onClick={() => !busy && setConfirming(false)}>
          <div
            className="ec-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ec-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="ec-confirm-title">Send this email now?</h2>
            <p>
              <strong>{subject.trim()}</strong> goes to {plural(count, 'person', 'people')} at{' '}
              {plural(preview?.company_count || 0, 'company', 'companies')} ({audienceWords(audience)}). It cannot be
              taken back.
            </p>
            <div className="ec-modal-actions">
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </button>
              <button type="button" className="list-btn-primary" aria-label="Confirm send bulk email" onClick={sendNow} disabled={busy}>
                {busy ? 'Sending…' : `Yes, send to ${plural(count, 'person', 'people')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
