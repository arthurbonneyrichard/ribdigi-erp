import type { Metadata } from 'next';
import LegalDoc from '../LegalDoc';

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy">
      <p>
        This policy covers the RIBDIGI ERP application. A company’s public shop on its own domain
        may publish a separate privacy page.
      </p>
      <p>
        We process account details used to sign in (company id, name, email, and optional phone),
        security events such as two-factor setup, and the business records a company enters (sales,
        purchases, stock, expenses, and support tickets).
      </p>
      <p>
        Company records stay on that company’s tenant. Platform staff see only what the owner
        console is built to show. We do not sell company data. Secrets are not placed in the public
        client bundle.
      </p>
      <p>
        Email and SMS leave our servers only when that company or the platform has configured a
        mail or SMS service. If those services are not set, verification and reset messages cannot
        be sent.
      </p>
      <p>
        Backups and restore follow the signed-in Backup screens and the operator runbooks. A restore
        is a deliberate action. Browser storage on a till holds only the offline sales queue for
        that signed-in device.
      </p>
      <p>To ask about personal data on an ERP account, open Help &amp; Support or contact Ribdigi House.</p>
    </LegalDoc>
  );
}
