'use client';

import { useState } from 'react';
import FormModal from './FormModal';
import { api } from '../lib/api';

export type CustomerGroup = {
  id: string;
  name: string;
  code?: string | null;
  discount_percent?: number | null;
  is_active?: boolean;
};

type Props = {
  groups: CustomerGroup[];
  customers: Array<{ customer_group_id?: string | null }>;
  onClose: () => void;
  /** Reload groups (and customers) after a change. */
  onChanged: () => Promise<void> | void;
};

/** Add customer groups, change their discount, and switch them on or off. */
export default function CustomerGroupsWindow({ groups, customers, onClose, onChanged }: Props) {
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupCode, setNewGroupCode] = useState('');
  const [newGroupDiscount, setNewGroupDiscount] = useState('0');
  const [groupDiscountDrafts, setGroupDiscountDrafts] = useState<Record<string, string>>({});
  const [groupManageFilter, setGroupManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const managedGroups = groups.filter((g) => {
    if (groupManageFilter === 'all') return true;
    const active = g.is_active !== false;
    return groupManageFilter === 'inactive' ? !active : active;
  });

  async function run(work: () => Promise<string>) {
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const done = await work();
      await onChanged();
      setMessage(done);
    } catch (err: any) {
      setError(err?.message || 'That change could not be saved.');
    } finally {
      setBusy(false);
    }
  }

  function createGroup() {
    const name = newGroupName.trim();
    if (!name) {
      setError('Give the group a name.');
      return;
    }
    void run(async () => {
      await api('/customers/groups', {
        method: 'POST',
        body: JSON.stringify({
          name,
          code: newGroupCode.trim() || null,
          discount_percent: Number(newGroupDiscount) || 0,
        }),
      });
      setNewGroupName('');
      setNewGroupCode('');
      setNewGroupDiscount('0');
      return `Group ${name} added`;
    });
  }

  function saveGroupDiscount(group: CustomerGroup) {
    void run(async () => {
      await api(`/customers/groups/${group.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ discount_percent: Number(groupDiscountDrafts[group.id] ?? 0) }),
      });
      setGroupDiscountDrafts((prev) => {
        const next = { ...prev };
        delete next[group.id];
        return next;
      });
      return `${group.name} discount saved`;
    });
  }

  function setGroupActive(group: CustomerGroup, is_active: boolean) {
    void run(async () => {
      await api(`/customers/groups/${group.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      return is_active ? `${group.name} switched on` : `${group.name} switched off`;
    });
  }

  return (
    <FormModal title="Customer groups" onClose={onClose} busy={busy}>
      <p className="muted" style={{ marginTop: 0 }}>
        A group gives its customers a discount off your normal prices. Put a customer in a group from their customer form.
      </p>
      {error || message ? (
        <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
          {error || message}
        </p>
      ) : null}
      <div className="cust-group-add">
        <div className="field">
          <label htmlFor="grp-name">Group name</label>
          <input
            id="grp-name"
            aria-label="Customer group name"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            placeholder="e.g. Wholesale"
          />
        </div>
        <div className="field">
          <label htmlFor="grp-disc">Discount %</label>
          <input
            id="grp-disc"
            value={newGroupDiscount}
            onChange={(e) => setNewGroupDiscount(e.target.value)}
            inputMode="decimal"
            aria-label="Customer group discount percent"
          />
        </div>
        <input
          className="sr-only"
          tabIndex={-1}
          aria-label="Customer group code"
          value={newGroupCode}
          onChange={(e) => setNewGroupCode(e.target.value)}
          placeholder="Code (optional)"
        />
        <button type="button" className="btn-primary" aria-label="Add group" onClick={createGroup} disabled={busy || !newGroupName.trim()}>
          Add group
        </button>
      </div>
      <div className="cust-group-head">
        <h4>Your groups</h4>
        <select
          value={groupManageFilter}
          onChange={(e) => setGroupManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
          aria-label="Customer group status filter"
        >
          <option value="all">All groups</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>
      </div>
      <div className="cust-group-wrap">
        <table className="table cust-group-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Customers</th>
              <th>Discount %</th>
              <th className="cust-group-act">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedGroups.map((g) => {
              const draft = groupDiscountDrafts[g.id] ?? String(g.discount_percent ?? 0);
              const changed = Number(draft) !== Number(g.discount_percent ?? 0);
              return (
                <tr key={g.id}>
                  <td>
                    {g.name}
                    {g.is_active === false ? <span className="muted"> · switched off</span> : null}
                  </td>
                  <td>{customers.filter((c) => c.customer_group_id === g.id).length}</td>
                  <td>
                    <input
                      value={draft}
                      onChange={(e) => setGroupDiscountDrafts((prev) => ({ ...prev, [g.id]: e.target.value }))}
                      inputMode="decimal"
                      className="cust-group-pct"
                      aria-label={`${g.name} discount percent`}
                    />
                  </td>
                  <td className="cust-group-act">
                    <div className="cust-group-row-actions">
                      <button
                        type="button"
                        className={changed ? 'btn-primary' : undefined}
                        disabled={busy || !changed}
                        onClick={() => saveGroupDiscount(g)}
                        aria-label={`Save customer group discount ${g.id}`}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className={g.is_active === false ? 'btn-ok' : 'btn-danger'}
                        disabled={busy}
                        onClick={() => setGroupActive(g, g.is_active === false)}
                        aria-label={g.is_active === false ? `Activate customer group ${g.id}` : `Deactivate customer group ${g.id}`}
                      >
                        {g.is_active === false ? 'Activate' : 'Deactivate'}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {managedGroups.length === 0 ? (
              <tr>
                <td colSpan={4} className="muted">No groups yet. Add one above.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </FormModal>
  );
}
