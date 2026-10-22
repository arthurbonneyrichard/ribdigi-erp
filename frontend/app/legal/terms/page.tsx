import type { Metadata } from 'next';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Terms of Service · RIBDIGI ERP',
};

export default function TermsPage() {
  return (
    <LegalDoc title="Terms of Service">
      <p>
        These terms cover the RIBDIGI ERP application that a company signs in to. They do not cover a
        shopper website on that company’s own domain.
      </p>
      <p>
        Ribdigi House provides the software. Each company keeps its own records. Company data is
        scoped to that company. Staff sign in with a company id, email, and password. Shoppers on a
        company storefront are not ERP users.
      </p>
      <p>
        Customer and till payments recorded in the ERP are tenders on the books. They are not a live
        collection of Ribdigi subscription fees. A checkout return does not mark a subscription
        invoice paid.
      </p>
      <p>
        Offline till selling is a prepared-device queue for supported POS sales. It is not claimed as
        Offline Complete. A closed browser cannot upload. Clearing site data can remove the browser
        queue.
      </p>
      <p>
        You must not share sign-in details, attempt to read another company’s records, or use the
        service to store unlawful data. Ribdigi may suspend a company that breaks these terms or a
        paid plan that has ended.
      </p>
      <p>For questions, use Help &amp; Support inside the signed-in app, or contact Ribdigi House.</p>
    </LegalDoc>
  );
}
