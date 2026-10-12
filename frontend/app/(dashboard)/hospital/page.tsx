'use client';

import { FormEvent, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { moduleEnabledForTenant } from '../../../lib/industryModules';

type Patient = { id: string; name: string; phone?: string | null };
type Visit = { id: string; patient_id: string; reason: string; status: string };

export default function HospitalPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [name, setName] = useState('');
  const [reason, setReason] = useState('');
  const [patientId, setPatientId] = useState('');
  const [visit, setVisit] = useState<Visit | null>(null);
  const [error, setError] = useState('');

  async function load() {
    const res = await api('/hospital/patients');
    setPatients(Array.isArray(res?.data) ? res.data : []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Could not load patients'));
  }, []);

  async function addPatient(e: FormEvent) {
    e.preventDefault();
    setError('');
    const res = await api('/hospital/patients', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
    setName('');
    setPatientId(res.data.id);
    await load();
  }

  async function openVisit(e: FormEvent) {
    e.preventDefault();
    setError('');
    const res = await api('/hospital/encounters', {
      method: 'POST',
      body: JSON.stringify({ patient_id: patientId, reason }),
    });
    setVisit(res.data);
    setReason('');
  }

  async function closeVisit() {
    if (!visit) return;
    const res = await api(`/hospital/encounters/${visit.id}/close`, { method: 'POST' });
    setVisit(res.data);
  }

  return (
    <main className="page">
      <h1>Hospital</h1>
      <p>Patients and visits for this hospital. This is not a diagnosis or insurance desk.</p>
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={addPatient}>
        <label>
          Patient name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <button type="submit">Add patient</button>
      </form>
      <form onSubmit={openVisit}>
        <label>
          Patient
          <select value={patientId} onChange={(e) => setPatientId(e.target.value)} required>
            <option value="">Select</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Visit reason
          <input value={reason} onChange={(e) => setReason(e.target.value)} required />
        </label>
        <button type="submit">Open visit</button>
      </form>
      {visit ? (
        <p>
          Visit {visit.status}: {visit.reason}{' '}
          {visit.status === 'open' ? (
            <button type="button" onClick={closeVisit}>
              Close visit
            </button>
          ) : null}
        </p>
      ) : null}
    </main>
  );
}
