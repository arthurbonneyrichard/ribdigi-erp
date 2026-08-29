"""POST /onboarding/checklist/steps/{step_id}/skip|unskip Path Literal OpenAPI."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from pydantic import TypeAdapter, ValidationError

from app import onboarding as onboarding_svc
from app.schemas import OnboardingStepIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _literal_values(annotated) -> set[str]:
    cur: object = annotated
    for _ in range(6):
        origin = get_origin(cur)
        args = get_args(cur)
        if origin is Literal:
            return set(args)
        if not args:
            break
        cur = args[0]
    raise AssertionError(f"Could not unwrap Literal from {annotated!r}")


def test_onboarding_step_id_literal_matches_valid_steps():
    adapter = TypeAdapter(OnboardingStepIdValue)
    for name in onboarding_svc.VALID_STEP_IDS:
        assert adapter.validate_python(name) == name
        assert adapter.validate_python(f"  {name.upper()} ") == name

    lit_args = _literal_values(OnboardingStepIdValue)
    assert lit_args == set(onboarding_svc.VALID_STEP_IDS)

    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("not_a_step")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_onboarding_step_id_ui_and_docs():
    page = (ROOT / "frontend/components/OnboardingChecklist.tsx").read_text(encoding="utf-8")
    assert "Onboarding unskip ${step.id}" in page
    assert "Onboarding skip ${step.id}" in page
    assert "Undo skip" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Onboarding Path step_id OpenAPI" in agents
    assert "OnboardingStepIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "OnboardingStepIdValue" in docs
    assert "POST /onboarding/checklist/steps/{step_id}/skip" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_onboarding_step_id_path_unknown_422_and_skip(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    unknown = await ac.post(
        "/api/v1/onboarding/checklist/steps/not_a_step/skip",
        headers=headers,
        json={},
    )
    assert unknown.status_code == 422, unknown.text

    blankish = await ac.post(
        "/api/v1/onboarding/checklist/steps/%20/skip",
        headers=headers,
        json={},
    )
    assert blankish.status_code == 422, blankish.text

    # Prefer a step that is often not auto-complete: create_supplier or first_sale.
    step = "create_supplier"
    skipped = await ac.post(
        f"/api/v1/onboarding/checklist/steps/{step}/skip",
        headers=headers,
        json={},
    )
    assert skipped.status_code == 200, skipped.text
    data = skipped.json()["data"]
    by_id = {s["id"]: s for s in (data.get("steps") or [])}
    assert by_id[step]["skipped"] is True

    restored = await ac.post(
        f"/api/v1/onboarding/checklist/steps/{step}/unskip",
        headers=headers,
        json={},
    )
    assert restored.status_code == 200, restored.text
    data2 = restored.json()["data"]
    by_id2 = {s["id"]: s for s in (data2.get("steps") or [])}
    assert by_id2[step]["skipped"] is False
