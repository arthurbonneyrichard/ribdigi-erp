'use client';

import { useParams } from 'next/navigation';
import RestaurantSite from '../../../components/restaurant-site/RestaurantSite';

/** A restaurant's website, opened at its menu for online food and drink orders. */
export default function RestaurantOrderPage() {
  const params = useParams<{ slug: string }>();
  return <RestaurantSite slug={String(params?.slug || '')} focus="menu" />;
}
