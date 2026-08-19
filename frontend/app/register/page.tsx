'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { api } from '../../lib/api';

const empty = {
  company_name: '',
  slug: '',
  industry: 'retail',
  currency: 'GHS',
  timezone: 'Africa/Accra',
  tax_jurisdiction: 'GH',
  admin_full_name: '',
  admin_email: '',
  admin_password: '',
};

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ slug: string; token?: string } | null>(null);

  function update(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function submit() {
    setError('');
    setBusy(true);
    try {
      const r = await api('/tenants', {
        method: 'POST',
        body: JSON.stringify({
          company_name: form.company_name,
          slug: form.slug.trim().toLowerCase(),
          industry: form.industry,
          currency: form.currency,
          timezone: form.timezone,
          tax_jurisdiction: form.tax_jurisdiction,
          admin_full_name: form.admin_full_name,
          admin_email: form.admin_email,
          admin_password: form.admin_password,
        }),
      });
      setDone({ slug: r.data.slug, token: r.data.email_verification_token });
      setStep(4);
    } catch (err: any) {
      setError(err.message || 'Registration failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <h1>Register company</h1>
      <p className="muted">Step {step} of 4 · Create your RIBDIGI tenant</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}

      {step === 1 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(2);
          }}
        >
          <input
            value={form.company_name}
            onChange={(e) => update('company_name', e.target.value)}
            placeholder="Company name"
            required
          />
          <input
            value={form.slug}
            onChange={(e) => update('slug', e.target.value)}
            placeholder="Tenant slug (e.g. acme)"
            required
          />
          <select value={form.industry} onChange={(e) => update('industry', e.target.value)}>
            <option value="retail">Retail</option>
            <option value="wholesale">Wholesale</option>
            <option value="services">Services</option>
            <option value="manufacturing">Manufacturing</option>
          </select>
          <button type="submit">Continue</button>
        </form>
      )}

      {step === 2 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setStep(3);
          }}
        >
          <input
            value={form.currency}
            onChange={(e) => update('currency', e.target.value)}
            placeholder="Currency (GHS)"
            required
          />
          <input
            value={form.timezone}
            onChange={(e) => update('timezone', e.target.value)}
            placeholder="Timezone"
            required
          />
          <select
            value={form.tax_jurisdiction}
            onChange={(e) => update('tax_jurisdiction', e.target.value)}
          >
            <option value="GH">Ghana (GH)</option>
            <option value="NG">Nigeria (NG)</option>
          </select>
          <button type="submit">Continue</button>
          <button type="button" onClick={() => setStep(1)}>
            Back
          </button>
        </form>
      )}

      {step === 3 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <input
            value={form.admin_full_name}
            onChange={(e) => update('admin_full_name', e.target.value)}
            placeholder="Admin full name"
            required
          />
          <input
            type="email"
            value={form.admin_email}
            onChange={(e) => update('admin_email', e.target.value)}
            placeholder="Admin email"
            required
          />
          <input
            type="password"
            value={form.admin_password}
            onChange={(e) => update('admin_password', e.target.value)}
            placeholder="Admin password"
            required
          />
          <button type="submit" disabled={busy}>
            {busy ? 'Creating…' : 'Create tenant'}
          </button>
          <button type="button" onClick={() => setStep(2)}>
            Back
          </button>
        </form>
      )}

      {step === 4 && done && (
        <div>
          <p>
            Tenant <strong>{done.slug}</strong> created. Check email to verify the admin account,
            then sign in.
          </p>
          {done.token && (
            <p className="muted">
              Dev verification token:{' '}
              <Link href={`/verify-email?token=${encodeURIComponent(done.token)}`}>Verify now</Link>
            </p>
          )}
          <button type="button" onClick={() => router.push('/')}>
            Go to login
          </button>
        </div>
      )}

      {step < 4 && (
        <p className="muted" style={{ marginTop: 16 }}>
          Already registered? <Link href="/">Sign in</Link>
        </p>
      )}
    </div>
  );
}
