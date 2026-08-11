/** Shared House evidence download helper (Stage 93 V1). */

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export async function downloadPlatformEvidence(): Promise<string> {
  const token = localStorage.getItem('token');
  const tenant = localStorage.getItem('tenant');
  const res = await fetch(`${apiBase}/platform/evidence`, {
    headers: {
      Authorization: token ? `Bearer ${token}` : '',
      'X-Tenant-ID': tenant || '',
    },
  });
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
