import type { Metadata } from 'next';
import Link from 'next/link';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Terms of Service · RIBDIGI ERP',
};

export default function TermsPage() {
  return (
    <LegalDoc title="Terms of Service">
      <p>
        Effective 15 November 2026. These terms are an agreement between Ribdigi House and the company that uses
        RIBDIGI ERP (&quot;the company&quot;, &quot;you&quot;). They cover the ERP application. They do not cover a
        shop, booking or menu website a company runs for its own customers.
      </p>

      <h2>Provider</h2>
      <p>
        Ribdigi House, Weija Old Barrier, Accra, Ghana. Telephone +233 30 294 4376, WhatsApp +233 53 053 7307, email
        info@ribdigihouse.com. Existing customers can also use Help &amp; Support inside the app.
      </p>

      <h2>Who can use it</h2>
      <p>
        RIBDIGI ERP is for businesses. The person who opens a company account must be at least 18 and allowed to
        bind that business to these terms. Staff accounts are created by the company&apos;s admin, who is responsible
        for who has access and with what role.
      </p>

      <h2>Your account and your company&apos;s records</h2>
      <p>
        Each company&apos;s records are kept separate from every other company&apos;s. Keep sign-in details private,
        use two-factor sign-in where offered, and tell us at once if you think an account has been misused. You are
        responsible for what is done under your company&apos;s accounts and for the accuracy of the records you
        enter. When your records include other people&apos;s personal information, you are its data controller and
        must have the right to hold and use it (see the <Link href="/legal/privacy">Privacy Policy</Link>).
      </p>

      <h2>Acceptable use</h2>
      <p>You must not:</p>
      <ul>
        <li>try to read, change or delete another company&apos;s records, or test the system&apos;s security without our written permission;</li>
        <li>store or send unlawful, fraudulent or infringing material, or use the ERP to deceive customers;</li>
        <li>send spam or messages people did not agree to receive through the email or SMS features;</li>
        <li>overload, scrape or copy the service, or resell it without an agreement with us;</li>
        <li>remove or work around limits, licences or security controls.</li>
      </ul>

      <h2>Plans, free trial and fees</h2>
      <p>
        The price, currency (normally Ghana cedis), billing period and any VAT for your company&apos;s plan are shown
        on Company &rarr; Billing before you agree to pay. A new company gets one free trial of 14 days. The trial
        ends on its own; it never turns into a paid plan without your agreement, and nothing is charged during it.
      </p>

      <h2>Renewal and payment</h2>
      <p>
        If you agree to automatic renewal, the plan renews at the end of each period at the amount you agreed to,
        until you turn renewal off. If the price or VAT changes, you will be asked to agree again before a new amount
        is charged. Payment is by card or Mobile Money through our payment provider (Paystack or Flutterwave), or by
        bank transfer recorded by Ribdigi House. Ribdigi House adds no fee on top of the amount shown; your bank or
        Mobile Money provider may apply its own charges. An invoice is marked paid only when the payment provider
        confirms the payment or Ribdigi House records it.
      </p>
      <p>
        If a renewal payment fails, it may be tried again, then a grace period starts, and after that access may be
        suspended until the invoice is paid. Your records are not deleted because a payment failed.
      </p>

      <h2>Cancelling</h2>
      <p>
        You can turn off renewal at any time on Company &rarr; Billing. Access continues until the end of the period
        already paid, and no further charge is made. Refunds are explained in the{' '}
        <Link href="/legal/refunds">Refund Policy</Link>.
      </p>

      <h2>Payments your company takes</h2>
      <p>
        RIBDIGI ERP records sales, payments and balances. It does not itself receive, hold, process or settle your
        customers&apos; money. Card and Mobile Money payments you take at the till go through your own payment
        provider account to your own account; cash and bank payments are only recorded. Disputes about a
        customer&apos;s payment are between you, your customer and your payment provider.
      </p>

      <h2>Who owns what</h2>
      <p>
        Your company owns its records. You give Ribdigi House permission to store and process them only to provide,
        secure and support the service. Ribdigi House owns the software, its design and the RIBDIGI name and logos;
        you get the right to use the ERP for your business while your account is active. Suggestions you send us may
        be used to improve the product.
      </p>

      <h2>Exporting your data</h2>
      <p>
        A company admin can download company backups from Backup and export reports while signed in. Before an
        account is closed we give the company a chance to take its data. After access ends, ask us within 30 days and
        we will provide a copy if it still exists.
      </p>

      <h2>Availability and maintenance</h2>
      <p>
        We work to keep the ERP available and back it up every day, but we do not promise it will always be
        available or free of errors. Updates can briefly interrupt access; we schedule large changes for quiet hours
        where we can and tell admins in advance about planned work that will take longer. The till can keep selling
        for a time without internet; sales wait on that device until it reconnects, and clearing the browser&apos;s
        site data removes any that have not been sent.
      </p>

      <h2>Suspension and ending the agreement</h2>
      <p>
        You can stop using the service and ask for your company to be deleted at any time (Security &rarr; Privacy and
        your data). We may suspend or end an account that breaks these terms, puts others at risk, or has an invoice
        unpaid after the grace period. Where we can, we warn you first and give you time to fix the problem or take
        your data.
      </p>

      <h2>Liability</h2>
      <p>
        The service is provided with reasonable care and skill. To the extent the law allows, Ribdigi House is not
        liable for lost profits, lost business or other indirect loss, or for loss caused by inaccurate records you
        enter, a device you control, or events outside our reasonable control. Our total liability for any claim is
        limited to the subscription fees your company paid in the twelve months before the claim. Nothing in these
        terms limits rights you have under Ghana law that cannot be limited, or liability for fraud or deliberate
        wrongdoing.
      </p>

      <h2>Disputes</h2>
      <p>
        Tell us about a problem first at info@ribdigihouse.com or through Help &amp; Support; we aim to answer within
        five working days and to resolve it fairly. If we cannot agree, either side may refer the dispute to
        mediation in Accra before going to court. These terms are governed by the laws of Ghana, and the courts of
        Ghana have jurisdiction.
      </p>

      <h2>Changes to these terms</h2>
      <p>
        We may update these terms. We will post the new version here with its date and email company admins at least
        30 days before a change that reduces your rights or raises your price takes effect. A price change applies
        only after you agree to it on Company &rarr; Billing.
      </p>
    </LegalDoc>
  );
}
