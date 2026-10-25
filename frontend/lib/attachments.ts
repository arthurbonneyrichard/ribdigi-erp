/** Authenticated attachment / binary helpers. Same-origin via apiFetch. */

import { apiFetch } from './api';

export type FetchedAttachment = {
  blob: Blob;
  filename: string;
  contentType: string;
};

function attachmentMessage(body: unknown, fallback: string): string {
  const rec = body && typeof body === 'object' ? (body as { detail?: unknown; message?: string }) : {};
  const detail = rec.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (detail && typeof detail === 'object') {
    const msg = (detail as { message?: unknown }).message;
    if (typeof msg === 'string' && msg.trim()) return msg;
  }
  if (typeof rec.message === 'string' && rec.message.trim()) return rec.message;
  return fallback;
}

export async function fetchAttachment(apiPath: string): Promise<FetchedAttachment> {
  const path = apiPath.startsWith('/') ? apiPath : `/${apiPath}`;
  const res = await apiFetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(attachmentMessage(body, 'Attachment download failed'));
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

export async function uploadAttachment(apiPath: string, file: File): Promise<any> {
  const path = apiPath.startsWith('/') ? apiPath : `/${apiPath}`;
  const form = new FormData();
  form.append('file', file);
  const res = await apiFetch(path, { method: 'POST', body: form });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(attachmentMessage(body, 'Upload failed'));
  return body;
}

export function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadAttachment(apiPath: string, fallbackName: string): Promise<void> {
  const { blob, filename } = await fetchAttachment(apiPath);
  triggerBlobDownload(blob, filename || fallbackName);
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
