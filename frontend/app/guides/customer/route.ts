import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

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
  const tenant = request.headers.get('x-tenant-id') || '';
  try {
    const upstream = await fetch(`${apiBase()}/staff-guide`, {
      headers: {
        Authorization: auth,
        ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
      },
      cache: 'no-store',
    });
    const type = (upstream.headers.get('content-type') || '').toLowerCase();
    if (!upstream.ok) {
      const body = await upstream.json().catch(() => ({ detail: 'Could not verify this account' }));
      return NextResponse.json(body, { status: upstream.status });
    }
    if (!type.includes('pdf')) {
      return NextResponse.json({ detail: 'Guide file is not available' }, { status: 502 });
    }
    const bytes = Buffer.from(await upstream.arrayBuffer());
    return new NextResponse(bytes, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': 'attachment; filename="RIBDIGI-ERP-Customer-User-Guide.pdf"',
        'Cache-Control': 'private, no-store',
      },
    });
  } catch {
    return NextResponse.json({ detail: 'Could not reach the guide service' }, { status: 503 });
  }
}
