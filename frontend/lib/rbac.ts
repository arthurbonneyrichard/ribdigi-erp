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
