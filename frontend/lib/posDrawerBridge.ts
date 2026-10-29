/** POS page publishes the open shift so the top bar can kick the drawer. */

export type PosDrawerBridgeState = {
  sessionId: string;
};

type Listener = (state: PosDrawerBridgeState | null) => void;

let current: PosDrawerBridgeState | null = null;
const listeners = new Set<Listener>();

export function setPosDrawerBridge(state: PosDrawerBridgeState | null) {
  current = state;
  listeners.forEach((listener) => listener(current));
}

export function subscribePosDrawerBridge(listener: Listener) {
  listeners.add(listener);
  listener(current);
  return () => {
    listeners.delete(listener);
  };
}

/** The top bar's Shift button asks the POS page to show its shift panel. */
export const POS_SHIFT_PANEL_EVENT = 'ribdigi:pos-shift-panel';

export function requestPosShiftPanel() {
  window.dispatchEvent(new Event(POS_SHIFT_PANEL_EVENT));
}

/** The top bar's Return button asks the POS page to open the till return panel. */
export const POS_RETURN_PANEL_EVENT = 'ribdigi:pos-return-panel';

export function requestPosReturnPanel() {
  window.dispatchEvent(new Event(POS_RETURN_PANEL_EVENT));
}

export const POS_DRAWER_KICK_EVENT = 'ribdigi:drawer-kick';

/** Browser-bridge / local helper: publish ESC/POS kick bytes after Open drawer or a cash sale. */
export function dispatchDrawerKick(payload: {
  mode?: string | null;
  kick_base64?: string | null;
  bridge?: boolean;
  ok?: boolean;
} | null | undefined) {
  if (typeof window === 'undefined' || !payload) return;
  const kick = String(payload.kick_base64 || '').trim();
  if (!kick) return;
  const mode = String(payload.mode || '').trim().toLowerCase();
  if (mode !== 'browser_bridge' && !payload.bridge) return;
  window.dispatchEvent(new CustomEvent(POS_DRAWER_KICK_EVENT, { detail: { ...payload, kick_base64: kick } }));
}
