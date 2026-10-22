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
