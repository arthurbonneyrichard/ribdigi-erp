'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';

// [label, href, module, icon]
const items: [string, string, string, string][] = [
  ['Dashboard', '/dashboard', 'dashboard', '\ud83d\udcca'],
  ['Company', '/company', 'company', '\ud83c\udfe2'],
  ['Inventory', '/inventory', 'inventory', '\ud83d\udce6'],
  ['Sales', '/sales', 'sales', '\ud83e\uddfe'],
  ['POS', '/pos', 'pos', '\ud83d\uded2'],
  ['Purchasing', '/purchasing', 'purchasing', '\ud83d\ude9a'],
  ['Expenses', '/expenses', 'expenses', '\ud83d\udcb8'],
  ['Accounting', '/accounting', 'accounting', '\ud83d\udcd2'],
  ['Credit', '/credit', 'credit', '\ud83d\udcb3'],
  ['Tax', '/tax', 'tax', '\ud83e\uddee'],
  ['Multi-Store', '/stores', 'stores', '\ud83c\udfec'],
  ['Reports', '/reports', 'reports', '\ud83d\udcc8'],
  ['Notifications', '/notifications', 'notifications', '\ud83d\udd14'],
  ['Audit', '/audit', 'audit', '\ud83d\udd0d'],
  ['Backup', '/backup', 'backup', '\ud83d\udcbe'],
  ['Security', '/security', 'security', '\ud83d\udd12'],
  ['AI Assistant', '/ai', 'ai', '\ud83e\udd16'],
  ['Users', '/users', 'users', '\ud83d\udc65'],
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
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();

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
    <div className={`shell${menuOpen ? ' nav-open' : ''}`}>
      <aside className="side">
        <div className="brand">RIBDIGI ERP</div>
        <nav className="nav">
          {visible.map(([n, h, , icon]) => {
            const active = pathname === h || pathname.startsWith(`${h}/`);
            return (
              <Link
                key={h}
                href={h}
                className={active ? 'active' : undefined}
                aria-current={active ? 'page' : undefined}
                onClick={() => setMenuOpen(false)}
              >
                <span className="nav-ico" aria-hidden>
                  {icon}
                </span>
                <span className="nav-label">
                  {n}
                  {h === '/notifications' && unread > 0 ? ` (${unread})` : ''}
                </span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="side-backdrop" onClick={() => setMenuOpen(false)} aria-hidden />
      <main className="main">
        <div className="topbar">
          <button
            type="button"
            className="menu-btn"
            aria-label="Toggle navigation menu"
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span aria-hidden>{'\u2630'}</span> Menu
          </button>
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
