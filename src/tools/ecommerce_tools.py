import json
from typing import Dict, Any, List

# Mock database
INVENTORY = {
    "iphone": {"price": 1000.0, "stock": 5, "weight": 0.2},
    "ipad": {"price": 800.0, "stock": 2, "weight": 0.5},
    "macbook": {"price": 2000.0, "stock": 3, "weight": 1.5},
}

COUPONS = {
    "WINNER": 0.10,  # 10% discount
    "SUPERDEAL": 0.20,  # 20% discount
}

def check_stock(item_name: str) -> str:
    """
    Checks stock and price for a given item.
    """
    item_lower = item_name.strip().lower()
    if item_lower in INVENTORY:
        return json.dumps(INVENTORY[item_lower])
    return json.dumps({"error": f"Item '{item_name}' not found."})

def get_discount(coupon_code: str) -> str:
    """
    Returns the discount rate for a coupon code.
    """
    coupon_upper = coupon_code.strip().upper()
    if coupon_upper in COUPONS:
        return json.dumps({"discount": COUPONS[coupon_upper]})
    return json.dumps({"discount": 0.0, "message": "Invalid or expired coupon."})

def calc_shipping(weight: float, destination: str) -> str:
    """
    Calculates shipping cost based on weight and destination.
    """
    dest = destination.strip().lower()
    # Simple pricing model
    if dest == "hanoi":
        base_rate = 5.0
    elif dest == "ho chi minh":
        base_rate = 10.0
    else:
        base_rate = 15.0
        
    cost = base_rate * float(weight)
    return json.dumps({"shipping_cost": round(cost, 2)})

# Tool definitions list for the ReAct Agent
ECOMMERCE_TOOLS = [
    {
        "name": "check_stock",
        "description": "check_stock(item_name: str) -> Returns JSON with 'price', 'stock', and 'weight' (in kg) of the item. Example: check_stock('iPhone')",
        "func": check_stock
    },
    {
        "name": "get_discount",
        "description": "get_discount(coupon_code: str) -> Returns JSON with 'discount' rate as a float (e.g. 0.10 for 10%). Example: get_discount('WINNER')",
        "func": get_discount
    },
    {
        "name": "calc_shipping",
        "description": "calc_shipping(weight: float, destination: str) -> Returns JSON with 'shipping_cost'. Example: calc_shipping(0.4, 'Hanoi')",
        "func": calc_shipping
    }
]
