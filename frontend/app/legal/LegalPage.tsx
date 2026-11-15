'use client';

import { useEffect, useState } from 'react';
import LegalDoc from './LegalDoc';
import LegalMarkdown from '../../components/LegalMarkdown';
import { api } from '../../lib/api';
import { LEGAL_DEFAULTS, type LegalSlug } from '../../lib/legalDefaults';

/**
 * A public legal page. Shows the built-in text at once, then the version the software owner
 * published in the console (Legal documents), if there is one.
 */
export default function LegalPage({ slug }: { slug: LegalSlug }) {
  const [doc, setDoc] = useState<{ title: string; body: string }>(LEGAL_DEFAULTS[slug]);

  useEffect(() => {
    let alive = true;
    api(`/legal/${slug}`)
      .then((r: any) => {
        const d = r?.data;
        if (alive && d && typeof d.body === 'string' && d.body.trim()) setDoc({ title: d.title || LEGAL_DEFAULTS[slug].title, body: d.body });
      })
      .catch(() => {
        /* keep the built-in text */
      });
    return () => {
      alive = false;
    };
  }, [slug]);

  return (
    <LegalDoc title={doc.title}>
      <LegalMarkdown text={doc.body} />
    </LegalDoc>
  );
}
