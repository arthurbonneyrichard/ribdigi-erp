import type { Metadata } from 'next';
import LegalPage from '../LegalPage';

export const metadata: Metadata = {
  title: 'Refund Policy · RIBDIGI ERP',
};

// The text lives in lib/legalDefaults.ts and can be replaced from the owner console (Legal documents).
export default function RefundsPage() {
  return <LegalPage slug="refunds" />;
}
