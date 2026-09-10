"""Iter 12 — Advanced Combo Slots.

Covers:
- Legacy flat product_ids combos still auto-apply.
- POST/GET slot combos with slots[] persisted.
- OR-slot semantics (total qty must be within [min,max]).
- AND-slot semantics (each product qty>=1 and <=max).
- Multi-slot combo end-to-end via /orders create + patch.
"""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "polymuze111@gmail.com"
ADMIN_PWD = "admin123"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PWD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def products(client):
    r = client.get(f"{API}/products")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="module")
def pids(products):
    """Pick a few real seeded product ids across food & drink."""
    drinks = [p for p in products if p.get("kind") == "drink"]
    foods = [p for p in products if p.get("kind") == "food"]
    assert len(drinks) >= 3 and len(foods) >= 3, "insufficient seeded products"
    return {
        "drinkA": drinks[0],
        "drinkB": drinks[1],
        "drinkC": drinks[2],
        "foodA": foods[0],
        "foodB": foods[1],
        "foodC": foods[2],
    }


TEST_COMBO_PREFIX = "TEST_ITER12_"


@pytest.fixture(autouse=True)
def _cleanup(client):
    yield
    # delete any TEST_ITER12_ combos after each test
    r = client.get(f"{API}/combos")
    if r.status_code == 200:
        for c in r.json():
            if str(c.get("name", "")).startswith(TEST_COMBO_PREFIX):
                client.delete(f"{API}/combos/{c['id']}")


def _line(p, qty=1):
    return {
        "product_id": p["id"], "name": p["name"], "price": p["price"],
        "qty": qty, "modifiers": [], "course": p.get("course", "main"),
        "held": False, "notes": "",
    }


def _make_order_payload(lines):
    return {
        "order_type": "pick_up", "guests": 1, "lines": lines,
        "discount_type": "none", "discount_value": 0,
        "service_charge_pct": 10, "notes": "",
    }


# ---------- Legacy flat product_ids ----------
def test_legacy_flat_combo_still_applies(client, pids):
    payload = {
        "name": TEST_COMBO_PREFIX + "legacy",
        "product_ids": [pids["drinkA"]["id"], pids["foodA"]["id"]],
        "slots": [],
        "discount_type": "percent",
        "discount_value": 20,
        "active": True,
    }
    r = client.post(f"{API}/combos", json=payload)
    assert r.status_code == 200, r.text
    combo = r.json()
    assert combo["slots"] == []
    assert set(combo["product_ids"]) == {pids["drinkA"]["id"], pids["foodA"]["id"]}

    # order containing both -> combo applies
    lines = [_line(pids["drinkA"]), _line(pids["foodA"])]
    r = client.post(f"{API}/orders", json=_make_order_payload(lines))
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["combo_discount"] > 0
    assert any(c["name"] == payload["name"] for c in o["combos_applied"])

    # order missing one -> combo does NOT apply
    lines2 = [_line(pids["drinkA"])]
    r = client.post(f"{API}/orders", json=_make_order_payload(lines2))
    assert r.status_code == 200
    o2 = r.json()
    assert o2["combo_discount"] == 0
    assert o2["combos_applied"] == []


# ---------- POST/GET slot combos ----------
def test_advanced_slot_combo_persists(client, pids):
    payload = {
        "name": TEST_COMBO_PREFIX + "adv",
        "product_ids": [],
        "slots": [
            {"operator": "or", "min_qty": 1, "max_qty": 1,
             "product_ids": [pids["drinkA"]["id"], pids["drinkB"]["id"], pids["drinkC"]["id"]]},
            {"operator": "and", "min_qty": 1, "max_qty": 2,
             "product_ids": [pids["foodA"]["id"], pids["foodB"]["id"]]},
        ],
        "discount_type": "percent",
        "discount_value": 15,
        "active": True,
    }
    r = client.post(f"{API}/combos", json=payload)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]

    # GET verifies slots roundtrip
    r = client.get(f"{API}/combos")
    assert r.status_code == 200
    combo = next(c for c in r.json() if c["id"] == cid)
    assert len(combo["slots"]) == 2
    assert combo["slots"][0]["operator"] == "or"
    assert combo["slots"][0]["min_qty"] == 1
    assert combo["slots"][0]["max_qty"] == 1
    assert combo["slots"][1]["operator"] == "and"
    assert combo["slots"][1]["max_qty"] == 2


