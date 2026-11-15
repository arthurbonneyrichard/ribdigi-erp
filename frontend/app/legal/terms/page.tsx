import type { Metadata } from 'next';
import LegalPage from '../LegalPage';

export const metadata: Metadata = {
  title: 'Terms of Service · RIBDIGI ERP',
};

// The text lives in lib/legalDefaults.ts and can be replaced from the owner console (Legal documents).
export default function TermsPage() {
  return <LegalPage slug="terms" />;
}
