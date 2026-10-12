/** Labels for the software-owner billing list. */

import type { FormatPrefs } from './format';

export type SubscriptionAmountResult = { amount: number } | { error: string };

export function subscriptionTermLabel(
  termValue: number | null | undefined,
  termUnit: string | null | undefined,
): string {
  if (termValue == null || !termUnit) return '—';
  const count = Number(termValue);
  if (!Number.isFinite(count) || count < 1) return '—';
  if (termUnit === 'years') return count === 1 ? '1 year' : `${count} years`;
  if (termUnit === 'months') return count === 1 ? '1 month' : `${count} months`;
  return '—';
}

export function subscriptionAmountLabel(
  amount: number | null | undefined,
  currency: string | null | undefined,
  formattedNumber: string,
): string {
  if (amount == null || formattedNumber === '') return '—';
  return `${(currency || 'GHS').toUpperCase()} ${formattedNumber}`;
}

export function subscriptionAmountToSend(
  raw: string,
  packageCode: string,
  prefs?: FormatPrefs | null,
): SubscriptionAmountResult {
  const thousand =
    prefs?.thousand_separator !== undefined && prefs?.thousand_separator !== null
      ? prefs.thousand_separator
      : ',';
  const decimal = prefs?.decimal_separator || '.';
  let text = raw.trim();
  if (!text) return { error: 'Enter an amount' };
  if (thousand) text = text.split(thousand).join('');
  if (decimal !== '.') text = text.split(decimal).join('.');
  if (!/^\d+(\.\d+)?$/.test(text)) return { error: 'Enter a valid amount' };
  const amount = Number(text);
  if (!Number.isFinite(amount)) return { error: 'Enter a valid amount' };
  const trial = (packageCode || '').trim().toLowerCase() === 'trial';
  if (!trial && amount <= 0) return { error: 'Enter an amount greater than zero' };
  return { amount };
}

const PAID_FEATURE_SETS = new Set(['starter', 'professional', 'enterprise']);

export type PackageCreateDraft = {
  name: string;
  code: string;
  packageCode: string;
  interval: string;
  amount: string;
  currency: string;
};

export function packageCodeFromName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
}

export function packageCreateBody(
  draft: PackageCreateDraft,
  prefs?: FormatPrefs | null,
): { body: Record<string, string | number | boolean> } | { error: string } {
  const name = draft.name.trim();
  if (name.length < 2) return { error: 'Enter a package name' };
  const code = draft.code.trim().toLowerCase();
  if (!/^[a-z0-9][a-z0-9-]{1,39}$/.test(code)) {
    return { error: 'Use a short code with letters, numbers, and hyphens' };
  }
  const packageCode = draft.packageCode.trim().toLowerCase();
  if (!PAID_FEATURE_SETS.has(packageCode)) return { error: 'Choose Starter, Professional, or Enterprise' };
  const interval = draft.interval.trim().toLowerCase();
  if (interval !== 'month' && interval !== 'year') return { error: 'Choose monthly or yearly' };
  const currency = draft.currency.trim().toUpperCase();
  if (currency !== 'GHS' && currency !== 'USD') return { error: 'Choose GHS or USD' };
  const parsed = subscriptionAmountToSend(draft.amount, packageCode, prefs);
  if ('error' in parsed) return parsed;
  return {
    body: {
      code,
      package_code: packageCode,
      name,
      interval,
      amount: parsed.amount,
      currency,
      is_active: true,
    },
  };
}

export function packageUpdateBody(
  draft: Omit<PackageCreateDraft, 'code'>,
  prefs?: FormatPrefs | null,
): { body: Record<string, string | number> } | { error: string } {
  const built = packageCreateBody({ ...draft, code: 'edit-ok' }, prefs);
  if ('error' in built) return built;
  return {
    body: {
      name: String(built.body.name),
      package_code: String(built.body.package_code),
      interval: String(built.body.interval),
      amount: Number(built.body.amount),
      currency: String(built.body.currency),
    },
  };
}

export function gatewaySaveBody(draft: {
  provider: string;
  mode: string;
  secret: string;
  webhookSecret: string;
}): { body: Record<string, string> } | { error: string } {
  const provider = draft.provider.trim().toLowerCase();
  const mode = draft.mode.trim().toLowerCase();
  if (provider !== 'mock' && provider !== 'paystack' && provider !== 'flutterwave') {
    return { error: 'Choose Sandbox, Paystack, or Flutterwave' };
  }
  if (mode !== 'sandbox' && mode !== 'live') return { error: 'Choose sandbox or live' };
  if (provider === 'mock' && mode === 'live') return { error: 'Sandbox cannot take live payments' };
  const body: Record<string, string> = { provider, mode };
  const secret = draft.secret.trim();
  const hook = draft.webhookSecret.trim();
  if (secret) body.secret = secret;
  if (hook) body.webhook_secret = hook;
  if (provider === 'paystack' && secret) {
    if (mode === 'sandbox' && !secret.startsWith('sk_test_')) {
      return { error: 'Paystack sandbox needs a test secret key' };
    }
    if (mode === 'live' && !secret.startsWith('sk_live_')) {
      return { error: 'Paystack live needs a live secret key' };
    }
  }
  if (provider === 'flutterwave' && secret) {
    if (mode === 'sandbox' && !secret.startsWith('FLWSECK_TEST-')) {
      return { error: 'Flutterwave sandbox needs a test secret key' };
    }
    if (mode === 'live' && (secret.startsWith('FLWSECK_TEST-') || !secret.startsWith('FLWSECK-'))) {
      return { error: 'Flutterwave live needs a live secret key' };
    }
  }
  return { body };
}

export function canAssignSubscription(
  permissions: Record<string, string[]> | null | undefined,
): boolean {
  if (!permissions) return false;
  const wildcard = permissions['*'] || [];
  if (wildcard.includes('*') || wildcard.includes('write')) return true;
  const packages = permissions.platform_packages || [];
  return packages.includes('write') || packages.includes('*');
}
