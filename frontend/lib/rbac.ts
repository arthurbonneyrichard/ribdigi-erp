/** Stage 1 menu visibility = module permission (ADR-004). */

export function canReadModule(
  permissions: Record<string, string[]> | null | undefined,
  module: string,
): boolean {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const actions = permissions[module] || [];
  return actions.includes('*') || actions.includes('read') || actions.includes('write');
}

/** Stage 95 P1 — party discoverability may gate on sales|customers / purchasing|suppliers. */
export function canReadAnyModule(
  permissions: Record<string, string[]> | null | undefined,
  modules: string[],
): boolean {
  return modules.some((module) => canReadModule(permissions, module));
}
