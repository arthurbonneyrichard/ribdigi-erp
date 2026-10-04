/**
 * Umami analytics for the ERP UI (analytics.ribdigihouse.com).
 *
 * Values are baked at frontend image build time. Query strings are excluded
 * so reset links and other tokens are not stored. Tracking is limited to
 * erp.ribdigihouse.com unless NEXT_PUBLIC_UMAMI_DOMAINS overrides that.
 */
const DEFAULT_SRC = 'https://analytics.ribdigihouse.com/script.js';
const DEFAULT_WEBSITE_ID = '0d5b3d4e-fe16-47bf-91f2-6ce564fb2e0e';
const DEFAULT_DOMAINS = 'erp.ribdigihouse.com';

export default function UmamiScript() {
  const websiteId = (process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || DEFAULT_WEBSITE_ID).trim();
  const src = (process.env.NEXT_PUBLIC_UMAMI_SRC || DEFAULT_SRC).trim();
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
