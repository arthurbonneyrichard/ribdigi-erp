/** Shared House evidence download helper (Stage 93 V1). */

import { apiFetch } from './api';

export async function downloadPlatformEvidence(): Promise<string> {
  const res = await apiFetch('/platform/evidence');
  if (!res.ok) throw new Error('Evidence download failed');
  const body = await res.json();
  const blob = new Blob([JSON.stringify(body.data ?? body, null, 2)], {
    type: 'application/json',
  });
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `platform-evidence-${stamp}.json`;
  a.click();
  URL.revokeObjectURL(url);
  return 'Evidence JSON downloaded (packaging honesty only)';
}
