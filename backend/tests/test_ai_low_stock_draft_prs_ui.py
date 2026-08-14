"""AI page Create draft PR(s) from low-stock predictions (BR-21.4)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ai_page_draft_pr_button_wired():
    ai = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Create draft PR(s)" in ai
    assert "createDraftPrsFromPredictions" in ai
    assert "/ai/inventory/low-stock-prediction/requests" in ai
    assert "lastAtRisk" in ai
    assert "include_open" in ai
    assert "Include open PRs" in ai
    assert "Inventory predictions" in ai


def test_ai_inventory_mvp_docs_mention_ui():
    mvp = (ROOT / "docs/AI_INVENTORY_MVP.md").read_text(encoding="utf-8")
    assert "Create draft PR(s)" in mvp
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Create draft PR(s)" in api
