import { apiFetch } from './api';

function attachPrintFrame(): HTMLIFrameElement {
  const iframe = document.createElement('iframe');
  iframe.setAttribute('title', 'Print document');
  iframe.setAttribute('aria-hidden', 'true');
  iframe.style.cssText =
    'position:fixed;right:0;bottom:0;width:210mm;height:297mm;border:0;opacity:0;pointer-events:none;z-index:-1';
  document.body.appendChild(iframe);
  return iframe;
}

function scheduleFrameCleanup(iframe: HTMLIFrameElement, extra?: () => void) {
  const cleanup = () => {
    extra?.();
    iframe.remove();
  };
  iframe.contentWindow?.addEventListener('afterprint', cleanup, { once: true });
  window.setTimeout(cleanup, 120_000);
}

function printFrame(frame: Window) {
  frame.focus();
  frame.print();
}

function escapePrintTitle(value: string) {
  return String(value || 'Document').replace(/[&<>"]/g, (ch) =>
    ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : ch === '>' ? '&gt;' : '&quot;',
  );
}

/** Chrome's PDF viewer in an iframe often opens a pop-up. Print the HTML document instead. */
export function preferHtmlPrintPath(path: string): string {
  const q = path.indexOf('?');
  if (q < 0) return path;
  const params = new URLSearchParams(path.slice(q + 1));
  if ((params.get('format') || '').toLowerCase() === 'pdf') {
    params.set('format', 'html');
    return `${path.slice(0, q)}?${params.toString()}`;
  }
  return path;
}

/** Print HTML in this tab. Returns false only if a frame cannot be created. */
export function printDocumentHtml(html: string): boolean {
  const iframe = attachPrintFrame();
  const frame = iframe.contentWindow;
  const doc = iframe.contentDocument;
  if (!frame || !doc) {
    iframe.remove();
    return false;
  }
  doc.open();
  doc.write(html);
  doc.close();
  scheduleFrameCleanup(iframe);
  window.setTimeout(() => printFrame(frame), 60);
  return true;
}

/** Print a visible desk sheet (reports) without printing the ERP chrome. */
export function printDocumentFromElement(el: HTMLElement, title = 'Document'): boolean {
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('button, .no-print, .reports-actions').forEach((node) => node.remove());
  const html =
    `<!doctype html><html lang="en"><head><meta charset="utf-8"/>` +
    `<title>${escapePrintTitle(title)}</title>` +
    `<style>` +
    `body{margin:16px;color:#10211b;font-family:"Segoe UI",Arial,sans-serif;background:#fff}` +
    `table{width:100%;border-collapse:collapse;table-layout:auto;font-size:12px}` +
    `th{background:#003d1f;color:#fff;text-align:left;padding:8px 10px;white-space:nowrap}` +
    `td{padding:8px 10px;border-bottom:1px solid #d4e5c4;vertical-align:top}` +
    `td.col-num,th.col-num,td.r{text-align:right;white-space:nowrap}` +
    `td.col-text{overflow-wrap:anywhere}` +
    `.muted{color:#4d5d56}.kpi{font-size:22px;font-weight:800}` +
    `.card{border:1px solid #d4e5c4;border-radius:8px;padding:12px;margin:0 0 12px}` +
    `.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}` +
    `h2,h3{color:#003d1f}` +
    `@media print{body{margin:0}}` +
    `</style></head><body>${clone.outerHTML}</body></html>`;
  return printDocumentHtml(html);
}

/** Print or download a blob URL in this tab. Never opens a pop-up. */
export function printDocumentBlobUrl(url: string, downloadName = 'document.pdf'): boolean {
  const iframe = attachPrintFrame();
  iframe.onload = () => {
    const frame = iframe.contentWindow;
    if (!frame) {
      iframe.remove();
      const a = document.createElement('a');
      a.href = url;
      a.download = downloadName;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      return;
    }
    scheduleFrameCleanup(iframe, () => URL.revokeObjectURL(url));
    window.setTimeout(() => printFrame(frame), 80);
  };
  iframe.src = url;
  return true;
}

/** Fetch a document print HTML page (or A4 PDF fallback) and print it without a pop-up. */
export async function openDocumentPrint(path: string) {
  const res = await apiFetch(preferHtmlPrintPath(path));
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
    printDocumentBlobUrl(url);
    return;
  }
  const html = await res.text();
  if (!printDocumentHtml(html)) {
    throw new Error('Print failed');
  }
}
