'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { formatDateTime, formatNumber } from '../../lib/format';

export default function Page() {
  const [tenant, setTenant] = useState<any>(null);
  const [emailStatus, setEmailStatus] = useState<any>(null);
  const [smsStatus, setSmsStatus] = useState<any>(null);
  const [storageStatus, setStorageStatus] = useState<any>(null);
  const [profilePhone, setProfilePhone] = useState('');
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [printHeader, setPrintHeader] = useState('');
  const [printFooter, setPrintFooter] = useState('');
  const [invTemplate, setInvTemplate] = useState('a4');
  const [receiptPaper, setReceiptPaper] = useState('80mm');

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  async function loadLogoPreview(hasLogo: boolean) {
    if (!hasLogo) {
      setLogoPreview(null);
      return;
    }
    try {
      const token = localStorage.getItem('token');
      const tenantId = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/tenants/me/logo`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
        },
      });
      if (!res.ok) {
        setLogoPreview(null);
        return;
      }
      const blob = await res.blob();
      setLogoPreview(URL.createObjectURL(blob));
    } catch {
      setLogoPreview(null);
    }
  }

  async function refresh() {
    const [r, e, s, me, st, print] = await Promise.all([
      api('/tenants/me'),
      api('/settings/email'),
      api('/settings/sms'),
      api('/me'),
      api('/settings/storage').catch(() => ({ data: null })),
      api('/settings/print').catch(() => ({ data: null })),
    ]);
    setTenant(r.data);
    setEmailStatus(e.data);
    setSmsStatus(s.data);
    setStorageStatus(st.data);
    setProfilePhone(me.data?.phone || '');
    if (print.data) {
      setPrintHeader(print.data.header_text || '');
      setPrintFooter(print.data.footer_text || '');
      setInvTemplate(print.data.default_invoice_template || 'a4');
      setReceiptPaper(print.data.default_receipt_paper || '80mm');
    }
    await loadLogoPreview(!!r.data?.has_logo);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function save() {
    setError('');
    try {
      const r = await api('/tenants/me', {
        method: 'PATCH',
        body: JSON.stringify({
          company_name: tenant.company_name,
          industry: tenant.industry,
          currency: tenant.currency,
          phone: tenant.phone,
          email: tenant.email,
          website: tenant.website,
          address: tenant.address,
          legal_name: tenant.legal_name,
          registration_number: tenant.registration_number,
          contact_person: tenant.contact_person,
          billing_address: tenant.billing_address,
          shipping_address: tenant.shipping_address,
          timezone: tenant.timezone,
          fiscal_year_start: tenant.fiscal_year_start,
          tax_jurisdiction: tenant.tax_jurisdiction,
          tax_registration_number: tenant.tax_registration_number,
          tax_filing_period: tenant.tax_filing_period,
          date_format: tenant.date_format,
          decimal_separator: tenant.decimal_separator,
          thousand_separator: tenant.thousand_separator,
          time_format: tenant.time_format,
          inactivity_timeout_minutes: Number(tenant.inactivity_timeout_minutes) || 30,
        }),
      });
      setTenant(r.data);
      setMessage('Profile saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function activate() {
    setError('');
    try {
      const r = await api('/tenants/me/activate', { method: 'POST', body: '{}' });
      setTenant(r.data);
      setMessage(r.message || 'Activated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function suspend() {
    if (!window.confirm('Suspend this tenant? All sessions will be revoked.')) return;
    setError('');
    try {
      const r = await api('/tenants/me/suspend', {
        method: 'POST',
        body: JSON.stringify({ reason: 'Admin requested' }),
      });
      setTenant(r.data);
      setMessage(r.message || 'Suspended');
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!tenant) {
    return (
      <Shell>
        <h1>Company</h1>
        {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
        <p className="muted">Loading…</p>
      </Shell>
    );
  }

  return (
    <Shell>
      <h1>Company</h1>
      <p className="muted">
        Status: {tenant.status} · Slug: {tenant.slug}
        {tenant.days_remaining != null && tenant.status === 'trial'
          ? ` · Trial days left: ${tenant.days_remaining}`
          : ''}
        {tenant.days_remaining != null && tenant.status === 'grace'
          ? ` · Grace days left: ${tenant.days_remaining}`
          : ''}
      </p>
      {tenant.status === 'trial' && (
        <div className="card" style={{ marginBottom: 12, borderLeft: '4px solid #ca8a04' }}>
          <p>
            Trial ends {tenant.trial_ends_at ? String(tenant.trial_ends_at).slice(0, 10) : 'soon'}
            {tenant.days_remaining != null ? ` (${tenant.days_remaining} day(s) left)` : ''}.
          </p>
          <button onClick={activate}>Activate now</button>
        </div>
      )}
      {tenant.read_only || tenant.status === 'grace' ? (
        <div className="card" style={{ marginBottom: 12, borderLeft: '4px solid #b91c1c' }}>
          <p>
            <b>Read-only grace period.</b> Writes are blocked until you activate.
            {tenant.grace_ends_at
              ? ` Grace ends ${String(tenant.grace_ends_at).slice(0, 10)}.`
              : ''}
          </p>
          <button onClick={activate}>Activate to restore access</button>
        </div>
      ) : null}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 16 }}>
        <h3>Company logo</h3>
        {tenant.has_logo && logoPreview && (
          <img src={logoPreview} alt="Company logo" style={{ maxHeight: 80, maxWidth: 200, objectFit: 'contain' }} />
        )}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          disabled={!!tenant.read_only}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setError('');
            try {
              const token = localStorage.getItem('token');
              const tenantId = localStorage.getItem('tenant');
              const form = new FormData();
              form.append('file', file);
              const res = await fetch(`${apiBase}/tenants/me/logo`, {
                method: 'POST',
                headers: {
                  ...(token ? { Authorization: `Bearer ${token}` } : {}),
                  ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
                },
                body: form,
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) throw new Error(body.detail?.message || body.detail || body.message || 'Upload failed');
              setTenant(body.data);
              setMessage('Logo uploaded');
              await loadLogoPreview(true);
            } catch (err: any) {
              setError(typeof err.message === 'string' ? err.message : 'Upload failed');
            } finally {
              e.target.value = '';
            }
          }}
        />
        {tenant.has_logo && (
          <button
            disabled={!!tenant.read_only}
            onClick={async () => {
              setError('');
              try {
                const r = await api('/tenants/me/logo', { method: 'DELETE' });
                setTenant(r.data);
                setLogoPreview(null);
                setMessage('Logo removed');
              } catch (err: any) {
                setError(err.message);
              }
            }}
          >
            Remove logo
          </button>
        )}
      </div>

      <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
        <input
          value={tenant.company_name || ''}
          onChange={(e) => setTenant({ ...tenant, company_name: e.target.value })}
          placeholder="Company name (trading)"
        />
        <input
          value={tenant.legal_name || ''}
          onChange={(e) => setTenant({ ...tenant, legal_name: e.target.value })}
          placeholder="Legal name"
        />
        <input
          value={tenant.registration_number || ''}
          onChange={(e) => setTenant({ ...tenant, registration_number: e.target.value })}
          placeholder="Company registration number"
        />
        <input
          value={tenant.contact_person || ''}
          onChange={(e) => setTenant({ ...tenant, contact_person: e.target.value })}
          placeholder="Primary contact person"
        />
        <select
          value={tenant.industry || 'retail'}
          onChange={(e) => setTenant({ ...tenant, industry: e.target.value })}
        >
          {['retail', 'mart', 'pharmacy', 'restaurant', 'bakery', 'wholesale', 'manufacturing'].map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
        <input
          value={tenant.currency || ''}
          onChange={(e) => setTenant({ ...tenant, currency: e.target.value })}
          placeholder="Currency"
        />
        <input
          value={tenant.phone || ''}
          onChange={(e) => setTenant({ ...tenant, phone: e.target.value })}
          placeholder="Phone"
        />
        <input
          value={tenant.email || ''}
          onChange={(e) => setTenant({ ...tenant, email: e.target.value })}
          placeholder="Email"
        />
        <input
          value={tenant.website || ''}
          onChange={(e) => setTenant({ ...tenant, website: e.target.value })}
          placeholder="Website"
        />
        <textarea
          value={tenant.address || ''}
          onChange={(e) => setTenant({ ...tenant, address: e.target.value })}
          placeholder="Headquarters address"
        />
        <textarea
          value={tenant.billing_address || ''}
          onChange={(e) => setTenant({ ...tenant, billing_address: e.target.value })}
          placeholder="Billing address"
        />
        <textarea
          value={tenant.shipping_address || ''}
          onChange={(e) => setTenant({ ...tenant, shipping_address: e.target.value })}
          placeholder="Shipping address"
        />
        <input
          value={tenant.timezone || ''}
          onChange={(e) => setTenant({ ...tenant, timezone: e.target.value })}
          placeholder="Timezone"
        />
        <input
          value={tenant.fiscal_year_start || ''}
          onChange={(e) => setTenant({ ...tenant, fiscal_year_start: e.target.value })}
          placeholder="Fiscal year start MM-DD"
        />
        <input
          value={tenant.tax_jurisdiction || 'GH'}
          onChange={(e) => setTenant({ ...tenant, tax_jurisdiction: e.target.value.toUpperCase() })}
          placeholder="Tax jurisdiction (e.g. GH)"
        />
        <input
          value={tenant.tax_registration_number || ''}
          onChange={(e) => setTenant({ ...tenant, tax_registration_number: e.target.value })}
          placeholder="TIN / VAT registration number (tax ID)"
        />
        <select
          value={tenant.tax_filing_period || 'monthly'}
          onChange={(e) => setTenant({ ...tenant, tax_filing_period: e.target.value })}
        >
          <option value="monthly">Filing period: monthly</option>
          <option value="quarterly">Filing period: quarterly</option>
        </select>

        <h3 style={{ marginTop: 8, marginBottom: 0 }}>Regional formatting</h3>
        <p className="muted" style={{ margin: 0 }}>
          Date, number, and time display for this company (BR-20.2).
        </p>
        <label className="muted">Date format</label>
        <select
          value={tenant.date_format || 'DD/MM/YYYY'}
          onChange={(e) => setTenant({ ...tenant, date_format: e.target.value })}
        >
          <option value="DD/MM/YYYY">DD/MM/YYYY</option>
          <option value="MM/DD/YYYY">MM/DD/YYYY</option>
          <option value="YYYY-MM-DD">YYYY-MM-DD</option>
        </select>
        <label className="muted">Decimal separator</label>
        <select
          value={tenant.decimal_separator || '.'}
          onChange={(e) => setTenant({ ...tenant, decimal_separator: e.target.value })}
        >
          <option value=".">Dot (1,234.56)</option>
          <option value=",">Comma (1.234,56)</option>
        </select>
        <label className="muted">Thousand separator</label>
        <select
          value={
            tenant.thousand_separator === undefined || tenant.thousand_separator === null
              ? ','
              : tenant.thousand_separator === ''
                ? 'none'
                : tenant.thousand_separator
          }
          onChange={(e) =>
            setTenant({
              ...tenant,
              thousand_separator: e.target.value === 'none' ? '' : e.target.value,
            })
          }
        >
          <option value=",">Comma</option>
          <option value=".">Dot</option>
          <option value=" ">Space</option>
          <option value="none">None</option>
        </select>
        <label className="muted">Time format</label>
        <select
          value={tenant.time_format || '24h'}
          onChange={(e) => setTenant({ ...tenant, time_format: e.target.value })}
        >
          <option value="24h">24-hour</option>
          <option value="12h">12-hour</option>
        </select>
        <p className="muted" style={{ margin: 0 }}>
          Preview: {formatNumber(1234.56, tenant)} · {formatDateTime(new Date(), tenant)}
        </p>

        <h3 style={{ marginTop: 8, marginBottom: 0 }}>Session timeout</h3>
        <p className="muted" style={{ margin: 0 }}>
          Minutes of inactivity before auto-logout (BR-19.3). Default 30; allowed 5–480.
        </p>
        <label className="muted">Inactivity timeout (minutes)</label>
        <input
          type="number"
          min={5}
          max={480}
          value={tenant.inactivity_timeout_minutes ?? 30}
          onChange={(e) =>
            setTenant({
              ...tenant,
              inactivity_timeout_minutes: Number(e.target.value) || 30,
            })
          }
        />

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={save} disabled={!!tenant.read_only}>
            Save profile
          </button>
          {(tenant.status === 'trial' || tenant.status === 'grace') && (
            <button onClick={activate}>Activate</button>
          )}
          {tenant.status !== 'suspended' && (
            <button onClick={suspend} style={{ color: '#b91c1c' }} disabled={!!tenant.read_only}>
              Suspend
            </button>
          )}
        </div>
      </div>

      {storageStatus && (
        <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
          <h2>Media storage</h2>
          <p className="muted">
            Backend: {storageStatus.backend}
            {storageStatus.backend === 's3'
              ? ` · Bucket ${storageStatus.bucket || '—'} · ${storageStatus.endpoint || 'AWS'}`
              : ` · Dir ${storageStatus.media_dir || '—'}`}
          </p>
          <p className="muted">
            Set STORAGE_BACKEND=s3 with S3_* / MinIO env vars for object storage. Keys stay tenant-scoped.
          </p>
        </div>
      )}

      <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
        <h2>Print branding</h2>
        <p className="muted">
          Header/footer on invoices and receipts. Logo from the company logo above is embedded on PDFs.
        </p>
        <label className="muted">Header text</label>
        <input
          value={printHeader}
          onChange={(e) => setPrintHeader(e.target.value)}
          placeholder="Tagline under company name"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <label className="muted">Footer text</label>
        <input
          value={printFooter}
          onChange={(e) => setPrintFooter(e.target.value)}
          placeholder="Thank you line"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <label>
            Invoice template{' '}
            <select value={invTemplate} onChange={(e) => setInvTemplate(e.target.value)}>
              <option value="a4">A4</option>
              <option value="thermal">Thermal</option>
            </select>
          </label>
          <label>
            Receipt paper{' '}
            <select value={receiptPaper} onChange={(e) => setReceiptPaper(e.target.value)}>
              <option value="80mm">80mm</option>
              <option value="58mm">58mm</option>
            </select>
          </label>
        </div>
        <button
          type="button"
          onClick={async () => {
            setError('');
            try {
              const r = await api('/settings/print', {
                method: 'PATCH',
                body: JSON.stringify({
                  header_text: printHeader,
                  footer_text: printFooter,
                  default_invoice_template: invTemplate,
                  default_receipt_paper: receiptPaper,
                }),
              });
              setPrintHeader(r.data?.header_text || '');
              setPrintFooter(r.data?.footer_text || '');
              setInvTemplate(r.data?.default_invoice_template || 'a4');
              setReceiptPaper(r.data?.default_receipt_paper || '80mm');
              setMessage('Print branding saved');
            } catch (err: any) {
              setError(err.message);
            }
          }}
        >
          Save print branding
        </button>
      </div>

      {emailStatus && (
        <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
          <h2>Email / SMTP</h2>
          <p className="muted">
            Mode: {emailStatus.mode} · Configured: {String(emailStatus.configured)} · Enabled:{' '}
            {String(emailStatus.enabled)}
          </p>
          <p className="muted">
            From: {emailStatus.from_name} &lt;{emailStatus.from_email || '—'}&gt; · Host:{' '}
            {emailStatus.host || 'console fallback'}
          </p>
          <button
            onClick={async () => {
              setError('');
              try {
                const r = await api('/settings/email/test', { method: 'POST', body: '{}' });
                setMessage(r.message || `Test email via ${r.data?.mode}`);
              } catch (err: any) {
                setError(err.message);
              }
            }}
          >
            Send test email to me
          </button>
        </div>
      )}

      {smsStatus && (
        <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
          <h2>SMS / Twilio</h2>
          <p className="muted">
            Mode: {smsStatus.mode} · Configured: {String(smsStatus.configured)} · Enabled:{' '}
            {String(smsStatus.enabled)}
          </p>
          <p className="muted">From: {smsStatus.from_number || 'console fallback'}</p>
          <input
            value={profilePhone}
            onChange={(e) => setProfilePhone(e.target.value)}
            placeholder="Your mobile (E.164 e.g. +233...)"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/me', {
                    method: 'PATCH',
                    body: JSON.stringify({ phone: profilePhone }),
                  });
                  setMessage('Profile phone saved');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Save my phone
            </button>
            <button
              onClick={async () => {
                setError('');
                try {
                  const r = await api('/settings/sms/test', { method: 'POST', body: '{}' });
                  setMessage(r.message || `Test SMS via ${r.data?.mode}`);
                } catch (err: any) {
                  setError(err.message);
                }
              }}
            >
              Send test SMS to me
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}
