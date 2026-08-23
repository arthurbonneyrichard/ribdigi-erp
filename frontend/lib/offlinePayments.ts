/**
 * Offline POS payment safety (§18) — cash default; no fabricated provider success.
 */

export const OFFLINE_CASH_METHODS = new Set(['cash']);

export const OFFLINE_PROVIDER_METHODS = new Set([
  'card',
  'wallet',
  'bank_transfer',
  'mobile_money',
  'momo',
  'online',
]);

export const OFFLINE_CREDIT_METHOD = 'credit';

export const OFFLINE_CREDIT_CACHED_NOTE = 'Cached customer credit data — revalidated on sync';

const SUPERVISOR_ROLES = new Set([
  'store_manager',
  'company_admin',
  'super_admin',
  'sales_officer',
  'accountant',
  'tenant_owner',
  'tenant_admin',
]);

export type OfflinePaymentContext = {
  role: string;
  permissions: Record<string, string[]> | null;
  customers: Array<{
    id: string;
    credit_limit?: number;
    balance?: number;
  }>;
  customerId: string;
};

export function normalizePaymentMethod(method: string | null | undefined): string {
  return (method || 'cash').trim().toLowerCase();
}

export function salePaymentMethods(body: Record<string, unknown>): string[] {
  const payments = body.payments;
  if (Array.isArray(payments) && payments.length) {
    return payments.map((p) =>
      normalizePaymentMethod(
        typeof p === 'object' && p && 'payment_method' in p
          ? String((p as { payment_method?: string }).payment_method || 'cash')
          : 'cash',
      ),
    );
  }
  return [normalizePaymentMethod(String(body.payment_method || 'cash'))];
}

export function canSupervisorOfflinePayment(
  role: string,
  permissions: Record<string, string[]> | null,
): boolean {
  const roleNorm = (role || 'cashier').trim().toLowerCase();
  if (SUPERVISOR_ROLES.has(roleNorm)) return true;
  if (!permissions) return false;
  return ['credit', 'expenses', 'purchasing'].some((module) =>
    (permissions[module] || []).includes('approve'),
  );
}

export function canOfflineCredit(
  permissions: Record<string, string[]> | null,
): boolean {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const credit = permissions.credit || [];
  return credit.includes('*') || credit.includes('read') || credit.includes('write');
}

export function hasCachedCustomerCredit(
  ctx: OfflinePaymentContext,
): boolean {
  if (!ctx.customerId) return false;
  const customer = ctx.customers.find((c) => c.id === ctx.customerId);
  if (!customer) return false;
  return customer.credit_limit != null || customer.balance != null;
}

export type OfflinePaymentPrep = {
  payloadMeta: Record<string, unknown>;
  userMessage?: string;
  blocked?: boolean;
  error?: string;
  requiresSupervisorPrompt?: boolean;
};

export function prepareOfflineSalePayments(
  body: Record<string, unknown>,
  ctx: OfflinePaymentContext,
  opts?: { supervisorReason?: string },
): OfflinePaymentPrep {
  const methods = salePaymentMethods(body);
  const payloadMeta: Record<string, unknown> = {
    offline_queued_at: new Date().toISOString(),
  };
  const isSupervisor = canSupervisorOfflinePayment(ctx.role, ctx.permissions);

  for (const method of methods) {
    if (OFFLINE_CASH_METHODS.has(method)) continue;

    if (method === OFFLINE_CREDIT_METHOD) {
      if (!ctx.customerId) {
        return {
          payloadMeta,
          blocked: true,
          error: 'Offline credit requires a registered customer',
        };
      }
      if (!hasCachedCustomerCredit(ctx)) {
        return {
          payloadMeta,
          blocked: true,
          error: 'Offline credit requires cached customer credit data from the last online load',
        };
      }
      if (!canOfflineCredit(ctx.permissions)) {
        return {
          payloadMeta,
          blocked: true,
          error: 'Missing credit permission for offline credit sales',
        };
      }
      payloadMeta.offline_credit_cached_ack = true;
      payloadMeta.offline_payment_note = OFFLINE_CREDIT_CACHED_NOTE;
      continue;
    }

    if (OFFLINE_PROVIDER_METHODS.has(method) || !OFFLINE_CASH_METHODS.has(method)) {
      if (!isSupervisor) {
        return {
          payloadMeta,
          blocked: true,
          error: `Offline ${method} payments are blocked for cashiers — use cash or wait until online`,
        };
      }
      const reason = (opts?.supervisorReason || '').trim();
      if (reason.length < 3) {
        return {
          payloadMeta,
          blocked: true,
          requiresSupervisorPrompt: true,
          error: `Supervisor acknowledgment required for offline ${method} (provider not verified)`,
        };
      }
      payloadMeta.offline_supervisor_ack = true;
      payloadMeta.offline_supervisor_reason = reason;
      payloadMeta.offline_provider_pending_verification = true;
      payloadMeta.offline_payment_note =
        'Provider payment queued offline — pending verification on sync (not provider-approved)';
    }
  }

  return {
    payloadMeta,
    userMessage: payloadMeta.offline_payment_note
      ? String(payloadMeta.offline_payment_note)
      : undefined,
  };
}

export function isOfflineProviderMethod(method: string): boolean {
  const norm = normalizePaymentMethod(method);
  return OFFLINE_PROVIDER_METHODS.has(norm);
}

export function isOfflineCheckout(online: boolean): boolean {
  return typeof navigator !== 'undefined' && (!online || !navigator.onLine);
}
