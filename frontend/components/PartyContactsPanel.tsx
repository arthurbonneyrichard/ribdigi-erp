'use client';

import { useEffect, useState } from 'react';
import { api } from '../lib/api';

type Contact = {
  id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  designation?: string | null;
  is_primary?: boolean;
};

type Props = {
  kind: 'customer' | 'supplier';
  partyId: string;
  partyLabel?: string;
};

export default function PartyContactsPanel({ kind, partyId, partyLabel }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [designation, setDesignation] = useState('');
  const [asPrimary, setAsPrimary] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const base = kind === 'customer' ? `/customers/${partyId}/contacts` : `/suppliers/${partyId}/contacts`;

  async function load() {
    if (!partyId) return;
    setError('');
    try {
      const r = await api(base);
      setContacts(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    setContacts([]);
    setMessage('');
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partyId, kind]);

  async function addContact() {
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Party contact name is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setLoading(true);
    try {
      await api(base, {
        method: 'POST',
        body: JSON.stringify({
          name: trimmedName,
          phone: phone.trim() || null,
          email: email.trim() || null,
          designation: designation.trim() || null,
          is_primary: asPrimary,
        }),
      });
      setName('');
      setPhone('');
      setEmail('');
      setDesignation('');
      setAsPrimary(false);
      setMessage('Contact added');
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function makePrimary(contactId: string) {
    setError('');
    try {
      await api(`${base}/${contactId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_primary: true }),
      });
      setMessage('Primary contact updated');
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeContact(contactId: string) {
    if (!window.confirm('Delete this contact?')) return;
    setError('');
    try {
      await api(`${base}/${contactId}`, { method: 'DELETE' });
      setMessage('Contact deleted');
      await load();
    } catch (err: any) {
      setError(err.message);
    }
  }

  if (!partyId) return null;

  return (
    <div className="card" style={{ marginTop: 12 }}>
      <h3 style={{ marginTop: 0 }}>
        Contacts{partyLabel ? ` — ${partyLabel}` : ''}
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Multiple contacts with name, phone, email, and designation (BR-6.1). Primary syncs to the
        party phone/email used for documents.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Designation</th>
            <th>Phone</th>
            <th>Email</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {contacts.map((c) => (
            <tr key={c.id}>
              <td>
                {c.name}
                {c.is_primary ? (
                  <span className="badge" style={{ marginLeft: 6 }}>
                    Primary
                  </span>
                ) : null}
              </td>
              <td>{c.designation || '—'}</td>
              <td>{c.phone || '—'}</td>
              <td>{c.email || '—'}</td>
              <td style={{ whiteSpace: 'nowrap' }}>
                {!c.is_primary && (
                  <button type="button" onClick={() => makePrimary(c.id)}>
                    Make primary
                  </button>
                )}{' '}
                <button type="button" onClick={() => removeContact(c.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {!contacts.length && (
            <tr>
              <td colSpan={5} className="muted">
                No contacts yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
        <input aria-label="Party contact name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Contact name" />
        <input
          value={designation}
          onChange={(e) => setDesignation(e.target.value)}
          placeholder="Designation"
          aria-label="Party contact designation"
        />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone (E.164 e.g. +233...)"
          aria-label="Party contact phone"
        />
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <label className="muted" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox"
            checked={asPrimary}
            onChange={(e) => setAsPrimary(e.target.checked)}
          />
          Primary
        </label>
        <button type="button" aria-label="Add party contact" onClick={addContact} disabled={loading || !name.trim()}>
          {loading ? 'Saving…' : 'Add contact'}
        </button>
      </div>
    </div>
  );
}
