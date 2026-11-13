'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeskIcon from '../../../../components/DeskIcon';
import EmailDesigner from '../../../../components/EmailDesigner';
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
  body?: string | null;
  body_complete?: boolean;
  filters?: {
    statuses?: string[];
    industries?: string[];
    packages?: string[];
    tenant_ids?: string[];
    include_company_email?: boolean;
    retry_of?: string;
  };
  recipient_count: number;
  company_count: number;
  sent_by?: string | null;
  status: 'sending' | 'finished' | 'stopped';
  sent?: number | null;
  failed?: number | null;
  failures?: { email: string; reason: string; company_name?: string }[];
};

type Company = {
  id: string;
  company_name: string;
  status?: string | null;
  industry?: string | null;
  package_code?: string | null;
};

type MailStatus = { mode: string; from_name?: string; from_email?: string };
type Rendered = { subject: string; html: string };
type Option = { value: string; label: string };
type Field = 'subject' | 'body';

const STATUSES: Option[] = [
  { value: 'trial', label: 'Trial' },
  { value: 'active', label: 'Active' },
  { value: 'grace', label: 'Grace' },
  { value: 'suspended', label: 'Suspended' },
];

const INDUSTRIES: Option[] = [
  { value: 'retail', label: 'Retail' },
  { value: 'wholesale', label: 'Wholesale' },
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

/** Ready-made openings the owner can start from and then change. */
const STARTERS: { key: string; label: string; subject: string; body: string }[] = [
  {
    key: 'feature',
    label: 'New feature',
    subject: 'New in Ribdigi ERP for {company_name}',
    body:
      'Hello {company_name},\n\nWe have added something new to Ribdigi ERP: [what it is].\n\n[How it helps and where to find it.]\n\nReply to this email if you have any questions.\n\nThe Ribdigi House team',
  },
  {
    key: 'maintenance',
    label: 'Planned maintenance',
    subject: 'Planned maintenance on [date]',
    body:
      'Hello {company_name},\n\nRibdigi ERP will be unavailable on [date] from [start time] to [end time] while we carry out planned maintenance.\n\nPlease finish any sales or stock counts before then. Nothing you have saved will be lost.\n\nThe Ribdigi House team',
  },
  {
    key: 'renewal',
    label: 'Plan renewal',
    subject: 'Your Ribdigi ERP plan is due for renewal',
    body:
      'Hello {company_name},\n\nYour Ribdigi ERP plan is due for renewal soon. Renew from Billing in the app to keep your staff signed in without a break.\n\nIf you need help choosing a plan, reply to this email.\n\nThe Ribdigi House team',
  },
];

const DRAFT_KEY = 'ribdigi:email-center:draft';
const PLACEHOLDER = '{company_name}';
const PLATFORM_LOGO_CID = 'cid:ribdigi-house-logo@ribdigi';

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

function labelsFor(values: string[] | undefined, options: Option[]) {
  return (values || []).map((v) => options.find((o) => o.value === v)?.label || v);
}

function audienceWords(filters: HistoryRow['filters']) {
  if (filters?.retry_of) return 'Retry of an earlier send';
  const picked = filters?.tenant_ids?.length || 0;
  const parts = [
    ...(picked ? [plural(picked, 'chosen company', 'chosen companies')] : []),
    ...labelsFor(filters?.statuses, STATUSES),
    ...labelsFor(filters?.industries, INDUSTRIES),
    ...labelsFor(filters?.packages, PACKAGES),
  ];
  return parts.length ? parts.join(', ') : 'All companies';
}

/** The email's own HTML with the inline logo pointed at the copy this site serves. */
function previewDoc(html: string) {
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  return html.split(PLATFORM_LOGO_CID).join(`${origin}/brand/ribdigi-house-email-logo.png`);
}

function companyMeta(row: Company) {
  return [
    labelsFor(row.status ? [row.status] : [], STATUSES)[0],
    labelsFor(row.industry ? [row.industry] : [], INDUSTRIES)[0],
    labelsFor(row.package_code ? [row.package_code] : [], PACKAGES)[0],
  ]
    .filter(Boolean)
    .join(' · ');
}

function readDraft(): { subject: string; body: string } | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return { subject: String(parsed?.subject || ''), body: String(parsed?.body || '') };
  } catch {
    return null;
  }
}

