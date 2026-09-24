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

function canDownloadStaffGuide(role: string, permissions: Record<string, string[]> | null): boolean {
  if (
    [
      'company_admin',
      'super_admin',
      'platform_owner',
      'platform_admin',
      'platform_support',
      'platform_finance',
    ].includes(role)
  ) {
    return true;
  }
  const perms = permissions || {};
  if (perms['*']?.includes('*')) return true;
  const sg = perms.staff_guide || [];
  return sg.includes('read') || sg.includes('download') || sg.includes('*');
}

export async function GET(request: NextRequest) {
  const auth = request.headers.get('authorization') || '';
  if (!auth.startsWith('Bearer ')) {
    return NextResponse.json({ detail: 'Sign in required' }, { status: 401 });
  }

  let role = '';
  let permissions: Record<string, string[]> | null = null;
  try {
    const me = await fetch(`${apiBase()}/me`, {
      headers: { Authorization: auth },
      cache: 'no-store',
    });
    if (me.status === 401) {
      return NextResponse.json({ detail: 'Sign in required' }, { status: 401 });
    }
    if (!me.ok) {
      return NextResponse.json({ detail: 'Could not verify this account' }, { status: me.status });
    }
    const body = await me.json();
    role = String(body?.data?.role || '');
    permissions =
      body?.data?.permissions && typeof body.data.permissions === 'object'
        ? body.data.permissions
        : null;
  } catch {
    return NextResponse.json({ detail: 'Could not verify this account' }, { status: 503 });
  }

  if (!canDownloadStaffGuide(role, permissions)) {
    return NextResponse.json(
      { detail: 'Missing permission: staff_guide:download' },
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
