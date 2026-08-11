'use client';

import { useEffect, useState } from 'react';
import PlatformShell from '../../../components/PlatformShell';
import { api } from '../../../lib/api';

export default function PlatformSettingsPage() {
  const [companyName, setCompanyName] = useState('');
  const [idle, setIdle] = useState(30);
  const [supportEmail, setSupportEmail] = useState('');
  const [supportPhone, setSupportPhone] = useState('');
  const [timezone, setTimezone] = useState('Africa/Accra');
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setError('');
    try {
      const r = await api('/platform/settings');
      setCompanyName(r.data?.company_name || '');
      setIdle(Number(r.data?.inactivity_timeout_minutes) || 30);
      setSupportEmail(r.data?.support_email || '');
      setSupportPhone(r.data?.support_phone || '');
      setTimezone(r.data?.timezone || 'Africa/Accra');
    } catch (err: any) {
      setError(err.message || 'Failed to load settings');
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setMsg('');
    try {
      await api('/platform/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          company_name: companyName,
          inactivity_timeout_minutes: idle,
          support_email: supportEmail,
          support_phone: supportPhone,
          timezone,
        }),
      });
      setMsg('Settings saved');
      await load();
    } catch (err: any) {
      setError(err.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <PlatformShell>
      <h1>Platform settings</h1>
      <p className="muted">Ribdigi House console settings (platform tenant only).</p>
      <p className="muted" style={{ maxWidth: 640 }}>
        House settings cover Ribdigi House identity, idle logout, and support contacts — not the
        full tenant Company profile (addresses, tax, document branding). Customer tenants manage
        that under Tenant Admin → Company.
      </p>
      {error && <p>{error}</p>}
      {msg && <p style={{ color: '#047857' }}>{msg}</p>}
      <form onSubmit={save} className="card" style={{ marginTop: 16, maxWidth: 480 }}>
        <label className="muted">Display name</label>
        <input
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          style={{ width: '100%', padding: 10, margin: '6px 0 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <label className="muted">Idle logout (minutes)</label>
        <input
          type="number"
          min={5}
          max={480}
          value={idle}
          onChange={(e) => setIdle(Number(e.target.value))}
          required
          style={{ width: '100%', padding: 10, margin: '6px 0 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <label className="muted">Support email</label>
        <input
          value={supportEmail}
          onChange={(e) => setSupportEmail(e.target.value)}
          type="email"
          style={{ width: '100%', padding: 10, margin: '6px 0 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <label className="muted">Support phone</label>
        <input
          value={supportPhone}
          onChange={(e) => setSupportPhone(e.target.value)}
          style={{ width: '100%', padding: 10, margin: '6px 0 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <label className="muted">House timezone</label>
        <input
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          placeholder="Africa/Accra"
          required
          style={{ width: '100%', padding: 10, margin: '6px 0 12px', borderRadius: 8, border: '1px solid #cbd5e1' }}
        />
        <button
          type="submit"
          disabled={busy}
          style={{ padding: '10px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 0 }}
        >
          Save
        </button>
      </form>

      <div className="card" style={{ marginTop: 24, maxWidth: 640 }}>
        <h2 style={{ fontSize: 16, marginTop: 0 }}>Operator runbooks (packaging links)</h2>
        <p className="muted">
          Curated references for Ribdigi House operators. Packaging only — not live SLA or go-live
          attestation.
        </p>
        <ul>
          <li>
            <code>docs/SUPPORT_RUNBOOK_MVP.md</code> — support runbook
          </li>
          <li>
            <code>docs/INCIDENT_PACK_MVP.md</code> — incident pack
          </li>
          <li>
            <code>docs/DR_LOGICAL_BACKUP_RUNBOOK.md</code> — logical backup DR
          </li>
          <li>
            <code>ops/mvp/README.md</code> — MVP evidence / ops index
          </li>
        </ul>
      </div>
    </PlatformShell>
  );
}