function writeDraft(subject: string, body: string) {
  try {
    if (subject.trim() || body.trim()) window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ subject, body }));
    else window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* private window: the draft just is not kept */
  }
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
          aria-label={`${legend}: any`}
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
              {on ? <DeskIcon name="check" size={13} /> : null}
              {opt.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function CompanyPicker({
  companies,
  value,
  onChange,
}: {
  companies: Company[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [query, setQuery] = useState('');
  const byId = useMemo(() => new Map(companies.map((c) => [c.id, c])), [companies]);
  const q = query.trim().toLowerCase();
  const matches = q
    ? companies.filter((c) => !value.includes(c.id) && c.company_name.toLowerCase().includes(q)).slice(0, 8)
    : [];
  return (
    <fieldset className="ec-chips">
      <legend>Companies</legend>
      {value.length > 0 && (
        <div className="ec-chip-row ec-picked">
          {value.map((id) => (
            <button
              key={id}
              type="button"
              className="ec-chip is-on"
              aria-label={`Remove ${byId.get(id)?.company_name || 'company'}`}
              onClick={() => onChange(value.filter((v) => v !== id))}
            >
              {byId.get(id)?.company_name || 'Company'}
              <span aria-hidden="true" className="ec-chip-x">
                &times;
              </span>
            </button>
          ))}
          <button type="button" className="ec-chip ec-chip-quiet" onClick={() => onChange([])}>
            Clear
          </button>
        </div>
      )}
      <div className="ec-search">
        <DeskIcon name="search" size={16} />
        <input
          aria-label="Find a company"
          value={query}
          placeholder={value.length ? 'Add another company' : 'All companies. Type a name to pick some'}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      {q && (
        <ul className="ec-pick-list" aria-label="Matching companies">
          {matches.length === 0 ? (
            <li className="ec-pick-none">No other company matches &ldquo;{query.trim()}&rdquo;.</li>
          ) : (
            matches.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  aria-label={`Pick ${c.company_name}`}
                  onClick={() => {
                    onChange([...value, c.id]);
                    setQuery('');
                  }}
                >
                  <span className="ec-pick-name">{c.company_name}</span>
                  <span className="ec-pick-meta">{companyMeta(c)}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </fieldset>
  );
}

function SendState({ row }: { row: HistoryRow }) {
  if (row.status === 'sending') return <Tag tone="info">Sending…</Tag>;
  if (row.status === 'stopped') return <Tag tone="bad">Stopped</Tag>;
  if (row.failed) return <Tag tone="warn">{`${row.sent} sent · ${row.failed} failed`}</Tag>;
  return <Tag tone="ok">{`${row.sent} sent`}</Tag>;
}

export default function EmailCenterPage() {
  const [view, setView] = useState<'compose' | 'design'>('compose');
  const [statuses, setStatuses] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [packages, setPackages] = useState<string[]>([]);
  const [tenantIds, setTenantIds] = useState<string[]>([]);
  const [includeCompanyEmail, setIncludeCompanyEmail] = useState(false);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [draftReady, setDraftReady] = useState(false);
  const [tab, setTab] = useState<'write' | 'preview'>('write');
  const [rendered, setRendered] = useState<Rendered | null>(null);
  const [rendering, setRendering] = useState(false);
  const [testTo, setTestTo] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [mail, setMail] = useState<MailStatus | null>(null);
  const [opened, setOpened] = useState<HistoryRow | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const subjectRef = useRef<HTMLInputElement>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const audienceRef = useRef<HTMLElement>(null);
  const lastField = useRef<Field>('body');

  const audience = useMemo(
    () => ({ statuses, industries, packages, tenant_ids: tenantIds, include_company_email: includeCompanyEmail }),
    [statuses, industries, packages, tenantIds, includeCompanyEmail],
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
    const draft = readDraft();
    if (draft) {
      setSubject(draft.subject);
      setBody(draft.body);
    }
    setDraftReady(true);
    api('/platform/email/status')
      .then((res) => setMail(res?.data || null))
      .catch((err) => setError(err.message || 'Could not open the email center'));
    api('/platform/email/companies')
      .then((res) => setCompanies(res?.data || []))
      .catch(() => setCompanies([]));
    loadHistory();
  }, [loadHistory]);

  // Keep the draft on this device so a refresh or a slip of the mouse loses nothing.
  useEffect(() => {
    if (!draftReady) return;
    const timer = window.setTimeout(() => writeDraft(subject, body), 400);
    return () => window.clearTimeout(timer);
  }, [subject, body, draftReady]);

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

  const subjectOk = subject.trim().length >= 2;
  const bodyOk = body.trim().length >= 2;
  const sampleName = preview?.sample?.[0]?.company_name || '';

  // The preview tab shows the real branded email and follows the typing.
  useEffect(() => {
    if (tab !== 'preview' || !subjectOk || !bodyOk) return;
    let live = true;
    setRendering(true);
    const timer = window.setTimeout(() => {
      api('/platform/email/render', {
        method: 'POST',
        body: JSON.stringify({ subject: subject.trim(), body: body.trim(), company_name: sampleName || null }),
      })
        .then((res) => live && setRendered(res?.data || null))
        .catch((err) => live && setError(err.message || 'Could not show the email'))
        .finally(() => live && setRendering(false));
    }, 350);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [tab, subject, body, subjectOk, bodyOk, sampleName]);

  // While a send is still going out, check back for its result.
  useEffect(() => {
    if (!history.some((row) => row.status === 'sending')) return;
    const timer = window.setInterval(loadHistory, 4000);
    return () => window.clearInterval(timer);
  }, [history, loadHistory]);

  // Escape closes whichever dialog is open, unless a send is in flight.
  useEffect(() => {
    if (!opened && !confirming) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || busy) return;
      setOpened(null);
      setConfirming(false);
      setRetrying(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [opened, confirming, busy]);

  const count = preview?.recipient_count || 0;
  const mode = mail?.mode || '';
  const mailOff = mode === 'disabled';
  const canSend = subjectOk && bodyOk && count > 0 && !preview?.too_many && !busy && !mailOff;
  const words = body.trim() ? body.trim().split(/\s+/).length : 0;
  const lastSent = history.find((row) => row.status === 'finished');

  function insertName() {
    const field = lastField.current;
    const el = field === 'subject' ? subjectRef.current : bodyRef.current;
    const current = field === 'subject' ? subject : body;
    const start = el?.selectionStart ?? current.length;
    const end = el?.selectionEnd ?? current.length;
    const next = current.slice(0, start) + PLACEHOLDER + current.slice(end);
    if (field === 'subject') setSubject(next.slice(0, 200));
    else setBody(next);
    setTab('write');
    window.requestAnimationFrame(() => {
      el?.focus();
      const at = start + PLACEHOLDER.length;
      el?.setSelectionRange(at, at);
    });
  }

  function useStarter(key: string) {
    const starter = STARTERS.find((s) => s.key === key);
    if (!starter) return;
    if ((subject.trim() || body.trim()) && !window.confirm('Replace what you have written with this starter?')) return;
    setSubject(starter.subject);
    setBody(starter.body);
    setTab('write');
    window.requestAnimationFrame(() => bodyRef.current?.focus());
  }

  function clearMessage() {
    if ((subject.trim() || body.trim()) && !window.confirm('Clear the subject and message?')) return;
    setSubject('');
    setBody('');
    setRendered(null);
    setTab('write');
  }

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
      setRendered(null);
      setTab('write');
      writeDraft('', '');
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'The email was not sent');
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  async function openSend(id: string) {
    setError('');
    setRetrying(false);
    try {
      const res = await api(`/platform/email/history/${id}`);
      setOpened(res?.data || null);
    } catch (err: any) {
      setError(err.message || 'Could not open that send');
    }
  }

  function useAgain(row: HistoryRow) {
    const f = row.filters || {};
    setSubject(row.subject || '');
    setBody(row.body || '');
    if (!f.retry_of) {
      setStatuses(f.statuses || []);
      setIndustries(f.industries || []);
      setPackages(f.packages || []);
      setTenantIds((f.tenant_ids || []).filter((id) => companies.some((c) => c.id === id)));
      setIncludeCompanyEmail(Boolean(f.include_company_email));
    }
    setOpened(null);
    setTab('write');
    setMessage('The message is back in the editor. Check who gets it, then send.');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function retryMissed(row: HistoryRow) {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await api(`/platform/email/history/${row.id}/retry`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      });
      setMessage(res?.message || 'Sending again.');
      setOpened(null);
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'The email was not sent again');
      setOpened(null);
    } finally {
      setBusy(false);
      setRetrying(false);
    }
  }

  const mailPill =
    mode === 'smtp' ? (
      <span className="ec-mode is-ok">
        <span className="ec-dot" aria-hidden="true" />
        Mail is live
      </span>
    ) : mode === 'console' ? (
      <span className="ec-mode is-warn">
        <span className="ec-dot" aria-hidden="true" />
        Test mode: log only
      </span>
    ) : mode === 'disabled' ? (
      <span className="ec-mode is-bad">
        <span className="ec-dot" aria-hidden="true" />
        Mail is off
      </span>
    ) : null;

  return (
    <div className="plat ec">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Email center"
        subtitle="Write once to the companies that use Ribdigi ERP. Each person gets a private copy with their company's name in it."
        subtitleClassName="plat-sub"
        actions={mailPill}
      />

      <div className="ec-views" role="tablist" aria-label="Email center">
        <button
          type="button"
          role="tab"
          aria-selected={view === 'compose'}
          className={view === 'compose' ? 'is-on' : undefined}
          onClick={() => setView('compose')}
        >
          <DeskIcon name="send" size={16} />
          Write email
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={view === 'design'}
          className={view === 'design' ? 'is-on' : undefined}
          onClick={() => setView('design')}
        >
          <DeskIcon name="tag" size={16} />
          Email design
        </button>
      </div>

      {view === 'design' ? (
        <EmailDesigner mode="platform" baseUrl="/platform/email/design" />
      ) : (
      <>

      {mailOff && (
        <p className="ec-banner ec-banner-bad" role="status">
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
          <button type="button" className="ec-banner-x" aria-label="Dismiss error" onClick={() => setError('')}>
            &times;
          </button>
        </p>
      )}
      {message && (
        <p className="ec-banner ec-banner-ok" role="status">
          <DeskIcon name="check" size={18} />
          <span>{message}</span>
          <button type="button" className="ec-banner-x" aria-label="Dismiss message" onClick={() => setMessage('')}>
            &times;
          </button>
        </p>
      )}

      <div className="ec-work">
        <section className="ec-compose" aria-label="Message">
          <div className="ec-compose-top">
            <div className="ec-tabs" role="tablist" aria-label="Message view">
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'write'}
                className={tab === 'write' ? 'is-on' : undefined}
                onClick={() => setTab('write')}
              >
                Write
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'preview'}
                className={tab === 'preview' ? 'is-on' : undefined}
                onClick={() => setTab('preview')}
              >
                Preview
              </button>
            </div>
            <span className="ec-saved" aria-live="polite">
              {subject.trim() || body.trim() ? 'Draft kept on this device' : 'New message'}
            </span>
          </div>

          <div className="ec-head-lines">
            <div className="ec-line">
              <span className="ec-line-k">From</span>
              <span className="ec-line-v">
                <strong>{mail?.from_name || 'Ribdigi House'}</strong>
                {mail?.from_email ? <span className="ec-line-sub"> &lt;{mail.from_email}&gt;</span> : null}
              </span>
            </div>
            <div className="ec-line">
              <span className="ec-line-k">To</span>
              <button
                type="button"
                className={`ec-to${preview?.too_many ? ' is-bad' : ''}`}
                aria-label="Change who gets it"
                onClick={() => audienceRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
              >
                <DeskIcon name="users" size={15} />
                {previewing && !preview
                  ? 'Counting…'
                  : `${plural(count, 'person', 'people')} at ${plural(preview?.company_count || 0, 'company', 'companies')}`}
                <span className="ec-to-sub">{audienceWords(audience)}</span>
              </button>
            </div>
            <div className="ec-line ec-line-subject">
              <label className="ec-line-k" htmlFor="ec-subject">
                Subject
              </label>
              <input
                id="ec-subject"
                ref={subjectRef}
                className="ec-subject"
                aria-label="Email subject"
                value={subject}
                maxLength={200}
                placeholder="What is this email about?"
                onFocus={() => {
                  lastField.current = 'subject';
                }}
                onChange={(event) => setSubject(event.target.value)}
              />
              <span className={`ec-count-sm${subject.length > 180 ? ' is-near' : ''}`}>{subject.length}/200</span>
            </div>
          </div>

          <div className="ec-toolbar">
            <button type="button" className="ec-tool" aria-label="Insert company name" onClick={insertName}>
              <DeskIcon name="plus" size={14} />
              Company name
            </button>
            <span className="ec-tool-sep" aria-hidden="true" />
            <span className="ec-tool-label">Start from</span>
            {STARTERS.map((s) => (
              <button
                key={s.key}
                type="button"
                className="ec-tool ec-tool-quiet"
                aria-label={`Start from ${s.label}`}
                onClick={() => useStarter(s.key)}
              >
                {s.label}
              </button>
            ))}
          </div>

          {tab === 'write' ? (
            <textarea
              ref={bodyRef}
              className="ec-body"
              aria-label="Email message"
              value={body}
              maxLength={20000}
              placeholder={'Hello {company_name},\n\nWrite your news here. Leave a blank line between paragraphs.'}
              onFocus={() => {
                lastField.current = 'body';
              }}
              onChange={(event) => setBody(event.target.value)}
            />
          ) : (
            <div className="ec-preview" aria-busy={rendering}>
              {!subjectOk || !bodyOk ? (
                <p className="ec-preview-empty">Write a subject and a message to see the email.</p>
              ) : rendered ? (
                <>
                  <p className="ec-preview-note">
                    The copy for <strong>{sampleName || 'Example Company'}</strong>. Each company sees its own name.
                  </p>
                  <div className="ec-preview-subject">{rendered.subject}</div>
                  <iframe className="ec-look" title="Email preview" sandbox="" srcDoc={previewDoc(rendered.html)} />
                </>
              ) : (
                <p className="ec-preview-empty">Getting the preview ready…</p>
              )}
            </div>
          )}

          <div className="ec-compose-meta">
            <span>
              Type <code>{PLACEHOLDER}</code> and each company sees its own name. The Ribdigi House logo and a line
              saying why they got the email are added for you.
            </span>
            <span className="ec-words">{plural(words, 'word', 'words')}</span>
          </div>

          <div className="ec-compose-foot">
            <div className="ec-test">
              <input
                aria-label="Test email address"
                type="email"
                value={testTo}
                placeholder={`Test to: your own email`}
                onChange={(event) => setTestTo(event.target.value)}
              />
              <button
                type="button"
                aria-label="Send test email"
                disabled={!subjectOk || !bodyOk || busy || mailOff}
                onClick={sendTest}
              >
                <DeskIcon name="mail" size={15} />
                Send test
              </button>
            </div>
            <div className="ec-foot-right">
              <button
                type="button"
                className="ec-quiet"
                aria-label="Clear message"
                disabled={busy || (!subject && !body)}
                onClick={clearMessage}
              >
                <DeskIcon name="trash" size={15} />
                Clear
              </button>
              <button
                type="button"
                className="list-btn-primary ec-send"
                aria-label="Send bulk email"
                disabled={!canSend}
                onClick={() => setConfirming(true)}
              >
                <DeskIcon name="send" size={17} />
                <span>{count ? `Send to ${plural(count, 'person', 'people')}` : 'Send'}</span>
              </button>
            </div>
          </div>
        </section>

        <aside className="ec-aside" ref={audienceRef} aria-label="Who gets it">
          <div className={`ec-reach${preview?.too_many ? ' is-bad' : ''}`} aria-live="polite">
            <span className="ec-reach-k">Who gets it</span>
            <strong>{previewing && !preview ? '…' : count}</strong>
            <span className="ec-reach-v">
              {count === 1 ? 'person' : 'people'} at {plural(preview?.company_count || 0, 'company', 'companies')}
            </span>
            {preview?.too_many && (
              <span className="ec-reach-warn">One send can reach at most {preview.max_recipients} people.</span>
            )}
          </div>

          <div className="ec-filters">
            <ChipGroup legend="Status" options={STATUSES} value={statuses} onChange={setStatuses} />
            <ChipGroup legend="Business type" options={INDUSTRIES} value={industries} onChange={setIndustries} />
            <ChipGroup legend="Plan" options={PACKAGES} value={packages} onChange={setPackages} />
            <CompanyPicker companies={companies} value={tenantIds} onChange={setTenantIds} />
            <label className="ec-switch">
              <input
                type="checkbox"
                aria-label="Also send to each company's own email"
                checked={includeCompanyEmail}
                onChange={(event) => setIncludeCompanyEmail(event.target.checked)}
              />
              <span className="ec-switch-track" aria-hidden="true" />
              <span className="ec-switch-text">Also send to each company&apos;s own email, not just its admins</span>
            </label>
          </div>

          {preview && count === 0 && <p className="ec-note">No company admins match these filters.</p>}
          {preview && preview.sample.length > 0 && (
            <details className="ec-sample">
              <summary>See who gets it</summary>
              <ul aria-label="Some of the people who get it">
                {preview.sample.map((row) => (
                  <li key={row.email}>
                    <span className="ec-avatar" aria-hidden="true">
                      {(row.company_name || '?').trim().charAt(0).toUpperCase()}
                    </span>
                    <span className="ec-sample-text">
                      <span className="ec-sample-name">{row.company_name}</span>
                      <span className="ec-sample-mail">{row.email}</span>
                    </span>
                  </li>
                ))}
                {count > preview.sample.length && (
                  <li className="ec-sample-more">and {count - preview.sample.length} more</li>
                )}
              </ul>
            </details>
          )}
        </aside>
      </div>

      <section className="ec-sent" aria-label="Sent emails">
        <div className="ec-sent-head">
          <h2>Sent emails</h2>
          {lastSent && <span className="ec-sent-sub">Last sent {timeAgo(lastSent.created_at)}</span>}
        </div>
        {!history.length ? (
          <div className="ec-empty">
            <span className="ec-empty-ico">
              <DeskIcon name="send" size={22} />
            </span>
            <p>Nothing sent yet. Your sends appear here with how many went out.</p>
          </div>
        ) : (
          <ul className="ec-history">
            {history.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className="ec-history-row"
                  aria-label={`Open sent email ${row.subject || ''}`}
                  onClick={() => openSend(row.id)}
                >
                  <span className={`ec-history-ico is-${row.status}${row.failed ? ' has-fail' : ''}`} aria-hidden="true">
                    <DeskIcon name={row.status === 'finished' && !row.failed ? 'check' : row.status === 'sending' ? 'clock' : 'alert'} size={16} />
                  </span>
                  <span className="ec-history-main">
                    <span className="ec-history-subject">{row.subject}</span>
                    <span className="ec-history-meta">
                      {audienceWords(row.filters)} · {plural(row.recipient_count, 'person', 'people')}
                      {row.sent_by ? ` · ${row.sent_by}` : ''}
                    </span>
                  </span>
                  <span className="ec-history-side">
                    <SendState row={row} />
                    <span className="ec-history-when">{timeAgo(row.created_at)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      </>
      )}

      {opened && (
        <div className="ec-modal-back" role="presentation" onClick={() => !busy && setOpened(null)}>
          <div
            className="ec-modal ec-modal-wide"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ec-open-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="ec-modal-head">
              <div>
                <h2 id="ec-open-title">{opened.subject}</h2>
                <p className="ec-modal-sub">
                  {audienceWords(opened.filters)} · {plural(opened.recipient_count, 'person', 'people')} at{' '}
                  {plural(opened.company_count, 'company', 'companies')} · {timeAgo(opened.created_at)}
                  {opened.sent_by ? ` · by ${opened.sent_by}` : ''}
                </p>
              </div>
              <SendState row={opened} />
            </div>
            {opened.status === 'stopped' && (
              <p className="ec-banner ec-banner-warn">
                <DeskIcon name="alert" size={18} />
                <span>
                  This send was cut off before it finished (for example by a server restart). Some people may not
                  have it. Use the message again to resend.
                </span>
              </p>
            )}
            <div className="ec-open-body" aria-label="Message that was sent">
              {opened.body}
              {!opened.body_complete && (
                <em className="ec-open-cut"> … only the opening lines of older sends were kept.</em>
              )}
            </div>
            {opened.failures && opened.failures.length > 0 && (
              <details className="ec-fail" open={opened.failures.length <= 5}>
                <summary>Who did not get it ({opened.failures.length})</summary>
                <ul>
                  {opened.failures.map((f) => (
                    <li key={f.email}>
                      <strong>{f.company_name || f.email}</strong>
                      <span>
                        {f.company_name ? `${f.email} · ` : ''}
                        {f.reason}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="ec-modal-actions">
              <button type="button" onClick={() => setOpened(null)} disabled={busy}>
                Close
              </button>
              <button
                type="button"
                aria-label="Use this message again"
                onClick={() => useAgain(opened)}
                disabled={busy || !opened.body_complete}
              >
                Use again
              </button>
              {opened.status === 'finished' && (opened.failed || 0) > 0 && opened.body_complete ? (
                <button
                  type="button"
                  className="list-btn-primary"
                  aria-label={retrying ? 'Confirm send again to the people it missed' : 'Send again to the people it missed'}
                  disabled={busy || mailOff}
                  onClick={() => (retrying ? retryMissed(opened) : setRetrying(true))}
                >
                  {retrying
                    ? busy
                      ? 'Sending…'
                      : `Yes, send to ${plural(opened.failed || 0, 'person', 'people')}`
                    : `Send again to the ${plural(opened.failed || 0, 'person', 'people')} it missed`}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {confirming && (
        <div className="ec-modal-back" role="presentation" onClick={() => !busy && setConfirming(false)}>
          <div
            className="ec-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ec-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <span className="ec-modal-ico" aria-hidden="true">
              <DeskIcon name="send" size={22} />
            </span>
            <h2 id="ec-confirm-title">Send this email now?</h2>
            <dl className="ec-confirm">
              <div>
                <dt>Subject</dt>
                <dd>{subject.trim()}</dd>
              </div>
              <div>
                <dt>To</dt>
                <dd>
                  {plural(count, 'person', 'people')} at {plural(preview?.company_count || 0, 'company', 'companies')}
                </dd>
              </div>
              <div>
                <dt>Who</dt>
                <dd>{audienceWords(audience)}</dd>
              </div>
            </dl>
            <p className="ec-modal-sub">Once it goes out it cannot be taken back.</p>
            <div className="ec-modal-actions">
              <button type="button" onClick={() => setConfirming(false)} disabled={busy}>
                Cancel
              </button>
              <button
                type="button"
                className="list-btn-primary"
                aria-label="Confirm send bulk email"
                onClick={sendNow}
                disabled={busy}
              >
                {busy ? 'Sending…' : `Yes, send to ${plural(count, 'person', 'people')}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
