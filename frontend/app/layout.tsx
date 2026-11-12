import UmamiScript from '../components/UmamiScript';
import './globals.css';

export const viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: '#4AB012',
};

export const metadata = {
  metadataBase: new URL('https://erp.ribdigihouse.com'),
  title: 'RIBDIGI ERP',
  description: 'One System. Total Business Control. A Ribdigi House Product.',
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

// Clicking anywhere in a date box opens the calendar, not only the small icon.
const datePickerInit = `(function(){try{var T={date:1,'datetime-local':1,month:1,week:1};document.addEventListener('click',function(e){var el=e.target;if(!el||el.tagName!=='INPUT'||!T[el.type]||el.disabled||el.readOnly||typeof el.showPicker!=='function')return;try{el.showPicker()}catch(_){}},true)}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preload" as="image" href="/brand/logo-full.png" fetchPriority="high" />
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <script dangerouslySetInnerHTML={{ __html: swInit }} />
        <script dangerouslySetInnerHTML={{ __html: datePickerInit }} />
        <UmamiScript />
      </head>
      <body>{children}</body>
    </html>
  );
}
