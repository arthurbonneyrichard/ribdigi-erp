/** Authenticated attachment fetch helpers (expenses / PI / JE). */

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export type FetchedAttachment = {
  blob: Blob;
  filename: string;
  contentType: string;
};

export async function fetchAttachment(apiPath: string): Promise<FetchedAttachment> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
  const path = apiPath.startsWith('/') ? apiPath : `/${apiPath}`;
  const res = await fetch(`${apiBase}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
    },
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || body.message || 'Attachment download failed';
    throw new Error(message);
  }
  const blob = await res.blob();
  const cd = res.headers.get('Content-Disposition') || '';
  const match = cd.match(/filename="?([^"]+)"?/i);
  const contentType = blob.type || res.headers.get('Content-Type') || 'application/octet-stream';
  return {
    blob,
    filename: match?.[1] || '',
    contentType,
  };
}

export function isImageContentType(contentType: string, filename?: string): boolean {
  if (contentType.startsWith('image/')) return true;
  const name = (filename || '').toLowerCase();
  return /\.(png|jpe?g|gif|webp|bmp)$/i.test(name);
}

export function isPdfContentType(contentType: string, filename?: string): boolean {
  if (contentType.includes('pdf')) return true;
  return (filename || '').toLowerCase().endsWith('.pdf');
}
