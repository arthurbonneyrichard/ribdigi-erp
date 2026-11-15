'use client';

/**
 * Owner console: open and edit the public legal pages (privacy, terms, refunds, cookies).
 * Every save is kept as a version. "Publish" puts it on the public page; "Save draft" does not.
 * With nothing published the public page shows the built-in text from lib/legalDefaults.ts.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import PageHeader from '../../../../components/PageHeader';
import { Tabs, Tag } from '../../../../components/PlatformUi';
import LegalMarkdown from '../../../../components/LegalMarkdown';
import { api } from '../../../../lib/api';
import { formatWhen } from '../../../../lib/format';
import { LEGAL_DEFAULTS, LEGAL_SLUGS, type LegalSlug } from '../../../../lib/legalDefaults';
import './legal.css';

type Version = {
  id: string;
  version: number;
  title: string;
  body: string;
  effective_date?: string | null;
  status: 'draft' | 'published';
  note?: string | null;
  created_by_name?: string | null;
  created_at?: string | null;
  published_at?: string | null;
};

type DocState = { latest: Version | null; published: Version | null; versions: Version[] };

const TABS = LEGAL_SLUGS.map((slug) => ({ key: slug, label: LEGAL_DEFAULTS[slug].title }));

const blankForm = (slug: LegalSlug) => ({ title: LEGAL_DEFAULTS[slug].title, body: LEGAL_DEFAULTS[slug].body, effective_date: '', note: '' });

export default function PlatformLegalPage() {
  const [slug, setSlug] = useState<LegalSlug>('privacy');
  const [doc, setDoc] = useState<DocState | null>(null);
  const [form, setForm] = useState(blankForm('privacy'));
  const [loadedFrom, setLoadedFrom] = useState('');
  const [view, setView] = useState<'write' | 'preview'>('write');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const fillFrom = useCallback((v: Version | null, s: LegalSlug) => {
    if (v) {
      setForm({ title: v.title, body: v.body, effective_date: v.effective_date || '', note: '' });
      setLoadedFrom(`version ${v.version}${v.status === 'draft' ? ' (draft)' : ''}`);
    } else {
      setForm(blankForm(s));
      setLoadedFrom('the built-in text');
    }
  }, []);

  const load = useCallback(
    async (s: LegalSlug, keepForm = false) => {
      setError('');
      try {
        const r = await api(`/platform/legal/${s}`);
        const d: DocState = { latest: r?.data?.latest || null, published: r?.data?.published || null, versions: r?.data?.versions || [] };
        setDoc(d);
        if (!keepForm) fillFrom(d.latest, s);
      } catch (err: any) {
        setError(err?.message || 'Could not load this document');
      }
    },
    [fillFrom],
  );

  useEffect(() => {
    setMessage('');
    load(slug);
  }, [slug, load]);

  const source = useMemo(() => {
    const v = doc?.versions.find((x) => `version ${x.version}${x.status === 'draft' ? ' (draft)' : ''}` === loadedFrom);
    return v ? { title: v.title, body: v.body, effective_date: v.effective_date || '' } : { ...LEGAL_DEFAULTS[slug], effective_date: '' };
  }, [doc, loadedFrom, slug]);
  const changed = form.title !== source.title || form.body !== source.body || form.effective_date !== source.effective_date;

  async function save(publish: boolean) {
    if (form.title.trim().length < 2) return setError('Give the page a title.');
    if (form.body.trim().length < 20) return setError('The text is too short.');
    if (publish && !window.confirm(`Publish this ${LEGAL_DEFAULTS[slug].title} to the public page now?`)) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const r = await api(`/platform/legal/${slug}`, {
        method: 'POST',
        body: JSON.stringify({
          title: form.title.trim(),
          body: form.body,
          effective_date: form.effective_date || null,
          note: form.note.trim() || null,
          publish,
        }),
      });
      setMessage(r?.message || 'Saved');
      await load(slug);
    } catch (err: any) {
      setError(err?.message || 'Could not save');
    } finally {
      setBusy(false);
    }
  }

  async function publishVersion(v: Version) {
    if (!window.confirm(`Put version ${v.version} on the public page? It is saved as a new version; nothing is overwritten.`)) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const r = await api(`/platform/legal/${slug}/versions/${v.version}/publish`, { method: 'POST' });
      setMessage(r?.message || 'Published');
      await load(slug);
    } catch (err: any) {
      setError(err?.message || 'Could not publish');
    } finally {
      setBusy(false);
    }
  }

  function startFromBuiltIn() {
    if (changed && !window.confirm('Replace what is in the editor with the built-in text?')) return;
    fillFrom(null, slug);
  }

  const pub = doc?.published;

  return (
    <div className="plat legal-ed">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Legal documents"
        subtitle="Open and edit the Privacy, Terms, Refund and Cookie pages. Publish puts your text on the public page; every version is kept."
        subtitleClassName="plat-sub"
      />
      {error ? <p className="erp-banner err" role="alert">{error}</p> : null}
      {message ? <p className="erp-banner ok" role="status">{message}</p> : null}
      <Tabs
        tabs={TABS}
        active={slug}
        onChange={(k: string) => {
          if (changed && !window.confirm('You have changes that are not saved. Leave this document?')) return;
          setSlug(k as LegalSlug);
        }}
        label="Legal document"
      />

      <div className="plat-panel">
        <div className="plat-panel-head">
          <h2>{LEGAL_DEFAULTS[slug].title}</h2>
          <a href={`/legal/${slug}`} target="_blank" rel="noopener noreferrer">
            Open public page
          </a>
        </div>
        <p className="legal-ed-live">
          {pub ? (
            <>
              <Tag tone="ok">Live</Tag> The public page shows version {pub.version}, published {formatWhen(pub.published_at) || ''}
              {pub.created_by_name ? ` by ${pub.created_by_name}` : ''}.
            </>
          ) : (
            <>
              <Tag tone="none">Built-in</Tag> Nothing published yet; the public page shows the built-in text.
            </>
          )}
          {doc?.latest?.status === 'draft' ? <> A newer draft (version {doc.latest.version}) is waiting.</> : null}
        </p>
        <p className="legal-ed-hint">
          Editing {loadedFrom || 'the built-in text'}
          {changed ? ' · changed, not saved' : ''}. Have a Ghanaian lawyer check legal wording before you publish.
        </p>

        <div className="legal-ed-fields">
          <label>
            Title
            <input value={form.title} maxLength={120} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} />
          </label>
          <label>
            Effective date
            <input type="date" value={form.effective_date} onChange={(e) => setForm((f) => ({ ...f, effective_date: e.target.value }))} />
          </label>
        </div>

        <div className="legal-ed-views" role="tablist" aria-label="Editor view">
          <button type="button" role="tab" aria-selected={view === 'write'} className={view === 'write' ? 'is-on' : ''} onClick={() => setView('write')}>
            Write
          </button>
          <button type="button" role="tab" aria-selected={view === 'preview'} className={view === 'preview' ? 'is-on' : ''} onClick={() => setView('preview')}>
            Preview
          </button>
        </div>
        {view === 'write' ? (
          <>
            <textarea
              className="legal-ed-text"
              aria-label={`${LEGAL_DEFAULTS[slug].title} text`}
              value={form.body}
              maxLength={60000}
              spellCheck
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
            />
            <p className="legal-ed-help">
              Leave an empty line between paragraphs. <code>## Heading</code> starts a section, lines starting with <code>- </code> make a
              list, <code>**bold**</code>, <code>[link text](/legal/terms)</code> (site pages, https:// or mailto: only).
              {slug === 'cookies' ? (
                <>
                  {' '}
                  <code>{'{{cookie_settings}}'}</code> on its own line shows the Cookie settings button; <code>{'{{analytics_status}}'}</code>{' '}
                  says whether analytics is on.
                </>
              ) : null}{' '}
              {form.body.length.toLocaleString()} / 60,000 characters.
            </p>
          </>
        ) : (
          <div className="legal-ed-preview">
            <h1>{form.title}</h1>
            <LegalMarkdown text={form.body} />
          </div>
        )}

        <label className="legal-ed-note">
          What changed (kept in the history)
          <input value={form.note} maxLength={500} placeholder="For example: added our DPC registration number" onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
        </label>

        <div className="legal-ed-actions">
          <button type="button" className="btn-ok" disabled={busy} onClick={() => save(true)}>
            Publish
          </button>
          <button type="button" disabled={busy} onClick={() => save(false)}>
            Save draft
          </button>
          <button type="button" disabled={busy || !changed} onClick={() => fillFrom(doc?.latest || null, slug)}>
            Discard changes
          </button>
          <button type="button" disabled={busy} onClick={startFromBuiltIn}>
            Start from built-in text
          </button>
        </div>
      </div>

      <div className="plat-panel">
        <div className="plat-panel-head">
          <h2>History</h2>
        </div>
        {!doc?.versions.length ? (
          <p className="muted">No saved versions yet.</p>
        ) : (
          <div className="plat-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Status</th>
                  <th scope="col">Saved</th>
                  <th scope="col">By</th>
                  <th scope="col">Note</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {doc.versions.map((v) => (
                  <tr key={v.id}>
                    <td>{v.version}</td>
                    <td>
                      {pub && pub.id === v.id ? (
                        <Tag tone="ok">Live</Tag>
                      ) : (
                        <Tag tone={v.status === 'draft' ? 'warn' : 'none'}>{v.status === 'draft' ? 'Draft' : 'Earlier'}</Tag>
                      )}
                    </td>
                    <td>{formatWhen(v.created_at) || '—'}</td>
                    <td>{v.created_by_name || '—'}</td>
                    <td>{v.note || <span className="muted">—</span>}</td>
                    <td>
                      <button
                        type="button"
                        aria-label={`Open version ${v.version} in the editor`}
                        onClick={() => {
                          if (changed && !window.confirm('Replace what is in the editor with this version?')) return;
                          fillFrom(v, slug);
                          setView('write');
                        }}
                      >
                        Open
                      </button>{' '}
                      {pub && pub.id === v.id ? null : (
                        <button type="button" className="btn-ok" disabled={busy} aria-label={`Publish version ${v.version}`} onClick={() => publishVersion(v)}>
                          Publish
                        </button>
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
