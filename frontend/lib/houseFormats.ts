/** House console regional formats (Stage 92 K1) — reuse format.ts helpers. */

import { api } from './api';
import type { RegionalFormats } from './format';

export const HOUSE_FORMAT_DEFAULTS: Required<RegionalFormats> = {
  date_format: 'DD/MM/YYYY',
  number_format: '1,234.56',
  time_format: '24h',
};

export async function fetchHouseFormats(): Promise<Required<RegionalFormats>> {
  try {
    const r = await api('/platform/settings');
    return {
      date_format: r.data?.date_format || HOUSE_FORMAT_DEFAULTS.date_format,
      number_format: HOUSE_FORMAT_DEFAULTS.number_format,
      time_format: r.data?.time_format || HOUSE_FORMAT_DEFAULTS.time_format,
    };
  } catch {
    return { ...HOUSE_FORMAT_DEFAULTS };
  }
}
