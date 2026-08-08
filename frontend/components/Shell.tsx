'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

const items = [
  ['Dashboard', '/dashboard'],
  ['Company', '/company'],
  ['Inventory', '/inventory'],
  ['Sales', '/sales'],
  ['POS', '/pos'],
  ['Purchasing', '/purchasing'],
  ['Expenses', '/expenses'],
  ['Accounting', '/accounting'],
  ['Credit', '/credit'],
  ['Tax', '/tax'],
  ['Multi-Store', '/stores'],
  ['Reports', '/reports'],
  ['Notifications', '/notifications'],
  ['Audit', '/audit'],
  ['Backup', '/backup'],
  ['Security', '/security'],
  ['AI Assistant', '/ai'],
  ['Users', '/users'],
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const r = await api('/notifications/unread-count');
        if (active) setUnread(r.data?.count || 0);
      } catch {
        if (active) setUnread(0);
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">RIBDIGI ERP</div>
        <nav className="nav">
          {items.map(([n, h]) => (
            <Link key={h} href={h}>
              {n}
              {h === '/notifications' && unread > 0 ? ` (${unread})` : ''}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          <Link href="/notifications" className="bell">
            Alerts{unread > 0 ? ` · ${unread}` : ''}
          </Link>
        </div>
        {children}
      </main>
    </div>
  );
}
