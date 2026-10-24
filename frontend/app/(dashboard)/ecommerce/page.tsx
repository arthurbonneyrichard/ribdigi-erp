'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import EmptyState from '../../../components/EmptyState';
import PageHeader from '../../../components/PageHeader';
import StatusChip from '../../../components/StatusChip';
import { api, apiFetch } from '../../../lib/api';
import { formatMoney, formatWhen } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import './ecom-desk.css';

const RESERVED_HOSTS = new Set([
  'ribdigi.com',
  'www.ribdigi.com',
  'ribdigihouse.com',
  'www.ribdigihouse.com',
  'erp.ribdigihouse.com',
]);
const RESERVED_SUFFIXES = ['.ribdigi.com', '.ribdigihouse.com'];
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', 'testserver', 'host.docker.internal']);

function hostFromWebsite(value: string): string {
  const raw = (value || '').trim();
  if (!raw) return '';
  try {
    if (raw.includes('://')) {
      const parsed = new URL(raw);
      return (parsed.hostname || '').toLowerCase().replace(/^www\./, '');
    }
  } catch {
    return '';
  }
  return raw.toLowerCase().replace(/^www\./, '').replace(/\/.*$/, '').replace(/\.$/, '');
}

function reservedHostMessage(value: string): string | null {
  const host = hostFromWebsite(value);
  if (!host) return null;
  if (RESERVED_HOSTS.has(host) || RESERVED_HOSTS.has(`www.${host}`) || RESERVED_SUFFIXES.some((suffix) => host.endsWith(suffix))) {
    return 'There is no public Ribdigi subdomain. Use a hostname you control.';
  }
  return null;
}

function remoteHttpMessage(value: string): string | null {
  const raw = value.trim();
  if (!raw.includes('://')) return null;
  try {
    const parsed = new URL(raw);
    const host = (parsed.hostname || '').toLowerCase();
    if (parsed.protocol === 'http:' && host && !LOCAL_HOSTS.has(host)) {
      return 'Remote websites must use https.';
    }
  } catch {
    return 'Use a public hostname or https website you control.';
  }
  return null;
}

async function copyText(value: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const field = document.createElement('textarea');
    field.value = value;
    field.setAttribute('readonly', '');
    field.style.position = 'fixed';
    field.style.left = '-9999px';
    document.body.appendChild(field);
    field.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(field);
    return ok;
  } catch {
    return false;
  }
}

