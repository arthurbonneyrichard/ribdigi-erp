/** Hardware barcode wedges type quickly and finish with Enter. */

export const WEDGE_KEY_GAP_MS = 50;

export type WedgeBuffer = { buf: string; last: number };

export function looksLikeBarcode(value: string) {
  const text = value.trim();
  if (!text || /\s/.test(text)) return false;
  return /^[A-Za-z0-9\-._]{4,48}$/.test(text);
}

/** True when focus is already in a text control the wedge must not steal. */
export function isPosTypingField(target: EventTarget | null): boolean {
  if (!target || typeof target !== 'object') return false;
  const el = target as HTMLElement;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return Boolean(el.isContentEditable);
}

type WedgeKey = {
  key: string;
  target: EventTarget | null;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  preventDefault?: () => void;
  stopPropagation?: () => void;
};

/**
 * Buffer a fast scan when focus is on the page (buttons, grid, body).
 * The barcode search field and every other text field keep their own keys.
 * A slow typist never fills a barcode-length buffer.
 */
export function consumeWedgeKey(
  event: WedgeKey,
  state: WedgeBuffer,
  onScan: (query: string) => void,
  nowMs: number = typeof performance !== 'undefined' ? performance.now() : Date.now()
): void {
  if (isPosTypingField(event.target)) return;
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.key === 'Enter') {
    const query = state.buf;
    const last = state.last;
    state.buf = '';
    state.last = 0;
    if (last && nowMs - last <= WEDGE_KEY_GAP_MS && looksLikeBarcode(query)) {
      event.preventDefault?.();
      event.stopPropagation?.();
      onScan(query);
    }
    return;
  }
  if (event.key.length !== 1) return;
  if (!state.last || nowMs - state.last > WEDGE_KEY_GAP_MS) {
    state.buf = event.key;
    state.last = nowMs;
    return;
  }
  state.buf += event.key;
  state.last = nowMs;
}
