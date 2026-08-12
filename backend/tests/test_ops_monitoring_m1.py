"""Stage 26 M1 — Monitoring & alerting fidelity (scrape / alerts / log-ship)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/monitoring")
EVIDENCE_FILE = EVIDENCE_DIR / "ops_monitoring_m1.json"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_prometheus_scrape_config_targets_metrics():
    prom = _read("ops/prometheus/prometheus.yml")
    assert "job_name: ribdigi-backend" in prom
    assert "metrics_path: /api/v1/metrics" in prom
    assert "rule_files" in prom
    assert "alerts" in prom
    assert "ribdigi-ready" in prom
    assert "/api/v1/health/ready" in prom


def test_alert_rules_cover_ribdigi_series():
    alerts = _read("ops/prometheus/alerts/ribdigi.yml")
    for name in (
        "RibdigiDown",
        "RibdigiHighErrorRate",
        "RibdigiHighLatency",
        "RibdigiNotReady",
        "RibdigiRabbitMQQueueDepthHigh",
    ):
        assert f"alert: {name}" in alerts, name
    assert "ribdigi_up" in alerts
    assert "ribdigi_http_requests_total" in alerts
    assert 'status=~"5.."' in alerts or "status=~'5..'" in alerts
    assert "ribdigi_http_request_duration_seconds_sum" in alerts
    assert "probe_success" in alerts
    assert "rabbitmq_queue_messages" in alerts


def test_log_shipping_fluent_bit_example():
    fb = _read("ops/logging/fluent-bit-ribdigi.conf.example")
    assert "ribdigi.request" in fb
    assert "request_id" in fb or "json" in fb.lower()
    assert "[INPUT]" in fb
    assert "[OUTPUT]" in fb
    assert "SIEM" in fb or "not a deployed" in fb.lower() or "example" in fb.lower()


def test_ops_monitoring_doc_stage26_m1():
    doc = _read("docs/OPS_MONITORING_MVP.md")
    assert "Stage 18 L1" in doc
    assert "Stage 26 M1" in doc
    assert "test_ops_monitoring_m1.py" in doc
    assert "/api/v1/metrics" in doc
    assert "/api/v1/health/ready" in doc
    assert "ops/prometheus/prometheus.yml" in doc
    assert "ops/prometheus/alerts/ribdigi.yml" in doc
    assert "RibdigiDown" in doc and "RibdigiHighErrorRate" in doc
    assert "fluent-bit-ribdigi.conf.example" in doc
    assert "Grafana" in doc or "PagerDuty" in doc
    assert "SIEM" in doc


def test_metrics_endpoint_still_exposes_series():
    from app.main import app
    from app.metrics import reset_for_tests
    from app.rate_limit import rate_limiter

    rate_limiter.reset_for_tests()
    reset_for_tests()
    client = TestClient(app)
    r = client.get("/api/v1/metrics")
    assert r.status_code == 200
    body = r.text
    assert "ribdigi_up 1" in body
    assert "ribdigi_http_requests_total" in body


def test_monitoring_gate_complete_mvp_and_evidence():
    pr = _read("PRODUCTION_READINESS.md")
    assert "- [x] Monitoring, metrics, logging and alerting complete." in pr
    assert "- [ ] Monitoring, metrics, logging and alerting complete." not in pr
    assert "Stage 26 M1" in pr
    assert "test_ops_monitoring_m1.py" in pr
    assert "OPS_MONITORING_MVP.md" in pr
    assert "ops/prometheus" in pr
    assert "Grafana" in pr or "PagerDuty" in pr
    assert "SIEM" in pr

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "workstream": "M1",
        "passed": True,
        "packaging_only": True,
        "hosted_grafana_claimed": False,
        "pagerduty_wired": False,
        "siem_claimed": False,
        "runbook": "docs/OPS_MONITORING_MVP.md",
        "prometheus": "ops/prometheus/prometheus.yml",
        "alerts": "ops/prometheus/alerts/ribdigi.yml",
    }
    EVIDENCE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["hosted_grafana_claimed"] is False
    assert loaded["pagerduty_wired"] is False
    assert loaded["siem_claimed"] is False
