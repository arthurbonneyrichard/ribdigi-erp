from types import SimpleNamespace

# Status transition helpers mirrored for unit clarity
TRANSFER_SHIPPABLE = {"requested"}
TRANSFER_RECEIVABLE = {"in_transit"}
TRANSFER_CANCELLABLE = {"draft", "requested", "in_transit"}


def can_ship(status: str, *, fully_approved: bool = False) -> bool:
    return status in TRANSFER_SHIPPABLE and fully_approved


def can_receive(status: str) -> bool:
    return status in TRANSFER_RECEIVABLE


def can_cancel(status: str) -> bool:
    return status in TRANSFER_CANCELLABLE


def test_transfer_status_gates():
    assert not can_ship("draft")
    assert not can_ship("requested", fully_approved=False)
    assert can_ship("requested", fully_approved=True)
    assert not can_ship("received", fully_approved=True)
    assert can_receive("in_transit")
    assert not can_receive("requested")
    assert can_cancel("in_transit")
    assert not can_cancel("received")