export default function EcommercePage() {
  const [storefront, setStorefront] = useState<any>(null);
  const [ecomTab, setEcomTab] = useState<'shop' | 'products' | 'orders' | 'website'>('shop');
  const [domains, setDomains] = useState<any[]>([]);
  const [listings, setListings] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [connectors, setConnectors] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [hostname, setHostname] = useState('');
  const [wooUrl, setWooUrl] = useState('');
  const [wooKey, setWooKey] = useState('');
  const [wooSecret, setWooSecret] = useState('');
  const [gatewaySecret, setGatewaySecret] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [denied, setDenied] = useState('');
  const [catalogQ, setCatalogQ] = useState('');
  const [mediaPreview, setMediaPreview] = useState<Record<string, string>>({});
  const prefs = useCompanyFormat();
  const MEDIA_MAX_BYTES = 2_000_000;
  const MEDIA_TYPES = new Set(['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif']);

  async function refresh() {
    const [home, catalog, orderList, conn, stock] = await Promise.all([
      api('/ecommerce'),
      api('/ecommerce/listings'),
      api('/ecommerce/orders'),
      api('/ecommerce/connectors'),
      api('/warehouses').catch(() => ({ data: [] })),
    ]);
    const nextStorefront = home.data?.storefront;
    setStorefront(nextStorefront);
    setDomains(home.data?.domains || []);
    setListings(catalog.data?.items || []);
    setOrders(orderList.data || []);
    const nextConnectors = conn.data?.connectors || [];
    setConnectors(nextConnectors);
    setJobs(conn.data?.jobs || []);
    setWarehouses(stock.data || []);
    const woo = nextConnectors.find((row: any) => row.platform === 'woocommerce');
    if (woo?.store_url && !wooUrl) {
      setWooUrl(woo.store_url);
    }
    const kinds: Array<['logo' | 'banner' | 'favicon', boolean]> = [
      ['logo', Boolean(nextStorefront?.has_logo)],
      ['banner', Boolean(nextStorefront?.has_banner)],
      ['favicon', Boolean(nextStorefront?.has_favicon)],
    ];
    const nextPreview: Record<string, string> = {};
    await Promise.all(
      kinds.map(async ([kind, present]) => {
        if (!present) return;
        const res = await apiFetch(`/ecommerce/media/${kind}`);
        if (!res.ok) return;
        nextPreview[kind] = URL.createObjectURL(await res.blob());
      }),
    );
    setMediaPreview((prev) => {
      Object.values(prev).forEach((url) => URL.revokeObjectURL(url));
      return nextPreview;
    });
  }

  useEffect(() => {
    refresh().catch((err: any) => {
      const text = err.message || 'Could not load online store';
      if (err.status === 403) setDenied(text);
      else setError(text);
    });
  }, []);

  const companyHost = hostFromWebsite(String(storefront?.company_website || ''));
  const companyLinked = useMemo(
    () => Boolean(companyHost && domains.some((row) => row.hostname === companyHost)),
    [companyHost, domains],
  );
  const primaryDomain = domains.find((row) => row.is_primary) || domains[0];
  const woo = connectors.find((row) => row.platform === 'woocommerce');
  const storefrontStatus = storefront?.enabled ? 'enabled' : 'disabled';

  async function run(action: string, work: () => Promise<void>, ok?: string) {
    setError('');
    setMessage('');
    setBusy(action);
    try {
      await work();
      if (ok) setMessage(ok);
    } catch (err: any) {
      setError(err.message || 'Could not complete that action');
    } finally {
      setBusy('');
    }
  }

  async function saveStorefront(e: FormEvent) {
    e.preventDefault();
    await run('storefront', async () => {
      await api('/ecommerce', {
        method: 'PATCH',
        body: JSON.stringify({
          is_enabled: !!storefront?.enabled,
          tagline: storefront?.tagline || null,
          announcement: storefront?.announcement || null,
          support_email: storefront?.support_email || null,
          support_phone: storefront?.support_phone || null,
          fulfillment_warehouse_id: storefront?.fulfillment_warehouse_id || null,
          allow_delivery: !!storefront?.allow_delivery,
          allow_pickup: !!storefront?.allow_pickup,
          pickup_address: storefront?.pickup_address || null,
          policy_shipping: storefront?.policy_shipping || null,
          policy_returns: storefront?.policy_returns || null,
          policy_privacy: storefront?.policy_privacy || null,
        }),
      });
      await refresh();
    }, 'Storefront saved');
  }

  async function uploadMedia(kind: 'logo' | 'banner' | 'favicon', file: File | undefined) {
    if (!file) return;
    if (!MEDIA_TYPES.has(file.type)) {
      setError('That file type is not allowed. Use PNG, JPEG, WebP, or GIF.');
      setMessage('');
      return;
    }
    if (file.size <= 0) {
      setError('The file is empty. Choose another image.');
      setMessage('');
      return;
    }
    if (file.size > MEDIA_MAX_BYTES) {
      setError('That file is too large. Maximum size is 2 MB.');
      setMessage('');
      return;
    }
    await run(`media-${kind}`, async () => {
      const form = new FormData();
      form.append('file', file);
      await api(`/ecommerce/media/${kind}`, { method: 'POST', body: form });
      await refresh();
    }, `Storefront ${kind} uploaded. This is separate from the ERP sidebar logo.`);
  }

  async function removeMedia(kind: 'logo' | 'banner' | 'favicon') {
    await run(`media-del-${kind}`, async () => {
      await api(`/ecommerce/media/${kind}`, { method: 'DELETE' });
      await refresh();
    }, `Storefront ${kind} removed.`);
  }

  async function addDomain(e: FormEvent) {
    e.preventDefault();
    const value = hostname.trim();
    const reserved = reservedHostMessage(value);
    const http = remoteHttpMessage(value);
    if (reserved || http) {
      setError(reserved || http || '');
      setMessage('');
      return;
    }
    await run('domain', async () => {
      await api('/ecommerce/domains', { method: 'POST', body: JSON.stringify({ hostname: value }) });
      setHostname('');
      await refresh();
    }, 'Website linked. Add the TXT record, then verify.');
  }

  async function linkCompanyWebsite() {
    const site = String(storefront?.company_website || '').trim();
    if (!site) {
      setError('Save a company website first, then link it here.');
      return;
    }
    const reserved = reservedHostMessage(site);
    if (reserved) {
      setError(reserved);
      setMessage('');
      return;
    }
    await run('company-site', async () => {
      await api('/ecommerce/domains', { method: 'POST', body: JSON.stringify({ hostname: site }) });
      await refresh();
    }, 'Company website linked. Add the TXT record, then verify.');
  }

  const preview = storefront?.preview_token ? (
    <a className="list-btn-primary" href={`/storefront?preview_token=${storefront.preview_token}`}>
      Open preview
    </a>
  ) : undefined;

  if (denied) {
    return (
      <main className="page ecom-desk">
        <PageHeader title="Online store" subtitle="Sell on this company’s verified domain." />
        <EmptyState
          role="alert"
          title="Online store is not available for this company"
          detail={`${denied} Retail trial, professional, and enterprise can enable it. Hotel and restaurant stay gated unless entitled. There is no public Ribdigi subdomain.`}
        />
      </main>
    );
  }

  if (!storefront) {
    return (
      <main className="page ecom-desk">
        <PageHeader title="Online store" subtitle="Loading this company’s storefront." />
        {error ? <p className="list-toast err" role="alert">{error}</p> : <p className="muted">Loading online store…</p>}
      </main>
    );
  }

  const visibleListings = listings.filter((row) => {
    const needle = catalogQ.trim().toLowerCase();
    if (!needle) return true;
    return `${row.name || ''} ${row.sku || ''} ${row.category || ''}`.toLowerCase().includes(needle);
  });
  const warehouseName =
    warehouses.find((row) => row.id === storefront.fulfillment_warehouse_id)?.name ||
    (storefront.fulfillment_warehouse_id ? 'Selected warehouse' : 'Company default');

  return (
    <main className="page ecom-desk">
      <PageHeader
        title="Online store"
        subtitle="Sell your products online. Only the products you publish appear in your shop."
        actions={
          <div className="ecom-head-actions">
            <StatusChip value={storefrontStatus} label={storefront.enabled ? 'Storefront on' : 'Storefront off'} />
            {preview}
          </div>
        }
      />
      {error ? <p className="list-toast err" role="alert">{error}</p> : null}
      {message ? <p className="list-toast ok" role="status">{message}</p> : null}

      <section className="card ecom-status" aria-label="Storefront status">
        <div>
          <p className="muted">Storefront</p>
          <p>{storefront.enabled ? `Enabled · ${warehouseName}` : 'Disabled'}</p>
        </div>
        <div>
          <p className="muted">Company website</p>
          {storefront.company_website ? (
            <p>
              <a href={storefront.company_website} target="_blank" rel="noreferrer">{storefront.company_website}</a>
              {companyLinked ? ' · linked' : ''}
            </p>
          ) : (
            <p>Not saved on <a href="/company">Company</a></p>
          )}
        </div>
        <div>
          <p className="muted">Linked website</p>
          <p>{primaryDomain ? `${primaryDomain.hostname} · ${primaryDomain.display_status || primaryDomain.status}` : 'None'}</p>
        </div>
        <div>
          <p className="muted">WooCommerce</p>
          <p>{woo?.enabled ? woo.store_url || 'Connected' : 'Not connected'}</p>
        </div>
      </section>

      <nav className="ecom-tabs" aria-label="Online store sections">
        {(
          [
            ['shop', 'Shop setup', storefront.enabled ? 'On' : 'Off'],
            ['products', 'Products', `${listings.filter((row) => row.published).length} online`],
            ['orders', 'Orders', `${orders.length}`],
            ['website', 'Website and payments', primaryDomain ? 'Linked' : ''],
          ] as ['shop' | 'products' | 'orders' | 'website', string, string][]
        ).map(([id, label, badge]) => (
          <button
            key={id}
            type="button"
            className={ecomTab === id ? 'ecom-tab is-on' : 'ecom-tab'}
            aria-pressed={ecomTab === id}
            aria-label={`Show online store ${label.toLowerCase()}`}
            onClick={() => setEcomTab(id)}
          >
            {label}
            {badge ? <span className="ecom-tab-badge">{badge}</span> : null}
          </button>
        ))}
      </nav>

      {ecomTab === 'shop' ? (
      <section className="card" aria-labelledby="ecom-storefront">
        <h2 id="ecom-storefront">Storefront settings</h2>
        <p className="muted">Enable the built-in shop, set policies, and choose how orders are fulfilled.</p>
        <form className="erp-form-grid" onSubmit={saveStorefront}>
          <label className="ecom-check span-2">
            <input
              type="checkbox"
              checked={!!storefront.enabled}
              aria-label="Storefront enabled"
              onChange={(e) => setStorefront({ ...storefront, enabled: e.target.checked })}
            />
            Enable built-in storefront
          </label>
          <label>
            Tagline
            <input
              aria-label="Storefront tagline"
              value={storefront.tagline || ''}
              onChange={(e) => setStorefront({ ...storefront, tagline: e.target.value })}
            />
          </label>
          <label>
            Fulfillment warehouse
            <select
              aria-label="Storefront fulfillment warehouse"
              value={storefront.fulfillment_warehouse_id || ''}
              onChange={(e) => setStorefront({ ...storefront, fulfillment_warehouse_id: e.target.value || null })}
            >
              <option value="">Company default</option>
              {warehouses.map((row) => (
                <option key={row.id} value={row.id}>{row.name || row.code || row.id}</option>
              ))}
            </select>
            {!warehouses.length ? (
              <span className="muted">Add a warehouse in Multi-Store before online stock can reserve.</span>
            ) : null}
          </label>
          <label>
            Support email
            <input
              aria-label="Storefront support email"
              type="email"
              value={storefront.support_email || ''}
              onChange={(e) => setStorefront({ ...storefront, support_email: e.target.value })}
            />
          </label>
          <label>
            Support phone
            <input
              aria-label="Storefront support phone"
              value={storefront.support_phone || ''}
              onChange={(e) => setStorefront({ ...storefront, support_phone: e.target.value })}
              placeholder="+233..."
            />
          </label>
          <label className="span-2">
            Announcement
            <textarea
              aria-label="Storefront announcement"
              value={storefront.announcement || ''}
              onChange={(e) => setStorefront({ ...storefront, announcement: e.target.value })}
            />
          </label>
          <label className="ecom-check">
            <input
              type="checkbox"
              checked={!!storefront.allow_delivery}
              aria-label="Storefront allow delivery"
              onChange={(e) => setStorefront({ ...storefront, allow_delivery: e.target.checked })}
            />
            Allow delivery
          </label>
          <label className="ecom-check">
            <input
              type="checkbox"
              checked={!!storefront.allow_pickup}
              aria-label="Storefront allow pickup"
              onChange={(e) => setStorefront({ ...storefront, allow_pickup: e.target.checked })}
            />
            Allow pickup
          </label>
          <label className="span-2">
            Pickup address
            <textarea
              aria-label="Storefront pickup address"
              value={storefront.pickup_address || ''}
              onChange={(e) => setStorefront({ ...storefront, pickup_address: e.target.value })}
            />
          </label>
          <label className="span-2">
            Shipping policy
            <textarea
              aria-label="Storefront shipping policy"
              value={storefront.policy_shipping || ''}
              onChange={(e) => setStorefront({ ...storefront, policy_shipping: e.target.value })}
            />
          </label>
          <label className="span-2">
            Returns policy
            <textarea
              aria-label="Storefront returns policy"
              value={storefront.policy_returns || ''}
              onChange={(e) => setStorefront({ ...storefront, policy_returns: e.target.value })}
            />
          </label>
          <label className="span-2">
            Privacy policy
            <textarea
              aria-label="Storefront privacy policy"
              value={storefront.policy_privacy || ''}
              onChange={(e) => setStorefront({ ...storefront, policy_privacy: e.target.value })}
            />
          </label>
          <button type="submit" className="list-btn-primary" aria-label="Save storefront settings" disabled={busy === 'storefront'}>
            Save storefront
          </button>
        </form>
      </section>
      ) : null}

      {ecomTab === 'shop' ? (
      <section className="card" aria-labelledby="ecom-media">
        <h2 id="ecom-media">Storefront media</h2>
        <p className="muted">
          Logo appears in the public shop header. Banner is the hero image. Favicon is the shop tab icon.
          These files are not the ERP sidebar logo. PNG, JPEG, WebP, or GIF, up to 2 MB. Nothing is shown until you upload it.
        </p>
        <div className="ecom-media-grid">
          {([
            ['logo', 'Storefront logo', 'Storefront logo file', storefront.has_logo],
            ['banner', 'Storefront banner', 'Storefront banner file', storefront.has_banner],
            ['favicon', 'Storefront favicon', 'Storefront favicon file', storefront.has_favicon],
          ] as Array<['logo' | 'banner' | 'favicon', string, string, boolean]>).map(([kind, label, fileLabel, present]) => (
            <article key={kind} className="ecom-media-card">
              <p>{label}</p>
              {present && mediaPreview[kind] ? (
                <img
                  className={kind === 'banner' ? 'ecom-media-preview' : 'ecom-media-preview is-mark'}
                  src={mediaPreview[kind]}
                  alt={label}
                />
              ) : (
                <div className="ecom-media-empty">No {kind} uploaded</div>
              )}
              <label>
                {label} file
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/gif"
                  aria-label={
                    kind === 'logo'
                      ? 'Storefront logo file'
                      : kind === 'banner'
                        ? 'Storefront banner file'
                        : 'Storefront favicon file'
                  }
                  disabled={busy.startsWith('media-')}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    void uploadMedia(kind, file);
                    e.target.value = '';
                  }}
                />
              </label>
              {present ? (
                <button
                  type="button"
                  aria-label={`Remove ${label.toLowerCase()}`}
                  disabled={busy === `media-del-${kind}`}
                  onClick={() => void removeMedia(kind)}
                >
                  Remove {kind}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      </section>
      ) : null}

      {ecomTab === 'website' ? (
      <section className="card" aria-labelledby="ecom-domains">
        <h2 id="ecom-domains">Link a website</h2>
        <p className="muted">
          Use a hostname you control for the built-in storefront. Paste a hostname or an https website.
          An existing WooCommerce site stays on the connector below — do not point that DNS here.
          Record HTTPS ready only after the reverse proxy has a certificate. This page does not issue TLS.
        </p>
        <form className="erp-form-grid" onSubmit={addDomain}>
          <label className="span-2">
            Website or hostname
            <input
              aria-label="Custom domain hostname"
              value={hostname}
              onChange={(e) => setHostname(e.target.value)}
              placeholder="https://shop.example.com"
              required
            />
          </label>
          <button type="submit" className="list-btn-primary" aria-label="Add custom domain" disabled={busy === 'domain'}>
            Link website
          </button>
        </form>
        {storefront.company_website ? (
          <p className="ecom-row-actions">
            <span>Company website: {storefront.company_website}</span>
            {companyLinked ? (
              <StatusChip value="active" label="Linked" />
            ) : (
              <button type="button" aria-label="Link company website" onClick={() => void linkCompanyWebsite()} disabled={busy === 'company-site'}>
                Link company website
              </button>
            )}
          </p>
        ) : (
          <p className="muted">
            Save a company website on <a href="/company">Company</a>, then link it here.
          </p>
        )}
        {!domains.length ? (
          <EmptyState
            title="No website linked"
            detail="Add a hostname you control, or link the company website. There is no public Ribdigi subdomain."
          />
        ) : null}
        {domains.map((domain) => (
          <article key={domain.id} className="ecom-domain">
            <div className="ecom-domain-top">
              <p className="ecom-domain-host">{domain.hostname}</p>
              <StatusChip value={domain.display_status || domain.status} />
            </div>
            <p className="muted ecom-dns">
              {domain.https_ready ? 'HTTPS ready · ' : ''}
              {domain.is_primary ? 'Primary · ' : ''}
              {domain.redirect_to_id ? 'Redirects · ' : ''}
              {domain.dns_instructions}
            </p>
            {domain.txt_record ? (
              <p className="ecom-txt">
                <span className="muted">TXT</span>
                <code>{domain.txt_record}</code>
              </p>
            ) : null}
            <div className="ecom-row-actions">
              <button
                type="button"
                aria-label={`Copy TXT record for ${domain.hostname}`}
                onClick={() => {
                  if (!domain.txt_record) {
                    setError('No TXT record to copy yet.');
                    return;
                  }
                  void copyText(domain.txt_record).then((ok) => {
                    if (ok) setMessage('TXT record copied.');
                    else setError('Could not copy TXT record');
                  });
                }}
              >
                Copy TXT
              </button>
              <button
                type="button"
                aria-label={`Verify domain ${domain.hostname}`}
                disabled={busy === `verify-${domain.id}`}
                onClick={() =>
                  void run(`verify-${domain.id}`, async () => {
                    await api(`/ecommerce/domains/${domain.id}/verify`, { method: 'POST' });
                    await refresh();
                  }, 'Domain verified.')
                }
              >
                Verify
              </button>
              <button
                type="button"
                aria-label={`Record HTTPS ready for ${domain.hostname}`}
                disabled={domain.status !== 'verified' || busy === `https-${domain.id}`}
                title={domain.status !== 'verified' ? 'Verify the hostname before recording HTTPS ready. This page does not issue TLS.' : undefined}
                onClick={() =>
                  void run(`https-${domain.id}`, async () => {
                    await api(`/ecommerce/domains/${domain.id}/https-ready`, { method: 'POST' });
                    await refresh();
                  }, 'HTTPS-ready recorded. Certificates stay an owner task.')
                }
              >
                Record HTTPS ready
              </button>
              <button
                type="button"
                aria-label={`Make ${domain.hostname} primary`}
                disabled={busy === `primary-${domain.id}`}
                onClick={() =>
                  void run(`primary-${domain.id}`, async () => {
                    await api(`/ecommerce/domains/${domain.id}/primary`, { method: 'POST' });
                    await refresh();
                  }, 'Primary website updated.')
                }
              >
                Primary
              </button>
              {domains.length > 1 ? (
                <label>
                  Redirect to
                  <select
                    aria-label={`Redirect ${domain.hostname}`}
                    value={domain.redirect_to_id || ''}
                    onChange={(e) =>
                      void run(`redirect-${domain.id}`, async () => {
                        await api(`/ecommerce/domains/${domain.id}/redirect`, {
                          method: 'POST',
                          body: JSON.stringify({ redirect_to_id: e.target.value || null }),
                        });
                        await refresh();
                      }, 'Redirect updated.')
                    }
                  >
                    <option value="">No redirect</option>
                    {domains.filter((item) => item.id !== domain.id).map((item) => (
                      <option key={item.id} value={item.id}>{item.hostname}</option>
                    ))}
                  </select>
                </label>
              ) : null}
              <button
                type="button"
                aria-label={`Unlink website ${domain.hostname}`}
                onClick={() =>
                  void run(`unlink-${domain.id}`, async () => {
                    await api(`/ecommerce/domains/${domain.id}`, { method: 'DELETE' });
                    await refresh();
                  }, 'Website unlinked.')
                }
              >
                Unlink
              </button>
            </div>
          </article>
        ))}
      </section>
      ) : null}

      {ecomTab === 'products' ? (
      <section className="card" aria-labelledby="ecom-catalog">
        <h2 id="ecom-catalog">Catalog</h2>
        <p className="muted">The ERP catalog is not published automatically. Online price and stock buffer are opt-in per product.</p>
        {listings.length ? (
          <label>
            Find product
            <input
              aria-label="Online catalog search"
              value={catalogQ}
              onChange={(e) => setCatalogQ(e.target.value)}
              placeholder="Search name, SKU, or category"
            />
          </label>
        ) : null}
        {!listings.length ? (
          <EmptyState
            title="No products to publish"
            detail="Add products in Inventory, then opt them in here. Nothing is sold online until you publish it."
          />
        ) : !visibleListings.length ? (
          <EmptyState title="No products match this search" detail="Clear the catalog search to see every product." />
        ) : (
          <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Status</th>
                  <th>ERP price</th>
                  <th>Online price</th>
                  <th>Stock buffer</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleListings.map((row) => (
                  <tr key={row.product_id}>
                    <td>{row.name}</td>
                    <td><StatusChip value={row.published ? 'published' : 'unpublished'} /></td>
                    <td>{formatMoney(row.selling_price, prefs, storefront.currency)}</td>
                    <td>
                      <input
                        aria-label={`Online price ${row.name}`}
                        type="number"
                        min="0"
                        step="0.01"
                        value={row.online_price ?? ''}
                        onChange={(e) =>
                          setListings((prev) =>
                            prev.map((item) =>
                              item.product_id === row.product_id
                                ? { ...item, online_price: e.target.value === '' ? null : Number(e.target.value) }
                                : item
                            )
                          )
                        }
                      />
                    </td>
                    <td>
                      <input
                        aria-label={`Stock buffer ${row.name}`}
                        type="number"
                        min="0"
                        step="1"
                        value={row.stock_buffer ?? 0}
                        onChange={(e) =>
                          setListings((prev) =>
                            prev.map((item) =>
                              item.product_id === row.product_id
                                ? { ...item, stock_buffer: Number(e.target.value || 0) }
                                : item
                            )
                          )
                        }
                      />
                    </td>
                    <td>
                      <div className="ecom-row-actions">
                        <button
                          type="button"
                          aria-label={`Save listing ${row.name}`}
                          onClick={() =>
                            void run(`listing-${row.product_id}`, async () => {
                              await api('/ecommerce/listings', {
                                method: 'PUT',
                                body: JSON.stringify({
                                  product_id: row.product_id,
                                  is_published: row.published,
                                  online_price: row.online_price,
                                  stock_buffer: row.stock_buffer,
                                }),
                              });
                              await refresh();
                            }, 'Listing saved.')
                          }
                        >
                          Save listing
                        </button>
                        <button
                          type="button"
                          className={row.published ? 'btn-danger' : 'btn-ok'}
                          aria-label={`${row.published ? 'Unpublish' : 'Publish'} ${row.name}`}
                          onClick={() =>
                            void run(`publish-${row.product_id}`, async () => {
                              await api('/ecommerce/listings', {
                                method: 'PUT',
                                body: JSON.stringify({ product_id: row.product_id, is_published: !row.published }),
                              });
                              await refresh();
                            }, row.published ? 'Unpublished.' : 'Published.')
                          }
                        >
                          {row.published ? 'Unpublish' : 'Publish'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      ) : null}

      {ecomTab === 'orders' ? (
      <section className="card" aria-labelledby="ecom-orders">
        <h2 id="ecom-orders">Orders</h2>
        <p className="muted">
          New orders wait for payment. When the customer pays (cash, MoMo or card on delivery or at pickup), press
          Payment received. Then move the order along: Pack, Send out, Delivered.
        </p>
        {!orders.length ? (
          <EmptyState title="No online orders yet" detail="Orders appear here as soon as a shopper places one in your online store." />
        ) : (
          <div className="list-table-wrap">
            <table className="table ecom-orders-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Customer</th>
                  <th>Items</th>
                  <th>Total</th>
                  <th>Status</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => {
                  const pickup = order.fulfillment === 'pickup';
                  return (
                  <tr key={order.id}>
                    <td>
                      <b className="ecom-order-no">{order.order_number}</b>
                      <span className="ecom-order-sub">{order.created_at ? formatWhen(order.created_at, prefs) : ''}</span>
                    </td>
                    <td>
                      <b>{order.guest_name || 'Guest'}</b>
                      {order.guest_phone ? <span className="ecom-order-sub">{order.guest_phone}</span> : null}
                      <span className="ecom-order-sub">
                        {pickup ? 'Pickup at the shop' : `Delivery${order.delivery_address ? `: ${order.delivery_address}` : ''}`}
                      </span>
                    </td>
                    <td className="ecom-order-items">{order.items_summary || '—'}</td>
                    <td>{formatMoney(order.total_amount, prefs, order.currency || storefront.currency)}</td>
                    <td><StatusChip value={order.status} /></td>
                    <td>
                      <div className="ecom-row-actions">
                        {order.status === 'awaiting_payment' ? (
                          <>
                            <button type="button" className="btn-ok" aria-label={`Collect payment ${order.order_number}`} onClick={() => void run(`collect-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/collect`, { method: 'POST' }); await refresh(); }, 'Payment recorded and the sale posted.')}>Payment received</button>
                            <button type="button" className="btn-danger" aria-label={`Cancel order ${order.order_number}`} onClick={() => void run(`cancel-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/cancel`, { method: 'POST' }); await refresh(); }, 'Order cancelled.')}>Cancel</button>
                          </>
                        ) : null}
                        {order.status === 'paid' ? (
                          <button type="button" className="btn-ok" aria-label={`Pack order ${order.order_number}`} onClick={() => void run(`pack-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/fulfill?target=packed`, { method: 'POST' }); await refresh(); }, 'Order packed.')}>{pickup ? 'Packed, ready for pickup' : 'Pack'}</button>
                        ) : null}
                        {order.status === 'packed' ? (
                          <button type="button" className="btn-ok" aria-label={`Dispatch order ${order.order_number}`} onClick={() => void run(`dispatch-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/fulfill?target=dispatched`, { method: 'POST' }); await refresh(); }, pickup ? 'Order handed over.' : 'Order sent out.')}>{pickup ? 'Hand over' : 'Send out'}</button>
                        ) : null}
                        {order.status === 'dispatched' ? (
                          <button type="button" className="btn-ok" aria-label={`Mark ${order.order_number} delivered`} onClick={() => void run(`deliver-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/fulfill?target=delivered`, { method: 'POST' }); await refresh(); }, 'Order delivered.')}>{pickup ? 'Collected' : 'Delivered'}</button>
                        ) : null}
                        {['paid', 'packed', 'dispatched', 'delivered', 'fulfilled'].includes(order.status) ? (
                          <button type="button" aria-label={`Return order ${order.order_number}`} onClick={() => void run(`return-${order.id}`, async () => { await api(`/ecommerce/orders/${order.id}/return`, { method: 'POST' }); await refresh(); }, 'Return posted.')}>Return</button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      ) : null}

      {ecomTab === 'website' ? (
      <section className="card" aria-labelledby="ecom-payments">
        <h2 id="ecom-payments">Storefront payments</h2>
        <p className="muted">Store a test webhook secret only. Live processor secrets stay out of this tree. A return URL does not mark paid.</p>
        <form
          className="erp-form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            void run('gateway', async () => {
              await api('/ecommerce/gateway', {
                method: 'PATCH',
                body: JSON.stringify({ provider: 'mock', mode: 'test', secret: gatewaySecret, webhook_secret: gatewaySecret }),
              });
              setGatewaySecret('');
            }, 'Gateway secret stored encrypted. A return URL does not mark paid.');
          }}
        >
          <label>
            Test webhook secret
            <input aria-label="Storefront gateway secret" type="password" value={gatewaySecret} onChange={(e) => setGatewaySecret(e.target.value)} />
          </label>
          <button type="submit" className="list-btn-primary" aria-label="Save storefront gateway">
            Save gateway
          </button>
        </form>
      </section>
      ) : null}

      {ecomTab === 'website' ? (
      <section className="card" aria-labelledby="ecom-woo">
        <h2 id="ecom-woo">Website connector</h2>
        <p className="muted">
          Link an existing WooCommerce website without changing its DNS. Keys stay encrypted. Shopify and other platforms stay closed.
        </p>
        <form
          className="erp-form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            const reserved = reservedHostMessage(wooUrl);
            const http = remoteHttpMessage(wooUrl);
            if (reserved || http) {
              setError(reserved || http || '');
              setMessage('');
              return;
            }
            void run('woo', async () => {
              await api('/ecommerce/connectors', {
                method: 'PATCH',
                body: JSON.stringify({
                  platform: 'woocommerce',
                  store_url: wooUrl.trim(),
                  consumer_key: wooKey.trim() || null,
                  consumer_secret: wooSecret.trim() || null,
                  enabled: true,
                }),
              });
              setWooKey('');
              setWooSecret('');
              await refresh();
            }, 'WooCommerce website linked. Credentials stay encrypted.');
          }}
        >
          <label className="span-2">
            WooCommerce URL
            <input aria-label="WooCommerce store URL" value={wooUrl} onChange={(e) => setWooUrl(e.target.value)} placeholder="https://shop.example.com" />
          </label>
          <label>
            Consumer key
            <input aria-label="WooCommerce consumer key" value={wooKey} onChange={(e) => setWooKey(e.target.value)} />
          </label>
          <label>
            Consumer secret
            <input aria-label="WooCommerce consumer secret" type="password" value={wooSecret} onChange={(e) => setWooSecret(e.target.value)} />
          </label>
          <button type="submit" className="list-btn-primary" aria-label="Save WooCommerce connector">
            Save WooCommerce
          </button>
        </form>
        {!connectors.length ? (
          <EmptyState title="No website connector" detail="Save a WooCommerce https URL and keys to import unpublished catalog and orders." />
        ) : null}
        {connectors.map((row) => (
          <article key={row.id} className="ecom-domain">
            <div className="ecom-domain-top">
              <p className="ecom-domain-host">{row.platform}</p>
              <StatusChip value={row.enabled ? 'active' : 'inactive'} />
            </div>
            <p className="muted ecom-dns">
              {row.store_url || 'No store URL'}
              {row.credentials_configured ? ' · credentials saved' : ' · credentials missing'}
              {row.last_error ? ` · ${row.last_error}` : ''}
            </p>
            {row.implemented ? (
              <div className="ecom-row-actions">
                <button type="button" aria-label={`Sync ${row.platform} products`} onClick={() => void run(`sync-p-${row.id}`, async () => { await api(`/ecommerce/connectors/${row.id}/sync`, { method: 'POST', body: JSON.stringify({ kind: 'products' }) }); await refresh(); }, 'Product sync queued.')}>
                  Sync products
                </button>
                <button type="button" aria-label={`Sync ${row.platform} orders`} onClick={() => void run(`sync-o-${row.id}`, async () => { await api(`/ecommerce/connectors/${row.id}/sync`, { method: 'POST', body: JSON.stringify({ kind: 'orders' }) }); await refresh(); }, 'Order sync queued.')}>
                  Sync orders
                </button>
                <button
                  type="button"
                  aria-label={`Disconnect ${row.platform} website`}
                  onClick={() =>
                    void run(`disc-${row.id}`, async () => {
                      await api('/ecommerce/connectors', {
                        method: 'PATCH',
                        body: JSON.stringify({ platform: row.platform, enabled: false }),
                      });
                      setWooUrl('');
                      setWooKey('');
                      setWooSecret('');
                      await refresh();
                    }, 'Website connector disconnected.')
                  }
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <p className="muted">Not implemented</p>
            )}
          </article>
        ))}
        {jobs.map((job) => (
          <p key={job.id} className="muted">
            {job.kind} {job.status} attempt {job.attempt}
            {job.error ? ` · ${job.error}` : ''}
          </p>
        ))}
        <button type="button" aria-label="Retry failed connector jobs" onClick={() => void run('retry', async () => { await api('/ecommerce/connectors/retry', { method: 'POST' }); await refresh(); }, 'Failed jobs retried.')}>
          Retry failed jobs
        </button>
      </section>
      ) : null}
    </main>
  );
}
