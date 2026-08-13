import './globals.css';
import ServiceWorkerRegister from '../components/ServiceWorkerRegister';
import type { Metadata, Viewport } from 'next';

export const metadata: Metadata = {
  title: 'RIBDIGI ERP',
  description: 'One ERP Platform. Unlimited Business.',
  manifest: '/manifest.webmanifest',
  applicationName: 'RIBDIGI',
  appleWebApp: {
    capable: true,
    title: 'RIBDIGI',
    statusBarStyle: 'default',
  },
};

export const viewport: Viewport = {
  themeColor: '#111827',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ServiceWorkerRegister />
        {children}
      </body>
    </html>
  );
}
