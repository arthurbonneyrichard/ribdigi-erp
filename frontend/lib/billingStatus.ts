/** Merge a gateway test/save payload into the platform billing status view. */

const RAW_SECRET_KEYS = new Set([
  'secret',
  'webhook_secret',
  'secret_enc',
  'webhook_secret_enc',
]);

function withoutRawSecrets(view: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(view)) {
    if (RAW_SECRET_KEYS.has(key)) continue;
    out[key] = value;
  }
  return out;
}

export function mergePlatformBillingStatus(current: unknown, payload: unknown): unknown {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return current;
  const probe = withoutRawSecrets(payload as Record<string, unknown>);
  const base =
    current && typeof current === 'object' && !Array.isArray(current)
      ? (current as Record<string, unknown>)
      : {};
  const priorGateway =
    base.gateway && typeof base.gateway === 'object' && !Array.isArray(base.gateway)
      ? withoutRawSecrets(base.gateway as Record<string, unknown>)
      : {};

  if (probe.gateway && typeof probe.gateway === 'object' && !Array.isArray(probe.gateway)) {
    const nextGateway = withoutRawSecrets(probe.gateway as Record<string, unknown>);
    return {
      ...base,
      ...probe,
      configured: probe.configured ?? base.configured,
      live_charges: probe.live_charges ?? base.live_charges,
      gateway: { ...priorGateway, ...nextGateway },
    };
  }

  return {
    ...base,
    provider: probe.provider || base.provider,
    configured: base.configured,
    live_charges: base.live_charges,
    connected: probe.connected ?? base.connected,
    gateway: { ...priorGateway, ...probe },
  };
}

export function billingGatewayLabel(provider: string | null | undefined): string {
  if (provider === 'paystack') return 'Paystack';
  if (provider === 'flutterwave') return 'Flutterwave';
  if (provider === 'mock') return 'Sandbox';
  if (provider && /^[a-z][a-z0-9-]{2,31}$/.test(provider)) {
    return provider
      .split('-')
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }
  return 'Not connected';
}
