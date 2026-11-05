'use client';

import { useParams } from 'next/navigation';
import { MenuBoardPage } from '../../../../components/digital-menu/DigitalMenu';

/** The menu board for a restaurant TV or large screen. */
export default function PublicMenuBoardPage() {
  const params = useParams<{ token: string }>();
  return <MenuBoardPage token={String(params?.token || '')} />;
}
