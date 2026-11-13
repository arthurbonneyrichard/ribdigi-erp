'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import './email-designer.css';

type Choice = { key: string; label: string };
type ThemeChoice = Choice & { header: string; line: string; button: string };
type Options = {
  themes: ThemeChoice[];
  header_styles: Choice[];
  logo_aligns: Choice[];
  button_shapes: Choice[];
  fonts: Choice[];
};
type Style = {
  theme: string;
  header_style?: string;
  logo_align: string;
  button_shape: string;
  font: string;
  show_details?: boolean;
  signature: string;
  footer_text: string;
  tagline?: string;
};

type Props = {
  /** company: a company's own emails. platform: Ribdigi House's emails (owner console). */
  mode: 'company' | 'platform';
  baseUrl: string;
  readOnly?: boolean;
};

function Segmented({
  label,
  choices,
  value,
  onChange,
}: {
  label: string;
  choices: Choice[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="ed-group" role="radiogroup" aria-label={label}>
      <span className="ed-group-label">{label}</span>
      <div className="ed-seg">
        {choices.map((c) => (
          <button
            key={c.key}
            type="button"
            role="radio"
            aria-checked={value === c.key}
            className={value === c.key ? 'is-on' : undefined}
            onClick={() => onChange(c.key)}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function EmailDesigner({ mode, baseUrl, readOnly = false }: Props) {
  const [options, setOptions] = useState<Options | null>(null);
  const [saved, setSaved] = useState<Style | null>(null);
  const [defaults, setDefaults] = useState<Style | null>(null);
  const [style, setStyle] = useState<Style | null>(null);
  const [sample, setSample] = useState<'document' | 'message'>(mode === 'platform' ? 'message' : 'document');
  const [device, setDevice] = useState<'desktop' | 'phone'>('desktop');
  const [html, setHtml] = useState('');
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<{ ok?: string; err?: string }>({});

  useEffect(() => {
    api(baseUrl)
      .then((res) => {
        const data = res?.data || {};
        setOptions(data.options || null);
        setSaved(data.style || null);
        setStyle(data.style || null);
        setDefaults(data.defaults || null);
      })
      .catch((err) => setFlash({ err: err.message || 'Could not load the email design' }));
  }, [baseUrl]);

  const dirty = useMemo(() => JSON.stringify(style) !== JSON.stringify(saved), [style, saved]);

  // The preview follows every change, a moment after the last one.
  useEffect(() => {
    if (!style) return;
    let live = true;
    setLoadingPreview(true);
    const timer = window.setTimeout(() => {
      api(`${baseUrl}/preview`, { method: 'POST', body: JSON.stringify({ ...style, sample }) })
        .then((res) => live && setHtml(res?.data?.html || ''))
        .catch((err) => live && setFlash({ err: err.message || 'Could not show the preview' }))
        .finally(() => live && setLoadingPreview(false));
    }, 300);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [style, sample, baseUrl]);

  const set = useCallback(<K extends keyof Style>(key: K, value: Style[K]) => {
    setFlash({});
    setStyle((prev) => (prev ? { ...prev, [key]: value } : prev));
  }, []);

  async function save() {
    if (!style) return;
    setBusy(true);
    setFlash({});
    try {
      const res = await api(baseUrl, { method: 'PATCH', body: JSON.stringify(style) });
      const next = res?.data?.style || style;
      setSaved(next);
      setStyle(next);
      setFlash({ ok: res?.message || 'Email design saved' });
    } catch (err: any) {
      setFlash({ err: err.message || 'The email design was not saved' });
    } finally {
      setBusy(false);
    }
  }

  if (!style || !options) {
    return (
      <div className="ed ed-loading" aria-busy="true">
        {flash.err ? <p className="ed-flash is-err">{flash.err}</p> : <p>Loading the email design…</p>}
      </div>
    );
  }

  const isCompany = mode === 'company';

  return (
    <div className={`ed ed-${mode}`}>
      <div className="ed-controls">
        <div className="ed-layout-note">
          <span className="ed-layout-badge">{isCompany ? 'Company letterhead' : 'Ribdigi House layout'}</span>
          <p>
            {isCompany
              ? 'Invoices, quotations, orders, receipts and notices your company sends use this design. Ribdigi House emails keep their own look.'
              : 'Sign-up, password reset and email center messages from Ribdigi House use this design. Companies design their own emails separately.'}
          </p>
        </div>

        <div className="ed-group" role="radiogroup" aria-label="Colour theme">
          <span className="ed-group-label">Colour theme</span>
          <div className="ed-swatches">
            {options.themes.map((t) => (
              <button
                key={t.key}
                type="button"
                role="radio"
                aria-checked={style.theme === t.key}
                aria-label={`Colour theme ${t.label}`}
                className={`ed-swatch${style.theme === t.key ? ' is-on' : ''}`}
                onClick={() => set('theme', t.key)}
              >
                <span className="ed-swatch-chip" aria-hidden="true">
                  <span style={{ background: t.header }} />
                  <span style={{ background: t.line }} />
                  <span style={{ background: t.button }} />
                </span>
                <span className="ed-swatch-name">{t.label}</span>
              </button>
            ))}
          </div>
        </div>

        {isCompany && (
          <Segmented
            label="Header"
            choices={options.header_styles}
            value={style.header_style || 'solid'}
            onChange={(k) => set('header_style', k)}
          />
        )}
        <Segmented label="Logo position" choices={options.logo_aligns} value={style.logo_align} onChange={(k) => set('logo_align', k)} />
        <Segmented label="Buttons" choices={options.button_shapes} value={style.button_shape} onChange={(k) => set('button_shape', k)} />
        <Segmented label="Lettering" choices={options.fonts} value={style.font} onChange={(k) => set('font', k)} />

        {isCompany && (
          <label className="ed-switch">
            <input
              type="checkbox"
              aria-label="Show company details in the header"
              checked={style.show_details !== false}
              onChange={(e) => set('show_details', e.target.checked)}
            />
            <span className="ed-switch-track" aria-hidden="true" />
            <span>Show address, phone, email and tax numbers in the header</span>
          </label>
        )}

        {!isCompany && (
          <div className="ed-field">
            <label htmlFor="ed-tagline">Tagline</label>
            <input
              id="ed-tagline"
              aria-label="Email tagline"
              value={style.tagline || ''}
              maxLength={80}
              placeholder="Empowering your digital growth"
              onChange={(e) => set('tagline', e.target.value)}
            />
          </div>
        )}
        <div className="ed-field">
          <label htmlFor={`ed-signature-${mode}`}>Sign-off</label>
          <input
            id={`ed-signature-${mode}`}
            aria-label="Email sign-off"
            value={style.signature}
            maxLength={200}
            placeholder={isCompany ? 'The Sunrise Mart team' : 'The Ribdigi House team'}
            onChange={(e) => set('signature', e.target.value)}
          />
          <span className="ed-hint">Added under every message. Leave blank for none.</span>
        </div>
        <div className="ed-field">
          <label htmlFor={`ed-footer-${mode}`}>Footer line</label>
          <input
            id={`ed-footer-${mode}`}
            aria-label="Email footer line"
            value={style.footer_text}
            maxLength={300}
            placeholder={isCompany ? 'Uses your print footer when blank' : 'For example: Questions? Reply to this email.'}
            onChange={(e) => set('footer_text', e.target.value)}
          />
        </div>

        <div className="ed-actions">
          <button
            type="button"
            className="ed-btn-quiet"
            disabled={busy || readOnly || !defaults}
            onClick={() => defaults && setStyle({ ...defaults })}
          >
            Reset to default
          </button>
          <button
            type="button"
            className="ed-btn-quiet"
            disabled={busy || !dirty}
            onClick={() => setStyle(saved)}
          >
            Undo changes
          </button>
          <button
            type="button"
            className="ed-btn-primary"
            aria-label="Save email design"
            disabled={busy || readOnly || !dirty}
            onClick={save}
          >
            {busy ? 'Saving…' : dirty ? 'Save design' : 'Saved'}
          </button>
        </div>
        {flash.ok && <p className="ed-flash is-ok" role="status">{flash.ok}</p>}
        {flash.err && <p className="ed-flash is-err" role="alert">{flash.err}</p>}
      </div>

      <div className="ed-stage">
        <div className="ed-stage-bar">
          <div className="ed-seg ed-seg-sm" role="tablist" aria-label="Preview content">
            <button type="button" role="tab" aria-selected={sample === 'document'} className={sample === 'document' ? 'is-on' : undefined} onClick={() => setSample('document')}>
              Invoice
            </button>
            <button type="button" role="tab" aria-selected={sample === 'message'} className={sample === 'message' ? 'is-on' : undefined} onClick={() => setSample('message')}>
              Message
            </button>
          </div>
          <div className="ed-seg ed-seg-sm" role="tablist" aria-label="Preview size">
            <button type="button" role="tab" aria-selected={device === 'desktop'} className={device === 'desktop' ? 'is-on' : undefined} onClick={() => setDevice('desktop')}>
              Desktop
            </button>
            <button type="button" role="tab" aria-selected={device === 'phone'} className={device === 'phone' ? 'is-on' : undefined} onClick={() => setDevice('phone')}>
              Phone
            </button>
          </div>
        </div>
        <div className={`ed-frame-wrap is-${device}`} aria-busy={loadingPreview}>
          {html ? (
            <iframe className="ed-frame" title="Email design preview" sandbox="" srcDoc={html} />
          ) : (
            <p className="ed-frame-empty">Getting the preview ready…</p>
          )}
        </div>
        <p className="ed-stage-note">
          {dirty ? 'Preview shows your unsaved changes.' : 'This is how your emails look now.'}
        </p>
      </div>
    </div>
  );
}
