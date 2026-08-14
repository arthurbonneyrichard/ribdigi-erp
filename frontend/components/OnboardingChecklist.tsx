'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';

type Step = {
  id: string;
  title: string;
  description: string;
  href: string;
  completed: boolean;
  auto_completed: boolean;
  skipped: boolean;
};

type Checklist = {
  steps: Step[];
  completed_count: number;
  total_count: number;
  progress_pct: number;
  dismissed: boolean;
  dismissible: boolean;
  visible: boolean;
  dismiss_threshold_pct: number;
};

export default function OnboardingChecklist({
  canManage,
}: {
  canManage: boolean;
}) {
  const [data, setData] = useState<Checklist | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await api('/onboarding/checklist');
      setData(r.data || null);
      setError('');
    } catch (err: any) {
      // Hide quietly for roles without access or transient errors.
      setData(null);
      setError(err?.message || '');
    }
  }, []);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  async function run(path: string) {
    setBusy(true);
    setError('');
    try {
      const r = await api(path, { method: 'POST', body: '{}' });
      setData(r.data || null);
    } catch (err: any) {
      setError(err.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  }

  if (!data) return null;

  const pct = Math.max(0, Math.min(100, Number(data.progress_pct) || 0));

  if (!data.visible) {
    if (!(canManage && data.dismissed && pct < 100)) return null;
    return (
      <div
        className="card"
        style={{
          marginBottom: 16,
          display: 'flex',
          gap: 10,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
        data-testid="onboarding-checklist-restore"
      >
        <span className="muted" style={{ flex: 1 }}>
          Getting started checklist was dismissed ({pct}% complete).
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={() => run('/onboarding/checklist/restore')}
        >
          Restore checklist
        </button>
        {error && <p style={{ color: '#b91c1c', margin: 0, width: '100%' }}>{error}</p>}
      </div>
    );
  }

  return (
    <div
      className="card"
      style={{ marginBottom: 16, display: 'grid', gap: 10 }}
      data-testid="onboarding-checklist"
    >
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <strong style={{ flex: 1 }}>Getting started</strong>
        <span className="muted">
          {data.completed_count}/{data.total_count} · {pct}%
        </span>
        <button type="button" onClick={() => setExpanded((v) => !v)} disabled={busy}>
          {expanded ? 'Collapse' : 'Expand'}
        </button>
        {canManage && data.dismissible && (
          <button
            type="button"
            onClick={() => run('/onboarding/checklist/dismiss')}
            disabled={busy}
          >
            Dismiss
          </button>
        )}
      </div>
      <div
        style={{
          height: 8,
          borderRadius: 999,
          background: 'var(--muted-bg, #e2e8f0)',
          overflow: 'hidden',
        }}
        aria-label={`Onboarding progress ${pct} percent`}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: '#0f766e',
            transition: 'width 200ms ease',
          }}
        />
      </div>
      {error && <p style={{ color: '#b91c1c', margin: 0 }}>{error}</p>}
      {expanded && (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 8 }}>
          {data.steps.map((step) => (
            <li
              key={step.id}
              style={{
                display: 'flex',
                gap: 10,
                flexWrap: 'wrap',
                alignItems: 'center',
                padding: '8px 0',
                borderTop: '1px solid var(--border, #eef1f7)',
              }}
            >
              <span aria-hidden style={{ width: 18, textAlign: 'center' }}>
                {step.completed ? '✓' : '○'}
              </span>
              <div style={{ flex: 1, minWidth: 180 }}>
                <div>
                  <Link href={step.href} style={{ fontWeight: 600 }}>
                    {step.title}
                  </Link>
                  {step.skipped ? (
                    <span className="muted"> · skipped</span>
                  ) : step.auto_completed ? (
                    <span className="muted"> · done</span>
                  ) : null}
                </div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {step.description}
                </div>
              </div>
              {canManage && !step.auto_completed && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    run(
                      step.skipped
                        ? `/onboarding/checklist/steps/${step.id}/unskip`
                        : `/onboarding/checklist/steps/${step.id}/skip`,
                    )
                  }
                >
                  {step.skipped ? 'Undo skip' : 'Skip'}
                </button>
              )}
              {!step.completed && (
                <Link href={step.href}>
                  <button type="button">Open</button>
                </Link>
              )}
            </li>
          ))}
        </ul>
      )}
      {canManage && !data.dismissible && (
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>
          Dismiss available after {data.dismiss_threshold_pct}% complete (skip counts).
        </p>
      )}
    </div>
  );
}
