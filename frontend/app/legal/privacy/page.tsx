import type { Metadata } from 'next';
import Link from 'next/link';
import LegalDoc from '../LegalDoc';

export const metadata: Metadata = {
  title: 'Privacy Policy · RIBDIGI ERP',
};

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy">
      <p>
        Effective 15 November 2026. This policy explains what personal information RIBDIGI ERP handles, why, who it
        is shared with, how long it is kept and what you can ask us to do with it. It covers the ERP application at
        erp.ribdigihouse.com. A company&apos;s own online shop, booking or menu page may publish its own privacy
        notice for its customers.
      </p>

      <h2>Who we are</h2>
      <p>
        RIBDIGI ERP is provided by Ribdigi House, Weija Old Barrier, Accra, Ghana. Telephone +233 30 294 4376,
        WhatsApp +233 53 053 7307, email info@ribdigihouse.com. Privacy questions and requests go to the same email
        address with &quot;Privacy&quot; in the subject, or through Help &amp; Support inside the app.
      </p>

      <h2>Two roles under Ghana&apos;s Data Protection Act, 2012 (Act 843)</h2>
      <p>
        <strong>Ribdigi House is the data controller</strong> for the details of the people who sign in to the ERP
        and for each company&apos;s subscription and billing records.
      </p>
      <p>
        <strong>Each company is the data controller</strong> for the business records it enters about its own
        customers, suppliers, guests, members, patients and staff. Ribdigi House processes those records only to run
        the ERP for that company and on its instructions. If a company holds information about you (for example as
        its customer or employee), contact that company first; we will help it answer you.
      </p>

      <h2>What we collect and why</h2>
      <ul>
        <li>
          <strong>Sign-in account:</strong> name, email, optional username and phone, role, company. Needed to give
          you access and to keep each company&apos;s records apart.
        </li>
        <li>
          <strong>Security records:</strong> your password (stored only as a one-way hash), two-factor and passkey
          details (secrets stored encrypted), sign-in sessions with the device&apos;s IP address and browser name, and
          an audit log of actions. Needed to protect accounts, investigate misuse and meet record-keeping duties.
        </li>
        <li>
          <strong>Subscription and billing:</strong> plan, amounts, VAT, invoices, the time and amount you agreed to
          for renewal, and payment references. Needed to bill fairly and show what was agreed.
        </li>
        <li>
          <strong>Support:</strong> the messages and files you send through Help &amp; Support, to answer you.
        </li>
        <li>
          <strong>Business records a company enters:</strong> sales, purchases, stock, accounts, and the people in
          them. Some desks hold more sensitive information because the company&apos;s work needs it: staff pay and
          statutory numbers on the HR desk, guest identity details on the hotel registration card, and the
          phone&apos;s location when a field rep or staff member checks in. Location is taken only at that moment and
          only when the company uses those features. The company decides what it enters.
        </li>
        <li>
          <strong>On your device:</strong> the browser keeps your sign-in, theme and menu choices, and a till&apos;s
          offline sales queue. See the <Link href="/legal/cookies">Cookie Policy</Link>.
        </li>
      </ul>
      <p>
        We do not sell personal information, do not use it for advertising and do not build profiles of people
        across sites.
      </p>

      <h2>Legal grounds</h2>
      <p>
        We process account, security and billing records because they are needed to provide the service you or your
        company signed up for, to comply with law (for example tax and accounting records), and for our legitimate
        interest in keeping the service secure. Optional marketing email and optional analytics rely on your consent,
        which you can withdraw at any time.
      </p>

      <h2>Who we share it with</h2>
      <p>
        Only the service providers needed to run the ERP, each receiving only what its job needs:
      </p>
      <ul>
        <li>our hosting and off-site backup storage providers, which store the database and its copies;</li>
        <li>
          email and SMS services (an SMTP mail service, and Twilio for SMS when a company turns it on), to deliver
          messages such as sign-in codes, receipts and notices;
        </li>
        <li>
          Paystack or Flutterwave, when a company pays its subscription by card or Mobile Money, or takes a Mobile
          Money payment at its till through its own Paystack account. Card numbers and PINs go to the payment
          provider, never to us;
        </li>
      </ul>
      <p>
        The ERP&apos;s AI features (insights, stock forecasts, reading receipts) run on our own servers. No outside AI
        service receives your information. If that ever changes, we will update this policy first.
      </p>
      <p>
        Exchange rates are fetched from public rate services without any personal information. We also share
        information when the law requires it, or to protect people or the service from harm. Platform staff see
        only what the owner console shows, and only for support, billing and security.
      </p>

      <h2>Payments</h2>
      <p>
        RIBDIGI ERP records payments that a company and its customers make. It does not itself receive, hold or
        settle customer money: Mobile Money and card payments go through the payment provider to the account of the
        company (or of Ribdigi House, for subscription fees).
      </p>

      <h2>International transfers</h2>
      <p>
        Some of these providers may store or handle information outside Ghana. Where they do, we use providers that
        protect it with contracts and security measures, and send only what the service needs.
      </p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Sign-in accounts: while the account is active; removed when it is deleted.</li>
        <li>
          A company&apos;s records: while it uses the service. After it leaves, we keep only what the law or an open
          billing dispute requires, then delete it.
        </li>
        <li>
          Accounting, tax and audit records: as long as Ghana law requires a business to keep them. The audit log
          cannot be edited.
        </li>
        <li>
          Backups: each company&apos;s daily copies follow its Backup settings; whole-database copies are kept for a
          limited number of days and older ones are deleted automatically.
        </li>
      </ul>

      <h2>Your rights</h2>
      <p>Under Act 843 you can ask us to:</p>
      <ul>
        <li>tell you what personal information we hold about you and give you a copy;</li>
        <li>correct information that is wrong (you can change your own name and phone in the app);</li>
        <li>delete it, unless we must keep it by law;</li>
        <li>stop processing it where it is not needed to provide the service, including marketing email;</li>
        <li>give a company its records in a form it can take elsewhere (company backups and report exports).</li>
      </ul>
      <p>
        To delete your own sign-in account, use <strong>Security &rarr; Privacy and your data</strong> after signing
        in. A company admin can also ask there for the whole company to be deleted. We confirm it is you with your
        password, may ask for more proof, and answer without undue delay and within the time Act 843 allows. Records the law requires us to keep, such as
        invoices and the books, stay without your name where possible. You may also complain to the Data Protection
        Commission of Ghana.
      </p>

      <h2>Email from us</h2>
      <p>
        Service messages about your account (sign-in codes, billing, security, outages) are part of the service.
        News and offers from Ribdigi House go to company admins and every one of them has an unsubscribe link. You
        can also turn them off under Security &rarr; Privacy and your data. Unsubscribing does not stop service
        messages.
      </p>

      <h2>Children</h2>
      <p>
        RIBDIGI ERP is a business system for adults working for a company. It is not meant for children and we do
        not knowingly let children sign in. A company may hold records about children in its own work (for example
        gym members or hotel guests); it is the controller for those records and must have the right to hold them.
      </p>

      <h2>Security</h2>
      <p>
        We use encrypted connections, one-way password hashing, encryption for stored secrets, separation of each
        company&apos;s records, two-factor sign-in, role-based access, rate limits and an audit log. No system can be
        made completely secure, and we do not claim it is. If a breach puts your information at risk, we will tell the
        affected companies and people, and the Data Protection Commission where the law requires it.
      </p>

      <h2>Changes</h2>
      <p>
        We will post any change here with a new effective date, and tell company admins by email when a change is
        significant.
      </p>
    </LegalDoc>
  );
}
