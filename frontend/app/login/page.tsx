import { redirect } from 'next/navigation';

/** Sign-in is the app root. `/login` must not 404. */
export default function LoginRedirectPage() {
  redirect('/');
}
