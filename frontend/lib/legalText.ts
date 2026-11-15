// A small, safe markup for the legal pages the software owner edits in the console.
// Blocks (separated by a blank line): "## Heading", "### Subheading", lines starting "- " (a list),
// anything else is a paragraph. Inline: **bold** and [text](link). Links may only point inside the
// site ("/legal/terms"), to https:// or to mailto:, so edited text can never inject a script.
// Placeholders: {{cookie_settings}} (a block: the Cookie settings button) and {{analytics_status}}
// (inline: whether analytics is on for this site).

export type Inline =
  | { kind: 'text'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'link'; text: string; href: string }
  | { kind: 'analytics_status' };

export type Block =
  | { kind: 'h2' | 'h3' | 'p'; parts: Inline[] }
  | { kind: 'ul'; items: Inline[][] }
  | { kind: 'cookie_settings' };

export function safeHref(href: string): string | null {
  const h = href.trim();
  if (/^\/(?!\/)[^\s]*$/.test(h)) return h;
  if (/^https:\/\/[^\s]+$/i.test(h)) return h;
  if (/^mailto:[^\s@]+@[^\s@]+$/i.test(h)) return h;
  return null;
}

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)\s]+)\)|\{\{analytics_status\}\}/g;
  let last = 0;
  let m: RegExpExecArray | null;
  const push = (text: string) => {
    if (text) out.push({ kind: 'text', text });
  };
  while ((m = re.exec(src))) {
    push(src.slice(last, m.index));
    if (m[1] !== undefined) out.push({ kind: 'bold', text: m[1] });
    else if (m[2] !== undefined) {
      const href = safeHref(m[3]);
      // A link that is not allowed is shown as its text only.
      out.push(href ? { kind: 'link', text: m[2], href } : { kind: 'text', text: m[2] });
    } else out.push({ kind: 'analytics_status' });
    last = m.index + m[0].length;
  }
  push(src.slice(last));
  return out;
}

export function parseLegalText(src: string): Block[] {
  const blocks: Block[] = [];
  const chunks = String(src || '')
    .replace(/\r\n?/g, '\n')
    .split(/\n\s*\n/)
    .map((c) => c.trim())
    .filter(Boolean);
  for (const chunk of chunks) {
    if (chunk === '{{cookie_settings}}') {
      blocks.push({ kind: 'cookie_settings' });
    } else if (chunk.startsWith('### ')) {
      blocks.push({ kind: 'h3', parts: parseInline(chunk.slice(4).replace(/\s+/g, ' ')) });
    } else if (chunk.startsWith('## ')) {
      blocks.push({ kind: 'h2', parts: parseInline(chunk.slice(3).replace(/\s+/g, ' ')) });
    } else if (/^[-*] /.test(chunk)) {
      // Each "- " starts an item; a following line without one continues the item.
      const items: string[] = [];
      for (const line of chunk.split('\n')) {
        if (/^\s*[-*] /.test(line)) items.push(line.replace(/^\s*[-*] /, ''));
        else if (items.length) items[items.length - 1] += ' ' + line.trim();
      }
      blocks.push({ kind: 'ul', items: items.map((i) => parseInline(i.trim())) });
    } else {
      blocks.push({ kind: 'p', parts: parseInline(chunk.replace(/\s+/g, ' ')) });
    }
  }
  return blocks;
}
