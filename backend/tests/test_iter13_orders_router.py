"""Iter 13 — HTTP integration tests for extracted /api/orders* router.

Covers:
  • POST /api/orders with HH line + non-HH line + order-level percent discount
  • POST /api/orders that matches a seeded combo (Duo Deal)
  • PATCH /api/orders/{id} recomputes totals with same exclusivity math
  • POST /api/orders/{id}/pay end-to-end
  • /api/orders/{id}/bump/{index} and /api/orders/{id}/fire respond
  • /api/orders, /api/tables, /api/kegs list endpoints still work
"""
import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path("/app/frontend/.env"))
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "polymuze111@gmail.com", "password": "admin123"}


@pytest.fixture(scope="module")
def sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def products(sess):
    r = sess.get(f"{API}/products", timeout=15)
    assert r.status_code == 200
    prods = r.json()
    assert len(prods) >= 3, "Need at least 3 seeded products"
    return prods


# ---------- Listing endpoints (regression: router extraction) ----------
def test_orders_list(sess):
    r = sess.get(f"{API}/orders", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_tables_list(sess):
    r = sess.get(f"{API}/tables", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_kegs_list(sess):
    r = sess.get(f"{API}/kegs", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- HH + order-level discount exclusivity ----------
def test_create_order_hh_line_excludes_order_discount(sess, products):
    p1, p2 = products[0], products[1]
    lines = [
        {"product_id": p1["id"], "name": p1["name"], "price": 40, "qty": 1, "hh_pct": 20},
        {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
    ]
    body = {
        "order_type": "dine_in",
        "lines": lines,
        "discount_type": "percent",
        "discount_value": 15,
        "service_charge_pct": 10,
    }
    r = sess.post(f"{API}/orders", json=body, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    # subtotal 140, discount = 15% of non-HH line (100) = 15
    assert d["subtotal"] == 140.0
    assert d["discount"] == 15.0
    assert p1["id"] in d["hh_locked_product_ids"]
    assert d["combo_locked_product_ids"] == []
    return d["id"]


# ---------- Combo application + order-level discount excludes combo lines ----------
@pytest.fixture(scope="module")
def duo_deal_combo(sess, products):
    """Ensure a 'Duo Deal' style combo exists — percent 15 on 2 products."""
    r = sess.get(f"{API}/combos", timeout=15)
    combos = r.json() if r.status_code == 200 else []
    for c in combos:
        if c.get("name") == "TEST_ITER13_DUO" and c.get("active"):
            sess.delete(f"{API}/combos/{c['id']}", timeout=15)
    body = {
        "name": "TEST_ITER13_DUO",
        "product_ids": [products[0]["id"], products[1]["id"]],
        "discount_type": "percent",
        "discount_value": 15,
        "active": True,
    }
    r = sess.post(f"{API}/combos", json=body, timeout=15)
    assert r.status_code in (200, 201), r.text
    combo = r.json()
    yield combo
    try:
        sess.delete(f"{API}/combos/{combo['id']}", timeout=15)
    except Exception:
        pass


def test_create_order_with_combo_lock(sess, products, duo_deal_combo):
    p1, p2, p3 = products[0], products[1], products[2]
    lines = [
        {"product_id": p1["id"], "name": p1["name"], "price": 100, "qty": 1},
        {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
        {"product_id": p3["id"], "name": p3["name"], "price": 50, "qty": 1},
    ]
    body = {
        "order_type": "dine_in",
        "lines": lines,
        "discount_type": "percent",
        "discount_value": 20,
        "service_charge_pct": 10,
    }
    r = sess.post(f"{API}/orders", json=body, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["combo_discount"] > 0, d
    # Either the pre-seeded 'Duo Deal' or our TEST_ITER13_DUO combo will match
    # first (same %). Both lock p1+p2, leaving p3 for the order-level discount.
    assert len(d["combos_applied"]) >= 1
    assert set(d["combo_locked_product_ids"]) >= {p1["id"], p2["id"]}
    # Order-level 20% applies only to p3 (50) => 10
    assert d["discount"] == 10.0


def test_two_overlapping_combos_only_best(sess, products):
    p1, p2, p3 = products[0], products[1], products[2]
    # Small combo — cash 10 off (p1,p2). Big — cash 50 off (p2,p3). Should pick Big.
    created = []
    for name, pids, v in [
        ("TEST_ITER13_SMALL", [p1["id"], p2["id"]], 10),
        ("TEST_ITER13_BIG", [p2["id"], p3["id"]], 50),
    ]:
        r = sess.post(f"{API}/combos", json={
            "name": name, "product_ids": pids,
            "discount_type": "cash", "discount_value": v, "active": True,
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        created.append(r.json()["id"])

    try:
        lines = [
            {"product_id": p1["id"], "name": p1["name"], "price": 100, "qty": 1},
            {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
            {"product_id": p3["id"], "name": p3["name"], "price": 100, "qty": 1},
        ]
        r = sess.post(f"{API}/orders", json={
            "order_type": "dine_in", "lines": lines,
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        applied_names = [c["name"] for c in d["combos_applied"]]
        # Only best wins between the two overlapping test combos.
        assert "TEST_ITER13_BIG" in applied_names
        assert "TEST_ITER13_SMALL" not in applied_names
    finally:
        for cid in created:
            sess.delete(f"{API}/combos/{cid}", timeout=15)


# ---------- PATCH recomputes with exclusivity ----------
def test_patch_order_recomputes_totals(sess, products):
    p1, p2 = products[0], products[1]
    # create simple order
    r = sess.post(f"{API}/orders", json={
        "order_type": "dine_in",
        "lines": [
            {"product_id": p1["id"], "name": p1["name"], "price": 100, "qty": 1},
        ],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
    }, timeout=15)
    assert r.status_code == 200, r.text
    oid = r.json()["id"]

    # PATCH — add HH line + non-HH line + 20% manual discount
    patch_body = {
        "lines": [
            {"product_id": p1["id"], "name": p1["name"], "price": 40, "qty": 1, "hh_pct": 20},
            {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
        ],
        "discount_type": "percent",
        "discount_value": 20,
    }
    r = sess.patch(f"{API}/orders/{oid}", json=patch_body, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["subtotal"] == 140.0
    # 20% of only non-HH (100) = 20
    assert d["discount"] == 20.0
    assert p1["id"] in d["hh_locked_product_ids"]


# ---------- Bump / Fire / Pay end-to-end ----------
def test_bump_fire_pay_flow(sess, products):
    p1 = products[0]
    # create order with 1 held line
    r = sess.post(f"{API}/orders", json={
        "order_type": "dine_in",
        "lines": [{"product_id": p1["id"], "name": p1["name"], "price": 60, "qty": 1,
                   "held": True, "course": "main"}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
    }, timeout=15)
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    total = r.json()["total"]

    # fire
    r = sess.post(f"{API}/orders/{oid}/fire", timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("fired", 0) >= 1

    # bump line 0
    r = sess.post(f"{API}/orders/{oid}/bump/0", timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    # pay cash
    r = sess.post(f"{API}/orders/{oid}/pay", json={
        "method": "cash", "amount": total, "tip": 0, "splits": [],
    }, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
