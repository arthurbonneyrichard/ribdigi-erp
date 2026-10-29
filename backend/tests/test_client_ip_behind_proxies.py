"""Behind Traefik and the Next.js proxy (private Docker addresses), the real visitor IP is the nearest public hop."""
from types import SimpleNamespace

from app.middleware import client_ip_from_request


def _req(xff, peer="172.18.0.7"):
    return SimpleNamespace(headers={"x-forwarded-for": xff}, client=SimpleNamespace(host=peer))


def test_private_proxy_hops_are_skipped():
    assert client_ip_from_request(_req("41.66.1.2, 172.18.0.5, 172.18.0.7")) == "41.66.1.2"


def test_spoofed_left_value_is_ignored():
    assert client_ip_from_request(_req("6.6.6.6, 41.66.1.2, 172.18.0.5")) == "41.66.1.2"


def test_all_private_falls_back_to_rightmost():
    assert client_ip_from_request(_req("10.0.0.1, 172.18.0.5")) == "172.18.0.5"
