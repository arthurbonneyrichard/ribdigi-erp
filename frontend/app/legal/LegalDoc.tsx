import type { ReactNode } from 'react';
import Link from 'next/link';
import LoginBrandLogo from '../../components/LoginBrandLogo';
import LoginLegalLinks from '../../components/LoginLegalLinks';

export default function LegalDoc({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="login-stage">
      <div className="login legal-doc">
        <LoginBrandLogo />
        <h1 className="login-heading">{title}</h1>
        <div className="legal-doc-body">{children}</div>
        <p className="login-foot">
          <Link href="/">Back to sign in</Link>
        </p>
        <LoginLegalLinks />
      </div>
    </div>
  );
}
