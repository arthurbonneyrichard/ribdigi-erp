export function storefrontApiRoot(): string {
  if (typeof window !== 'undefined') return '/api/v1';
  const raw =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1';
  return raw.replace(/\/$/, '');
}

export function previewTokenFromLocation(): string | null {
  if (typeof window === 'undefined') return null;
  const query = new URLSearchParams(window.location.search).get('preview_token');
  if (query && query.trim()) {
    sessionStorage.setItem('ribdigi.storefront.preview', query.trim());
    return query.trim();
  }
  return sessionStorage.getItem('ribdigi.storefront.preview');
}

export function cartToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('ribdigi.storefront.cart');
}

export function setCartToken(token: string | null) {
  if (!token) {
    sessionStorage.removeItem('ribdigi.storefront.cart');
    notifyStorefrontCart();
    return;
  }
  sessionStorage.setItem('ribdigi.storefront.cart', token);
  notifyStorefrontCart();
}

export function shopMoney(amount: number | string | null | undefined, currency = 'GHS') {
  const n = typeof amount === 'number' ? amount : Number(amount);
  if (!Number.isFinite(n)) return '';
  return `${currency} ${n.toFixed(2)}`;
}

export function notifyStorefrontCart() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event('ribdigi-storefront-cart'));
}

export function storefrontAssetUrl(path: string) {
  const preview = previewTokenFromLocation();
  const url = new URL(`${storefrontApiRoot()}${path}`, 'http://local.invalid');
  if (preview && !url.searchParams.get('preview_token')) {
    url.searchParams.set('preview_token', preview);
  }
  return `${storefrontApiRoot()}${url.pathname}${url.search}`;
}

export function storefrontHref(href: string) {
  if (typeof window === 'undefined') return href;
  const token = new URLSearchParams(window.location.search).get('preview_token')
    || sessionStorage.getItem('ribdigi.storefront.preview');
  if (!token) return href;
  return href.includes('?')
    ? `${href}&preview_token=${encodeURIComponent(token)}`
    : `${href}?preview_token=${encodeURIComponent(token)}`;
}

export function shopperToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('ribdigi.storefront.shopper');
}

export function setShopperToken(token: string | null) {
  if (!token) {
    sessionStorage.removeItem('ribdigi.storefront.shopper');
    return;
  }
  sessionStorage.setItem('ribdigi.storefront.shopper', token);
}

export async function storefrontFetch(path: string, init: RequestInit = {}) {
  const preview = previewTokenFromLocation();
  const url = new URL(`${storefrontApiRoot()}${path}`, 'http://local.invalid');
  if (preview && !url.searchParams.get('preview_token')) {
    url.searchParams.set('preview_token', preview);
  }
  const headers = new Headers(init.headers || {});
  headers.set('Accept', 'application/json');
  const shopper = shopperToken();
  if (shopper) headers.set('X-Storefront-Shopper', shopper);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${storefrontApiRoot()}${url.pathname}${url.search}`, {
    ...init,
    headers,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      (typeof detail === 'object' && detail?.message) ||
      (typeof detail === 'string' ? detail : payload?.message) ||
      'Storefront request failed';
    const error = new Error(message) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return payload;
}
