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
  const [emailHost, setEmailHost] = useState('');
  const [emailPort, setEmailPort] = useState('587');
  const [emailUser, setEmailUser] = useState('');
  const [emailPassword, setEmailPassword] = useState('');
  const [emailFromEmail, setEmailFromEmail] = useState('');
  const [emailFromName, setEmailFromName] = useState('');
  const [emailUseTls, setEmailUseTls] = useState(true);
  const [emailUseSsl, setEmailUseSsl] = useState(false);
  const [smsAccountSid, setSmsAccountSid] = useState('');
  const [smsAuthToken, setSmsAuthToken] = useState('');
  const [smsFromNumber, setSmsFromNumber] = useState('');
  const [suspendReason, setSuspendReason] = useState('');

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
    if (e.data) {
      setEmailHost(e.data.host || '');
      setEmailPort(String(e.data.port ?? 587));
      setEmailUser(e.data.username || '');
      setEmailPassword('');
      setEmailFromEmail(e.data.from_email || '');
      setEmailFromName(e.data.from_name || '');
      setEmailUseTls(e.data.use_tls !== false);
      setEmailUseSsl(!!e.data.use_ssl);
    }
    setSmsStatus(s.data);
    if (s.data) {
      setSmsAccountSid(s.data.account_sid || '');
      setSmsAuthToken('');
      setSmsFromNumber(s.data.from_number || '');
    }
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
          // Omit blank phone so Save does not 422 (E164PhoneValue); leave prior value.
          ...(String(tenant.phone || '').trim()
            ? { phone: String(tenant.phone).trim() }
            : {}),
          email: tenant.email,
          // Omit blank website so Save does not 422 (WebhookUrlValue); leave prior value.
          ...(String(tenant.website || '').trim()
            ? { website: String(tenant.website).trim() }
            : {}),
          // Omit blank HQ address so Save does not 422 (AddressValue); leave prior.
          ...(String(tenant.address || '').trim()
            ? { address: String(tenant.address).trim() }
            : {}),
          // Omit blank legal name so Save does not 422 (LegalNameValue); leave prior.
          ...(String(tenant.legal_name || '').trim()
            ? { legal_name: String(tenant.legal_name).trim() }
            : {}),
          // Omit blank registration so Save does not 422 (RegistrationNumberValue); leave prior.
          ...(String(tenant.registration_number || '').trim()
            ? { registration_number: String(tenant.registration_number).trim() }
            : {}),
          // Omit blank contact so Save does not 422 (ContactPersonValue); leave prior.
          ...(String(tenant.contact_person || '').trim()
            ? { contact_person: String(tenant.contact_person).trim() }
            : {}),
          // Omit blank billing/shipping so Save does not 422 (AddressValue); leave prior.
          ...(String(tenant.billing_address || '').trim()
            ? { billing_address: String(tenant.billing_address).trim() }
            : {}),
          ...(String(tenant.shipping_address || '').trim()
            ? { shipping_address: String(tenant.shipping_address).trim() }
            : {}),
          timezone: tenant.timezone,
          fiscal_year_start: tenant.fiscal_year_start,
          tax_jurisdiction: tenant.tax_jurisdiction,
          // Omit blank TIN so Save does not 422 (TaxRegistrationNumberValue); leave prior.
          ...(String(tenant.tax_registration_number || '').trim()
            ? { tax_registration_number: String(tenant.tax_registration_number).trim() }
            : {}),
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
    const reason = suspendReason.trim();
    if (!reason) {
      setError('Enter a suspend reason before suspending this company');
      return;
    }
    if (!window.confirm('Suspend this tenant? All sessions will be revoked.')) return;
    setError('');
    setMessage('');
    try {
      const r = await api('/tenants/me/suspend', {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setSuspendReason('');
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
          <button className="btn-ok" onClick={activate}>Activate now</button>
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
          <button className="btn-ok" onClick={activate}>Activate to restore access</button>
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
          aria-label="Company trading name"
        />
        <input
          value={tenant.legal_name || ''}
          onChange={(e) => setTenant({ ...tenant, legal_name: e.target.value })}
          placeholder="Legal name"
          aria-label="Company legal name"
        />
        <input
          value={tenant.registration_number || ''}
          onChange={(e) => setTenant({ ...tenant, registration_number: e.target.value })}
          placeholder="Company registration number"
          aria-label="Company registration number"
        />
        <input
          value={tenant.contact_person || ''}
          onChange={(e) => setTenant({ ...tenant, contact_person: e.target.value })}
          placeholder="Primary contact person"
          aria-label="Company contact person"
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
        <select
          value={tenant.currency || 'GHS'}
          onChange={(e) => setTenant({ ...tenant, currency: e.target.value })}
          aria-label="Company currency"
        >
          {Array.from(
            new Set(
              [tenant.currency || 'GHS', 'GHS', 'USD', 'EUR', 'GBP', 'NGN', 'XOF', 'CAD'].filter(Boolean),
            ),
          ).map((c) => (
            <option key={c} value={c}>
              Currency: {c}
            </option>
          ))}
        </select>
        <input
          value={tenant.phone || ''}
          onChange={(e) => setTenant({ ...tenant, phone: e.target.value })}
          placeholder="Phone (E.164 e.g. +233...)"
          aria-label="Company phone"
        />
        <input
          value={tenant.email || ''}
          onChange={(e) => setTenant({ ...tenant, email: e.target.value })}
          placeholder="Email"
        />
        <input
          value={tenant.website || ''}
          onChange={(e) => setTenant({ ...tenant, website: e.target.value })}
          placeholder="Website (https://…)"
          aria-label="Company website"
        />
        <textarea
          value={tenant.address || ''}
          onChange={(e) => setTenant({ ...tenant, address: e.target.value })}
          placeholder="Headquarters address"
          aria-label="Company headquarters address"
        />
        <textarea
          value={tenant.billing_address || ''}
          onChange={(e) => setTenant({ ...tenant, billing_address: e.target.value })}
          placeholder="Billing address"
          aria-label="Company billing address"
        />
        <textarea
          value={tenant.shipping_address || ''}
          onChange={(e) => setTenant({ ...tenant, shipping_address: e.target.value })}
          placeholder="Shipping address"
          aria-label="Company shipping address"
        />
        <select
          value={tenant.timezone || 'Africa/Accra'}
          onChange={(e) => setTenant({ ...tenant, timezone: e.target.value })}
          aria-label="Company timezone"
        >
          {Array.from(
            new Set(
              [
                tenant.timezone || 'Africa/Accra',
                'Africa/Accra',
                'Africa/Lagos',
                'Africa/Abidjan',
                'Africa/Nairobi',
                'Africa/Johannesburg',
                'UTC',
                'Europe/London',
                'America/New_York',
                'Asia/Dubai',
              ].filter(Boolean),
            ),
          ).map((z) => (
            <option key={z} value={z}>
              Timezone: {z}
            </option>
          ))}
        </select>
        <input
          value={tenant.fiscal_year_start || '01-01'}
          onChange={(e) => setTenant({ ...tenant, fiscal_year_start: e.target.value })}
          placeholder="Fiscal year start MM-DD"
          pattern="(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
          maxLength={5}
          aria-label="Fiscal year start"
          title="MM-DD (e.g. 01-01)"
        />
        <select
          value={tenant.tax_jurisdiction || 'GH'}
          onChange={(e) => setTenant({ ...tenant, tax_jurisdiction: e.target.value })}
          aria-label="Tax jurisdiction"
        >
          <option value="GH">Tax jurisdiction: GH — Ghana</option>
        </select>
        <input
          value={tenant.tax_registration_number || ''}
          onChange={(e) => setTenant({ ...tenant, tax_registration_number: e.target.value })}
          placeholder="TIN / VAT registration number (tax ID)"
          aria-label="TIN / VAT registration number"
        />
        <select
          value={tenant.tax_filing_period || 'monthly'}
          onChange={(e) => setTenant({ ...tenant, tax_filing_period: e.target.value })}
          aria-label="Tax filing period"
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

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          {tenant.status !== 'suspended' && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 260 }}>
              <span className="muted">Suspend reason (required)</span>
              <input
                value={suspendReason}
                onChange={(e) => setSuspendReason(e.target.value)}
                placeholder="Required before Suspend"
                title="Required suspend reason (1–500 chars; letters/digits required)"
                aria-label="Tenant suspend reason"
                disabled={!!tenant.read_only}
              />
            </label>
          )}
          <button onClick={save} disabled={!!tenant.read_only} aria-label="Save company profile">
            Save profile
          </button>
          {(tenant.status === 'trial' || tenant.status === 'grace') && (
            <button className="btn-ok" onClick={activate}>Activate</button>
          )}
          {tenant.status !== 'suspended' && (
            <button
              className="btn-danger"
              onClick={suspend}
              disabled={!!tenant.read_only}
              aria-label="Suspend company"
            >
              Suspend
            </button>
          )}
        </div>
        {tenant.status === 'suspended' && tenant.suspended_reason ? (
          <p className="muted" style={{ marginTop: 8 }}>
            Suspended reason: {tenant.suspended_reason}
          </p>
        ) : null}
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
          Header/footer on invoices, receipts, and outbound emails. Company logo is embedded on PDFs
          and branded HTML emails.
        </p>
        <label className="muted">Header text</label>
        <input
          value={printHeader}
          onChange={(e) => setPrintHeader(e.target.value)}
          placeholder="Tagline under company name"
          title="Optional header (1–200 chars; letters/digits required); blank clears"
          aria-label="Print branding header text"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <label className="muted">Footer text</label>
        <input
          value={printFooter}
          onChange={(e) => setPrintFooter(e.target.value)}
          placeholder="Thank you line"
          title="Optional footer (1–300 chars; letters/digits required); blank clears"
          aria-label="Print branding footer text"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <label>
            Invoice template{' '}
            <select
              value={invTemplate}
              onChange={(e) => setInvTemplate(e.target.value)}
              aria-label="Default invoice template"
            >
              <option value="a4">A4</option>
              <option value="thermal">Thermal</option>
            </select>
          </label>
          <label>
            Receipt paper{' '}
            <select
              value={receiptPaper}
              onChange={(e) => setReceiptPaper(e.target.value)}
              aria-label="Default receipt paper"
            >
              <option value="80mm">80mm</option>
              <option value="58mm">58mm</option>
            </select>
          </label>
        </div>
        <button
          type="button"
          aria-label="Save print branding"
          onClick={async () => {
            setError('');
            try {
              const r = await api('/settings/print', {
                method: 'PATCH',
                body: JSON.stringify({
                  // null clears; blank would 422 (PrintHeader/FooterTextValue)
                  header_text: printHeader.trim() || null,
                  footer_text: printFooter.trim() || null,
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
            Mode: {emailStatus.mode} · Source: {emailStatus.source || '—'} · Configured:{' '}
            {String(emailStatus.configured)} · Enabled: {String(emailStatus.enabled)}
            {emailStatus.tenant_override ? ' · Tenant override' : ''}
          </p>
          <label className="muted">SMTP host</label>
          <input
            value={emailHost}
            onChange={(e) => setEmailHost(e.target.value)}
            placeholder="smtp.example.com"
            aria-label="Company SMTP host"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">Port</label>
          <input
            value={emailPort}
            onChange={(e) => setEmailPort(e.target.value)}
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">Username</label>
          <input
            value={emailUser}
            onChange={(e) => setEmailUser(e.target.value)}
            aria-label="Company SMTP username"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">
            Password{emailStatus.has_password ? ' (saved — leave blank to keep)' : ''}
          </label>
          <input
            type="password"
            value={emailPassword}
            onChange={(e) => setEmailPassword(e.target.value)}
            placeholder={emailStatus.has_password ? '••••••••' : ''}
            autoComplete="new-password"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">From email</label>
          <input
            type="email"
            value={emailFromEmail}
            onChange={(e) => setEmailFromEmail(e.target.value)}
            placeholder="noreply@example.com"
            aria-label="Company from email"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">From name</label>
          <input
            value={emailFromName}
            onChange={(e) => setEmailFromName(e.target.value)}
            aria-label="Company from name"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
            <input
              type="checkbox"
              checked={emailUseTls}
              onChange={(e) => {
                setEmailUseTls(e.target.checked);
                if (e.target.checked) setEmailUseSsl(false);
              }}
            />
            Use STARTTLS
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <input
              type="checkbox"
              checked={emailUseSsl}
              onChange={(e) => {
                setEmailUseSsl(e.target.checked);
                if (e.target.checked) setEmailUseTls(false);
              }}
            />
            Use SSL
          </label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={async () => {
                setError('');
                try {
                  const body: Record<string, unknown> = {
                    port: Number(emailPort) || 587,
                    use_tls: emailUseTls,
                    use_ssl: emailUseSsl,
                  };
                  // Omit blank host so Save does not 422 (SmtpHostValue); leave prior value.
                  const trimmedHost = emailHost.trim();
                  if (trimmedHost) body.host = trimmedHost;
                  // Omit blank username so Save does not 422 (SmtpUsernameValue); leave prior.
                  const trimmedUser = emailUser.trim();
                  if (trimmedUser) body.username = trimmedUser;
                  const trimmedFrom = emailFromEmail.trim();
                  if (trimmedFrom) body.from_email = trimmedFrom;
                  // Omit blank from_name so Save does not 422 (SmtpFromNameValue); leave prior.
                  const trimmedFromName = emailFromName.trim();
                  if (trimmedFromName) body.from_name = trimmedFromName;
                  if (emailPassword) body.password = emailPassword;
                  const r = await api('/settings/email', {
                    method: 'PATCH',
                    body: JSON.stringify(body),
                  });
                  setEmailStatus(r.data);
                  setEmailPassword('');
                  setMessage('Email settings saved');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              aria-label="Save email settings"
            >
              Save email settings
            </button>
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
              aria-label="Send test email to me"
            >
              Send test email to me
            </button>
          </div>
        </div>
      )}

      {smsStatus && (
        <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
          <h2>SMS / Twilio</h2>
          <p className="muted">
            Mode: {smsStatus.mode} · Source: {smsStatus.source || '—'} · Configured:{' '}
            {String(smsStatus.configured)} · Enabled: {String(smsStatus.enabled)}
            {smsStatus.tenant_override ? ' · Tenant override' : ''}
          </p>
          <label className="muted">Account SID</label>
          <input
            value={smsAccountSid}
            onChange={(e) => setSmsAccountSid(e.target.value)}
            placeholder="ACxxxxxxxx"
            aria-label="Company SMS account SID"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">
            Auth token{smsStatus.has_auth_token ? ' (saved — leave blank to keep)' : ''}
          </label>
          <input
            type="password"
            value={smsAuthToken}
            onChange={(e) => setSmsAuthToken(e.target.value)}
            placeholder={smsStatus.has_auth_token ? '••••••••' : ''}
            autoComplete="new-password"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">From number (E.164)</label>
          <input
            value={smsFromNumber}
            onChange={(e) => setSmsFromNumber(e.target.value)}
            placeholder="+15551234567"
            aria-label="Company SMS from number"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <label className="muted">Your mobile (for test SMS)</label>
          <input
            value={profilePhone}
            onChange={(e) => setProfilePhone(e.target.value)}
            placeholder="Your mobile (E.164 e.g. +233...)"
            aria-label="Profile phone for SMS test"
            style={{ width: '100%', marginBottom: 8 }}
          />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={async () => {
                setError('');
                try {
                  const body: Record<string, unknown> = {};
                  // Omit blank SID so Save does not 422 (TwilioAccountSidValue); leave prior.
                  const trimmedSid = smsAccountSid.trim();
                  if (trimmedSid) body.account_sid = trimmedSid;
                  const trimmedFrom = smsFromNumber.trim();
                  if (trimmedFrom) body.from_number = trimmedFrom;
                  if (smsAuthToken) body.auth_token = smsAuthToken;
                  const r = await api('/settings/sms', {
                    method: 'PATCH',
                    body: JSON.stringify(body),
                  });
                  setSmsStatus(r.data);
                  setSmsAuthToken('');
                  setMessage('SMS settings saved');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              aria-label="Save SMS settings"
            >
              Save SMS settings
            </button>
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
              aria-label="Save my phone"
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
              aria-label="Send test SMS to me"
            >
              Send test SMS to me
            </button>
          </div>
        </div>
      )}
    </Shell>
  );
}
