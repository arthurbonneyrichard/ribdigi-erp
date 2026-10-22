import type { Metadata } from 'next';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Terms of Service · RIBDIGI ERP',
};

export default function TermsPage() {
  return (
    <LegalDoc title="Terms of Service">
      <p>
        Effective 22 October 2026. These terms cover the RIBDIGI ERP application that a company
        signs in to. They do not cover a shopper website on that company’s own domain.
      </p>

      <h2>Provider</h2>
      <p>
        Ribdigi House provides the software. Public contact: Weija Old Barrier, Accra, Ghana;
        telephone 0302 944 376; email info@ribdigihouse.com. A registered company number is not
        published on this page. Use Help &amp; Support inside the signed-in app for an existing
        company.
      </p>

      <h2>Accounts and company records</h2>
      <p>
        Each company keeps its own records. Company data is scoped to that company. Staff sign in
        with a company id, email, and password. Shoppers on a company storefront are not ERP users.
        You must not share sign-in details, attempt to read another company’s records, or use the
        service to store unlawful data.
      </p>

      <h2>Fees, renewal, and refunds</h2>
      <p>
        Subscription fees are the amounts on that company’s assigned plan and invoices (trial,
        starter, professional, or enterprise, by term). Customer and till payments recorded in the
        ERP are tenders on the books. They are not a live collection of Ribdigi subscription fees.
        A checkout return does not mark a subscription invoice paid. An invoice becomes paid only
        when a signed billing webhook matches the company, amount, and currency, or when the
        platform owner records a matching payment.
      </p>
      <p>
        Canceling automatic renewal stops later charges and leaves access through the paid-through
        date. Failed charges may retry, then enter a grace period, then suspend access. Tenant data
        is not deleted because a charge failed. Subscription refunds are not automatic; ask
        Ribdigi House at info@ribdigihouse.com or through Help &amp; Support. Paid self-serve
        card collection is not live until Ribdigi House has configured a payment gateway.
      </p>

      <h2>Offline till</h2>
      <p>
        Offline till selling is a prepared-device queue for supported POS sales. It is not claimed
        as Offline Complete. A closed browser cannot upload. Clearing site data can remove the
        browser queue.
      </p>

      <h2>Liability</h2>
      <p>
        The service is provided as it is. Ribdigi House does not certify the product and does not
        promise uninterrupted access, a live payment gateway, or recovery of a till queue after
        site data is cleared. Ribdigi House is not liable for lost profits, lost stock accuracy
        after a device failure, or other indirect loss. For a paid company, liability for a claim
        about this service is limited to the subscription fees that company paid in the twelve
        months before the claim.
      </p>

      <h2>Termination and data export</h2>
      <p>
        Ribdigi House may suspend a company that breaks these terms or a paid plan that has ended.
        A company administrator can export records from Backup and from Reports while signed in.
        After access ends, ask Ribdigi House for a copy before the account is removed. A platform
        owner purge deletes that company’s tenant. It does not restore a cleared browser queue.
      </p>

      <h2>Governing law</h2>
      <p>
        These terms are governed by the laws of Ghana. Disputes are subject to the courts of Ghana.
      </p>

      <p>
        For questions, use Help &amp; Support inside the signed-in app, or contact Ribdigi House
        at the address above. A lawyer has not yet approved this page.
      </p>
    </LegalDoc>
  );
}
