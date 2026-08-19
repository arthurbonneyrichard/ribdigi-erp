'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const WEBHOOK_EVENTS = [
  'sale.created',
  'sale.paid',
  'stock.low',
  'stock.in',
  'stock.out',
  'purchase.order.created',
  'purchase.grn.received',
  'customer.created',
  'supplier.created',
  'expense.approved',
  'user.login',
  'tenant.suspended',
  'webhook.test',
] as const;

type ApiKeyRow = {
  id: string;
  name: string;
  key_prefix?: string;
  status?: string;
  permissions?: Record<string, string[]>;
  expires_at?: string | null;
  last_used_at?: string | null;
  request_count?: number;
  created_at?: string;
  api_key?: string;
};

type WebhookRow = {
  id: string;
  url: string;
  events?: string[];
  is_active?: boolean;
  description?: string | null;
  failure_count?: number;
  last_status_code?: number | null;
  last_delivery_at?: string | null;
  secret?: string;
};

type WebhookDelivery = {
  id: string;
  webhook_id: string;
  event: string;
  status: string;
  attempt_count?: number;
  response_status?: number | null;
  error?: string | null;
  next_retry_at?: string | null;
  created_at?: string;
  delivered_at?: string | null;
  can_retry?: boolean;
};

export default function Page() {
  const [keys, setKeys] = useState<ApiKeyRow[]>([]);
  const [hooks, setHooks] = useState<WebhookRow[]>([]);
  const [webhookManageFilter, setWebhookManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [apiKeyManageFilter, setApiKeyManageFilter] = useState<
    'all' | 'active' | 'revoked' | 'expired'
  >('all');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revealedKey, setRevealedKey] = useState('');
  const [revealedSecret, setRevealedSecret] = useState('');
  const [usage, setUsage] = useState<any>(null);
  const [deliveriesFor, setDeliveriesFor] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [deliveriesBusy, setDeliveriesBusy] = useState(false);
  const [deliveryStatusFilter, setDeliveryStatusFilter] = useState<
    'all' | 'pending' | 'pending_retry' | 'delivered' | 'failed'
  >('all');

  const [keyName, setKeyName] = useState('');
  const [keyExpires, setKeyExpires] = useState('');
  const [hookUrl, setHookUrl] = useState('');
  const [hookDesc, setHookDesc] = useState('');
  const [hookEvents, setHookEvents] = useState<string[]>(['sale.created', 'webhook.test']);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const [k, w] = await Promise.all([api('/api-keys'), api('/webhooks')]);
    setKeys(k.data || []);
    setHooks(w.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  function toggleEvent(ev: string) {
    setHookEvents((prev) =>
      prev.includes(ev) ? prev.filter((x) => x !== ev) : [...prev, ev]
    );
  }

  async function createKey() {
    const name = keyName.trim();
    if (!name) {
      setError('API key name is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setRevealedKey('');
    setBusy(true);
    try {
      const body: Record<string, unknown> = { name };
      const expiry = keyExpires.trim();
      if (expiry) body.expires_at = expiry;
      const r = await api('/api-keys', { method: 'POST', body: JSON.stringify(body) });
      setRevealedKey(r.data?.api_key || '');
      setMessage(r.message || 'API key created — copy the secret now');
      setKeyName('');
      setKeyExpires('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function revokeKey(id: string) {
    if (!window.confirm('Revoke this API key? Clients using it will lose access immediately.')) {
      return;
    }
    setError('');
    try {
      await api(`/api-keys/${id}`, { method: 'DELETE' });
      setMessage('API key revoked');
      if (usage?.id === id) setUsage(null);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadUsage(id: string) {
    setError('');
    try {
      const r = await api(`/api-keys/${id}/usage`);
      setUsage({ id, ...r.data });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createWebhook() {
    setError('');
    setMessage('');
    setRevealedSecret('');
    if (!hookEvents.length) {
      setError('Select at least one webhook event');
      return;
    }
    setBusy(true);
    try {
      const r = await api('/webhooks', {
        method: 'POST',
        body: JSON.stringify({
          url: hookUrl,
          events: hookEvents,
          description: hookDesc.trim() || null,
          is_active: true,
        }),
      });
      setRevealedSecret(r.data?.secret || '');
      setMessage(r.message || 'Webhook created — copy the signing secret now');
      setHookUrl('');
      setHookDesc('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function testWebhook(id: string) {
    setError('');
    try {
      const r = await api(`/webhooks/${id}/test`, { method: 'POST', body: '{}' });
      setMessage(
        `Test delivery: ${r.data?.status || 'unknown'}` +
          (r.data?.response_status != null ? ` (HTTP ${r.data.response_status})` : '') +
          (r.data?.error ? ` — ${r.data.error}` : '')
      );
      await refresh();
      if (deliveriesFor === id) {
        await loadDeliveries(id);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadDeliveries(id: string) {
    setError('');
    setDeliveriesBusy(true);
    setDeliveriesFor(id);
    try {
      const r = await api(`/webhooks/${id}/deliveries?limit=30`);
      setDeliveries(r.data || []);
    } catch (err: any) {
      setError(err.message);
      setDeliveries([]);
    } finally {
      setDeliveriesBusy(false);
    }
  }

  async function retryDelivery(webhookId: string, deliveryId: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/webhooks/${webhookId}/deliveries/${deliveryId}/retry`, {
        method: 'POST',
        body: '{}',
      });
      setMessage(
        `Retry: ${r.data?.status || 'unknown'}` +
          (r.data?.response_status != null ? ` (HTTP ${r.data.response_status})` : '') +
          (r.data?.error ? ` — ${r.data.error}` : '')
      );
      await refresh();
      await loadDeliveries(webhookId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function rotateSecret(id: string) {
    if (!window.confirm('Rotate signing secret? Subscribers must update to the new secret.')) {
      return;
    }
    setError('');
    setRevealedSecret('');
    try {
      const r = await api(`/webhooks/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ rotate_secret: true }),
      });
      setRevealedSecret(r.data?.secret || '');
      setMessage('Signing secret rotated — copy the new secret now');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function toggleActive(row: WebhookRow) {
    setError('');
    try {
      await api(`/webhooks/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !row.is_active }),
      });
      setMessage(row.is_active ? 'Webhook disabled' : 'Webhook enabled');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deleteWebhook(id: string) {
    if (!window.confirm('Delete this webhook endpoint?')) return;
    setError('');
    try {
      await api(`/webhooks/${id}`, { method: 'DELETE' });
      setMessage('Webhook deleted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const managedHooks = hooks.filter((h) => {
    if (webhookManageFilter === 'all') return true;
    const active = h.is_active !== false;
    return webhookManageFilter === 'inactive' ? !active : active;
  });
  const managedKeys = keys.filter((k) => {
    if (apiKeyManageFilter === 'all') return true;
    return (k.status || 'active') === apiKeyManageFilter;
  });
  const managedDeliveries = deliveries.filter((d) => {
    if (deliveryStatusFilter === 'all') return true;
    return (d.status || 'pending') === deliveryStatusFilter;
  });

  return (
    <Shell>
      <h1>Integrations</h1>
      <p className="muted">
        API keys and outbound webhooks for company admins (BR-18.1 / BR-18.6). Secrets are shown
        once at create/rotate — store them securely.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {(revealedKey || revealedSecret) && (
        <div
          className="card"
          style={{ marginBottom: 16, borderLeft: '4px solid #ca8a04', maxWidth: 720 }}
        >
          <h2 style={{ marginTop: 0 }}>Copy secret now</h2>
          {revealedKey && (
            <>
              <p className="muted">API key (will not be shown again)</p>
              <code style={{ wordBreak: 'break-all', display: 'block', marginBottom: 8 }}>
                {revealedKey}
              </code>
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(revealedKey)}
              >
                Copy API key
              </button>
            </>
          )}
          {revealedSecret && (
            <>
              <p className="muted" style={{ marginTop: revealedKey ? 12 : 0 }}>
                Webhook signing secret (will not be shown again)
              </p>
              <code style={{ wordBreak: 'break-all', display: 'block', marginBottom: 8 }}>
                {revealedSecret}
              </code>
              <button
                type="button"
                onClick={() => navigator.clipboard?.writeText(revealedSecret)}
              >
                Copy signing secret
              </button>
            </>
          )}
        </div>
      )}

      <div className="card" style={{ marginBottom: 16, maxWidth: 720 }}>
        <h2>API keys</h2>
        <p className="muted">
          Authenticate with <code>X-API-Key</code> or <code>Authorization: Bearer</code>. Default
          permissions are read-only inventory/sales/purchasing/customers/reports.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <input
            value={keyName}
            onChange={(e) => setKeyName(e.target.value)}
            placeholder="Key name"
            aria-label="API key name"
            style={{ minWidth: 160 }}
          />
          <input
            type="text"
            value={keyExpires}
            onChange={(e) => setKeyExpires(e.target.value)}
            placeholder="YYYY-MM-DD or ISO datetime"
            title="Optional expiry (YYYY-MM-DD or ISO datetime)"
            aria-label="API key expiry"
          />
          <button
            type="button"
            onClick={createKey}
            disabled={busy || !keyName.trim()}
            aria-label="Create API key"
          >
            Create API key
          </button>
        </div>
        <select
          value={apiKeyManageFilter}
          onChange={(e) =>
            setApiKeyManageFilter(e.target.value as 'all' | 'active' | 'revoked' | 'expired')
          }
          title="Filter manage API key list by status"
          aria-label="API key status filter"
          style={{ marginBottom: 12 }}
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="revoked">Revoked only</option>
          <option value="expired">Expired only</option>
        </select>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Prefix</th>
              <th>Status</th>
              <th>Requests</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedKeys.map((k) => (
              <tr key={k.id}>
                <td>{k.name}</td>
                <td>
                  <code>{k.key_prefix || '—'}</code>
                </td>
                <td>{k.status}</td>
                <td>{k.request_count ?? 0}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => loadUsage(k.id)}>
                    Usage
                  </button>
                  {k.status === 'active' && (
                    <button type="button" onClick={() => revokeKey(k.id)}>
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!managedKeys.length && (
              <tr>
                <td colSpan={5} className="muted">
                  No API keys for this filter
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {usage && (
          <p className="muted" style={{ marginTop: 8 }}>
            Usage for selected key: {JSON.stringify(usage)}
          </p>
        )}
      </div>

      <div className="card" style={{ maxWidth: 960 }}>
        <h2>Webhooks</h2>
        <p className="muted">
          Outbound HTTPS deliveries signed with <code>X-Ribdigi-Signature</code> (HMAC-SHA256). Live
          fan-out today: <code>webhook.test</code>, <code>sale.created</code> (invoice + POS),{' '}
          <code>sale.paid</code> (AR payment + settled POS), <code>customer.created</code>,{' '}
          <code>supplier.created</code>, <code>purchase.order.created</code>,{' '}
          <code>purchase.grn.received</code>, <code>expense.approved</code>, <code>stock.low</code>,{' '}
          <code>stock.in</code> (manual / non-GRN inbound; GRN uses <code>purchase.grn.received</code>{' '}
          only), <code>stock.out</code> (manual / non-POS-invoice outbound),{' '}
          <code>tenant.suspended</code>, <code>user.login</code> (interactive auth only; not refresh).
        </p>
        <details style={{ marginBottom: 12 }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Verify signature (subscriber)</summary>
          <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
            <p className="muted" style={{ margin: 0 }}>
              Header format <code>t=&lt;unix&gt;,v1=&lt;hex&gt;</code>. Signed bytes are the ASCII
              timestamp, a dot, then the raw JSON body. Reject if timestamp skew exceeds 300s. Full
              samples: API docs §17.4 / Security Guide §8.5.
            </p>
            <pre
              style={{
                margin: 0,
                padding: 12,
                overflow: 'auto',
                fontSize: 12,
                background: 'var(--surface-2, #f8fafc)',
                borderRadius: 8,
              }}
            >{`# Python
import hashlib, hmac, time

def verify(secret, body: bytes, header: str, skew=300) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    ts = int(parts.get("t", "0"))
    if abs(int(time.time()) - ts) > skew:
        return False
    signed = f"{ts}.".encode() + body
    got = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(got, parts.get("v1", ""))

# Golden fixture
# secret = whsec_demo_secret_123456
# body   = {"event":"webhook.test",...}  # exact raw bytes
# t=1723705200
# v1=8ba12e1df3b867331f2ccf13f760ace4afd370df9d542012046eb4aba49bb2e2`}</pre>
            <button
              type="button"
              onClick={() =>
                navigator.clipboard?.writeText(
                  `import hashlib, hmac, time\n\ndef verify(secret, body: bytes, header: str, skew=300) -> bool:\n    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)\n    ts = int(parts.get("t", "0"))\n    if abs(int(time.time()) - ts) > skew:\n        return False\n    signed = f"{ts}.".encode() + body\n    got = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()\n    return hmac.compare_digest(got, parts.get("v1", ""))\n`
                )
              }
            >
              Copy Python verifier
            </button>
          </div>
        </details>
        <label className="muted">Endpoint URL</label>
        <input
          value={hookUrl}
          onChange={(e) => setHookUrl(e.target.value)}
          placeholder="https://your-app.com/webhooks/ribdigi"
          aria-label="Webhook endpoint URL"
          title="Absolute https URL (http only for localhost)"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <label className="muted">Description</label>
        <input
          value={hookDesc}
          onChange={(e) => setHookDesc(e.target.value)}
          placeholder="Optional label"
          aria-label="Webhook description"
          style={{ width: '100%', marginBottom: 8 }}
        />
        <p className="muted" style={{ marginBottom: 4 }}>
          Events
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
          {WEBHOOK_EVENTS.map((ev) => (
            <label key={ev} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={hookEvents.includes(ev)}
                onChange={() => toggleEvent(ev)}
              />
              <span style={{ fontSize: 13 }}>{ev}</span>
            </label>
          ))}
        </div>
        <button type="button" onClick={createWebhook} disabled={busy || !hookUrl}>
          Create webhook
        </button>

        <select
          value={webhookManageFilter}
          onChange={(e) =>
            setWebhookManageFilter(e.target.value as 'all' | 'active' | 'inactive')
          }
          title="Filter manage webhook list by status"
          aria-label="Webhook status filter"
          style={{ marginTop: 12 }}
        >
          <option value="all">All statuses</option>
          <option value="active">Active only</option>
          <option value="inactive">Inactive only</option>
        </select>

        <table style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>URL</th>
              <th>Events</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedHooks.map((h) => (
              <tr key={h.id}>
                <td style={{ maxWidth: 220, wordBreak: 'break-all' }}>
                  {h.url}
                  {h.is_active === false ? (
                    <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                      [inactive]
                    </span>
                  ) : null}
                  {h.description ? (
                    <div className="muted" style={{ fontSize: 12 }}>
                      {h.description}
                    </div>
                  ) : null}
                </td>
                <td style={{ fontSize: 12 }}>{(h.events || []).join(', ')}</td>
                <td>
                  {h.is_active ? 'active' : 'disabled'}
                  {h.failure_count ? ` · fails ${h.failure_count}` : ''}
                  {h.last_status_code != null ? ` · HTTP ${h.last_status_code}` : ''}
                </td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => testWebhook(h.id)}>
                    Test
                  </button>
                  <button type="button" onClick={() => loadDeliveries(h.id)}>
                    Deliveries
                  </button>
                  <button type="button" onClick={() => rotateSecret(h.id)}>
                    Rotate secret
                  </button>
                  <button type="button" onClick={() => toggleActive(h)}>
                    {h.is_active ? 'Disable' : 'Enable'}
                  </button>
                  <button type="button" onClick={() => deleteWebhook(h.id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!managedHooks.length && (
              <tr>
                <td colSpan={4} className="muted">
                  {hooks.length ? 'No webhooks for this filter' : 'No webhooks yet'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {deliveriesFor && (
          <div style={{ marginTop: 16, display: 'grid', gap: 8 }}>
            <strong>
              Delivery history
              {hooks.find((h) => h.id === deliveriesFor)
                ? ` — ${hooks.find((h) => h.id === deliveriesFor)?.url}`
                : ''}
            </strong>
            <p className="muted" style={{ margin: 0 }}>
              Recent attempts from GET /webhooks/:id/deliveries. Retry re-signs and POSTs the stored
              payload (pending_retry or failed). Optional Query status ∈
              pending|pending_retry|delivered|failed (blank/invalid → 422).
            </p>
            <select
              value={deliveryStatusFilter}
              onChange={(e) =>
                setDeliveryStatusFilter(
                  e.target.value as
                    | 'all'
                    | 'pending'
                    | 'pending_retry'
                    | 'delivered'
                    | 'failed'
                )
              }
              title="Filter delivery history by status"
              aria-label="Webhook delivery status filter"
            >
              <option value="all">All statuses</option>
              <option value="pending">Pending only</option>
              <option value="pending_retry">Pending retry only</option>
              <option value="delivered">Delivered only</option>
              <option value="failed">Failed only</option>
            </select>
            {deliveriesBusy ? <p className="muted">Loading…</p> : null}
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Event</th>
                  <th>Status</th>
                  <th>HTTP</th>
                  <th>Attempts</th>
                  <th>Error</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {managedDeliveries.map((d) => (
                  <tr key={d.id}>
                    <td style={{ fontSize: 12 }}>
                      {d.created_at ? String(d.created_at).replace('T', ' ').slice(0, 19) : '—'}
                    </td>
                    <td style={{ fontSize: 12 }}>{d.event}</td>
                    <td>{d.status}</td>
                    <td>{d.response_status ?? '—'}</td>
                    <td>{d.attempt_count ?? 0}</td>
                    <td style={{ fontSize: 12, maxWidth: 180, wordBreak: 'break-word' }}>
                      {d.error || '—'}
                    </td>
                    <td>
                      {d.can_retry ? (
                        <button type="button" onClick={() => retryDelivery(deliveriesFor, d.id)}>
                          Retry
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
                {!managedDeliveries.length && !deliveriesBusy && (
                  <tr>
                    <td colSpan={7} className="muted">
                      {deliveries.length
                        ? 'No deliveries for this filter'
                        : 'No deliveries yet — click Test to create one'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <button type="button" onClick={() => loadDeliveries(deliveriesFor)} disabled={deliveriesBusy}>
              Refresh deliveries
            </button>
          </div>
        )}
      </div>
    </Shell>
  );
}
