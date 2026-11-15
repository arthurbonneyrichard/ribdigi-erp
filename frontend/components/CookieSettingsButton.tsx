'use client';

import { openCookieSettings } from '../lib/consent';

export default function CookieSettingsButton() {
  return (
    <button type="button" className="login-secondary" onClick={openCookieSettings}>
      Open cookie settings
    </button>
  );
}
