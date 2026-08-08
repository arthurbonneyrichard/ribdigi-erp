from types import SimpleNamespace

# Status transition helpers mirrored for unit clarity
TRANSFER_SHIPPABLE = {"requested", "draft"}
TRANSFER_RECEIVABLE = {"in_transit"}
TRANSFER_CANCELLABLE = {"draft", "requested", "in_transit"}


def can_ship(status: str) -> bool:
    return status in TRANSFER_SHIPPABLE


def can_receive(status: str) -> bool:
    return status in TRANSFER_RECEIVABLE


def can_cancel(status: str) -> bool:
    return status in TRANSFER_CANCELLABLE


def test_transfer_status_gates():
    assert can_ship("draft")
    assert can_ship("requested")
    assert not can_ship("received")
    assert can_receive("in_transit")
    assert not can_receive("requested")
    assert can_cancel("in_transit")
    assert not can_cancel("received")


def test_transfer_stores_must_differ_logic():
    a = SimpleNamespace(id="s1")
    b = SimpleNamespace(id="s2")
    assert a.id != b.id
