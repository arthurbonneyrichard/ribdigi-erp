/**
 * Minimal i18n scaffold (ADR-006 / BR-2.7).
 * Commercial MVP ships English only; additional locales plug into catalogs later.
 */

export const DEFAULT_LOCALE = 'en' as const;
export const SUPPORTED_LOCALES = ['en'] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

const en = {
  'app.name': 'RIBDIGI BUSINESS ERP',
  'language.mvp_only':
    'UI language is English for the commercial MVP. Additional language packs will plug into this i18n scaffold later.',
  'language.label': 'Language',
  'language.english': 'English',
} as const;

export type MessageKey = keyof typeof en;

const catalogs: Record<AppLocale, Record<MessageKey, string>> = {
  en,
};

export function isSupportedLocale(value: string | null | undefined): value is AppLocale {
  return value === 'en';
}

export function t(key: MessageKey, locale: AppLocale = DEFAULT_LOCALE): string {
  const catalog = catalogs[locale] || catalogs.en;
  return catalog[key] || catalogs.en[key] || key;
}
