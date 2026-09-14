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

/** CSV / dump exports — first-class ``export`` action (write does not imply export). */
export function canExportModule(
  permissions: Record<string, string[]> | null | undefined,
  module: string,
): boolean {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const actions = permissions[module] || [];
  return actions.includes('*') || actions.includes('export');
}

/** COGS / margin / valuation cost — first-class ``view_cost`` action. */
export function canViewCost(
  permissions: Record<string, string[]> | null | undefined,
  module: string = 'inventory',
): boolean {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const actions = permissions[module] || [];
  return actions.includes('*') || actions.includes('view_cost');
}

/** Stage 95 P1 — party discoverability may gate on sales|customers / purchasing|suppliers. */
export function canReadAnyModule(
  permissions: Record<string, string[]> | null | undefined,
  modules: string[],
): boolean {
  return modules.some((module) => canReadModule(permissions, module));
}
