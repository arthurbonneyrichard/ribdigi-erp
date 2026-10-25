import { apiFetch } from './api';

/** Open a document print HTML page or A4 PDF in a new tab. */
export async function openDocumentPrint(path: string) {
  const res = await apiFetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = (body as { detail?: unknown; message?: string }).detail;
    const message = (body as { message?: string }).message;
    throw new Error(
      (typeof detail === 'string' && detail)
        || (typeof message === 'string' && message)
        || `Print failed (${res.status})`,
    );
  }
  const type = (res.headers.get('content-type') || '').toLowerCase();
  if (type.includes('pdf')) {
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const w = window.open(url, '_blank', 'noopener');
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    if (!w) {
      throw new Error('Allow pop-ups to print this document.');
    }
    return;
  }
  const html = await res.text();
  const w = window.open('', '_blank');
  if (!w) {
    throw new Error('Allow pop-ups to print this document.');
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
}
