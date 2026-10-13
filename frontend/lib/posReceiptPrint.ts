/** Open the existing browser receipt print path once. Returns false if no window opened. */

function escapePrintText(value: string) {
  return value.replace(/[&<>]/g, (ch) => (ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : '&gt;'));
}

export function openReceiptPrintWindow(html: string | undefined, text: string): boolean {
  const body = html
    ? html
    : `<!doctype html><html><head><meta charset="utf-8"/>` +
      `<style>@page{margin:0;size:80mm auto}body{margin:0;display:flex;justify-content:center;width:80mm}` +
      `pre{font-family:'Courier New',ui-monospace,monospace;font-weight:700;` +
      `font-size:13px;line-height:1.15;white-space:pre;margin:0}</style>` +
      `</head><body><pre>${escapePrintText(text)}</pre></body></html>`;
  const iframe = document.createElement('iframe');
  iframe.setAttribute('title', 'Print');
  iframe.style.cssText = 'position:fixed;left:-10000px;top:0;width:80mm;height:100vh;border:0';
  document.body.appendChild(iframe);
  const frame = iframe.contentWindow;
  const doc = iframe.contentDocument;
  if (!frame || !doc) {
    iframe.remove();
    return false;
  }
  doc.open();
  doc.write(body);
  doc.close();
  const cleanup = () => iframe.remove();
  frame.addEventListener('afterprint', cleanup, { once: true });
  window.setTimeout(cleanup, 120000);
  frame.focus();
  frame.print();
  return true;
}
