# ADR-006: English-only UI for Commercial MVP (i18n scaffold)

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-2.7 (Language Configuration) requires:

- Switch UI language per user
- MVP supports English; framework for i18n

Primary market documentation already states English for Phase 1, with additional languages in a later phase. Shipping incomplete translation packs or a fake language switcher would violate commercial MVP honesty.

## Decision

For Stage 1 / Commercial MVP:

1. **UI language is English only** (`locale` / `preferred_language` = `en`).
2. A **minimal i18n scaffold** exists (`frontend/lib/i18n.ts`) with an English message catalog and `t()` helper so future language packs can plug in without a parallel stack.
3. `GET /me` exposes `locale`, `preferred_language`, and `supported_locales` (`["en"]`).
4. `PATCH /me` accepts `preferred_language` but **only `en`** until additional packs ship; other values return 400.
5. Per-user non-English language switching and translated UI packs are **post-MVP**.

## Consequences

- BR-2.7 is PARTIAL for MVP: English + framework yes; multi-language switching deferred.
- Admin/user docs must not claim additional language packs are available.
- Regional formatting (date/number/time/timezone) remains separate from UI language (E13).

See also Stage 184 language/i18n remaining-gate index: [`I18N_REMAINING_GATE_MVP.md`](I18N_REMAINING_GATE_MVP.md) (multi-language remains deferred; not Complete).
