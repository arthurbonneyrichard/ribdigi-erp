"""Frontend API errors must show FastAPI 422 msg, not a generic Request failed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_api_formats_fastapi_422_detail_array():
    api_ts = (ROOT / "frontend/lib/api.ts").read_text(encoding="utf-8")
    assert "export function formatApiError" in api_ts
    assert "Array.isArray(detail)" in api_ts
    assert "rec.msg" in api_ts
    assert "Request failed" in api_ts
    assert "Your session expired" in api_ts
    assert "You do not have permission" in api_ts
    assert "That record already exists" in api_ts
    assert "typeof detail === 'string'" in api_ts
    staff = (ROOT / "frontend/app/(dashboard)/platform/staff/page.tsx").read_text(encoding="utf-8")
    assert "api('/platform/staff'" in staff
    assert "method: 'POST'" in staff
    assert "role: form.role" in staff
    assert "platform_admin" in staff
    assert "E.164" in staff
