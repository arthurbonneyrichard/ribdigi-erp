export const LIST_PAGE_SIZE = 10;

export type SortDir = 1 | -1;

export function paginate<T>(rows: T[], page: number, pageSize = LIST_PAGE_SIZE) {
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / pageSize) || 1);
  const safePage = Math.min(Math.max(1, page), pages);
  const start = (safePage - 1) * pageSize;
  return { page: safePage, pages, total, rows: rows.slice(start, start + pageSize) };
}

export function compareText(a: unknown, b: unknown, dir: SortDir) {
  return (
    String(a || '').localeCompare(String(b || ''), undefined, {
      numeric: true,
      sensitivity: 'base',
    }) * dir
  );
}

export type ProductListFilters = {
  q: string;
  categoryId: string;
  brandId: string;
  stock: 'all' | 'low' | 'ok';
};

export function matchesProductList(
  p: {
    name?: string;
    sku?: string;
    barcode?: string;
    category?: string;
    brand?: string;
    category_id?: string;
    brand_id?: string;
  },
  f: ProductListFilters,
  stockStatus: 'red' | 'yellow' | 'green',
) {
  const q = f.q.trim().toLowerCase();
  if (q) {
    const hay = `${p.name || ''} ${p.sku || ''} ${p.barcode || ''} ${p.category || ''} ${p.brand || ''}`
      .toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (f.categoryId && String(p.category_id || '') !== f.categoryId) return false;
  if (f.brandId && String(p.brand_id || '') !== f.brandId) return false;
  if (f.stock === 'low' && stockStatus === 'green') return false;
  if (f.stock === 'ok' && stockStatus !== 'green') return false;
  return true;
}

export function sortProducts(rows: any[], key: string, dir: SortDir) {
  const copy = rows.slice();
  copy.sort((a, b) => {
    switch (key) {
      case 'sku':
        return compareText(a.sku, b.sku, dir);
      case 'category':
        return compareText(a.category, b.category, dir);
      case 'brand':
        return compareText(a.brand, b.brand, dir);
      case 'price':
        return (Number(a.selling_price || 0) - Number(b.selling_price || 0)) * dir;
      case 'qty':
        return (Number(a.stock_qty || 0) - Number(b.stock_qty || 0)) * dir;
      case 'created':
        return compareText(a.created_at, b.created_at, dir);
      default:
        return compareText(a.name, b.name, dir);
    }
  });
  return copy;
}

export function sortByKey<T>(rows: T[], get: (row: T) => string | number, dir: SortDir) {
  const copy = rows.slice();
  copy.sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
    return compareText(av, bv, dir);
  });
  return copy;
}
