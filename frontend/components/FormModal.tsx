'use client';

import { useEffect, useId, useRef, type ReactNode } from 'react';

type FormModalProps = {
  title: string;
  onClose: () => void;
  children: ReactNode;
  dirty?: boolean;
  busy?: boolean;
  /** Sticky footer actions (typically Save). Header Close is hidden unless `headerClose` is true. */
  footer?: ReactNode;
  /** Keep the header Close control. Defaults to true when `footer` is omitted. */
  headerClose?: boolean;
  closeLabel?: string;
  closeAriaLabel?: string;
};

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export default function FormModal({
  title,
  onClose,
  children,
  dirty = false,
  busy = false,
  footer,
  headerClose,
  closeLabel = 'Close',
  closeAriaLabel,
}: FormModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const lastFocus = useRef<HTMLElement | null>(null);
  const dirtyRef = useRef(dirty);
  const busyRef = useRef(busy);
  const onCloseRef = useRef(onClose);
  const titleId = useId();
  dirtyRef.current = dirty;
  busyRef.current = busy;
  onCloseRef.current = onClose;

  const showHeaderClose = headerClose ?? footer == null;
  const showFooter = footer != null || !showHeaderClose;
  const footerCloseAria = closeAriaLabel ?? (closeLabel === 'Close' ? 'Close dialog' : closeLabel);

  function requestClose() {
    if (busyRef.current) return;
    if (dirtyRef.current && typeof window !== 'undefined' && !window.confirm('You have unsaved changes. Discard them?')) {
      return;
    }
    onCloseRef.current();
  }

  useEffect(() => {
    lastFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const panel = panelRef.current;
    const nodes = panel ? Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
    (nodes.find((el) => el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') || nodes[0])?.focus();

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        requestClose();
        return;
      }
      if (e.key !== 'Tab' || !panel) return;
      const list = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => !el.hasAttribute('disabled') && el.tabIndex !== -1,
      );
      if (!list.length) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
      lastFocus.current?.focus?.();
    };
    // requestClose reads latest dirty/busy via closure on each open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="erp-modal-root">
      <div className="erp-modal-back" onClick={requestClose} aria-hidden />
      <div
        ref={panelRef}
        className="erp-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="erp-modal-head">
          <h3 id={titleId} style={{ margin: 0 }}>
            {title}
          </h3>
          {showHeaderClose ? (
            <button type="button" onClick={requestClose} disabled={busy} aria-label="Close dialog">
              Close
            </button>
          ) : null}
        </div>
        <div className="erp-modal-body">{children}</div>
        {showFooter ? (
          <div className="erp-modal-foot">
            {!showHeaderClose ? (
              <button type="button" onClick={requestClose} disabled={busy} aria-label={footerCloseAria}>
                {closeLabel}
              </button>
            ) : null}
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}
