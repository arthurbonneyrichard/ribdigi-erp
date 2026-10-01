export const LIST_PAGE_SIZE = 10;

/** Display-only product title. Does not mutate stored catalog names. */
export function displayProductName(name: unknown): string {
  const text = String(name ?? '').trim();
  return text ? text.toUpperCase() : '—';
}

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
  stock: 'all' | 'low' | 'oos' | 'ok';
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
  stockStatus: 'out' | 'red' | 'yellow' | 'green',
) {
  const q = f.q.trim().toLowerCase();
  if (q) {
    const hay = `${p.name || ''} ${p.sku || ''} ${p.barcode || ''} ${p.category || ''} ${p.brand || ''}`
      .toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (f.categoryId && String(p.category_id || '') !== f.categoryId) return false;
  if (f.brandId && String(p.brand_id || '') !== f.brandId) return false;
  if (f.stock === 'oos' && stockStatus !== 'out') return false;
  if (f.stock === 'low' && stockStatus !== 'red') return false;
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

export type CustomerListFilters = {
  q: string;
  status: 'all' | 'active' | 'inactive';
  groupId: string;
  profileType: 'all' | 'registered' | 'walk_in';
};

export function matchesCustomerList(
  c: {
    name?: string | null;
    code?: string | null;
    email?: string | null;
    phone?: string | null;
    category?: string | null;
    status?: string | null;
    profile_type?: string | null;
    customer_group_id?: string | null;
    customer_group?: { name?: string } | null;
  },
  f: CustomerListFilters,
) {
  const q = f.q.trim().toLowerCase();
  if (q) {
    const hay = `${c.name || ''} ${c.code || ''} ${c.email || ''} ${c.phone || ''} ${c.category || ''} ${
      c.customer_group?.name || ''
    }`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  const st = c.status || 'active';
  if (f.status === 'active' && st === 'inactive') return false;
  if (f.status === 'inactive' && st !== 'inactive') return false;
  if (f.groupId && String(c.customer_group_id || '') !== f.groupId) return false;
  if (f.profileType !== 'all' && (c.profile_type || 'registered') !== f.profileType) return false;
  return true;
}

export function sortCustomers(rows: any[], key: string, dir: SortDir) {
  const copy = rows.slice();
  copy.sort((a, b) => {
    switch (key) {
      case 'code':
        return compareText(a.code, b.code, dir);
      case 'status':
        return compareText(a.status || 'active', b.status || 'active', dir);
      case 'group':
        return compareText(a.customer_group?.name, b.customer_group?.name, dir);
      case 'email':
        return compareText(a.email, b.email, dir);
      case 'balance':
        return (Number(a.balance || 0) - Number(b.balance || 0)) * dir;
      default:
        return compareText(a.name, b.name, dir);
    }
  });
  return copy;
}
