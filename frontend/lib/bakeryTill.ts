/**
 * Which bakery till this device uses. A bakery can run more than one till at a time; the
 * server takes the till from the X-Bakery-Till header (the till's shift id). Without it the
 * server uses the till the signed-in person opened, or the only open one.
 */
import { api } from './api';

const KEY = 'ribdigi.bakery.till.v1';

export function chosenTill(): string | null {
  try {
    return window.localStorage.getItem(KEY) || null;
  } catch {
    return null;
  }
}

export function chooseTill(id: string | null): void {
  try {
    if (id) window.localStorage.setItem(KEY, id);
    else window.localStorage.removeItem(KEY);
  } catch {
    /* private window: the server falls back to the person's own till */
  }
}

export function tillHeaders(): Record<string, string> {
  const id = chosenTill();
  return id ? { 'X-Bakery-Till': id } : {};
}

/** `api()` with this device's till attached. */
export function bakeryApi(path: string, opts: RequestInit = {}): Promise<any> {
  return api(path, { ...opts, headers: { ...((opts.headers as Record<string, string>) || {}), ...tillHeaders() } });
}

/** Open a printable page the server builds (labels, invoices). Needs the sign-in, so fetch then show. */
export async function openPrintable(path: string): Promise<void> {
  const { apiFetch } = await import('./api');
  const page = window.open('', '_blank', 'width=720,height=900');
  const res = await apiFetch(path, { headers: tillHeaders() });
  const text = await res.text();
  if (!page) return;
  page.document.open();
  page.document.write(text);
  page.document.close();
}
