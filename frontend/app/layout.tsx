import './globals.css';

export const metadata = {
  title: 'RIBDIGI ERP',
  description: 'One ERP Platform. Unlimited Business.',
};

// Runs before paint to avoid a flash of the wrong theme. Uses the saved
// preference if present, otherwise follows the device (prefers-color-scheme).
const themeInit = `(function(){try{var t=localStorage.getItem('theme');var m=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.setAttribute('data-theme',(t==='light'||t==='dark')?t:(m?'dark':'light'));}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
