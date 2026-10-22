import Link from 'next/link';

export default function LoginLegalLinks() {
  return (
    <p className="login-legal">
      <Link href="/legal/terms">Terms of Service</Link>
      {' · '}
      <Link href="/legal/privacy">Privacy Policy</Link>
    </p>
  );
}
