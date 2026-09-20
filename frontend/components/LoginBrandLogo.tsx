'use client';

/**
 * Sign-in wordmark. The login card is always the dark green card, so the
 * white wordmark is the one shown in light and dark app themes.
 */
export default function LoginBrandLogo({
  alt = 'RIBDIGI ERP — One System. Total Business Control.',
}: {
  alt?: string;
}) {
  return (
    <div className="login-brand">
      <img
        className="login-logo"
        src="/brand/logo-full.png"
        alt={alt}
        width={1024}
        height={341}
      />
    </div>
  );
}
