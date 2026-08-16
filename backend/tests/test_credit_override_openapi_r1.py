"""Credit override OpenAPI model_validator honesty (BR-11.1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import CreditLimitOverrideBody, PosSaleCreate, TransactionCreate


@pytest.mark.parametrize(
    "cls,extra",
    [
        (CreditLimitOverrideBody, {}),
        (TransactionCreate, {"items": []}),
        (
            PosSaleCreate,
            {"items": [{"product_id": "p1", "quantity": 1}]},
        ),
    ],
)
def test_override_flag_requires_reason_at_schema(cls, extra):
    ok = cls.model_validate(
        {
            **extra,
            "override_credit_limit": True,
            "override_reason": "Manager approved",
        }
    )
    assert ok.override_credit_limit is True
    assert ok.override_reason == "Manager approved"

    # Flag false — reason optional
    cls.model_validate({**extra, "override_credit_limit": False})

    with pytest.raises(ValidationError) as missing:
        cls.model_validate({**extra, "override_credit_limit": True})
    assert "override_reason" in str(missing.value).lower()

    with pytest.raises(ValidationError) as blank:
        cls.model_validate(
            {**extra, "override_credit_limit": True, "override_reason": "   "}
        )
    assert "override_reason" in str(blank.value).lower()
