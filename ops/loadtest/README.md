# Loadtest operator examples (Stage 28 C1)

Versioned packaging for operator ~1000-VU certification. **Not** a CI-forged capacity certificate.

| File | Role |
|------|------|
| `1000vu-cert-checklist.json` | Operator steps + pass criteria + artifact schema |
| `operator_1000vu_run.example.json` | Run report schema example (`passed: false` placeholder) |

Harness remains `backend/loadtest/` (`--smoke`, `--ci-capacity`, optional `locustfile.py`). Stage 26 C1 proves CI capacity only.

## Operator outline

1. Size staging; tune rate limits.
2. Real staging tenant credentials via env (never commit).
3. Run Locust or httpx toward ~1000 VU; target p95 &lt; 500 ms, 0% errors.
4. Copy `operator_1000vu_run.example.json` → durable ops path; fill measured fields.
5. Attach to launch change log.

Authoritative docs: `docs/LOAD_CERT_PACK_MVP.md`, `docs/LOAD_CAPACITY_MVP.md` (`test_load_cert_pack_c1.py`).
