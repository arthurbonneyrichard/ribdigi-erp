'use client';

/** The company's own browser-tab icon (favicon) for its public website. */

import { useCallback, useEffect, useState } from 'react';
import { api, apiFetch } from '../lib/api';
import './online-alerts.css';

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function SiteIconSetting({ editable = true }: { editable?: boolean }) {
  const [has, setHas] = useState<boolean | null>(null);
  const [src, setSrc] = useState('');
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    api('/online-alerts')
      .then((res) => setHas(Boolean(res.data?.has_favicon)))
      .catch(() => setHas(null));
  }, []);

  useEffect(() => {
    if (!has) {
      setSrc('');
      return;
    }
    let live = true;
    let made = '';
    apiFetch('/online-alerts/favicon')
      .then(async (res) => {
        if (!res.ok) return;
        made = URL.createObjectURL(await res.blob());
        if (live) setSrc(made);
      })
      .catch(() => undefined);
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [has, tick]);

  const upload = useCallback(async (file?: File | null) => {
    if (!file) return;
    if (!/^image\/(png|jpe?g|webp)$/i.test(file.type)) {
      setMsg({ ok: false, text: 'Choose a PNG, JPG or WebP picture.' });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append('file', file);
      await api('/online-alerts/favicon', { method: 'POST', body: form });
      setHas(true);
      setTick((t) => t + 1);
      setMsg({ ok: true, text: 'Icon saved. Your website shows it on the browser tab.' });
    } catch (err) {
      setMsg({ ok: false, text: problem(err) });
    } finally {
      setBusy(false);
    }
  }, []);

  async function remove() {
    setBusy(true);
    setMsg(null);
    try {
      await api('/online-alerts/favicon', { method: 'DELETE' });
      setHas(false);
      setMsg({ ok: true, text: 'Icon removed.' });
    } catch (err) {
      setMsg({ ok: false, text: problem(err) });
    } finally {
      setBusy(false);
    }
  }

  if (has === null) return null;
  return (
    <section className="oa-panel" aria-label="Website icon">
      <header className="oa-head">
        <div>
          <h2>Website icon</h2>
          <p>The small picture on the browser tab and in bookmarks when guests open your website. Use your logo or a simple mark.</p>
        </div>
      </header>
      <div className="oa-icon-row">
        <label
          className={`oa-icon-drop${over ? ' over' : ''}${src ? ' has' : ''}${busy ? ' busy' : ''}`}
          onDragOver={(e) => {
            e.preventDefault();
            if (editable) setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            if (editable && !busy) void upload(e.dataTransfer.files?.[0]);
          }}
        >
          {src ? <img src={src} alt="Your website icon" /> : null}
          <span className="oa-icon-cue">
            <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M12 16V4" />
              <path d="M7 9l5-5 5 5" />
              <path d="M5 20h14" />
            </svg>
            <b>{busy ? 'Saving…' : over ? 'Drop to upload' : src ? 'Change' : 'Add icon'}</b>
            {!src && !busy ? <small>Drag here or click</small> : null}
          </span>
          <input type="file" accept="image/png,image/jpeg,image/webp" disabled={!editable || busy} aria-label="Website icon file" onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ''; }} />
        </label>
        <div className="oa-icon-side">
          <div className="oa-browser" aria-hidden>
            <div className="oa-browser-bar">
              <span className="dots"><i /><i /><i /></span>
              <div className="oa-tab-preview">
                {src ? <img src={src} alt="" /> : <i />}
                <span>Your website</span>
                <em>×</em>
              </div>
            </div>
            <div className="oa-browser-sizes">
              <span>On the tab</span>
              {src ? <img src={src} alt="" width={16} height={16} /> : <i style={{ width: 16, height: 16 }} />}
              <span>Bookmark</span>
              {src ? <img src={src} alt="" width={32} height={32} /> : <i style={{ width: 32, height: 32 }} />}
              <span>Phone</span>
              {src ? <img src={src} alt="" width={48} height={48} className="round" /> : <i style={{ width: 48, height: 48 }} />}
            </div>
          </div>
          <ul className="oa-icon-tips">
            <li>Square picture, at least 128 pixels wide</li>
            <li>PNG, JPG or WebP</li>
            <li>We shrink it for you</li>
          </ul>
          <p className="oa-hint">Browsers can take a day to show a new icon.</p>
          <div className="oa-actions">
            <label className="oa-primary oa-file">
              {busy ? 'Saving…' : has ? 'Change icon' : 'Choose a picture'}
              <input type="file" accept="image/png,image/jpeg,image/webp" disabled={!editable || busy} aria-label="Choose website icon" onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ''; }} />
            </label>
            {has ? (
              <button type="button" className="oa-secondary" disabled={!editable || busy} aria-label="Remove website icon" onClick={() => void remove()}>
                Remove
              </button>
            ) : null}
          </div>
        </div>
      </div>
      {msg ? <p className={msg.ok ? 'oa-ok' : 'oa-error'} role="status">{msg.text}</p> : null}
    </section>
  );
}
