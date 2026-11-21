import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/**
 * Receives Content-Security-Policy violation reports while the strict policy runs in report-only mode.
 * Writes one short log line per report (the blocked directive and address, never cookies or bodies
 * beyond the report) and answers 204. Public by design: browsers send reports without a sign-in.
 */
export async function POST(request: NextRequest) {
  try {
    const text = (await request.text()).slice(0, 4000);
    const parsed = JSON.parse(text) as Record<string, any>;
    const r = (parsed['csp-report'] || parsed) as Record<string, unknown>;
    const clip = (v: unknown) => String(v ?? '').slice(0, 200);
    console.warn(
      JSON.stringify({
        event: 'csp_violation',
        directive: clip(r['violated-directive'] || r['effective-directive']),
        blocked: clip(r['blocked-uri']),
        page: clip(r['document-uri']).split('?')[0],
        source: clip(r['source-file']).split('?')[0],
        line: clip(r['line-number']),
        disposition: clip(r['disposition']),
      }),
    );
  } catch {
    // Malformed report: ignore.
  }
  return new NextResponse(null, { status: 204 });
}
