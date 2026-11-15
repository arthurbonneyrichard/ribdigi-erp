/**
 * Optional Umami analytics for the ERP UI. Off unless both
 * NEXT_PUBLIC_UMAMI_SRC and NEXT_PUBLIC_UMAMI_WEBSITE_ID are set at frontend
 * image build time (no built-in address, so a missing analytics server is
 * never requested). Query strings are excluded so reset links and other tokens
 * are not stored. Tracking is limited to erp.ribdigihouse.com unless
 * NEXT_PUBLIC_UMAMI_DOMAINS overrides that.
 */
const DEFAULT_DOMAINS = 'erp.ribdigihouse.com';

export default function UmamiScript() {
  const websiteId = (process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '').trim();
  const src = (process.env.NEXT_PUBLIC_UMAMI_SRC || '').trim();
  const domains = (process.env.NEXT_PUBLIC_UMAMI_DOMAINS || DEFAULT_DOMAINS).trim();
  if (!websiteId || !src) return null;

  return (
    <script
      defer
      src={src}
      data-website-id={websiteId}
      data-domains={domains}
      data-exclude-search="true"
    />
  );
}
