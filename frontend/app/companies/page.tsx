'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { setWorkspaceContext } from '../../lib/workspaceContext';

type Company = {
  id: string;
  code: string;
  name: string;
  industry: string;
  is_active: boolean;
  is_default: boolean;
};

type BusinessType = { id: string; code: string; label: string };

export default function CompaniesPage() {
  const [rows, setRows] = useState<Company[]>([]);
  const [types, setTypes] = useState<BusinessType[]>([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [industry, setIndustry] = useState('retail');
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
      await api('/companies', {
        method: 'POST',
        body: JSON.stringify({ name, code: code || undefined, industry }),
      });
      setName('');
      setCode('');
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
              <strong>{c.name}</strong> ({c.code}) — {c.industry}
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
        <form onSubmit={onCreate} style={{ marginTop: 24, maxWidth: 420 }}>
          <h2>Add company</h2>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Code
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="MAIN" />
          </label>
          <label>
            Business type / industry
            <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
              {types.map((t) => (
                <option key={t.code || t.id} value={t.code}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={busy || !name.trim()}>
            {busy ? 'Creating…' : 'Create company'}
          </button>
        </form>
      </div>
    </Shell>
  );
}
