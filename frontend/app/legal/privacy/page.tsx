import type { Metadata } from 'next';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Privacy Policy · RIBDIGI ERP',
};

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy">
      <p>
        Effective 22 October 2026. This policy covers the RIBDIGI ERP application. A company’s
        public shop on its own domain may publish a separate privacy page.
      </p>

      <h2>Who we are</h2>
      <p>
        Ribdigi House provides RIBDIGI ERP. Public contact: Weija Old Barrier, Accra, Ghana;
        telephone 0302 944 376; email info@ribdigihouse.com. This policy is written to follow
        Ghana’s Data Protection Act, 2012 (Act 843). A lawyer has not yet approved this page.
      </p>

      <h2>What we process</h2>
      <p>
        We process account details used to sign in (company id, name, email, and optional phone),
        security events such as two-factor setup, billing invoices for that company, and the
        business records a company enters (sales, purchases, stock, expenses, and support
        tickets).
      </p>

      <h2>Roles under Act 843</h2>
      <p>
        For business records a company enters about its own customers, suppliers, and staff, that
        company is the data controller. Ribdigi House processes those records to run the ERP for
        that company. For platform account and subscription records (sign-in email, plan, invoices),
        Ribdigi House is the data controller.
      </p>

      <h2>Why we process it</h2>
      <p>
        We process this information to provide the signed-in product, keep companies isolated from
        each other, send verification or reset messages when email or SMS is configured, collect
        or record subscription fees, and keep an audit trail. We do not sell company or personal
        data.
      </p>

      <h2>Sharing</h2>
      <p>
        Company records stay on that company’s tenant. Platform staff see only what the owner
        console is built to show. Email and SMS leave our servers only when that company or the
        platform has configured a mail or SMS service. If those services are not set, verification
        and reset messages cannot be sent. Secrets are not placed in the public client bundle.
      </p>

      <h2>Retention</h2>
      <p>
        Account and company records stay while the company uses the service and through any
        paid-through date after renewal is cancelled. Backups follow the signed-in Backup screens
        and the operator runbooks. After an account is closed or purged, remaining copies are kept
        only as long as billing disputes or Ghana law require, then deleted. Browser storage on a
        till holds only the offline sales queue for that signed-in device.
      </p>

      <h2>Your rights under Act 843</h2>
      <p>
        A person may ask to see, correct, or delete personal data we hold, or object to processing
        that is not required to run the account. For data a company entered about its own people,
        start with that company. For a platform account, open Help &amp; Support or email
        info@ribdigihouse.com. We may refuse a deletion that would break a legal or accounting
        record we must keep.
      </p>

      <h2>Security</h2>
      <p>
        A restore is a deliberate action. Passwords are stored hashed. Access follows the signed-in
        role. This is not a certification that every risk is removed.
      </p>

      <p>
        To ask about personal data on an ERP account, open Help &amp; Support or contact Ribdigi
        House at the address above.
      </p>
    </LegalDoc>
  );
}
