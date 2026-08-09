'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [tenant, setTenant] = useState<any>(null);
  const [emailStatus, setEmailStatus] = useState<any>(null);
  const [smtpForm, setSmtpForm] = useState({
    smtp_enabled: false,
    smtp_host: '',
    smtp_port: '587',
    smtp_username: '',
    smtp_password: '',
    smtp_from_email: '',
    smtp_from_name: '',
    smtp_use_tls: true,
    smtp_use_ssl: false,
  });
  const [smsStatus, setSmsStatus] = useState<any>(null);
  const [storageStatus, setStorageStatus] = useState<any>(null);
  const [profilePhone, setProfilePhone] = useState('');
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [branches, setBranches] = useState<any[]>([]);
  const [departments, setDepartments] = useState<any[]>([]);
  const [branchForm, setBranchForm] = useState({
    code: '',
    name: '',
    address: '',
    phone: '',
    email: '',
  });
  const [deptForm, setDeptForm] = useState({ code: '', name: '', branch_id: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

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
    const [r, e, s, me, st, br, dep] = await Promise.all([
      api('/tenants/me'),
      api('/settings/email'),
      api('/settings/sms'),
      api('/me'),
      api('/settings/storage').catch(() => ({ data: null })),
      api('/branches').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
    ]);
    setTenant(r.data);
    setEmailStatus(e.data);
    if (e.data) {
      setSmtpForm({
        smtp_enabled: !!e.data.tenant_override_enabled,
        smtp_host: e.data.source === 'tenant' ? e.data.host || '' : '',
        smtp_port: String(e.data.port || 587),
        smtp_username: e.data.source === 'tenant' ? e.data.username || '' : '',
        smtp_password: '',
        smtp_from_email: e.data.source === 'tenant' ? e.data.from_email || '' : '',
        smtp_from_name: e.data.source === 'tenant' ? e.data.from_name || '' : '',
        smtp_use_tls: e.data.use_tls !== false,
        smtp_use_ssl: !!e.data.use_ssl,
      });
    }
    setSmsStatus(s.data);
    setStorageStatus(st.data);
    setProfilePhone(me.data?.phone || '');
    setBranches(br.data || []);
    setDepartments(dep.data || []);
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
          timezone: tenant.timezone,
          fiscal_year_start: tenant.fiscal_year_start,
          tax_jurisdiction: tenant.tax_jurisdiction,
          tax_registration_number: tenant.tax_registration_number,
          tax_filing_period: tenant.tax_filing_period,
          document_numbering: tenant.document_numbering || undefined,
          invoice_print_template: tenant.invoice_print_template || undefined,
          plan_code: tenant.plan_code || undefined,
          legal_name: tenant.legal_name || undefined,
          registration_number: tenant.registration_number || undefined,
          billing_address: tenant.billing_address || undefined,
          shipping_address: tenant.shipping_address || undefined,
          warehouse_address: tenant.warehouse_address || undefined,
          contact_person_name: tenant.contact_person_name || undefined,
          contact_person_email: tenant.contact_person_email || undefined,
          contact_person_phone: tenant.contact_person_phone || undefined,
          inactivity_timeout_minutes: tenant.inactivity_timeout_minutes || undefined,
          date_format: tenant.date_format || undefined,
          number_format: tenant.number_format || undefined,
          time_format: tenant.time_format || undefined,
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
        Status: {tenant.status} · Plan: {tenant.plan_code || 'trial'} · Slug: {tenant.slug}
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
        <p className="muted" style={{ margin: 0 }}>
          Shown on invoices, receipts, quotations, and credit notes when printing.
        </p>
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
          placeholder="Company name"
        />
        <input
          value={tenant.legal_name || ''}
          onChange={(e) => setTenant({ ...tenant, legal_name: e.target.value })}
          placeholder="Legal name"
        />
        <input
          value={tenant.registration_number || ''}
          onChange={(e) => setTenant({ ...tenant, registration_number: e.target.value })}
          placeholder="Registration number"
        />
        <select
          value={tenant.plan_code || 'trial'}
          onChange={(e) => setTenant({ ...tenant, plan_code: e.target.value })}
        >
          {['trial', 'starter', 'growth', 'enterprise'].map((p) => (
            <option key={p} value={p}>
              Plan: {p}
            </option>
          ))}
        </select>
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
          placeholder="Primary address"
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
        <textarea
          value={tenant.warehouse_address || ''}
          onChange={(e) => setTenant({ ...tenant, warehouse_address: e.target.value })}
          placeholder="Warehouse address"
        />
        <input
          value={tenant.contact_person_name || ''}
          onChange={(e) => setTenant({ ...tenant, contact_person_name: e.target.value })}
          placeholder="Contact person name"
        />
        <input
          value={tenant.contact_person_email || ''}
          onChange={(e) => setTenant({ ...tenant, contact_person_email: e.target.value })}
          placeholder="Contact person email"
        />
        <input
          value={tenant.contact_person_phone || ''}
          onChange={(e) => setTenant({ ...tenant, contact_person_phone: e.target.value })}
          placeholder="Contact person phone"
        />
        <input
          type="number"
          min={5}
          max={480}
          value={tenant.inactivity_timeout_minutes ?? 30}
          onChange={(e) =>
            setTenant({ ...tenant, inactivity_timeout_minutes: Number(e.target.value) || 30 })
          }
          placeholder="Inactivity timeout (minutes)"
        />
        <select
          value={tenant.date_format || 'DD/MM/YYYY'}
          onChange={(e) => setTenant({ ...tenant, date_format: e.target.value })}
        >
          {['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'].map((f) => (
            <option key={f} value={f}>
              Date format: {f}
            </option>
          ))}
        </select>
        <select
          value={tenant.number_format || '1,234.56'}
          onChange={(e) => setTenant({ ...tenant, number_format: e.target.value })}
        >
          {['1,234.56', '1.234,56', '1 234.56'].map((f) => (
            <option key={f} value={f}>
              Number format: {f}
            </option>
          ))}
        </select>
        <select
          value={tenant.time_format || '24h'}
          onChange={(e) => setTenant({ ...tenant, time_format: e.target.value })}
        >
          <option value="24h">Time format: 24h</option>
          <option value="12h">Time format: 12h</option>
        </select>
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
          placeholder="TIN / VAT registration number"
        />
        <select
          value={tenant.tax_filing_period || 'monthly'}
          onChange={(e) => setTenant({ ...tenant, tax_filing_period: e.target.value })}
        >
          <option value="monthly">Filing period: monthly</option>
          <option value="quarterly">Filing period: quarterly</option>
        </select>
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

      <div className="card" style={{ marginTop: 16, maxWidth: 720 }}>
        <h2>Invoice print template</h2>
        <p className="muted">Default layout for sales invoice print (A4 or thermal).</p>
        <select
          value={tenant.invoice_print_template || 'a4'}
          onChange={(e) => setTenant({ ...tenant, invoice_print_template: e.target.value })}
          style={{ maxWidth: 220 }}
        >
          <option value="a4">A4</option>
          <option value="thermal_80">Thermal 80mm</option>
          <option value="thermal_58">Thermal 58mm</option>
        </select>
        <div style={{ marginTop: 8 }}>
          <button onClick={save} disabled={!!tenant.read_only}>
            Save print template
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16, maxWidth: 720 }}>
        <h2>Document numbering</h2>
        <p className="muted">Configure invoice/PO/GRN/quotation prefixes and next series numbers.</p>
        <table className="table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Prefix</th>
              <th>Year</th>
              <th>Pad</th>
              <th>Next #</th>
              <th>Preview</th>
            </tr>
          </thead>
          <tbody>
            {(
              [
                ['sales_invoice', 'Sales invoice'],
                ['purchase_invoice', 'Purchase invoice'],
                ['purchase_order', 'Purchase order'],
                ['goods_receipt', 'GRN'],
                ['sales_quotation', 'Quotation'],
                ['sales_order', 'Sales order'],
                ['sales_return', 'Sales return'],
                ['sales_credit_note', 'Sales credit note'],
                ['purchase_return', 'Purchase return'],
                ['purchase_debit_note', 'Purchase debit note'],
              ] as const
            ).map(([key, label]) => {
              const series = tenant.document_numbering?.[key] || {};
              const preview = tenant.document_numbering_preview?.[key] || '—';
              return (
                <tr key={key}>
                  <td>{label}</td>
                  <td>
                    <input
                      value={series.prefix || ''}
                      onChange={(e) =>
                        setTenant({
                          ...tenant,
                          document_numbering: {
                            ...(tenant.document_numbering || {}),
                            [key]: { ...series, prefix: e.target.value },
                          },
                        })
                      }
                      style={{ width: 90 }}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!series.include_year}
                      onChange={(e) =>
                        setTenant({
                          ...tenant,
                          document_numbering: {
                            ...(tenant.document_numbering || {}),
                            [key]: { ...series, include_year: e.target.checked },
                          },
                        })
                      }
                    />
                  </td>
                  <td>
                    <input
                      value={String(series.pad ?? 4)}
                      onChange={(e) =>
                        setTenant({
                          ...tenant,
                          document_numbering: {
                            ...(tenant.document_numbering || {}),
                            [key]: { ...series, pad: Number(e.target.value) || 1 },
                          },
                        })
                      }
                      style={{ width: 60 }}
                    />
                  </td>
                  <td>
                    <input
                      value={String(series.next_number ?? 1)}
                      onChange={(e) =>
                        setTenant({
                          ...tenant,
                          document_numbering: {
                            ...(tenant.document_numbering || {}),
                            [key]: { ...series, next_number: Number(e.target.value) || 1 },
                          },
                        })
                      }
                      style={{ width: 90 }}
                    />
                  </td>
                  <td className="muted">{preview}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <button onClick={save} disabled={!!tenant.read_only} style={{ marginTop: 8 }}>
          Save numbering
        </button>
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

      {emailStatus && (
        <div className="card" style={{ marginTop: 16, maxWidth: 520 }}>
          <h2>Email / SMTP</h2>
          <p className="muted">
            Mode: {emailStatus.mode} · Source: {emailStatus.source} · Configured:{' '}
            {String(emailStatus.configured)} · Enabled: {String(emailStatus.enabled)}
          </p>
          <p className="muted">
            Effective from: {emailStatus.from_name} &lt;{emailStatus.from_email || '—'}&gt; · Host:{' '}
            {emailStatus.host || 'console fallback'}
          </p>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            <label>
              <input
                type="checkbox"
                checked={smtpForm.smtp_enabled}
                onChange={(e) => setSmtpForm({ ...smtpForm, smtp_enabled: e.target.checked })}
              />{' '}
              Use tenant SMTP override
            </label>
            <input
              value={smtpForm.smtp_host}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_host: e.target.value })}
              placeholder="SMTP host"
            />
            <input
              value={smtpForm.smtp_port}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_port: e.target.value })}
              placeholder="Port"
            />
            <input
              value={smtpForm.smtp_username}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_username: e.target.value })}
              placeholder="Username"
            />
            <input
              type="password"
              value={smtpForm.smtp_password}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_password: e.target.value })}
              placeholder={emailStatus.has_password ? 'Password (leave blank to keep)' : 'Password'}
            />
            <input
              value={smtpForm.smtp_from_email}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_from_email: e.target.value })}
              placeholder="From email"
            />
            <input
              value={smtpForm.smtp_from_name}
              onChange={(e) => setSmtpForm({ ...smtpForm, smtp_from_name: e.target.value })}
              placeholder="From name"
            />
            <label>
              <input
                type="checkbox"
                checked={smtpForm.smtp_use_tls}
                onChange={(e) => setSmtpForm({ ...smtpForm, smtp_use_tls: e.target.checked })}
              />{' '}
              STARTTLS
            </label>
            <label>
              <input
                type="checkbox"
                checked={smtpForm.smtp_use_ssl}
                onChange={(e) => setSmtpForm({ ...smtpForm, smtp_use_ssl: e.target.checked })}
              />{' '}
              SSL
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                disabled={!!tenant.read_only}
                onClick={async () => {
                  setError('');
                  try {
                    const body: any = {
                      smtp_enabled: smtpForm.smtp_enabled,
                      smtp_host: smtpForm.smtp_host || null,
                      smtp_port: Number(smtpForm.smtp_port) || 587,
                      smtp_username: smtpForm.smtp_username || null,
                      smtp_from_email: smtpForm.smtp_from_email || null,
                      smtp_from_name: smtpForm.smtp_from_name || null,
                      smtp_use_tls: smtpForm.smtp_use_tls,
                      smtp_use_ssl: smtpForm.smtp_use_ssl,
                    };
                    if (smtpForm.smtp_password) body.smtp_password = smtpForm.smtp_password;
                    const r = await api('/settings/email', {
                      method: 'PATCH',
                      body: JSON.stringify(body),
                    });
                    setEmailStatus(r.data);
                    setSmtpForm({ ...smtpForm, smtp_password: '' });
                    setMessage('SMTP settings saved');
                  } catch (err: any) {
                    setError(err.message);
                  }
                }}
              >
                Save SMTP
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
              >
                Send test email to me
              </button>
            </div>
          </div>
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

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Branches &amp; departments</h3>
        <p className="muted">Org units for user assignment and department/branch record scopes.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            try {
              await api('/branches', {
                method: 'POST',
                body: JSON.stringify(branchForm),
              });
              setBranchForm({ code: '', name: '', address: '', phone: '', email: '' });
              setMessage('Branch created');
              await refresh();
            } catch (err: any) {
              setError(err.message);
            }
          }}
          style={{ display: 'grid', gap: 8, maxWidth: 480, marginBottom: 16 }}
        >
          <strong>New branch</strong>
          <input
            value={branchForm.code}
            onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value })}
            placeholder="Code"
            required
          />
          <input
            value={branchForm.name}
            onChange={(e) => setBranchForm({ ...branchForm, name: e.target.value })}
            placeholder="Name"
            required
          />
          <input
            value={branchForm.address}
            onChange={(e) => setBranchForm({ ...branchForm, address: e.target.value })}
            placeholder="Address (optional)"
          />
          <input
            value={branchForm.phone}
            onChange={(e) => setBranchForm({ ...branchForm, phone: e.target.value })}
            placeholder="Phone (optional)"
          />
          <input
            value={branchForm.email}
            onChange={(e) => setBranchForm({ ...branchForm, email: e.target.value })}
            placeholder="Email (optional)"
          />
          <button type="submit">Add branch</button>
        </form>
        <ul>
          {branches.map((b) => (
            <li key={b.id}>
              {b.code} — {b.name}
              {b.phone ? ` · ${b.phone}` : ''}
              {b.is_active ? '' : ' (inactive)'}
            </li>
          ))}
          {!branches.length && <li className="muted">No branches yet</li>}
        </ul>

        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setError('');
            try {
              await api('/departments', {
                method: 'POST',
                body: JSON.stringify({
                  code: deptForm.code,
                  name: deptForm.name,
                  branch_id: deptForm.branch_id || null,
                }),
              });
              setDeptForm({ code: '', name: '', branch_id: '' });
              setMessage('Department created');
              await refresh();
            } catch (err: any) {
              setError(err.message);
            }
          }}
          style={{ display: 'grid', gap: 8, maxWidth: 480, marginTop: 16 }}
        >
          <strong>New department</strong>
          <input
            value={deptForm.code}
            onChange={(e) => setDeptForm({ ...deptForm, code: e.target.value })}
            placeholder="Code"
            required
          />
          <input
            value={deptForm.name}
            onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
            placeholder="Name"
            required
          />
          <select
            value={deptForm.branch_id}
            onChange={(e) => setDeptForm({ ...deptForm, branch_id: e.target.value })}
          >
            <option value="">No branch</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <button type="submit">Add department</button>
        </form>
        <ul>
          {departments.map((d) => (
            <li key={d.id}>
              {d.code} — {d.name} {d.is_active ? '' : '(inactive)'}
            </li>
          ))}
          {!departments.length && <li className="muted">No departments yet</li>}
        </ul>
      </div>
    </Shell>
  );
}
