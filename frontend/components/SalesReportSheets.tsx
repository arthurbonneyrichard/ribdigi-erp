'use client';

import { plainLabel } from '../lib/format';

const PAGE_SIZE = 50;

export const SALES_RETURNS_NOTE =
  'Completed sales only. Header discounts are already taken out of revenue. Posted returns are listed on Sales returns and are not subtracted here.';

type Props = {
  view: string;
  data: any;
  sectionErrors: Record<string, string>;
  multiStore: boolean;
  fmtMoney: (value: unknown) => string;
  formatWhen: (value?: string | Date | null) => string;
  page: number;
  onPage: (page: number) => void;
};

function note(text?: string) {
  return <p className="muted">{text || SALES_RETURNS_NOTE}</p>;
}

function emptyRow(cols: number, text: string) {
  return (
    <tr>
      <td colSpan={cols} className="muted">
        {text}
      </td>
    </tr>
  );
}

function pager(count: number, page: number, onPage: (page: number) => void) {
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  if (count <= PAGE_SIZE) return null;
  return (
    <p className="muted no-print">
      <button type="button" disabled={page <= 0} onClick={() => onPage(page - 1)} aria-label="Previous report page">
        Previous
      </button>{' '}
      Page {page + 1} of {pages}{' '}
      <button
        type="button"
        disabled={page + 1 >= pages}
        onClick={() => onPage(page + 1)}
        aria-label="Next report page"
      >
        Next
      </button>
    </p>
  );
}

function slicePage<T>(rows: T[], page: number): T[] {
  const start = page * PAGE_SIZE;
  return rows.slice(start, start + PAGE_SIZE);
}

