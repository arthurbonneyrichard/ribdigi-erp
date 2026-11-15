import type { Metadata } from 'next';
import LegalPage from '../LegalPage';

export const metadata: Metadata = {
  title: 'Privacy Policy · RIBDIGI ERP',
};

// The text lives in lib/legalDefaults.ts and can be replaced from the owner console (Legal documents).
export default function PrivacyPage() {
  return <LegalPage slug="privacy" />;
}
