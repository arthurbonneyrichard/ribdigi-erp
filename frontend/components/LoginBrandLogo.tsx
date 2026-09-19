'use client';

/**
 * Sign-in wordmark. The login card stays light on the green stage in every theme,
 * so the dark logo is always the one shown.
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
        src="/brand/logo-full-dark.png"
        alt={alt}
        width={1024}
        height={341}
      />
    </div>
  );
}
