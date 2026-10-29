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
  hotel?: boolean;
  restaurant?: boolean;
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
  hotel = false,
  restaurant = false,
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
            {restaurant ? (
              <>
                <p className="muted">A restaurant till discount is included in this discount. The menu amount stays.</p>
                <p className="muted">A restaurant bill with no store stays off a store filter.</p>
                <p className="muted">A restaurant till return with no store stays off a store filter.</p>
              </>
            ) : null}
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
    if (restaurant) {
      const menuCols = 3 + (showProfit ? 1 : 0);
      const emptyMenu =
        view === 'category'
          ? 'No category sales for this period.'
          : view === 'brand'
            ? 'No brand sales for this period.'
            : 'No menu item sales for this period.';
      return (
        <>
          <p className="muted">A restaurant till return comes off menu items sold. The original receipt stays on the till report.</p>
          {sectionErrors.products || sectionErrors.report ? (
            <p style={{ color: '#b91c1c' }}>{sectionErrors.products || sectionErrors.report}</p>
          ) : null}
          <p className="muted">
            Quantity {pack?.total_quantity ?? 0}
            {' · Revenue '}
            {fmtMoney(pack?.total_revenue)}
            {showProfit && pack?.total_profit != null ? <> · Profit {fmtMoney(pack.total_profit)}</> : null}
          </p>
          <p className="muted">A restaurant till tax stays off this menu amount. The till receipt keeps the tax.</p>
          <div className="list-table-wrap rest-fit-table rest-menu-sales">
            <table className="table">
              <colgroup>
                <col style={{ width: showProfit ? '40%' : '46%' }} />
                <col style={{ width: showProfit ? '18%' : '22%' }} />
                <col style={{ width: showProfit ? '22%' : '32%' }} />
                {showProfit ? <col style={{ width: '20%' }} /> : null}
              </colgroup>
              <thead>
                <tr>
                  <th>{view === 'category' ? 'Category' : view === 'brand' ? 'Brand' : 'Menu item'}</th>
                  <th>Qty</th>
                  <th>Revenue</th>
                  {showProfit ? <th>Profit</th> : null}
                </tr>
              </thead>
              <tbody>
                {slicePage(rows, page).map((row: any) => (
                  <tr key={row.product_id || row.category_id || row.brand_id || row[nameKey]}>
                    <td data-label={view === 'category' ? 'Category' : view === 'brand' ? 'Brand' : 'Menu item'}>
                      {row[nameKey] || (view === 'products' ? 'No menu item' : view === 'category' ? 'No category' : 'No brand')}
                      {view === 'products' ? (
                        <>
                          <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                            {row.sku || 'No code'}
                          </span>
                          <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                            {row.category_name || 'No category'}
                          </span>
                        </>
                      ) : null}
                    </td>
                    <td data-label="Qty">{row.quantity}</td>
                    <td data-label="Revenue">{fmtMoney(row.revenue)}</td>
                    {showProfit ? (
                      <td data-label="Profit">{row.profit != null ? fmtMoney(row.profit) : 'No profit'}</td>
                    ) : null}
                  </tr>
                ))}
                {!rows.length ? emptyRow(menuCols, emptyMenu) : null}
              </tbody>
            </table>
          </div>
          {pager(rows.length, page, onPage)}
        </>
      );
    }
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
                <th>{view === 'category' ? 'Category' : view === 'brand' ? 'Brand' : hotel ? 'Supply' : 'Product'}</th>
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
        <p className="muted">
          {restaurant
            ? 'A refunded table bill is taken out of completed sales and listed here. A restaurant till return is listed here, and the original receipt stays on the till report. A restaurant till return follows the store on the original receipt.'
            : 'Posted returns are not subtracted from the other sales reports.'}
        </p>
        {sectionErrors.returns ? <p style={{ color: '#b91c1c' }}>{sectionErrors.returns}</p> : null}
        <p className="muted">
          {restaurant ? (
            <>
              {pack?.return_count ?? 0}{' '}
              {(pack?.return_count ?? 0) === 1 ? 'return' : 'returns'}
              {' · Total '}
              {fmtMoney(pack?.total_amount)}
              {' · Posted '}
              {fmtMoney(pack?.posted_amount)}
              {' · Quantity '}
              {pack?.total_quantity ?? 0}
            </>
          ) : (
            <>
              {pack?.return_count ?? 0} returns · total {fmtMoney(pack?.total_amount)} · posted{' '}
              {fmtMoney(pack?.posted_amount)} · qty {pack?.total_quantity ?? 0}
            </>
          )}
        </p>
        <div className={restaurant ? 'list-table-wrap rest-bill-return' : 'list-table-wrap'}>
          <table className="table">
            {restaurant ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '24%' }} />
                <col style={{ width: '16%' }} />
                <col style={{ width: '20%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>Return</th>
                {restaurant ? null : <th>Customer</th>}
                <th>Reason</th>
                {restaurant ? null : <th>Status</th>}
                <th>Qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((ret: any) => (
                <tr key={ret.id}>
                  {restaurant ? (
                    <td data-label="Return">
                      {ret.return_number || 'No return'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {ret.customer_name || 'No customer'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {ret.status ? plainLabel(String(ret.status)) : 'No status'}
                      </span>
                    </td>
                  ) : (
                    <td>{ret.return_number}</td>
                  )}
                  {restaurant ? null : <td>{ret.customer_name}</td>}
                  <td data-label={restaurant ? 'Reason' : undefined}>
                    {restaurant
                      ? (ret.reason ? plainLabel(String(ret.reason)) : 'No reason')
                      : plainLabel(ret.reason)}
                  </td>
                  {restaurant ? null : <td>{plainLabel(ret.status)}</td>}
                  <td data-label={restaurant ? 'Qty' : undefined}>{ret.quantity}</td>
                  <td data-label={restaurant ? 'Amount' : undefined}>{fmtMoney(ret.total_amount)}</td>
                </tr>
              ))}
              {!rows.length
                ? emptyRow(
                    restaurant ? 4 : 6,
                    restaurant ? 'No bill returns for these dates.' : 'No sales returns for this period.',
                  )
                : null}
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
    if (restaurant && view === 'transactions') {
      const detailCols = showStore ? 4 : 3;
      return (
        <>
          {note('A restaurant till return comes off this list. The original receipt stays on the till report.')}
          {data?.truncated ? (
            <p className="muted">Showing the latest {rows.length} of {data.count}. Narrow the dates to see the rest. Totals include every row in this filter.</p>
          ) : null}
          <p className="muted">
            {data?.count ?? rows.length}{' '}
            {(data?.count ?? rows.length) === 1 ? 'bill' : 'bills'}
            {' · Total '}
            {fmtMoney(data?.total)}
          </p>
          <div className="list-table-wrap rest-detailed-sales">
            <table className="table">
              <colgroup>
                <col style={{ width: showStore ? '28%' : '34%' }} />
                <col style={{ width: showStore ? '32%' : '40%' }} />
                <col style={{ width: showStore ? '22%' : '26%' }} />
                {showStore ? <col style={{ width: '18%' }} /> : null}
              </colgroup>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Bill</th>
                  <th>Total</th>
                  {showStore ? <th>Store</th> : null}
                </tr>
              </thead>
              <tbody>
                {slicePage(rows, page).map((row: any) => (
                  <tr key={row.id}>
                    <td data-label="When">{formatWhen(row.when)}</td>
                    <td data-label="Bill">
                      {row.number || 'No bill'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.customer || 'No customer'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.source ? plainLabel(String(row.source)) : 'No source'}
                      </span>
                    </td>
                    <td data-label="Total">{fmtMoney(row.total)}</td>
                    {showStore ? <td data-label="Store">{row.store_name || 'No store'}</td> : null}
                  </tr>
                ))}
                {!rows.length ? emptyRow(detailCols, 'No bills in this period.') : null}
              </tbody>
            </table>
          </div>
          {pager(rows.length, page, onPage)}
        </>
      );
    }
    if (restaurant && view === 'pos') {
      const tillCols = showStore ? 4 : 3;
      return (
        <>
          {note(data?.returns_note)}
          {data?.truncated ? (
            <p className="muted">Showing the latest {rows.length} of {data.count}. Narrow the dates to see the rest. Totals include every row in this filter.</p>
          ) : null}
          <p className="muted">
            {data?.count ?? rows.length}{' '}
            {(data?.count ?? rows.length) === 1 ? 'receipt' : 'receipts'}
            {' · Total '}
            {fmtMoney(data?.total)}
          </p>
          <div className="list-table-wrap rest-fit-table rest-till-sales">
            <table className="table">
              <colgroup>
                <col style={{ width: showStore ? '28%' : '34%' }} />
                <col style={{ width: showStore ? '32%' : '40%' }} />
                <col style={{ width: showStore ? '22%' : '26%' }} />
                {showStore ? <col style={{ width: '18%' }} /> : null}
              </colgroup>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Receipt</th>
                  <th>Total</th>
                  {showStore ? <th>Store</th> : null}
                </tr>
              </thead>
              <tbody>
                {slicePage(rows, page).map((row: any) => (
                  <tr key={row.id}>
                    <td data-label="When">{formatWhen(row.when)}</td>
                    <td data-label="Receipt">
                      {row.number || 'No receipt'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.customer || 'No customer'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.cashier || 'No cashier'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.payment_method ? plainLabel(String(row.payment_method)) : 'No tender'}
                      </span>
                    </td>
                    <td data-label="Total">{fmtMoney(row.total)}</td>
                    {showStore ? <td data-label="Store">{row.store_name || 'No store'}</td> : null}
                  </tr>
                ))}
                {!rows.length ? emptyRow(tillCols, 'No restaurant till receipts in this period.') : null}
              </tbody>
            </table>
          </div>
          {pager(rows.length, page, onPage)}
        </>
      );
    }
    if (restaurant && view === 'quotations') {
      return (
        <>
          {note(data?.returns_note)}
          {data?.truncated ? (
            <p className="muted">Showing the latest {rows.length} of {data.count}. Narrow the dates to see the rest. Totals include every row in this filter.</p>
          ) : null}
          <p className="muted">
            {data?.count ?? rows.length}{' '}
            {(data?.count ?? rows.length) === 1 ? 'quotation' : 'quotations'}
            {' · Total '}
            {fmtMoney(data?.total)}
          </p>
          <div className="list-table-wrap rest-fit-table rest-quotations">
            <table className="table">
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '42%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Quotation</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {slicePage(rows, page).map((row: any) => (
                  <tr key={row.id}>
                    <td data-label="When">{formatWhen(row.when)}</td>
                    <td data-label="Quotation">
                      {row.number || 'No quotation'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.customer || 'No customer'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.status ? plainLabel(String(row.status)) : 'No status'}
                      </span>
                    </td>
                    <td data-label="Total">{fmtMoney(row.total)}</td>
                  </tr>
                ))}
                {!rows.length ? emptyRow(3, 'No quotations for these dates.') : null}
              </tbody>
            </table>
          </div>
          {pager(rows.length, page, onPage)}
        </>
      );
    }
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
                {view === 'pos' ? <th>{hotel ? 'Staff' : 'Cashier'}</th> : null}
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
        {restaurant ? (
          <>
            <p className="muted">
              Completed bills only. A refunded table bill is taken out of this list and listed on Bill returns. A restaurant till return comes off this list and is listed on Bill returns. The original receipt stays on the till report.
            </p>
            <p className="muted">A completed restaurant bill is included in this tax.</p>
            <p className="muted">A restaurant till return comes off this tax. The original receipt stays on the till report.</p>
            <p className="muted">A restaurant till tax stays off this sales amount. The till receipt keeps the tax.</p>
            <p className="muted">A restaurant till discount comes off this sales amount. The menu amount stays.</p>
          </>
        ) : (
          note(data?.returns_note)
        )}
        {data?.truncated ? (
          <p className="muted">Showing the latest {rows.length} lines of {data.count}. Totals include every line in this filter.</p>
        ) : null}
        <p className="muted">
          {restaurant ? (
            <>
              Quantity {data?.total_quantity ?? 0}
              {' · Sales '}
              {fmtMoney(data?.total_sales)}
              {' · Discount '}
              {fmtMoney(data?.total_discount)}
              {' · Tax '}
              {fmtMoney(data?.total_tax)}
              {showCost ? <> · Profit {fmtMoney(data?.total_profit)}</> : null}
            </>
          ) : (
            <>
              Qty {data?.total_quantity ?? 0} · sales {fmtMoney(data?.total_sales)} · discount {fmtMoney(data?.total_discount)} · tax{' '}
              {fmtMoney(data?.total_tax)}
              {showCost ? ` · profit ${fmtMoney(data?.total_profit)}` : ''}
            </>
          )}
        </p>
        <div className={restaurant ? 'list-table-wrap rest-sold-lines' : 'list-table-wrap'}>
          <table className="table">
            {restaurant ? (
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '30%' }} />
                <col style={{ width: '14%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurant ? <th>Menu item</th> : <th>Date</th>}
                {restaurant ? <th>When</th> : <th>Number</th>}
                {restaurant ? null : <th>{hotel ? 'Supply' : 'Product'}</th>}
                {restaurant ? null : <th>SKU</th>}
                {restaurant ? null : <th>Barcode</th>}
                {restaurant ? null : <th>Category</th>}
                {restaurant ? null : <th>Brand</th>}
                <th>Qty</th>
                {restaurant ? null : <th>Unit price</th>}
                {restaurant ? null : <th>Discount</th>}
                {restaurant ? null : <th>Tax</th>}
                {restaurant ? <th>Amount</th> : <th>Sales total</th>}
                {restaurant ? null : <th>Customer</th>}
                {restaurant ? null : <th>{hotel ? 'Staff' : 'Cashier'}</th>}
                {restaurant ? null : <th>Payment</th>}
                {showStore && !restaurant ? <th>Store</th> : null}
                {showCost && !restaurant ? <th>Cost</th> : null}
                {showCost && !restaurant ? <th>Profit</th> : null}
              </tr>
            </thead>
            <tbody>
              {slicePage(rows, page).map((row: any) => (
                <tr key={row.id}>
                  {restaurant ? (
                    <td data-label="Menu item">
                      {row.product || 'No menu item'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.sku || 'No code'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.category || 'No category'}
                      </span>
                    </td>
                  ) : (
                    <td>{formatWhen(row.when)}</td>
                  )}
                  {restaurant ? (
                    <td data-label="When">
                      {row.when ? formatWhen(row.when) : 'No date'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.number || 'No bill'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.customer || 'No customer'}
                        {showStore && row.store_name ? ` · ${row.store_name}` : ''}
                      </span>
                    </td>
                  ) : (
                    <td>{row.number}</td>
                  )}
                  {restaurant ? null : <td>{row.product}</td>}
                  {restaurant ? null : <td>{row.sku || '—'}</td>}
                  {restaurant ? null : <td>{row.barcode || '—'}</td>}
                  {restaurant ? null : <td>{row.category || '—'}</td>}
                  {restaurant ? null : <td>{row.brand || '—'}</td>}
                  <td data-label={restaurant ? 'Qty' : undefined}>{row.quantity}</td>
                  {restaurant ? null : <td>{fmtMoney(row.unit_price)}</td>}
                  {restaurant ? null : <td>{fmtMoney(row.discount)}</td>}
                  {restaurant ? null : <td>{fmtMoney(row.tax)}</td>}
                  {restaurant ? (
                    <td data-label="Amount">
                      {fmtMoney(row.sales_total)}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Unit {fmtMoney(row.unit_price)}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Discount {fmtMoney(row.discount)} · Tax {fmtMoney(row.tax)}
                        {showCost
                          ? ` · Cost ${row.cost == null ? '—' : fmtMoney(row.cost)} · Profit ${row.profit == null ? '—' : fmtMoney(row.profit)}`
                          : ''}
                      </span>
                    </td>
                  ) : (
                    <td>{fmtMoney(row.sales_total)}</td>
                  )}
                  {restaurant ? null : <td>{row.customer || '—'}</td>}
                  {restaurant ? null : <td>{row.cashier || '—'}</td>}
                  {restaurant ? null : <td>{plainLabel(row.payment_method)}</td>}
                  {showStore && !restaurant ? <td>{row.store_name || '—'}</td> : null}
                  {showCost && !restaurant ? <td>{row.cost == null ? '—' : fmtMoney(row.cost)}</td> : null}
                  {showCost && !restaurant ? <td>{row.profit == null ? '—' : fmtMoney(row.profit)}</td> : null}
                </tr>
              ))}
              {!rows.length
                ? emptyRow(
                    restaurant ? 4 : cols,
                    restaurant
                      ? 'No menu items sold in this period.'
                      : hotel
                        ? 'No items sold in this period.'
                        : 'No products sold in this period.',
                  )
                : null}
            </tbody>
          </table>
        </div>
        {pager(rows.length, page, onPage)}
      </>
    );
  }

  if (view === 'payments') {
    const rows = data?.rows || [];
    if (restaurant) {
      return (
        <>
          {note('A restaurant till return comes off this tender. The original receipt stays on the till report.')}
          <p className="muted">
            Total {fmtMoney(data?.total)}. Unpaid balances are labelled On account. Card, Mobile Money, and bank are recorded tenders. This list does not charge a card. Gift cards and loyalty stay on retail sales.
          </p>
          <div className="list-table-wrap rest-fit-table rest-tenders">
            <table className="table">
              <colgroup>
                <col style={{ width: '46%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '32%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Tender</th>
                  <th>Count</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row: any) => (
                  <tr key={row.payment_method}>
                    <td data-label="Tender">{row.payment_method ? plainLabel(String(row.payment_method)) : 'No tender'}</td>
                    <td data-label="Count">{row.count}</td>
                    <td data-label="Amount">{fmtMoney(row.amount)}</td>
                  </tr>
                ))}
                {!rows.length ? emptyRow(3, 'No tenders in this period.') : null}
              </tbody>
            </table>
          </div>
        </>
      );
    }
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
    if (restaurant) {
      return (
        <>
          {note('A restaurant till return comes off this discount. The original receipt stays on the till report.')}
          <p className="muted">
            Bill discounts {fmtMoney(data?.header_discounts)} · Line discounts {fmtMoney(data?.line_discounts)} · Total{' '}
            {fmtMoney(data?.total)}
          </p>
          <div className="list-table-wrap rest-fit-table rest-discounts">
            <table className="table">
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '42%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>When</th>
                  <th>Discount</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {slicePage(rows, page).map((row: any) => (
                  <tr key={row.id}>
                    <td data-label="When">{formatWhen(row.when)}</td>
                    <td data-label="Discount">
                      {row.number || 'No number'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {row.kind ? plainLabel(String(row.kind)) : 'No kind'}
                      </span>
                    </td>
                    <td data-label="Amount">{fmtMoney(row.amount)}</td>
                  </tr>
                ))}
                {!rows.length ? emptyRow(3, 'No bill discounts in this period.') : null}
              </tbody>
            </table>
          </div>
          {pager(rows.length, page, onPage)}
        </>
      );
    }
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
    if (restaurant) {
      return (
        <>
          {note(data?.returns_note)}
          <p className="muted">Outstanding {fmtMoney(data?.total_due)}</p>
          <div className="list-table-wrap rest-fit-table rest-credit">
            <table className="table">
              <colgroup>
                <col style={{ width: '62%' }} />
                <col style={{ width: '38%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Guest</th>
                  <th>Owed</th>
                </tr>
              </thead>
              <tbody>
                {parties.map((row: any) => (
                  <tr key={row.party_id}>
                    <td data-label="Guest">{row.name || 'No guest'}</td>
                    <td data-label="Owed">{fmtMoney(row.total_due)}</td>
                  </tr>
                ))}
                {!parties.length ? emptyRow(2, 'No open bills on account.') : null}
              </tbody>
            </table>
          </div>
          {documents.length ? (
            <>
              <h3 style={{ marginTop: 16 }}>Open bills</h3>
              <div className="list-table-wrap rest-fit-table rest-credit">
                <table className="table">
                  <colgroup>
                    <col style={{ width: '62%' }} />
                    <col style={{ width: '38%' }} />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Bill</th>
                      <th>Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slicePage(documents, page).map((row: any) => (
                      <tr key={row.id}>
                        <td data-label="Bill">
                          {row.document_number || 'No bill'}
                          <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                            {row.party_name || 'No guest'}
                          </span>
                        </td>
                        <td data-label="Balance">{fmtMoney(row.balance_due)}</td>
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
