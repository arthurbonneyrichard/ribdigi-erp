import { readFile } from 'fs/promises';
import path from 'path';
import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const GUIDE = 'RIBDIGI-ERP-Customer-User-Guide.pdf';

function apiBase() {
  return (
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://localhost:8000/api/v1'
  ).replace(/\/$/, '');
}

export async function GET(request: NextRequest) {
  const auth = request.headers.get('authorization') || '';
  if (!auth.startsWith('Bearer ')) {
    return NextResponse.json({ detail: 'Sign in required' }, { status: 401 });
  }

  let role = '';
  try {
    const me = await fetch(`${apiBase()}/me`, {
      headers: { Authorization: auth },
      cache: 'no-store',
    });
    if (!me.ok) {
      return NextResponse.json({ detail: 'Sign in required' }, { status: 401 });
    }
    const body = await me.json();
    role = String(body?.data?.role || '');
  } catch {
    return NextResponse.json({ detail: 'Could not verify this account' }, { status: 503 });
  }

  if (role !== 'company_admin') {
    return NextResponse.json(
      { detail: 'Only a company administrator can download this guide' },
      { status: 403 }
    );
  }

  try {
    const bytes = await readFile(path.join(process.cwd(), 'guides', GUIDE));
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="${GUIDE}"`,
        'Cache-Control': 'private, no-store',
      },
    });
  } catch {
    return NextResponse.json({ detail: 'Guide file is not available' }, { status: 404 });
  }
}
