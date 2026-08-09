'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

const items: [string, string, string][] = [
  ['Dashboard', '/dashboard', 'dashboard'],
  ['Company', '/company', 'company'],
  ['Inventory', '/inventory', 'inventory'],
  ['Sales', '/sales', 'sales'],
  ['POS', '/pos', 'pos'],
  ['Purchasing', '/purchasing', 'purchasing'],
  ['Expenses', '/expenses', 'expenses'],
  ['Accounting', '/accounting', 'accounting'],
  ['Credit', '/credit', 'credit'],
  ['Tax', '/tax', 'tax'],
  ['Multi-Store', '/stores', 'stores'],
  ['Reports', '/reports', 'reports'],
  ['Notifications', '/notifications', 'notifications'],
  ['Audit', '/audit', 'audit'],
  ['Backup', '/backup', 'backup'],
  ['Security', '/security', 'security'],
  ['AI Assistant', '/ai', 'ai'],
  ['Users', '/users', 'users'],
];

function canReadModule(permissions: Record<string, string[]> | null | undefined, module: string) {
  if (!permissions) return false;
  if (permissions['*']?.includes('*')) return true;
  const actions = permissions[module] || [];
  return actions.includes('*') || actions.includes('read') || actions.includes('write');
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [countRes, meRes] = await Promise.all([
          api('/notifications/unread-count').catch(() => ({ data: { count: 0 } })),
          api('/me'),
        ]);
        if (!active) return;
        setUnread(countRes.data?.count || 0);
        setPermissions(meRes.data?.permissions || {});
      } catch {
        if (active) {
          setUnread(0);
          setPermissions({});
        }
      }
    }
    load();
    const id = setInterval(load, 30000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const visible = items.filter(([, , module]) => canReadModule(permissions, module));

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">RIBDIGI ERP</div>
        <nav className="nav">
          {visible.map(([n, h]) => (
            <Link key={h} href={h}>
              {n}
              {h === '/notifications' && unread > 0 ? ` (${unread})` : ''}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar">
          {canReadModule(permissions, 'notifications') && (
            <Link href="/notifications" className="bell">
              Alerts{unread > 0 ? ` · ${unread}` : ''}
            </Link>
          )}
        </div>
        {children}
      </main>
    </div>
  );
}
