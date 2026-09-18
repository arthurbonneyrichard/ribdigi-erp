import UmamiScript from '../components/UmamiScript';
import './globals.css';

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

// Runs before paint to avoid a flash of the wrong theme. Uses the saved
// preference if present, otherwise follows the device (prefers-color-scheme).
const themeInit = `(function(){try{var t=localStorage.getItem('theme');var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.setAttribute('data-theme',(t==='light'||t==='dark')?t:(m?'dark':'light'));}catch(e){}})();`;

const swInit = `(function(){try{if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <script dangerouslySetInnerHTML={{ __html: swInit }} />
      </head>
      <body>
        <UmamiScript />
        {children}
      </body>
    </html>
  );
}
