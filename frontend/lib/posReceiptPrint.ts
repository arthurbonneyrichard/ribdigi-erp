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
    `<style>@page{margin:0;size:80mm auto}html,body{margin:0;padding:0;width:80mm;max-width:80mm}` +
    `.slip{width:72mm;max-width:80mm;margin:0 auto}` +
    `pre{font-family:'Courier New',ui-monospace,monospace;font-weight:700;` +
    `font-size:13px;line-height:1.15;white-space:pre-wrap;overflow-wrap:anywhere;margin:0 auto;text-align:center}` +
    `.powered{text-align:center;font-family:'Courier New',ui-monospace,monospace;` +
    `font-weight:700;font-size:2.5px;line-height:1.2;margin-top:1mm;overflow-wrap:anywhere}` +
    `.feed{height:20mm;line-height:20mm;font-size:1px;overflow:hidden}</style>` +
    `</head><body><div class="slip"><pre>${escapePrintText(body.join('\n').trim())}</pre>` +
    `<div class="powered">Powered by RIBDIGI ERP</div><div class="feed">&nbsp;</div></div></body></html>`
  );
}

export function openReceiptPrintWindow(html: string | undefined, text: string): boolean {
  const body = html ? html : receiptHtmlFromText(text);
  const iframe = document.createElement('iframe');
  iframe.setAttribute('title', 'Print');
  iframe.style.cssText = 'position:fixed;left:0;top:0;width:80mm;height:0;border:0;opacity:0;pointer-events:none';
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
  const fit = () => {
    const height = Math.max(doc.documentElement?.scrollHeight || 0, doc.body?.scrollHeight || 0, 200);
    iframe.style.height = `${height}px`;
  };
  fit();
  const cleanup = () => iframe.remove();
  frame.addEventListener('afterprint', cleanup, { once: true });
  window.setTimeout(cleanup, 120000);
  window.setTimeout(() => {
    fit();
    frame.focus();
    frame.print();
  }, 60);
  return true;
}
