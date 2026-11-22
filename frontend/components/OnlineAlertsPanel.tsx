'use client';

/**
 * Order and booking alerts, for the restaurant, the online shop and the hotel.
 * Tells the business by email and WhatsApp (and in the ERP) the moment a customer orders or books online.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import './online-alerts.css';

type Cfg = {
  emails: string[];
  whatsapp: string | null;
  whatsapp_from: string | null;
  whatsapp_template: string | null;
  orders: boolean;
  bookings: boolean;
  email_on: boolean;
  whatsapp_on: boolean;
  industry: 'restaurant' | 'retail' | 'hotel';
  company_email?: string | null;
  channels?: { email?: string; whatsapp?: string; whatsapp_ready?: boolean };
};

const WORDS = {
  restaurant: { orders: 'Online food orders', bookings: 'Table bookings', lead: 'a guest orders or books on your website' },
  retail: { orders: 'Online shop orders', bookings: '', lead: 'a customer places an order in your online shop' },
  hotel: { orders: '', bookings: 'Online stay requests', lead: 'a guest asks for a room on your booking page' },
} as const;

const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE = /^\+\d{8,15}$/;

function Status({ ok, text }: { ok: boolean | 'warn'; text: string }) {
  return <span className={`oa-status ${ok === true ? 'ok' : ok === 'warn' ? 'warn' : 'off'}`}>{text}</span>;
}

export default function OnlineAlertsPanel({ editable = true }: { editable?: boolean }) {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [emails, setEmails] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [sender, setSender] = useState('');
  const [template, setTemplate] = useState('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = useCallback((c: Cfg) => {
    setCfg(c);
    setEmails((c.emails || []).join(', '));
    setWhatsapp(c.whatsapp || '');
    setSender(c.whatsapp_from || '');
    setTemplate(c.whatsapp_template || '');
  }, []);

  useEffect(() => {
    api('/online-alerts')
      .then((res) => apply(res.data))
      .catch(() => setCfg(null));
  }, [apply]);

  const list = useMemo(() => emails.split(/[,\s;]+/).map((e) => e.trim()).filter(Boolean), [emails]);
  const badEmail = list.find((e) => !EMAIL.test(e));
  const badPhone = whatsapp.trim() && !PHONE.test(whatsapp.trim().replace(/[\s-]/g, ''));
  const badSender = sender.trim() && !PHONE.test(sender.trim().replace(/[\s-]/g, ''));
  const dirty =
    !!cfg &&
    (list.join(',') !== (cfg.emails || []).join(',') ||
      whatsapp.trim() !== (cfg.whatsapp || '') ||
      sender.trim() !== (cfg.whatsapp_from || '') ||
      template.trim() !== (cfg.whatsapp_template || ''));

  async function save(patch: Record<string, unknown>, done = 'Saved.') {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api('/online-alerts', { method: 'PUT', body: JSON.stringify(patch) });
      apply(res.data);
      setMsg({ ok: true, text: done });
    } catch (err) {
      setMsg({ ok: false, text: problem(err) });
    } finally {
      setBusy(false);
    }
  }

  async function saveContacts() {
    if (badEmail) return setMsg({ ok: false, text: `“${badEmail}” is not an email address.` });
    if (badPhone) return setMsg({ ok: false, text: 'Write the WhatsApp number with the country code, like +233241234567.' });
    if (badSender) return setMsg({ ok: false, text: 'Write the sender number with the country code, like +14155238886.' });
    await save(
      {
        emails: list,
        whatsapp: whatsapp.trim().replace(/[\s-]/g, '') || null,
        whatsapp_from: sender.trim().replace(/[\s-]/g, '') || null,
        whatsapp_template: template.trim() || null,
      },
      'Contacts saved.',
    );
  }

  async function sendTest() {
    setBusy(true);
    setMsg(null);
    try {
      const res = await api('/online-alerts/test', { method: 'POST' });
      const r = res.data || {};
      const parts: string[] = [];
      if (r.email) parts.push(r.email.sent ? `Email sent to ${(r.email.to || []).join(', ')}.` : `Email did not send: ${r.email.error || 'check the email settings'}.`);
      if (r.whatsapp) parts.push(r.whatsapp.sent ? 'WhatsApp sent.' : `WhatsApp did not send: ${String(r.whatsapp.error || 'check the number and sender').slice(0, 160)}`);
      if (!parts.length) parts.push('Nothing to send yet. Add an email address or a WhatsApp number, save, then try again.');
      setMsg({ ok: !parts.some((p) => p.includes('did not') || p.startsWith('Nothing')), text: parts.join(' ') });
    } catch (err) {
      setMsg({ ok: false, text: problem(err) });
    } finally {
      setBusy(false);
    }
  }

  if (!cfg) return null;
  const words = WORDS[cfg.industry] || WORDS.retail;
  const ch = cfg.channels || {};
  const off = !editable || busy;
  const toggles: [keyof Cfg, string][] = [];
  if (words.orders) toggles.push(['orders', words.orders]);
  if (words.bookings) toggles.push(['bookings', words.bookings]);
  toggles.push(['email_on', 'Use email'], ['whatsapp_on', 'Use WhatsApp']);

  return (
    <section className="oa-panel" aria-label="Order and booking alerts">
      <header className="oa-head">
        <div>
          <h2>{cfg.industry === 'hotel' ? 'Stay request alerts' : 'Order and booking alerts'}</h2>
          <p>Get told straight away when {words.lead}. The alert also shows in the ERP bell.</p>
        </div>
      </header>

      <div className="oa-grid">
        <div className="oa-box">
          <div className="oa-box-head">
            <h3>Email</h3>
            {ch.email === 'disabled' ? <Status ok={false} text="Switched off" /> : ch.email === 'console' ? <Status ok="warn" text="Test mode" /> : <Status ok text="Ready" />}
          </div>
          <label className="oa-field">
            <span>Send to (up to 5, separated by commas)</span>
            <input
              value={emails}
              disabled={!editable}
              inputMode="email"
              placeholder={cfg.company_email ? `Now using ${cfg.company_email}` : 'owner@yourbusiness.com'}
              aria-label="Alert email addresses"
              aria-invalid={Boolean(badEmail)}
              onChange={(e) => setEmails(e.target.value)}
            />
          </label>
          {badEmail ? <p className="oa-warn">“{badEmail}” is not an email address.</p> : <p className="oa-hint">Sent from your company email settings.</p>}
        </div>

        <div className="oa-box">
          <div className="oa-box-head">
            <h3>WhatsApp</h3>
            {ch.whatsapp_ready ? <Status ok text="Twilio connected" /> : <Status ok="warn" text={ch.whatsapp === 'console' ? 'Test mode' : 'Twilio not set up'} />}
          </div>
          <label className="oa-field">
            <span>Your WhatsApp number (with country code)</span>
            <input
              value={whatsapp}
              disabled={!editable}
              inputMode="tel"
              placeholder="+233241234567"
              aria-label="Alert WhatsApp number"
              aria-invalid={Boolean(badPhone)}
              onChange={(e) => setWhatsapp(e.target.value)}
            />
          </label>
          {badPhone ? <p className="oa-warn">Start with + and the country code, like +233241234567.</p> : null}
          <details className="oa-adv">
            <summary>WhatsApp sender and template</summary>
            <label className="oa-field">
              <span>Sender number from Twilio</span>
              <input value={sender} disabled={!editable} inputMode="tel" placeholder="+14155238886" aria-label="Twilio WhatsApp sender number" aria-invalid={Boolean(badSender)} onChange={(e) => setSender(e.target.value)} />
            </label>
            <label className="oa-field">
              <span>Approved message template id (optional)</span>
              <input value={template} disabled={!editable} placeholder="HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" aria-label="Twilio WhatsApp template id" onChange={(e) => setTemplate(e.target.value)} />
            </label>
            <p className="oa-hint">
              WhatsApp goes through your Twilio account (set up under Company, SMS). WhatsApp only lets a business start a chat with an approved template. Without one, messages work in Twilio&apos;s test sandbox and when you have messaged the number in the last 24 hours.
            </p>
          </details>
        </div>
      </div>

      <div className="oa-switches" role="group" aria-label="Which alerts to send">
        {toggles.map(([key, label]) => (
          <label key={String(key)} className="oa-switch">
            <input type="checkbox" checked={Boolean(cfg[key])} disabled={off} aria-label={label} onChange={(e) => void save({ [key]: e.target.checked }, e.target.checked ? `${label} on.` : `${label} off.`)} />
            <span className="track" aria-hidden />
            <span>{label}</span>
          </label>
        ))}
      </div>

      <div className="oa-actions">
        <button type="button" className="oa-primary" disabled={off || !dirty} aria-label="Save alert contacts" onClick={() => void saveContacts()}>
          {dirty ? 'Save contacts' : 'Saved'}
        </button>
        <button type="button" className="oa-secondary" disabled={off || dirty} aria-label="Send a test alert" title={dirty ? 'Save your changes first' : undefined} onClick={() => void sendTest()}>
          Send me a test
        </button>
        {dirty ? <span className="oa-hint">You have changes to save.</span> : null}
      </div>
      {msg ? <p className={msg.ok ? 'oa-ok' : 'oa-error'} role="status">{msg.text}</p> : null}
    </section>
  );
}
