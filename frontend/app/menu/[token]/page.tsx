'use client';

import { useParams } from 'next/navigation';
import { GuestMenuPage } from '../../../components/digital-menu/DigitalMenu';

/** What a guest sees after scanning the restaurant's QR code. No app and no sign-in. */
export default function PublicMenuPage() {
  const params = useParams<{ token: string }>();
  return <GuestMenuPage token={String(params?.token || '')} />;
}
