import { usesStoreStockTransfers } from './industries';

export { usesStoreStockTransfers };

export type TransferLine = {
  product_id?: string;
  quantity?: number;
  shipped_qty?: number;
  received_qty?: number;
};

export type StockTransferRow = {
  id: string;
  transfer_number?: string;
  status?: string;
  from_store_id?: string | null;
  to_store_id?: string | null;
  from_warehouse_id?: string | null;
  to_warehouse_id?: string | null;
  item_count?: number;
  quantity_total?: number;
  created_at?: string | null;
  rejection_reason?: string | null;
  items?: TransferLine[];
};

export function transferProductCount(row: StockTransferRow): number {
  if (typeof row.item_count === 'number') return row.item_count;
  return (row.items || []).length;
}

export function transferQtyTotal(row: StockTransferRow): number {
  if (row.quantity_total != null && Number.isFinite(Number(row.quantity_total))) {
    return Number(row.quantity_total);
  }
  return (row.items || []).reduce((sum, line) => sum + Number(line.quantity || 0), 0);
}

export function matchesTransferSearch(
  row: StockTransferRow,
  query: string,
  labels: { from: string; to: string },
): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const hay = [
    row.transfer_number,
    row.status,
    row.rejection_reason,
    labels.from,
    labels.to,
    row.from_store_id,
    row.to_store_id,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return hay.includes(q);
}

export function formatTransferDate(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

export function transferOnDate(
  row: { created_at?: string | null },
  dateFrom: string,
  dateTo: string,
): boolean {
  if (!dateFrom && !dateTo) return true;
  const raw = row.created_at || '';
  const day = raw.slice(0, 10);
  if (!day) return false;
  if (dateFrom && day < dateFrom) return false;
  if (dateTo && day > dateTo) return false;
  return true;
}

export function warehouseQtyMap(
  items: { product_id?: string; quantity?: number }[],
): Record<string, number> {
  const m: Record<string, number> = {};
  for (const row of items) {
    if (row.product_id) m[row.product_id] = Number(row.quantity || 0);
  }
  return m;
}

/** Client-side checks before POST /inventory/stock-transfers. */
export function transferLineQtyError(qty: number, available?: number): string | null {
  if (!Number.isFinite(qty) || qty <= 0) return 'Each product line needs a positive quantity';
  if (available != null && Number.isFinite(available) && qty > available) {
    return `Quantity exceeds available stock (${available})`;
  }
  return null;
}

export function sameWarehouseError(fromId: string, toId: string): string | null {
  if (!fromId || !toId) return 'Select source and destination locations';
  if (fromId === toId) return 'Source and destination must be different';
  return null;
}
