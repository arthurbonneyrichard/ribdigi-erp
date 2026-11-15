'use client';

import { Fragment } from 'react';
import Link from 'next/link';
import CookieSettingsButton from './CookieSettingsButton';
import { analyticsConfigured } from '../lib/consent';
import { parseLegalText, type Inline } from '../lib/legalText';

function Parts({ parts }: { parts: Inline[] }) {
  return (
    <>
      {parts.map((p, i) => {
        if (p.kind === 'bold') return <strong key={i}>{p.text}</strong>;
        if (p.kind === 'link')
          return p.href.startsWith('/') ? (
            <Link key={i} href={p.href}>
              {p.text}
            </Link>
          ) : (
            <a key={i} href={p.href} rel="noopener noreferrer">
              {p.text}
            </a>
          );
        if (p.kind === 'analytics_status')
          return (
            <Fragment key={i}>
              {analyticsConfigured()
                ? 'It is turned on for this site, so you are asked before it loads.'
                : 'It is currently turned off, so no banner is shown.'}
            </Fragment>
          );
        return <Fragment key={i}>{p.text}</Fragment>;
      })}
    </>
  );
}

/** Renders the legal-page markup as React elements only (no HTML is ever injected). */
export default function LegalMarkdown({ text }: { text: string }) {
  return (
    <>
      {parseLegalText(text).map((b, i) => {
        if (b.kind === 'cookie_settings') return <CookieSettingsButton key={i} />;
        if (b.kind === 'ul')
          return (
            <ul key={i}>
              {b.items.map((item, j) => (
                <li key={j}>
                  <Parts parts={item} />
                </li>
              ))}
            </ul>
          );
        if (b.kind === 'h2')
          return (
            <h2 key={i}>
              <Parts parts={b.parts} />
            </h2>
          );
        if (b.kind === 'h3')
          return (
            <h3 key={i}>
              <Parts parts={b.parts} />
            </h3>
          );
        return (
          <p key={i}>
            <Parts parts={b.parts} />
          </p>
        );
      })}
    </>
  );
}
