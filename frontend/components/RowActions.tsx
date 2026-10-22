'use client';

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

export type RowActionItem = {
  key: string;
  label?: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  ariaLabel?: string;
  variant?: 'default' | 'ok' | 'danger';
  hidden?: boolean;
  /** Custom content (pay field, etc.) instead of a plain button. */
  node?: ReactNode;
};

type Props = {
  /** Accessible name for the overflow trigger. */
  label?: string;
  /** How many items stay visible before the ⋯ menu. */
  primaryMax?: number;
  items: RowActionItem[];
};

function actionClass(variant?: RowActionItem['variant']) {
  if (variant === 'ok') return 'btn-ok';
  if (variant === 'danger') return 'btn-danger';
  return undefined;
}

export default function RowActions({ label = 'More actions', primaryMax = 1, items }: Props) {
  const visible = items.filter((item) => !item.hidden);
  const primary = visible.slice(0, Math.max(0, primaryMax));
  const more = visible.slice(Math.max(0, primaryMax));
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const renderItem = (item: RowActionItem, inMenu: boolean) => {
    if (item.node) {
      return (
        <div key={item.key} className={inMenu ? 'erp-row-menu-slot' : 'erp-row-action-slot'}>
          {item.node}
        </div>
      );
    }
    return (
      <button
        key={item.key}
        type="button"
        className={actionClass(item.variant)}
        disabled={item.disabled}
        title={item.title}
        aria-label={item.ariaLabel || (typeof item.label === 'string' ? item.label : undefined)}
        role={inMenu ? 'menuitem' : undefined}
        onClick={() => {
          item.onClick?.();
          setOpen(false);
        }}
      >
        {item.label}
      </button>
    );
  };

  if (visible.length === 0) return <span className="muted">—</span>;

  return (
    <div className="erp-row-actions" ref={rootRef}>
      {primary.map((item) => renderItem(item, false))}
      {more.length > 0 ? (
        <div className="erp-row-menu">
          <button
            type="button"
            className="erp-row-menu-trigger"
            aria-label={label}
            aria-expanded={open}
            aria-haspopup="menu"
            aria-controls={menuId}
            onClick={() => setOpen((v) => !v)}
          >
            ⋯
          </button>
          {open ? (
            <div className="erp-row-menu-pop" id={menuId} role="menu">
              {more.map((item) => renderItem(item, true))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
