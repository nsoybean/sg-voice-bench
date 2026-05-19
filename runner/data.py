# runner/tools.py — seed data

SEED_ORDERS = {
    "ORD-8830": {"item": "Kaya toast set",      "status": "preparing",  "placed_mins_ago": 4,   "amount": 5.40},
    "ORD-8825": {"item": "Chicken rice",        "status": "delivering", "placed_mins_ago": 38,  "amount": 6.50},
    "ORD-8822": {"item": "Laksa",               "status": "delivered",  "placed_mins_ago": 95,  "amount": 8.20},
    "ORD-8815": {"item": "Roti prata set",      "status": "delivered",  "placed_mins_ago": 180, "amount": 7.00},
}

SEED_REFUNDS = {
    "ORD-8822": {"status": "processing", "amount": 8.20, "eta": "3-5 business days"},
}
