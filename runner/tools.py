import copy
import json

from agents import function_tool

SEED_ORDERS = {
    "ORD-8830": {"item": "Kaya toast set",      "status": "preparing",  "placed_mins_ago": 4,   "amount": 5.40},
    "ORD-8825": {"item": "Chicken rice",        "status": "delivering", "placed_mins_ago": 38,  "amount": 6.50},
    "ORD-8822": {"item": "Laksa",               "status": "delivered",  "placed_mins_ago": 95,  "amount": 8.20},
    "ORD-8815": {"item": "Roti prata set",      "status": "delivered",  "placed_mins_ago": 180, "amount": 7.00},
}
SEED_REFUNDS = {
    "ORD-8822": {"status": "processing", "amount": 8.20, "eta": "3-5 business days"},
}


class State:
    """Per-case state. Fresh copy for each test case."""
    def __init__(self):
        self.orders  = copy.deepcopy(SEED_ORDERS)
        self.refunds = copy.deepcopy(SEED_REFUNDS)

# Module-level holder so function_tool closures see current state
_state: State = State()

def reset_state() -> State:
    global _state
    _state = State()
    return _state


@function_tool
def list_orders(status_filter: str = "all", limit: int = 5) -> str:
    """List recent orders, most recent first. status_filter: all|active|delivered|cancelled."""
    items = sorted(_state.orders.items(), key=lambda kv: kv[1]["placed_mins_ago"])
    if status_filter == "active":
        items = [(k, v) for k, v in items if v["status"] in ("preparing", "delivering")]
    elif status_filter == "delivered":
        items = [(k, v) for k, v in items if v["status"] == "delivered"]
    elif status_filter == "cancelled":
        items = [(k, v) for k, v in items if v["status"] == "cancelled"]
    return json.dumps([{"order_id": k, **v} for k, v in items[:limit]])


@function_tool
def get_order(order_id: str) -> str:
    """Get details for a specific order by ID."""
    o = _state.orders.get(order_id)
    if not o:
        return json.dumps({"error": "not_found", "order_id": order_id})
    return json.dumps({"order_id": order_id, **o})


@function_tool
def cancel_order(order_id: str) -> str:
    """Cancel a specific order. Fails for already-delivered orders."""
    o = _state.orders.get(order_id)
    if not o:
        return json.dumps({"error": "not_found", "order_id": order_id})
    if o["status"] == "delivered":
        return json.dumps({"error": "already_delivered", "order_id": order_id})
    o["status"] = "cancelled"
    _state.refunds[order_id] = {"status": "processing", "amount": o["amount"], "eta": "3-5 business days"}
    return json.dumps({"order_id": order_id, "cancelled": True, "refund_eta": "3-5 business days"})


@function_tool
def list_refunds() -> str:
    """List pending and recent refunds."""
    return json.dumps([{"order_id": k, **v} for k, v in _state.refunds.items()])


@function_tool
def check_refund_status(order_id: str) -> str:
    """Check refund status for a specific order."""
    r = _state.refunds.get(order_id)
    if not r:
        return json.dumps({"error": "no_refund", "order_id": order_id})
    return json.dumps({"order_id": order_id, **r})


@function_tool
def escalate_to_human(reason: str) -> str:
    """Escalate to a human agent."""
    return json.dumps({"escalated": True, "reason": reason, "wait_time": "2 mins"})


TOOLS = [list_orders, get_order, cancel_order, list_refunds, check_refund_status, escalate_to_human]
