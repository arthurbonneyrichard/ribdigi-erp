'use client';

import { useEffect, useState, type ComponentProps } from 'react';
import PosOfflinePanel from '../components/PosOfflinePanel';

export type PosOfflineHostProps = ComponentProps<typeof PosOfflinePanel>;

type Listener = () => void;

let current: PosOfflineHostProps | null = null;
const listeners = new Set<Listener>();

/** POS page publishes the offline panel; the shell Online button opens it. */
export function setPosOfflinePanelProps(next: PosOfflineHostProps | null) {
  current = next;
  listeners.forEach((listener) => listener());
}

export function PosOfflineTopSlot({ embedded = false }: { embedded?: boolean }) {
  const [props, setProps] = useState<PosOfflineHostProps | null>(current);

  useEffect(() => {
    const listener = () => setProps(current);
    listeners.add(listener);
    setProps(current);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  if (!props) return null;
  return <PosOfflinePanel {...props} embedded={embedded} />;
}
