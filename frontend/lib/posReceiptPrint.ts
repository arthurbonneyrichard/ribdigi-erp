/** Open the existing browser receipt print path once. Returns false if no window opened. */

function escapePrintText(value: string) {
  return value.replace(/[&<>]/g, (ch) => (ch === '&' ? '&amp;' : ch === '<' ? '&lt;' : '&gt;'));
}

function receiptHtmlFromText(text: string) {
  const lines = String(text || '').split('\n');
  const body: string[] = [];
  for (const line of lines) {
    if (line.trim() === 'Powered by RIBDIGI ERP' || line.trim() === 'Powered by RIBDIGI') continue;
    body.push(line);
  }
  return (
    `<!doctype html><html><head><meta charset="utf-8"/>` +
    `<style>@page{margin:0;size:80mm auto}html,body{margin:0;padding:0;width:100%}` +
    `body{display:flex;justify-content:center}` +
    `.slip{width:72mm;max-width:80mm;margin:2mm auto}` +
    `pre{font-family:'Courier New',ui-monospace,monospace;font-weight:700;` +
    `font-size:13px;line-height:1.15;white-space:pre;margin:0 auto;text-align:center}` +
    `.powered{text-align:center;font-family:'Courier New',ui-monospace,monospace;` +
    `font-weight:700;font-size:2.5px;line-height:1.2;margin-top:2mm;white-space:nowrap}` +
    `.feed{height:22mm}</style>` +
    `</head><body><div class="slip"><pre>${escapePrintText(body.join('\n').trim())}</pre>` +
    `<div class="powered">Powered by RIBDIGI ERP</div><div class="feed"></div></div></body></html>`
  );
}

export function openReceiptPrintWindow(html: string | undefined, text: string): boolean {
  const body = html ? html : receiptHtmlFromText(text);
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
