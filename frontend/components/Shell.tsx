'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { canReadModule } from '../lib/rbac';

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

export default function Shell({ children }: { children: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  const [permissions, setPermissions] = useState<Record<string, string[]> | null>(null);
  const [idleMinutes, setIdleMinutes] = useState(30);

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
        setIdleMinutes(Number(meRes.data?.inactivity_timeout_minutes) || 30);
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

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('token');
    if (!token) return;
    const timeoutMs = Math.max(5, idleMinutes) * 60 * 1000;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let loggingOut = false;

    async function performIdleLogout() {
      if (loggingOut) return;
      loggingOut = true;
      try {
        await api('/auth/idle-logout', { method: 'POST', body: '{}' });
      } catch {
        // Still clear local credentials if the server call fails (expired token, etc.)
      }
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/';
    }

    const reset = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        void performIdleLogout();
      }, timeoutMs);
    };
    const events = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'] as const;
    events.forEach((ev) => window.addEventListener(ev, reset, { passive: true }));
    reset();
    return () => {
      if (timer) clearTimeout(timer);
      events.forEach((ev) => window.removeEventListener(ev, reset));
    };
  }, [idleMinutes]);

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
