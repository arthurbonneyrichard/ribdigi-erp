'use client';

import { useEffect, useState } from 'react';
import FormModal from '../../../components/FormModal';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { normalizeIndustry } from '../../../lib/industries';
import { getMe } from '../../../lib/meCache';
import { isHotelIndustry } from '../../../lib/tenantNav';
import { downloadAttachment } from '../../../lib/attachments';
import { AmountField } from '../../../components/AmountField';
import { formatMoney } from '../../../lib/format';
import { useStoreContext } from '../../../lib/storeContext';

type TaxRate = {
  id: string;
  name: string;
  rate: number;
  tax_type: string;
  pricing_mode: string;
  components?: { code: string; name: string; rate: number; basis: string }[] | null;
  is_reverse_charge?: boolean;
  is_default: boolean;
  is_active: boolean;
};

export default function Page() {
  const [rows, setRows] = useState<TaxRate[]>([]);
  const [hotelOps, setHotelOps] = useState(false);
  const [restaurantOps, setRestaurantOps] = useState(false);
  useEffect(() => {
    getMe()
      .then((r) => {
        setHotelOps(isHotelIndustry(r.data?.industry));
        setRestaurantOps(normalizeIndustry(r.data?.industry) === 'restaurant');
      })
      .catch(() => undefined);
  }, []);
  const [report, setReport] = useState<any>(null);
  const [filing, setFiling] = useState<any>(null);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [stores, setStores] = useState<any[]>([]);
  const [name, setName] = useState('Standard VAT');
  const [rate, setRate] = useState('15');
  const [taxType, setTaxType] = useState('vat');
  const [pricingMode, setPricingMode] = useState('exclusive');
  const [reverseCharge, setReverseCharge] = useState(false);
  const [componentsJson, setComponentsJson] = useState('');
  const [calcAmount, setCalcAmount] = useState('100');
  const [calcResult, setCalcResult] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [taxRateManageFilter, setTaxRateManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [filingJurisdictionFilter, setFilingJurisdictionFilter] = useState<'' | 'GH'>('');
  const [rateBusy, setRateBusy] = useState(false);
  const [taxAddOpen, setTaxAddOpen] = useState(false);

  const managedRates = rows.filter((r) => {
    if (taxRateManageFilter === 'all') return true;
    const active = r.is_active !== false;
    return taxRateManageFilter === 'inactive' ? !active : active;
  });

  function qs() {
    const params = new URLSearchParams();
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    // trim so UuidIdValue Query store_id does not 422
    const storeTrim = storeId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (filingJurisdictionFilter) params.set('jurisdiction', filingJurisdictionFilter);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function refresh() {
    const q = qs();
    const [rates, taxReport, filingPack] = await Promise.all([
      api('/tax/rates'),
      api(`/reports/tax${q}`),
      api(`/reports/tax/filing${q}`),
    ]);
    setRows(rates.data || []);
    setReport(taxReport.data);
    setFiling(filingPack.data);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    api('/stores')
      .then((r) => {
        setStores(r.data || []);
        if (ctxStoreId && (r.data || []).some((s: any) => s.id === ctxStoreId)) {
          setStoreId(ctxStoreId);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (ctxStoreId) setStoreId(ctxStoreId);
  }, [ctxStoreId]);
  async function createRate() {
    if (rateBusy) return;
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError('Tax rate name is required.');
      setMessage('');
      return;
    }
    setError('');
    setMessage('');
    setRateBusy(true);
    try {
      let components = null;
      if (componentsJson.trim()) {
        const parsed = JSON.parse(componentsJson);
        if (!Array.isArray(parsed)) throw new Error('Components must be a JSON array');
        // Omit blank code/name so schema omit/`null` path applies (blank → 422).
        components = parsed.map((c: Record<string, unknown>) => {
          if (!c || typeof c !== 'object') return c;
          const next: Record<string, unknown> = { ...c };
          if (typeof next.code === 'string') {
            const code = next.code.trim();
            next.code = code || null;
          }
          if (typeof next.name === 'string') {
            const label = next.name.trim();
            next.name = label || null;
          }
          return next;
        });
      }
      await api('/tax/rates', {
        method: 'POST',
        body: JSON.stringify({
          name: trimmedName,
          rate: Number(rate),
          tax_type: taxType,
          pricing_mode: pricingMode,
          components,
          is_reverse_charge: reverseCharge,
          is_default: rows.length === 0,
          is_active: true,
        }),
      });
      setMessage('Tax rate created');
      setComponentsJson('');
      setReverseCharge(false);
      setTaxAddOpen(false);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRateBusy(false);
    }
  }

  async function makeDefault(id: string) {
    setError('');
    try {
      await api(`/tax/rates/${id}/default`, { method: 'POST' });
      setMessage('Default rate updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setRateActive(row: TaxRate, is_active: boolean) {
    setError('');
    setMessage('');
    try {
      await api(`/tax/rates/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(is_active ? `Tax rate ${row.name} activated` : `Tax rate ${row.name} deactivated`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function calculate() {
    setError('');
    try {
      const r = await api('/tax/calculate', {
        method: 'POST',
        body: JSON.stringify({ amount: Number(calcAmount) }),
      });
      setCalcResult(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadFiling(format: 'csv' | 'pdf' | 'xlsx', reportType: 'tax_filing' | 'tax_filing_gh' = 'tax_filing') {
    setError('');
    setMessage('');
    try {
      const params = new URLSearchParams();
      params.set('report_type', reportType);
      params.set('format', format);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      const storeTrim = storeId.trim();
      if (storeTrim) params.set('store_id', storeTrim);
      if (reportType === 'tax_filing_gh') {
        params.set('jurisdiction', filingJurisdictionFilter || 'GH');
      } else if (filingJurisdictionFilter) {
        params.set('jurisdiction', filingJurisdictionFilter);
      }
      await downloadAttachment(`/reports/export?${params}`, `${reportType}.${format}`);
      setMessage(
        reportType === 'tax_filing_gh'
          ? `Ghana VAT return ${format.toUpperCase()} downloaded`
          : `Filing pack ${format.toUpperCase()} downloaded`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  const boxes = filing?.filing_boxes?.boxes || [];

  function taxKindLabel(kind: string) {
    if (kind === 'vat') return 'VAT';
    if (kind === 'gst') return 'GST';
    if (kind === 'sales_tax') return 'Sales tax';
    if (kind === 'custom') return 'Custom';
    return kind;
  }

  return (
    <div className={restaurantOps ? 'work tax-page' : 'work'}>
      <PageHeader
        title="Tax"
        subtitle={
          hotelOps
            ? 'Room folio lines are nights times the nightly rate. A tax rate stored here is not added to that room line. It can apply to other charges. Changing a rate does not change past invoices.'
            : restaurantOps
              ? 'The default rate applies unless a menu item or bill line uses a different one. Inclusive means the price already contains tax; exclusive means tax is added on top. Changing a rate does not change past bills. Table orders stay on the restaurant desk until a bill is posted.'
              : 'The default rate applies unless a product or line uses a different one. Inclusive means the price already contains tax; exclusive means tax is added on top. Changing a rate does not change past invoices. A Ghana VAT summary is available for export when your tax country is Ghana.'
        }
        actions={
          <button type="button" className="list-btn-primary" onClick={() => setTaxAddOpen(true)} aria-label="Add a tax rate">
            Add a tax rate
          </button>
        }
      />
      {error && <p className="erp-banner err" role="alert">{error}</p>}
      {message && <p className="erp-banner ok" role="status">{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Period</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            title="From date"
            aria-label="Tax from date"
          />
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            title="To date"
            aria-label="Tax to date"
          />
          <select
            value={storeId}
            onChange={(e) => {
              setStoreId(e.target.value);
              setCtxStoreId(e.target.value);
            }}
            aria-label="Tax report store filter"
          >
            <option value="">{hotelOps ? 'All locations' : 'All stores'}</option>
            {stores
              .filter((s) => s.is_active !== false)
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
          <select
            value={filingJurisdictionFilter}
            onChange={(e) => {
              const next = e.target.value as '' | 'GH';
              setFilingJurisdictionFilter(next);
            }}
            aria-label="Tax filing jurisdiction filter"
          >
            <option value="">Tenant default</option>
            {(filing?.jurisdiction === 'GH' || filingJurisdictionFilter === 'GH') && (
              <option value="GH">GH — Ghana VAT</option>
            )}
          </select>
          <button
            onClick={() => refresh().catch((err) => setError(err.message))}
            aria-label="Apply tax period filters"
          >
            Apply
          </button>
        </div>
      </div>

      <div className="work-pair">
        {taxAddOpen ? (
        <FormModal
          title="Add a tax rate"
          busy={rateBusy}
          dirty={Boolean(name.trim() && name.trim() !== 'Standard VAT') || rate !== '15' || Boolean(componentsJson.trim())}
          onClose={() => setTaxAddOpen(false)}
        >
          <div style={{ display: 'grid', gap: 8 }}>
            <label>
              Name
            <input aria-label="Tax rate name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Standard VAT" />
            </label>
            <label>
              Rate %
            <input value={rate} onChange={(e) => setRate(e.target.value)} placeholder="Rate %" aria-label="Tax rate percent" />
            </label>
            <label>
              Kind
            <select
              value={taxType}
              onChange={(e) => setTaxType(e.target.value)}
              aria-label="Tax rate type"
            >
              <option value="vat">VAT</option>
              <option value="gst">GST</option>
              <option value="sales_tax">Sales tax</option>
              <option value="custom">Custom</option>
            </select>
            </label>
            <label>
              How prices work
            <select
              value={pricingMode}
              onChange={(e) => setPricingMode(e.target.value)}
              aria-label="Tax pricing mode"
            >
              <option value="exclusive">Exclusive — tax added on top of the price</option>
              <option value="inclusive">Inclusive — price already includes tax</option>
            </select>
            </label>
            <label className="muted">
              <input
                type="checkbox"
                checked={reverseCharge}
                onChange={(e) => setReverseCharge(e.target.checked)}
                aria-label="Tax reverse charge"
              />{' '}
              Buyer self-assesses (reverse charge)
            </label>
            <details>
              <summary className="muted">Advanced: compound components</summary>
            <textarea
              value={componentsJson}
              onChange={(e) => setComponentsJson(e.target.value)}
              rows={3}
              placeholder='Only if you use split GST components'
              aria-label="Tax rate components JSON"
              title="Advanced: the parts of this tax in JSON, e.g. [{&quot;name&quot;:&quot;NHIL&quot;,&quot;rate&quot;:2.5}]"
            />
            </details>
            <button type="button" aria-label="Add tax rate" onClick={createRate} disabled={!name.trim() || rateBusy}>
              {rateBusy ? 'Saving…' : 'Add rate'}
            </button>
          </div>
        </FormModal>
        ) : null}
        <div className="card">
          <h3>Preview with default rate</h3>
          <p className="muted">An estimate. The amount on a saved sale or bill is final.</p>
          <AmountField
            value={calcAmount}
            onChange={(e) => setCalcAmount(e.target.value)}
            aria-label="Tax calculator amount"
          />
          <button onClick={calculate} style={{ marginTop: 8 }} aria-label="Calculate tax">
            Calculate with default rate
          </button>
          {calcResult && (
            <p className="muted" style={{ marginTop: 8 }}>
              Before tax {formatMoney(calcResult.net)} · Tax {formatMoney(calcResult.tax)} · Customer pays {formatMoney(calcResult.gross)} (
              {calcResult.rate}% {calcResult.pricing_mode === 'inclusive' ? 'included in price' : 'added on top'}
              {calcResult.is_reverse_charge ? ' · reverse charge' : ''})
            </p>
          )}
        </div>
        <div className="card">
          <h3>This period{report?.store_name ? ` · ${report.store_name}` : ''}</h3>
          <p>VAT collected on sales: {report ? formatMoney(report.output_tax ?? 0) : '—'}</p>
          <p className="muted">
            {restaurantOps ? 'Bills' : 'Invoices'} {formatMoney(report?.output_tax_invoices ?? 0)} · {hotelOps ? 'Shop till' : restaurantOps ? 'Restaurant till' : 'Till'} {formatMoney(report?.output_tax_pos ?? 0)}
            {report?.reverse_charge_tax
              ? ` · Reverse charge (customer pays) ${formatMoney(report.reverse_charge_tax)}`
              : ''}
          </p>
          {restaurantOps ? (
            <>
              <p className="muted">A restaurant till return comes off this till tax. The original receipt stays on the till report.</p>
              <p className="muted">A completed restaurant bill is included in this bill tax.</p>
            </>
          ) : null}
          <p>VAT on purchases you can claim back: {report ? formatMoney(report.input_tax ?? 0) : '—'}</p>
          <p className="muted">
            {report?.input_tax_source === 'purchase_orders'
              ? 'Worked out from purchase orders, because no supplier bills are recorded for this period.'
              : 'Worked out from supplier bills.'}
          </p>
          <div className="kpi">{report ? formatMoney(report.net_tax_payable ?? 0) : '—'}</div>
          <p className="muted">VAT to pay for this period (a negative amount is a refund)</p>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Filing pack</h3>
        <p className="muted">
          Boxes for your records
          {filing?.store_name ? ` · ${filing.store_name}` : ''}
          {filing?.jurisdiction === 'GH'
            ? ' · Ghana VAT return mapping is available below (not sent to GRA automatically)'
            : filing?.jurisdiction
              ? ` · Company jurisdiction: ${filing.jurisdiction}`
              : ''}
          {filing?.tax_registration_number
            ? ` · TIN ${filing.tax_registration_number}`
            : ' · TIN not set (set on Company)'}
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <button onClick={() => downloadFiling('csv')} aria-label="Export tax filing CSV">
            Export CSV
          </button>
          <button onClick={() => downloadFiling('xlsx')} aria-label="Export tax filing Excel">
            Export Excel
          </button>
          <button onClick={() => downloadFiling('pdf')} aria-label="Export tax filing PDF">
            Export PDF
          </button>
          {filing?.jurisdiction === 'GH' && (
            <>
          <button
            onClick={() => downloadFiling('xlsx', 'tax_filing_gh')}
            aria-label="Export Ghana VAT Excel"
          >
            Export Ghana VAT (XLSX)
          </button>
          <button
            onClick={() => downloadFiling('csv', 'tax_filing_gh')}
            aria-label="Export Ghana VAT CSV"
          >
            Export Ghana VAT (CSV)
          </button>
          <button
            onClick={() => downloadFiling('pdf', 'tax_filing_gh')}
            aria-label="Export Ghana VAT PDF"
          >
            Export Ghana VAT (PDF)
          </button>
            </>
          )}
        </div>
        {!!filing?.government?.warnings?.length && (
          <p style={{ color: '#b45309' }}>{filing.government.warnings.join(' · ')}</p>
        )}
        {filing?.government?.boxes?.length ? (
          <>
            <h4 style={{ marginTop: 8 }}>{filing.government.template_name || 'Government return'}</h4>
            <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Box</th>
                  <th>Label</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {filing.government.boxes.map((b: any) => (
                  <tr key={b.code || b.box}>
                    <td>{b.box}</td>
                    <td>{b.label}</td>
                    <td>{b.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </>
        ) : null}
        <h4 style={{ marginTop: 12 }}>Neutral boxes</h4>
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Box</th>
              <th>Label</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {boxes.map((b: any) => (
              <tr key={b.box}>
                <td>{b.box}</td>
                <td>{b.label}</td>
                <td>{b.amount}</td>
              </tr>
            ))}
            {!boxes.length && (
              <tr>
                <td colSpan={3} className="muted">
                  No filing data for period
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>
          Output lines: {filing?.schedules?.output?.length ?? 0} · Input lines:{' '}
          {filing?.schedules?.input?.length ?? 0}
        </p>
      </div>

      <select
        value={taxRateManageFilter}
        onChange={(e) => setTaxRateManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
        title="Filter manage tax rate list by status"
        aria-label="Tax rate status filter"
        style={{ marginTop: 16, marginBottom: 8 }}
      >
        <option value="all">All statuses</option>
        <option value="active">Active only</option>
        <option value="inactive">Inactive only</option>
      </select>
      <div className={restaurantOps ? 'list-table-wrap rest-tax-table' : undefined}>
      <table className="table">
        {restaurantOps ? (
          <colgroup>
            <col style={{ width: '34%' }} />
            <col style={{ width: '14%' }} />
            <col style={{ width: '30%' }} />
            <col style={{ width: '22%' }} />
          </colgroup>
        ) : null}
        <thead>
          <tr>
            {restaurantOps ? <th>Rate</th> : <th>Name</th>}
            {restaurantOps ? <th>Percent</th> : <th>Type</th>}
            {restaurantOps ? null : <th>Rate</th>}
            {restaurantOps ? <th>On the price</th> : <th>Mode</th>}
            {restaurantOps ? null : <th>RC</th>}
            {restaurantOps ? null : <th>Components</th>}
            {restaurantOps ? null : <th>Default</th>}
            {restaurantOps ? null : <th>Active</th>}
            {restaurantOps ? <th>Actions</th> : <th></th>}
          </tr>
        </thead>
        <tbody>
          {managedRates.map((r) => (
            <tr key={r.id}>
              {restaurantOps ? (
                <td data-label="Rate">
                  {r.name}
                  <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                    {taxKindLabel(r.tax_type)}
                    {r.is_default ? ' · Default rate' : ''}
                    {r.is_active === false ? ' · Not in use' : ''}
                  </span>
                </td>
              ) : (
                <td>{r.name}</td>
              )}
              {restaurantOps ? (
                <td data-label="Percent">{r.rate}%</td>
              ) : (
                <td>{r.tax_type}</td>
              )}
              {restaurantOps ? null : <td>{r.rate}%</td>}
              {restaurantOps ? (
                <td data-label="On the price">
                  {r.pricing_mode === 'inclusive' ? 'Included in price' : 'Added on top'}
                  <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                    {r.is_reverse_charge
                      ? 'Customer pays the tax'
                      : r.components?.length
                        ? ''
                        : 'No extra parts'}
                    {r.components?.length
                      ? `${r.is_reverse_charge ? ' · ' : ''}${r.components.map((c) => `${c.code} ${c.rate}%`).join(' + ')}`
                      : ''}
                  </span>
                </td>
              ) : (
                <td>{r.pricing_mode === 'inclusive' ? 'Included in price' : 'Added on top'}</td>
              )}
              {restaurantOps ? null : <td>{String(!!r.is_reverse_charge)}</td>}
              {restaurantOps ? null : (
              <td className="muted">
                {r.components?.length
                  ? r.components.map((c) => `${c.code}:${c.rate}%`).join(' + ')
                  : '—'}
              </td>
              )}
              {restaurantOps ? null : <td>{String(r.is_default)}</td>}
              {restaurantOps ? null : (
              <td>
                {r.is_active === false ? 'no' : 'yes'}
                {r.is_active === false ? ' [inactive]' : ''}
              </td>
              )}
              <td data-label="Actions" style={restaurantOps ? undefined : { display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {r.is_active !== false && !r.is_default && (
                  <button type="button" onClick={() => makeDefault(r.id)} aria-label={`Set default tax rate ${r.id}`}>
                    Set default
                  </button>
                )}
                <button
                  type="button"
                  className={r.is_active === false ? 'btn-ok' : 'btn-danger'}
                  onClick={() => setRateActive(r, r.is_active === false)}
                  aria-label={
                    r.is_active === false
                      ? `Activate tax rate ${r.id}`
                      : `Deactivate tax rate ${r.id}`
                  }
                >
                  {r.is_active === false ? 'Activate' : 'Deactivate'}
                </button>
              </td>
            </tr>
          ))}
          {managedRates.length === 0 && restaurantOps && (
            <tr>
              <td colSpan={4} className="muted">
                {taxRateManageFilter === 'all'
                  ? 'No tax rates yet. Add a rate when you are ready to charge tax on a bill.'
                  : 'No rates for this filter. Choose All statuses to see every rate.'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>
    </div>
  );
}
