'use client';

/**
 * Login / auth wordmark: dark glyphs on the light card, white glyphs when the
 * card is dark (`data-theme="dark"`).
 */
export default function LoginBrandLogo({
  alt = 'RIBDIGI ERP — One System. Total Business Control.',
}: {
  alt?: string;
}) {
  return (
    <div className="login-brand">
      <img
        className="login-logo login-logo-on-light"
        src="/brand/logo-full-dark.png"
        alt={alt}
        width={1024}
        height={341}
      />
      <img
        className="login-logo login-logo-on-dark"
        src="/brand/logo-full.png"
        alt={alt}
        width={1024}
        height={341}
      />
    </div>
  );
}
