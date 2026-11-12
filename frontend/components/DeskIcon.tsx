/**
 * Line icons for the desk screens. One stroke weight, 24px grid, drawn in currentColor so
 * they follow the text colour in light and dark mode. Decorative: always paired with words.
 */

const PATHS: Record<string, string> = {
  home: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  cash: 'M3 7h18v10H3zM7 7v10M17 7v10M12 10a2 2 0 1 0 0 4a2 2 0 1 0 0-4',
  bag: 'M6 8h12l1 12H5zM9 8V6a3 3 0 0 1 6 0v2',
  cart: 'M3 4h2l2.4 11h10.2L20 7H6.2M9 20a1 1 0 1 0 0-.01M17 20a1 1 0 1 0 0-.01',
  receipt: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3',
  truck: 'M2 6h11v10H2zM13 10h4l3 3v3h-7M6 19a2 2 0 1 0 0-.01M17 19a2 2 0 1 0 0-.01',
  flame: 'M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-7 1 1 2 2 3 2 0-2-1-3 0-5z',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
  box: 'M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10',
  wallet: 'M3 7h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H3zM3 7l12-3v3M16 13h2',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  clock: 'M12 7v5l3 2M12 21a9 9 0 1 0 0-18a9 9 0 1 0 0 18',
  users: 'M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6M3 20a6 6 0 0 1 12 0M16 5a3 3 0 0 1 0 6M18 14a5 5 0 0 1 3 6',
  alert: 'M12 3l10 18H2zM12 10v4M12 17v.01',
  check: 'M4 12l5 5L20 6',
  plus: 'M12 5v14M5 12h14',
  search: 'M11 18a7 7 0 1 0 0-14a7 7 0 1 0 0 14M21 21l-5-5',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  bread: 'M5 20V11a3.5 3.5 0 0 1 0-7h14a3.5 3.5 0 0 1 0 7v9zM9 7.5l-1.5 3M13 7.5l-1.5 3M17 7.5l-1.5 3',
  cake: 'M4 21h16M5 21v-7h14v7M5 16c2 1 3 1 5 0s3-1 5 0 3 1 4 0M12 14V9M12 6v.01',
  phone: 'M5 3h4l2 5-3 2a11 11 0 0 0 6 6l2-3 5 2v4a2 2 0 0 1-2 2A17 17 0 0 1 3 5a2 2 0 0 1 2-2',
  map: 'M12 21s-7-6-7-11a7 7 0 0 1 14 0c0 5-7 11-7 11zM12 12a2 2 0 1 0 0-4a2 2 0 1 0 0 4',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  print: 'M7 9V3h10v6M7 17H4v-7h16v7h-3M7 14h10v7H7z',
  download: 'M12 4v11M7 10l5 5 5-5M4 20h16',
  door: 'M5 21V3h11l3 2v16M5 21h14M13 12v.01',
  calendarCheck: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M9 15l2 2 4-4',
  tag: 'M3 12V3h9l9 9-9 9zM7 7v.01',
  leaf: 'M5 19C5 9 11 4 20 4c0 9-5 15-15 15zM5 19l8-8',
  mail: 'M3 6h18v12H3zM3 7l9 6 9-6',
  send: 'M21 3L10 14M21 3l-7 18-4-7-7-4z',
}

export default function DeskIcon({ name, size = 20 }: { name: string; size?: number }) {
  const d = PATHS[name] || PATHS.box;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={d} />
    </svg>
  );
}
