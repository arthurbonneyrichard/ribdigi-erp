'use client';

import { useParams } from 'next/navigation';
import RestaurantSite from '../../../components/restaurant-site/RestaurantSite';

/** A restaurant's website, opened at its "Book a table" section. */
export default function RestaurantBookingPage() {
  const params = useParams<{ slug: string }>();
  return <RestaurantSite slug={String(params?.slug || '')} focus="book" />;
}
