# MVP closeout / handoff maps (Stage 31–32)

| File | Role |
|------|------|
| `gate-matrix.json` | PRODUCTION_READINESS launch-gate honesty matrix — Complete (MVP) vs Remaining post-MVP vs Deferred ADR (Stage 31 G1) |
| `deferred-adr-register.json` | ADR-001–006 deferred honesty index — MVP Accepted vs post-MVP Remaining (Stage 31 R1) |
| `operator-remaining-register.json` | Stage 26–30 honesty-flag consolidation — all Remaining stay false (Stage 31 O1) |
| `mvp-declaration.json` | Commercial MVP packaging declaration — packaging Complete ≠ live go-live / §7 (Stage 31 C1) |
| `mvp-declaration-evidence.example.json` | Operator evidence schema after real go-live (not a forged certificate) |
| `acceptance-archive.json` | Stage 1–31 exit criteria + freeze ADR index — packaging archive ≠ live go-live (Stage 32 A1) |
| `operator-handoff.json` | Ops take-over checklist from Stage 26–31 packs — handoff packaging ≠ live go-live / §7 (Stage 32 H1) |
| `release-notes.json` | Commercial MVP release notes — packaging Complete surfaces + Remaining honesty ≠ production live (Stage 32 N1) |

Authoritative MVP docs:

- `docs/MVP_GATE_MATRIX_MVP.md` (`backend/tests/test_mvp_gate_matrix_g1.py`) — Stage 31 G1
- `docs/DEFERRED_ADR_REGISTER_MVP.md` (`backend/tests/test_deferred_adr_register_r1.py`) — Stage 31 R1
- `docs/OPERATOR_REMAINING_MVP.md` (`backend/tests/test_operator_remaining_o1.py`) — Stage 31 O1
- `docs/MVP_DECLARATION_MVP.md` (`backend/tests/test_mvp_declaration_c1.py`) — Stage 31 C1
- `docs/ACCEPTANCE_ARCHIVE_MVP.md` (`backend/tests/test_acceptance_archive_a1.py`) — Stage 32 A1
- `docs/OPERATOR_HANDOFF_MVP.md` (`backend/tests/test_operator_handoff_h1.py`) — Stage 32 H1
- `docs/RELEASE_NOTES_MVP.md` (`backend/tests/test_release_notes_n1.py`) — Stage 32 N1

Do **not** treat this packaging as production go-live, deferred ADR implementation, or live-run certification. Top-level flags stay `go_live_claimed: false` / `deferred_implemented_claimed: false` / `live_runs_certified: false` / `section_7_signed: false` / `handoff_complete_claimed: false` / `production_live_claimed: false`.