# ---------- OR-slot semantics ----------
def test_or_slot_semantics(client, pids):
    A = pids["drinkA"]
    B = pids["drinkB"]
    combo = {
        "name": TEST_COMBO_PREFIX + "or",
        "product_ids": [],
        "slots": [{"operator": "or", "min_qty": 1, "max_qty": 1,
                   "product_ids": [A["id"], B["id"]]}],
        "discount_type": "cash", "discount_value": 10, "active": True,
    }
    r = client.post(f"{API}/combos", json=combo)
    assert r.status_code == 200

    def _combo_applied(lines):
        rr = client.post(f"{API}/orders", json=_make_order_payload(lines))
        assert rr.status_code == 200, rr.text
        return any(c["name"] == combo["name"] for c in rr.json()["combos_applied"])

    assert _combo_applied([_line(A, 1)]) is True, "1xA within [1,1] should match"
    assert _combo_applied([_line(A, 1), _line(B, 1)]) is False, "total=2 > max=1 should NOT match"
    assert _combo_applied([_line(A, 2)]) is False, "2xA > max=1 should NOT match"
    # empty-of-slot order with only unrelated foods
    assert _combo_applied([_line(pids["foodC"], 1)]) is False, "0 of both should NOT match"


# ---------- AND-slot semantics ----------
def test_and_slot_semantics(client, pids):
    A, B, C = pids["foodA"], pids["foodB"], pids["foodC"]
    combo = {
        "name": TEST_COMBO_PREFIX + "and",
        "product_ids": [],
        "slots": [{"operator": "and", "min_qty": 1, "max_qty": 2,
                   "product_ids": [A["id"], B["id"], C["id"]]}],
        "discount_type": "cash", "discount_value": 5, "active": True,
    }
    r = client.post(f"{API}/combos", json=combo)
    assert r.status_code == 200

    def _applied(lines):
        rr = client.post(f"{API}/orders", json=_make_order_payload(lines))
        assert rr.status_code == 200
        return any(c["name"] == combo["name"] for c in rr.json()["combos_applied"])

    assert _applied([_line(A), _line(B), _line(C)]) is True
    assert _applied([_line(A), _line(B)]) is False, "missing C should NOT match"
    assert _applied([_line(A, 3), _line(B), _line(C)]) is False, "qty=3 > max=2 should NOT match"
    assert _applied([_line(A, 2), _line(B, 2), _line(C, 2)]) is True, "each at max=2 should match"


# ---------- Multi-slot end-to-end via create + patch ----------
def test_multi_slot_create_and_patch(client, pids):
    drink = pids["drinkA"]  # Slot A
    f1 = pids["foodA"]
    f2 = pids["foodB"]
    combo = {
        "name": TEST_COMBO_PREFIX + "multi",
        "product_ids": [],
        "slots": [
            {"operator": "or", "min_qty": 1, "max_qty": 1,
             "product_ids": [drink["id"], pids["drinkB"]["id"], pids["drinkC"]["id"]]},
            {"operator": "and", "min_qty": 1, "max_qty": 2,
             "product_ids": [f1["id"], f2["id"]]},
        ],
        "discount_type": "percent", "discount_value": 20, "active": True,
    }
    r = client.post(f"{API}/combos", json=combo)
    assert r.status_code == 200

    # CREATE order matching -> combo applies
    lines = [_line(drink), _line(f1), _line(f2)]
    r = client.post(f"{API}/orders", json=_make_order_payload(lines))
    assert r.status_code == 200, r.text
    o = r.json()
    oid = o["id"]
    assert o["combo_discount"] > 0
    assert any(c["name"] == combo["name"] for c in o["combos_applied"])

    # GET to verify persisted
    rg = client.get(f"{API}/orders/{oid}")
    assert rg.status_code == 200
    assert rg.json()["combo_discount"] > 0

    # PATCH lines: remove f2 -> Slot B fails -> combo removed
    new_lines = [_line(drink), _line(f1)]
    rp = client.patch(f"{API}/orders/{oid}", json={"lines": new_lines})
    assert rp.status_code == 200, rp.text
    op = rp.json()
    assert op["combo_discount"] == 0
    assert op["combos_applied"] == []
