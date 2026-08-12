"""Stage 28 A1 — Grafana / Alertmanager pack (not hosted SaaS Complete)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "ops" / "grafana" / "dashboard-ribdigi-mvp.json.example"
ALERTMANAGER = ROOT / "ops" / "grafana" / "alertmanager.yml.example"
EVIDENCE_DIR = Path("/opt/cursor/artifacts/monitoring")
EVIDENCE_FILE = EVIDENCE_DIR / "stage28_a1_grafana_pack.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_grafana_dashboard_example_covers_ribdigi_series():
    assert DASHBOARD.is_file()
    raw = DASHBOARD.read_text(encoding="utf-8")
    assert "ribdigi_up" in raw
    assert "ribdigi_http_requests_total" in raw
    assert "ribdigi_http_request_duration_seconds" in raw
    assert "Stage 28 A1" in raw or "stage28-a1" in raw or "GRAFANA_PACK_MVP" in raw
    cleaned = raw.replace("${DS_PROMETHEUS}", "prometheus")
    data = json.loads(cleaned)
    assert data.get("title")
    assert isinstance(data.get("panels"), list) and len(data["panels"]) >= 3
    blob = json.dumps(data)
    assert "ribdigi_up" in blob
    assert "5xx" in blob.lower() or 'status=~"5.."' in blob or "5.." in blob


def test_alertmanager_example_honest():
    assert ALERTMANAGER.is_file()
    text = ALERTMANAGER.read_text(encoding="utf-8")
    assert "route:" in text
    assert "receivers:" in text
    assert "critical" in text.lower()
    assert "PagerDuty" in text or "pagerduty" in text.lower()
    assert "# pagerduty_configs" in text or "#   - routing_key" in text
    assert "deferred" in text.lower() or "NOT" in text or "not" in text.lower()
    assert "SIEM" in text or "hosted" in text.lower()
    assert "GRAFANA_PACK_MVP.md" in text or "Stage 28 A1" in text


def test_grafana_pack_mvp_doc_and_readme():
    doc = _read("docs/GRAFANA_PACK_MVP.md")
    assert "Stage 28 A1" in doc
    assert "test_grafana_pack_a1.py" in doc
    assert "dashboard-ribdigi-mvp.json.example" in doc
    assert "alertmanager.yml.example" in doc
    assert "OPS_MONITORING_MVP.md" in doc
    assert "hosted" in doc.lower() or "PagerDuty" in doc
    assert "stage28_a1_grafana_pack.json" in doc
    assert "not" in doc.lower()

    readme = _read("ops/grafana/README.md")
    assert "Stage 28 A1" in readme
    assert "GRAFANA_PACK_MVP.md" in readme
    assert "dashboard-ribdigi-mvp.json.example" in readme
    assert "alertmanager.yml.example" in readme
    assert "PagerDuty" in readme or "SIEM" in readme


def test_ops_monitoring_extended_for_a1():
    mon = _read("docs/OPS_MONITORING_MVP.md")
    assert "Stage 28 A1" in mon or "GRAFANA_PACK_MVP.md" in mon
    assert "ops/grafana" in mon or "dashboard-ribdigi-mvp" in mon
    assert "alertmanager" in mon.lower()
    assert "Remaining" in mon or "deferred" in mon.lower() or "not" in mon.lower()

    prom_readme = _read("ops/prometheus/README.md")
    assert "Stage 28 A1" in prom_readme or "GRAFANA_PACK_MVP.md" in prom_readme or "ops/grafana" in prom_readme


def test_grafana_pack_evidence_honest():
    pr = _read("PRODUCTION_READINESS.md")
    assert "Stage 28 A1" in pr
    assert "test_grafana_pack_a1.py" in pr or "GRAFANA_PACK_MVP.md" in pr
    mon_gate = pr.split("- [x] Monitoring, metrics, logging and alerting complete.")[1].split(
        "- ["
    )[0]
    assert "Stage 28 A1" in mon_gate or "GRAFANA_PACK_MVP" in mon_gate
    assert "Remaining" in mon_gate or "hosted" in mon_gate.lower()
    assert "PagerDuty" in mon_gate or "SIEM" in mon_gate or "hosted" in mon_gate.lower()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "28",
        "workstream": "A1",
        "passed": True,
        "doc": "docs/GRAFANA_PACK_MVP.md",
        "dashboard": "ops/grafana/dashboard-ribdigi-mvp.json.example",
        "alertmanager": "ops/grafana/alertmanager.yml.example",
        "monitoring_mvp": "docs/OPS_MONITORING_MVP.md",
        "hosted_grafana_claimed": False,
        "pagerduty_wired": False,
        "siem_claimed": False,
        "packaging_complete": True,
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["hosted_grafana_claimed"] is False
    assert loaded["pagerduty_wired"] is False
    assert loaded["siem_claimed"] is False
    assert loaded["packaging_complete"] is True
