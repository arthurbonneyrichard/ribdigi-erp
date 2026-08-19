'use client';

import { useEffect, useRef, useState } from 'react';

type Props = {
  open: boolean;
  onClose: () => void;
  onScan: (code: string) => void;
  title?: string;
};

const SCAN_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128', 'code_39', 'qr_code'];

function isSecureEnough() {
  if (typeof window === 'undefined') return false;
  return window.isSecureContext || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
}

export default function BarcodeCameraScanner({ open, onClose, onScan, title = 'Scan barcode' }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const onScanRef = useRef(onScan);
  const lastScanRef = useRef<{ code: string; at: number }>({ code: '', at: 0 });
  const [status, setStatus] = useState('Starting camera…');
  const [unsupported, setUnsupported] = useState('');

  useEffect(() => {
    onScanRef.current = onScan;
  }, [onScan]);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    let timer = 0;

    async function start() {
      setUnsupported('');
      setStatus('Starting camera…');

      if (!isSecureEnough()) {
        setUnsupported(
          'Camera scanning needs HTTPS (or localhost). Use a USB/Bluetooth wedge scanner in the search field instead.',
        );
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setUnsupported('This browser cannot access the camera. Use a USB/Bluetooth wedge scanner instead.');
        return;
      }
      if (typeof window.BarcodeDetector !== 'function') {
        setUnsupported(
          'Camera barcode detection is not available in this browser. Use Chrome/Edge, or type/scan with a USB/Bluetooth wedge scanner.',
        );
        return;
      }

      try {
        const Detector = window.BarcodeDetector;
        const supported = await Detector.getSupportedFormats();
        const formats = SCAN_FORMATS.filter((f) => supported.includes(f));
        const detector = new Detector({ formats: formats.length ? formats : undefined });
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = stream;
        await video.play();
        setStatus('Point the camera at a barcode');

        const tick = async () => {
          if (cancelled || !videoRef.current) return;
          const videoEl = videoRef.current;
          if (videoEl.readyState >= 2) {
            try {
              const codes = await detector.detect(videoEl);
              const raw = codes[0]?.rawValue?.trim();
              if (raw) {
                const now = Date.now();
                if (raw !== lastScanRef.current.code || now - lastScanRef.current.at > 1600) {
                  lastScanRef.current = { code: raw, at: now };
                  onScanRef.current(raw);
                }
              }
            } catch {
              /* frame decode failures are normal while focusing */
            }
          }
          timer = window.setTimeout(tick, 220);
        };
        timer = window.setTimeout(tick, 300);
      } catch (err: any) {
        setUnsupported(err?.message || 'Could not open the camera. Check permissions and try again.');
      }
    }

    start();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.72)',
        zIndex: 80,
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
    >
      <div
        style={{
          width: 'min(560px, 100%)',
          background: '#0f172a',
          color: '#f8fafc',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 20px 50px rgba(0,0,0,0.35)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px' }}>
          <strong>{title}</strong>
          <button type="button" onClick={onClose} style={{ padding: '6px 10px' }}>
            Close
          </button>
        </div>
        {unsupported ? (
          <p style={{ padding: 16, margin: 0, color: '#fde68a' }}>{unsupported}</p>
        ) : (
          <>
            <div style={{ position: 'relative', background: '#020617' }}>
              <video
                ref={videoRef}
                muted
                playsInline
                style={{ width: '100%', display: 'block', maxHeight: '60vh', objectFit: 'cover' }}
              />
              <div
                aria-hidden
                style={{
                  position: 'absolute',
                  inset: '18% 12%',
                  border: '2px solid rgba(248,250,252,0.85)',
                  borderRadius: 8,
                  boxShadow: '0 0 0 9999px rgba(2,6,23,0.35)',
                  pointerEvents: 'none',
                }}
              />
            </div>
            <p style={{ padding: '10px 14px', margin: 0, color: '#cbd5e1' }}>{status}</p>
          </>
        )}
      </div>
    </div>
  );
}
