#!/bin/sh
# Always runs before migrate/backend commands so Dokploy command overrides
# cannot skip migration content checks.
set -eu

BUILD_ID_FILE=/app/.build-id
MIG=/app/alembic/versions/20260917_0106_transaction_client_request_id.py
OVL=/app/scripts/migrations_overlay/20260917_0106_transaction_client_request_id.py
MIG107=/app/alembic/versions/20260917_0107_pos_devices.py

echo "entrypoint: start $(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [ -f "$BUILD_ID_FILE" ]; then
  echo "entrypoint: image build-id=$(cat "$BUILD_ID_FILE")"
else
  echo "entrypoint: WARNING missing $BUILD_ID_FILE" >&2
fi

if [ ! -f "$OVL" ]; then
  echo "entrypoint: FATAL missing overlay $OVL" >&2
  exit 9
fi
if [ ! -f "$MIG107" ]; then
  echo "entrypoint: FATAL missing commercial migration $MIG107 (wrong ERP branch/image)" >&2
  exit 11
fi

# Always install the known-good idempotent 0106 over whatever was baked/cached.
cp "$OVL" "$MIG"
echo "entrypoint: installed idempotent 0106 overlay into alembic/versions"

if grep -n 'op\.add_column(' "$MIG" >/dev/null 2>&1; then
  echo "entrypoint: FATAL overlay still contains op.add_column(" >&2
  grep -n 'op\.add_column(' "$MIG" >&2 || true
  exit 12
fi
if grep -F 'ADD COLUMN client_request_id' "$MIG" >/dev/null 2>&1; then
  echo "entrypoint: FATAL overlay contains unconditional ADD COLUMN client_request_id" >&2
  exit 14
fi
if ! grep -F 'RIBDIGI_0106_IF_NOT_EXISTS_V3' "$MIG" >/dev/null 2>&1; then
  echo "entrypoint: FATAL overlay missing RIBDIGI_0106_IF_NOT_EXISTS_V3" >&2
  exit 15
fi
if ! grep -F 'ADD COLUMN IF NOT EXISTS client_request_id' "$MIG" >/dev/null 2>&1; then
  echo "entrypoint: FATAL overlay missing ADD COLUMN IF NOT EXISTS" >&2
  exit 16
fi

echo "entrypoint: 0106 proof OK (overlay installed)"
# Line 18 must NOT be op.add_column (that is the known-bad original file).
LINE18=$(sed -n '18p' "$MIG" || true)
echo "entrypoint: 0106 line18=${LINE18}"
case "$LINE18" in
  *op.add_column*)
    echo "entrypoint: FATAL line 18 is still op.add_column — wrong file" >&2
    exit 17
    ;;
esac

exec "$@"
