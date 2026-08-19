/** ADR-490 — workspace context (tenant vs company). */

const KIND_KEY = 'workspace_kind';
const COMPANY_KEY = 'company_id';

export type WorkspaceKind = 'tenant' | 'company' | 'platform';

export function getWorkspaceKind(): WorkspaceKind {
  if (typeof window === 'undefined') return 'company';
  const v = localStorage.getItem(KIND_KEY);
  if (v === 'tenant' || v === 'company' || v === 'platform') return v;
  return 'company';
}

export function getCompanyId(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(COMPANY_KEY);
}

export function setWorkspaceContext(kind: WorkspaceKind, companyId?: string | null) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(KIND_KEY, kind);
  if (kind === 'company' && companyId) {
    localStorage.setItem(COMPANY_KEY, companyId);
  } else if (kind !== 'company') {
    localStorage.removeItem(COMPANY_KEY);
  }
  window.dispatchEvent(new CustomEvent('ribdigi-workspace-changed'));
}

export function clearWorkspaceContext() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(KIND_KEY);
  localStorage.removeItem(COMPANY_KEY);
}

export function subscribeWorkspace(cb: () => void) {
  if (typeof window === 'undefined') return () => undefined;
  const handler = () => cb();
  window.addEventListener('ribdigi-workspace-changed', handler);
  return () => window.removeEventListener('ribdigi-workspace-changed', handler);
}
