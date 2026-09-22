import UmamiScript from '../components/UmamiScript';
import './globals.css';

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#4AB012',
};

export const metadata = {
  title: 'RIBDIGI ERP',
  description: 'One System. Total Business Control. A Ribdigi House Product.',
  themeColor: '#4AB012',
  applicationName: 'RIBDIGI ERP',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: 'any' },
      { url: '/icon.png', type: 'image/png' },
    ],
    apple: [{ url: '/apple-icon.png', sizes: '180x180', type: 'image/png' }],
  },
  openGraph: {
    title: 'RIBDIGI ERP',
    description: 'One System. Total Business Control. A Ribdigi House Product.',
    siteName: 'RIBDIGI ERP',
    images: [{ url: '/brand/logo-full.png', alt: 'RIBDIGI ERP — One System. Total Business Control.' }],
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'RIBDIGI ERP',
    description: 'One System. Total Business Control. A Ribdigi House Product.',
    images: ['/brand/logo-full.png'],
  },
};

// Runs before paint to avoid a flash of the wrong theme.
// Prefer the active signed-in user's scoped key when present; otherwise light (white) default.
const themeInit = `(function(){try{var uid=localStorage.getItem('ribdigi.theme.userId');var t=uid?localStorage.getItem('ribdigi.theme.'+uid):null;if(t!=='light'&&t!=='dark'){t='light'}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','light')}})();`;

const swInit = `(function(){try{if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <script dangerouslySetInnerHTML={{ __html: swInit }} />
        <UmamiScript />
      </head>
      <body>{children}</body>
    </html>
  );
}
