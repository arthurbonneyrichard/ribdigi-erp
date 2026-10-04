'use client';

import { useEffect, useState } from 'react';
import {
  fetchAttachment,
  isImageContentType,
  isPdfContentType,
} from '../lib/attachments';

type Props = {
  open: boolean;
  /** API path under /api/v1, e.g. `/expenses/{id}/attachment` */
  apiPath: string;
  title?: string;
  /** Optional fallback label when Content-Disposition is not exposed cross-origin */
  fallbackName?: string;
  onClose: () => void;
  onError?: (message: string) => void;
};

/**
 * Inline preview modal for expense / PI / JE attachments (BR-9.4).
 * Uses authenticated blob fetch + object URL (works even when Content-Disposition is attachment).
 */
export default function AttachmentPreview({
  open,
  apiPath,
  title,
  fallbackName,
  onClose,
  onError,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [filename, setFilename] = useState('');
  const [contentType, setContentType] = useState('');
  const [localError, setLocalError] = useState('');

  useEffect(() => {
    if (!open || !apiPath) return;
    let revoked = false;
    let url: string | null = null;
    setLoading(true);
    setLocalError('');
    setObjectUrl(null);
    fetchAttachment(apiPath)
      .then((att) => {
        if (revoked) return;
        url = URL.createObjectURL(att.blob);
        setObjectUrl(url);
        setFilename(att.filename || fallbackName || '');
        setContentType(att.contentType);
      })
      .catch((err: any) => {
        if (revoked) return;
        const msg = err?.message || 'Unable to load attachment';
        setLocalError(msg);
        onError?.(msg);
      })
      .finally(() => {
        if (!revoked) setLoading(false);
      });
    return () => {
      revoked = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [open, apiPath, fallbackName, onError]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const showImage = objectUrl && isImageContentType(contentType, filename);
  const showPdf = objectUrl && isPdfContentType(contentType, filename);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title || 'Attachment preview'}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        className="card"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(920px, 96vw)',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          margin: 0,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>{title || 'Attachment preview'}</h3>
          <button type="button" onClick={onClose} aria-label="Close preview">
            Close
          </button>
        </div>
        {filename && filename.toLowerCase() !== 'attachment' ? (
          <p className="muted" style={{ margin: 0 }}>
            {filename}
          </p>
        ) : null}
        {loading && <p className="muted">Loading…</p>}
        {localError && <p style={{ color: '#b91c1c' }}>{localError}</p>}
        {showImage && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={objectUrl!}
            alt={filename || 'Attachment'}
            style={{ maxWidth: '100%', maxHeight: '75vh', objectFit: 'contain', margin: '0 auto' }}
          />
        )}
        {showPdf && (
          <iframe
            title={filename || 'PDF preview'}
            src={objectUrl!}
            style={{ width: '100%', height: '75vh', border: '1px solid #ccc', borderRadius: 4 }}
          />
        )}
        {objectUrl && !showImage && !showPdf && !loading && (
          <p className="muted">
            Preview is available for images and PDFs. Use Download for this file type ({contentType || 'unknown'}).
          </p>
        )}
      </div>
    </div>
  );
}
