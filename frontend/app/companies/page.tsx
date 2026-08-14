'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api, authHeaders } from '../../lib/api';
import { setWorkspaceContext } from '../../lib/workspaceContext';

type Company = {
  id: string;
  code: string;
  name: string;
  industry: string;
  business_type_label?: string | null;
  has_logo?: boolean;
  is_active: boolean;
  is_default: boolean;
};

type BusinessType = { id: string; code: string; label: string };

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function CompaniesPage() {
  const [rows, setRows] = useState<Company[]>([]);
  const [types, setTypes] = useState<BusinessType[]>([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [industry, setIndustry] = useState('retail');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [address, setAddress] = useState('');
  const [currency, setCurrency] = useState('GHS');
  const [timezone, setTimezone] = useState('Africa/Accra');
  const [fiscalYearStart, setFiscalYearStart] = useState('01-01');
  const [taxRegistration, setTaxRegistration] = useState('');
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    setWorkspaceContext('tenant');
    const [list, bt] = await Promise.all([api('/companies'), api('/business-types')]);
    setRows(list.data || []);
    setTypes(bt.data || []);
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        await load();
      } catch (e: unknown) {
        if (active) setError(e instanceof Error ? e.message : 'Failed to load companies');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const selected = types.find((t) => t.code === industry);
      const created = await api('/companies', {
        method: 'POST',
        body: JSON.stringify({
          name,
          code: code || undefined,
          industry,
          business_type_id: selected && selected.id !== selected.code ? selected.id : undefined,
          phone: phone || undefined,
          email: email || undefined,
          address: address || undefined,
          currency: currency || undefined,
          timezone: timezone || undefined,
          fiscal_year_start: fiscalYearStart || undefined,
          tax_registration_number: taxRegistration || undefined,
        }),
      });
      const companyId = created.data?.id as string | undefined;
      if (companyId && logoFile) {
        const form = new FormData();
        form.append('file', logoFile);
        const res = await fetch(`${API_BASE}/companies/${companyId}/logo`, {
          method: 'POST',
          headers: authHeaders(),
          body: form,
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || body.message || 'Logo upload failed');
        }
        window.dispatchEvent(new CustomEvent('ribdigi-branding-changed'));
      }
      setName('');
      setCode('');
      setPhone('');
      setEmail('');
      setAddress('');
      setTaxRegistration('');
      setLogoFile(null);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <div className="page">
        <h1>Companies</h1>
        <p className="muted">
          Operating businesses under this tenant. Creating a company consumes a subscription slot.
        </p>
        {error && <p className="error">{error}</p>}
        <ul>
          {rows.map((c) => (
            <li key={c.id}>
              <strong>{c.name}</strong> ({c.code}) — {c.business_type_label || c.industry}
              {c.has_logo ? ' · logo' : ''}
              {c.is_default ? ' · default' : ''}
              {' · '}
              <button
                type="button"
                onClick={() => {
                  setWorkspaceContext('company', c.id);
                  window.location.assign('/dashboard');
                }}
              >
                Switch to company
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={onCreate} style={{ marginTop: 24, maxWidth: 480 }}>
          <h2>Add company</h2>
          <label>
            Company name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Code
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="MAIN" />
          </label>
          <label>
            Business type
            <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
              {types.map((t) => (
                <option key={t.code || t.id} value={t.code}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Company logo (optional)
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
            />
          </label>
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Address
            <textarea value={address} onChange={(e) => setAddress(e.target.value)} rows={2} />
          </label>
          <label>
            Tax registration number
            <input value={taxRegistration} onChange={(e) => setTaxRegistration(e.target.value)} />
          </label>
          <label>
            Currency
            <input value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </label>
          <label>
            Timezone
            <input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
          </label>
          <label>
            Financial year start (MM-DD)
            <input value={fiscalYearStart} onChange={(e) => setFiscalYearStart(e.target.value)} />
          </label>
          <button type="submit" disabled={busy || !name.trim()}>
            {busy ? 'Creating…' : 'Create company'}
          </button>
        </form>
      </div>
    </Shell>
  );
}
