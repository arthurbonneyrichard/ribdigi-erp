'use client';

import { useEffect } from 'react';

/** Shows a company's own icon and name on the browser tab of its public pages. */
export function usePageIcon(href: string | null | undefined, title?: string | null) {
  useEffect(() => {
    const previousTitle = document.title;
    if (title) document.title = title;
    const links = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel~="icon"], link[rel="apple-touch-icon"]'));
    const saved = links.map((l) => [l, l.href] as const);
    let added: HTMLLinkElement | null = null;
    if (href) {
      if (links.length) {
        links.forEach((l) => {
          l.href = href;
          l.removeAttribute('sizes');
          l.removeAttribute('type');
        });
      } else {
        added = document.createElement('link');
        added.rel = 'icon';
        added.href = href;
        document.head.appendChild(added);
      }
    }
    return () => {
      document.title = previousTitle;
      saved.forEach(([l, old]) => {
        l.href = old;
      });
      added?.remove();
    };
  }, [href, title]);
}
