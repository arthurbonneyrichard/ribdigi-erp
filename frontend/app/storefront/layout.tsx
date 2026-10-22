import StorefrontShell from './StorefrontShell';
import './storefront.css';

export default function StorefrontLayout({ children }: { children: React.ReactNode }) {
  return <StorefrontShell>{children}</StorefrontShell>;
}