export default function SalesReportSheets({
  view,
  data,
  sectionErrors,
  multiStore,
  fmtMoney,
  formatWhen,
  page,
  onPage,
}: Props) {
  if (view === 'summary') {
    const days = Array.isArray(data?.monthly?.daily) ? data.monthly.daily : [];
    const quiet =
      !sectionErrors.daily &&
      !sectionErrors.monthly &&
      Number(data?.daily?.total_revenue || 0) === 0 &&
      Number(data?.monthly?.total_revenue || 0) === 0 &&
      days.length === 0;
    const monthLabel =
      data?.monthly?.year && data?.monthly?.month
        ? `${data.monthly.year}-${String(data.monthly.month).padStart(2, '0')}`
        : 'This month';
    return (
      <>
        {note(data?.daily?.returns_note)}
        {sectionErrors.daily ? <p style={{ color: '#b91c1c' }}>{sectionErrors.daily}</p> : null}
        {sectionErrors.monthly ? <p style={{ color: '#b91c1c' }}>{sectionErrors.monthly}</p> : null}
        {quiet ? <p className="muted">No sales for this day or month.</p> : null}
        <div className="grid">
          <div className="card">
            <h3>
              {data?.daily?.date ? `Day · ${data.daily.date}` : 'Today'}
              {multiStore && data?.daily?.store_name ? ` · ${data.daily.store_name}` : ''}
            </h3>
            <p>Revenue: {fmtMoney(data?.daily?.total_revenue)}</p>
            <p>Discounts: {fmtMoney(data?.daily?.discounts)}</p>
            <p>
              Invoices: {data?.daily?.invoice_count ?? 0}
              {' · '}
              Register: {data?.daily?.pos_count ?? 0}
            </p>
          </div>
          <div className="card">
            <h3>
              {monthLabel}
              {multiStore && data?.monthly?.store_name ? ` · ${data.monthly.store_name}` : ''}
            </h3>
            <p>Revenue: {fmtMoney(data?.monthly?.total_revenue)}</p>
            {data?.monthly?.change_pct != null ? (
              <p>
                Change on last month: {Number(data.monthly.change_pct) >= 0 ? '+' : ''}
                {data.monthly.change_pct}%
              </p>
            ) : null}
          </div>
        </div>
        <h3 style={{ marginTop: 16 }}>Days in this month</h3>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {days.map((row: any) => (
                <tr key={row.date}>
                  <td>{row.date}</td>
                  <td>{fmtMoney(row.revenue)}</td>
                </tr>
              ))}
              {!days.length ? emptyRow(2, 'No sales on the days in this month.') : null}
            </tbody>
          </table>
        </div>
      </>
    );
  }

  if (view === 'products' || view === 'category' || view === 'brand') {
    const products = data?.products?.products || data?.products || [];
    const pack = data?.products && !Array.isArray(data.products) ? data.products : data;
    const rows =
      view === 'category'
        ? pack?.categories || []
        : view === 'brand'
          ? pack?.brands || []
          : Array.isArray(products)
            ? products
            : pack?.products || [];
    const nameKey = view === 'category' ? 'category_name' : view === 'brand' ? 'brand_name' : 'name';
    const showProfit = pack?.include_cost === true;
    const cols = (view === 'products' ? 5 : 3) + (showProfit ? 1 : 0);
    return (
      <>
        {note(pack?.returns_note)}
        {sectionErrors.products || sectionErrors.report ? (
          <p style={{ color: '#b91c1c' }}>{sectionErrors.products || sectionErrors.report}</p>
        ) : null}
        <p className="muted">
          Qty {pack?.total_quantity ?? 0} · revenue {fmtMoney(pack?.total_revenue)}
          {showProfit && pack?.total_profit != null ? ` · profit ${fmtMoney(pack.total_profit)}` : ''}
        </p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{view === 'category' ? 'Category' : view === 'brand' ? 'Brand' : 'Product'}</th>
                {view === 'products' ? <th>SKU</th> : null}
                {view === 'products' ? <th>Category</th> : null}
                <th>Qty</th>
                <th>Revenue</th>
                {showProfit ? <th>Profit</th> : null}
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((row: any) => (
                <tr key={row.product_id || row.category_id || row.brand_id || row[nameKey]}>
                  <td>{row[nameKey] || '—'}</td>
                  {view === 'products' ? <td>{row.sku || '—'}</td> : null}
                  {view === 'products' ? <td>{row.category_name || '—'}</td> : null}
                  <td>{row.quantity}</td>
                  <td>{fmtMoney(row.revenue)}</td>
                  {showProfit ? <td>{row.profit != null ? fmtMoney(row.profit) : '—'}</td> : null}
                </tr>
              ))}
              {!rows.length ? emptyRow(cols, 'No product sales for this period.') : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'returns') {
    const rows = Array.isArray(data?.returns) ? data.returns : [];
    const pack = data;
    return (
      <>
        <p className="muted">Posted returns are not subtracted from the other sales reports.</p>
        {sectionErrors.returns ? <p style={{ color: '#b91c1c' }}>{sectionErrors.returns}</p> : null}
        <p className="muted">
          {pack?.return_count ?? 0} returns · total {fmtMoney(pack?.total_amount)} · posted{' '}
          {fmtMoney(pack?.posted_amount)} · qty {pack?.total_quantity ?? 0}
        </p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Return</th>
                <th>Customer</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((ret: any) => (
                <tr key={ret.id}>
                  <td>{ret.return_number}</td>
                  <td>{ret.customer_name}</td>
                  <td>{plainLabel(ret.reason)}</td>
                  <td>{plainLabel(ret.status)}</td>
                  <td>{ret.quantity}</td>
                  <td>{fmtMoney(ret.total_amount)}</td>
                </tr>
              ))}
              {!rows.length ? emptyRow(6, 'No sales returns for this period.') : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'transactions' || view === 'pos' || view === 'quotations') {
    const rows = data?.rows || [];
    const showStore = multiStore && view !== 'quotations';
    let cols = 4;
    if (view === 'pos') cols += 2;
    else cols += 1;
    if (showStore) cols += 1;
    return (
      <>
        {note(data?.returns_note)}
        {data?.truncated ? (
          <p className="muted">Showing the latest {rows.length} of {data.count}. Narrow the dates to see the rest. Totals include every row in this filter.</p>
        ) : null}
        <p className="muted">
          {data?.count ?? rows.length} · total {fmtMoney(data?.total)}
        </p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>{view === 'pos' ? 'Receipt' : view === 'quotations' ? 'Quotation' : 'Number'}</th>
                <th>Customer</th>
                {view === 'quotations' ? <th>Status</th> : null}
                {view === 'pos' ? <th>Cashier</th> : null}
                {view === 'pos' ? <th>Payment</th> : null}
                {view !== 'quotations' && view !== 'pos' ? <th>Source</th> : null}
                <th>Total</th>
                {showStore ? <th>Store</th> : null}
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((row: any) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.when)}</td>
                  <td>{row.number}</td>
                  <td>{row.customer}</td>
                  {view === 'quotations' ? <td>{plainLabel(row.status)}</td> : null}
                  {view === 'pos' ? <td>{row.cashier || '—'}</td> : null}
                  {view === 'pos' ? <td>{plainLabel(row.payment_method)}</td> : null}
                  {view !== 'quotations' && view !== 'pos' ? <td>{plainLabel(row.source)}</td> : null}
                  <td>{fmtMoney(row.total)}</td>
                  {showStore ? <td>{row.store_name || '—'}</td> : null}
                </tr>
              ))}
              {!rows.length
                ? emptyRow(cols, view === 'quotations' ? 'No quotations in this period.' : 'No sales in this period.')
                : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'lines') {
    const rows = data?.lines || [];
    const showCost = Boolean(data?.include_cost);
    const showStore = multiStore;
    const cols = 15 + (showStore ? 1 : 0) + (showCost ? 2 : 0);
    return (
      <>
        {note(data?.returns_note)}
        {data?.truncated ? (
          <p className="muted">Showing the latest {rows.length} lines of {data.count}. Totals include every line in this filter.</p>
        ) : null}
        <p className="muted">
          Qty {data?.total_quantity ?? 0} · sales {fmtMoney(data?.total_sales)} · discount {fmtMoney(data?.total_discount)} · tax{' '}
          {fmtMoney(data?.total_tax)}
          {showCost ? ` · profit ${fmtMoney(data?.total_profit)}` : ''}
        </p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Number</th>
                <th>Product</th>
                <th>SKU</th>
                <th>Barcode</th>
                <th>Category</th>
                <th>Brand</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Discount</th>
                <th>Tax</th>
                <th>Sales total</th>
                <th>Customer</th>
                <th>Cashier</th>
                <th>Payment</th>
                {showStore ? <th>Store</th> : null}
                {showCost ? <th>Cost</th> : null}
                {showCost ? <th>Profit</th> : null}
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((row: any) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.when)}</td>
                  <td>{row.number}</td>
                  <td>{row.product}</td>
                  <td>{row.sku || '—'}</td>
                  <td>{row.barcode || '—'}</td>
                  <td>{row.category || '—'}</td>
                  <td>{row.brand || '—'}</td>
                  <td>{row.quantity}</td>
                  <td>{fmtMoney(row.unit_price)}</td>
                  <td>{fmtMoney(row.discount)}</td>
                  <td>{fmtMoney(row.tax)}</td>
                  <td>{fmtMoney(row.sales_total)}</td>
                  <td>{row.customer || '—'}</td>
                  <td>{row.cashier || '—'}</td>
                  <td>{plainLabel(row.payment_method)}</td>
                  {showStore ? <td>{row.store_name || '—'}</td> : null}
                  {showCost ? <td>{row.cost == null ? '—' : fmtMoney(row.cost)}</td> : null}
                  {showCost ? <td>{row.profit == null ? '—' : fmtMoney(row.profit)}</td> : null}
                </tr>
              ))}
              {!rows.length ? emptyRow(cols, 'No products sold in this period.') : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'payments') {
    const rows = data?.rows || [];
    return (
      <>
        {note(data?.returns_note)}
        <p className="muted">Total {fmtMoney(data?.total)}. Unpaid balances are labelled On account.</p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Payment method</th>
                <th>Count</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any) => (
                <tr key={row.payment_method}>
                  <td>{plainLabel(row.payment_method)}</td>
                  <td>{row.count}</td>
                  <td>{fmtMoney(row.amount)}</td>
                </tr>
              ))}
              {!rows.length ? emptyRow(3, 'No payments in this period.') : null}
            </tbody>
          </table>
        </div>
      </>
    );
  }

  if (view === 'discounts') {
    const rows = data?.rows || [];
    return (
      <>
        {note(data?.returns_note)}
        <p className="muted">
          Invoice discounts {fmtMoney(data?.header_discounts)} · line discounts {fmtMoney(data?.line_discounts)} · total{' '}
          {fmtMoney(data?.total)}
        </p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Number</th>
                <th>Kind</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((row: any) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.when)}</td>
                  <td>{row.number}</td>
                  <td>{row.kind}</td>
                  <td>{fmtMoney(row.amount)}</td>
                </tr>
              ))}
              {!rows.length ? emptyRow(4, 'No discounts in this period.') : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'credit') {
    const parties = data?.parties || [];
    const documents = data?.documents || [];
    return (
      <>
        {note(data?.returns_note)}
        <p className="muted">Outstanding {fmtMoney(data?.total_due)}</p>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {parties.map((row: any) => (
                <tr key={row.party_id}>
                  <td>{row.name}</td>
                  <td>{fmtMoney(row.total_due)}</td>
                </tr>
              ))}
              {!parties.length ? emptyRow(2, 'No outstanding customer balances.') : null}
            </tbody>
          </table>
        </div>
        {documents.length ? (
          <>
            <h3 style={{ marginTop: 16 }}>Open invoices</h3>
            <div className="list-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Customer</th>
                    <th>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {slicePage(documents, page).map((row: any) => (
                    <tr key={row.id}>
                      <td>{row.document_number}</td>
                      <td>{row.party_name}</td>
                      <td>{fmtMoney(row.balance_due)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pager(documents.length, page, onPage)}
          </>
        ) : null}
      </>
    );
  }

  return null;
}
