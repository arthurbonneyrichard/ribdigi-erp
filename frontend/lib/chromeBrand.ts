/** Platform chrome marks for the sidebar (default until company upload). Never tenant documents. */

export const PLATFORM_SIDEBAR_LOGO = '/brand/logo-sidebar.png';
export const PLATFORM_DASHBOARD_LOGO = '/brand/logo-full-dark.png';

export function chromeLogoSrc(
  uploadedUrl: string | null | undefined,
  fallback: string,
): string {
  return uploadedUrl || fallback;
}

export function chromeLogoAlt(uploaded: boolean, companyName: string): string {
  const name = companyName.trim();
  return uploaded ? name || 'Company logo' : 'RIBDIGI ERP';
}
