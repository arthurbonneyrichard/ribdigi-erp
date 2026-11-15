import type { Metadata } from 'next';
import Link from 'next/link';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Refund Policy · RIBDIGI ERP',
};

export default function RefundsPage() {
  return (
    <LegalDoc title="Refund Policy">
      <p>
        Effective 15 November 2026. This policy covers RIBDIGI ERP subscription payments made to Ribdigi House. It
        does not cover payments your customers make to your company; those are between you and your customer. This
        policy does not take away any right you have under Ghana&apos;s consumer protection law.
      </p>

      <h2>Free trial</h2>
      <p>
        The 14-day trial is free and nothing is charged during it. It ends on its own, so there is nothing to cancel
        and nothing to refund.
      </p>

      <h2>Cancelling a subscription</h2>
      <p>
        Turn off renewal at any time on Company &rarr; Billing. You keep access until the end of the period you have
        paid for, and you are not charged again. Turning renewal off does not by itself refund the current period.
      </p>
      <p>
        If you cancel within 14 days of your first paid period and ask for a refund, we refund that first payment in
        full. After that, if the service has not worked as described and we could not fix it, ask us and we will
        offer a fair refund for the unused part of the period.
      </p>

      <h2>Payments we always refund</h2>
      <ul>
        <li><strong>Duplicate payments:</strong> if the same invoice was paid twice, the extra payment is refunded in full.</li>
        <li>
          <strong>Failed transactions:</strong> if money left your account but the payment did not complete and the
          invoice was not marked paid, we either mark the invoice paid or refund the money, whichever you prefer.
        </li>
        <li>
          <strong>Payments made by mistake:</strong> a payment for the wrong company or the wrong plan, reported to us
          within 14 days and before the plan was used, is refunded in full or moved to the right invoice.
        </li>
        <li>
          <strong>Payments you did not authorise:</strong> tell us and your bank or Mobile Money provider straight away.
          We stop further charges on that card or wallet, investigate with the payment provider, and refund a payment
          that was not authorised by your company.
        </li>
      </ul>

      <h2>Charges we cannot return</h2>
      <p>
        Ribdigi House adds no fees on top of the price shown on Company &rarr; Billing, and charges no fee for a
        refund. Charges made by your own bank or Mobile Money provider (for example for currency conversion) are
        theirs and may not come back with the refund. If VAT was charged, it is refunded with the payment it was part
        of.
      </p>

      <h2>Billing disputes</h2>
      <p>
        If you think an amount is wrong, contact us before raising a dispute with your bank, so we can usually fix it
        faster. We do not suspend an account over an invoice while we are looking into your complaint about it.
      </p>

      <h2>How to ask and how long it takes</h2>
      <p>
        Email info@ribdigihouse.com with &quot;Refund&quot; in the subject, or use Help &amp; Support. Give your company
        name, the invoice number and the reason. We reply within five working days. Approved refunds go back the way
        you paid: card and Mobile Money refunds normally appear within 5 to 10 working days after we approve them,
        depending on your provider; bank transfers within 5 working days.
      </p>
      <p>
        Questions about subscriptions in general are covered in the <Link href="/legal/terms">Terms of Service</Link>.
      </p>
    </LegalDoc>
  );
}
