/** Business-type (industry) gating for industry-specific modules.

 * Must stay aligned with backend `app.packages.INDUSTRY_SPECIFIC_MODULES`
 * and `INDUSTRY_MODULE_ALLOWLIST`. Shared/core modules are never blocked here.
 */

export const INDUSTRY_SPECIFIC_MODULES = ['hotel', 'fmcg'] as const;

export type IndustrySpecificModule = (typeof INDUSTRY_SPECIFIC_MODULES)[number];

const ALLOWLIST: Record<string, ReadonlySet<string>> = {
  hotel: new Set(['hotel']),
  fmcg: new Set(['fmcg']),
};

export function industryAllowsModule(
  industry: string | null | undefined,
  module: string
): boolean {
  const mod = String(module || '')
    .trim()
    .toLowerCase();
  if (!mod || !(INDUSTRY_SPECIFIC_MODULES as readonly string[]).includes(mod)) {
    return true;
  }
  const ind = String(industry || 'retail')
    .trim()
    .toLowerCase();
  return ALLOWLIST[ind]?.has(mod) ?? false;
}

export function moduleEnabledForTenant(
  enabledModules: string[] | null | undefined,
  industry: string | null | undefined,
  module: string
): boolean {
  const mod = String(module || '')
    .trim()
    .toLowerCase();
  if (!industryAllowsModule(industry, mod)) return false;
  if (!enabledModules || enabledModules.length === 0) {
    // Until /me loads, treat as unknown — callers should wait.
    return false;
  }
  return enabledModules.map((m) => m.toLowerCase()).includes(mod);
}
