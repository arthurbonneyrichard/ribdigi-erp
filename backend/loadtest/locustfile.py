"""Optional Locust scenarios for staging capacity runs (Stage 5 L1).

Install Locust separately (not a production runtime dependency):
  pip install locust

Run (example):
  locust -f loadtest/locustfile.py --host https://api.example.com \\
    --users 100 --spawn-rate 10 --run-time 5m --headless

Environment:
  LOADTEST_EMAIL, LOADTEST_PASSWORD, LOADTEST_TENANT, LOADTEST_TOTP (optional)
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task


class RibdigiUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self) -> None:
        self.auth_headers = {}
        email = os.getenv("LOADTEST_EMAIL", "")
        password = os.getenv("LOADTEST_PASSWORD", "")
        tenant = os.getenv("LOADTEST_TENANT", "")
        totp = os.getenv("LOADTEST_TOTP", "")
        if not (email and password and tenant):
            return
        payload = {"email": email, "password": password, "tenant_id": tenant}
        if totp:
            payload["totp_code"] = totp
        with self.client.post("/api/v1/auth/login", json=payload, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"login {resp.status_code}")
                return
            data = resp.json().get("data") or {}
            token = data.get("access_token")
            tenant_id = (data.get("user") or {}).get("tenant_id") or tenant
            if not token:
                resp.failure("missing token")
                return
            self.auth_headers = {
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": tenant_id,
            }
            resp.success()

    @task(5)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(3)
    def products(self) -> None:
        if not self.auth_headers:
            return
        self.client.get(
            "/api/v1/products",
            headers=self.auth_headers,
            params={"limit": 50},
            name="/api/v1/products",
        )

    @task(2)
    def dashboard(self) -> None:
        if not self.auth_headers:
            return
        self.client.get(
            "/api/v1/dashboard",
            headers=self.auth_headers,
            name="/api/v1/dashboard",
        )
