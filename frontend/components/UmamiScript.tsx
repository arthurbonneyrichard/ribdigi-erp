import Script from 'next/script';

/**
 * Umami analytics for the ERP UI.
 *
 * Disabled unless NEXT_PUBLIC_UMAMI_WEBSITE_ID is set at frontend build time
 * (Next inlines NEXT_PUBLIC_* during `next build`). Query strings are excluded
 * so reset links and other tokens are not stored in analytics.
 */
export default function UmamiScript() {
  const websiteId = (process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID || '').trim();
  if (!websiteId) return null;

  const src = (process.env.NEXT_PUBLIC_UMAMI_SRC || 'https://cloud.umami.is/script.js').trim();
  const domains = (process.env.NEXT_PUBLIC_UMAMI_DOMAINS || '').trim();

  return (
    <Script
      src={src}
      strategy="afterInteractive"
      data-website-id={websiteId}
      data-exclude-search="true"
      {...(domains ? { 'data-domains': domains } : {})}
    />
  );
}
