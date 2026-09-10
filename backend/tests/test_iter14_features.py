"""Iter 14 — Deal-Of-The-Night schedule, Auto-Close tabs, Merge, Move-line."""
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
BAR = {"email": "bartender@hkbar.com", "password": "bartender123"}


@pytest.fixture(scope="module")
def admin_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def bar_sess():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=BAR, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Bartender login failed: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def products(admin_sess):
    r = admin_sess.get(f"{API}/products", timeout=15)
    assert r.status_code == 200
    return r.json()


# ---------- Deal-Of-The-Night schedule ----------
def test_scheduled_combo_out_of_window_not_applied(admin_sess, products):
    p1, p2 = products[0], products[1]
    # Create combo scheduled 00:00-00:01 — extremely unlikely to be "now"
    body = {
        "name": "TEST_ITER14_DOTN_OUT",
        "product_ids": [p1["id"], p2["id"]],
        "discount_type": "percent",
        "discount_value": 25,
        "active": True,
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "start_time": "00:00", "end_time": "00:01"},
    }
    r = admin_sess.post(f"{API}/combos", json=body, timeout=15)
    assert r.status_code in (200, 201), r.text
    combo = r.json()
    cid = combo["id"]
    try:
        # Create matching order
        r = admin_sess.post(f"{API}/orders", json={
            "order_type": "pick_up",
            "lines": [
                {"product_id": p1["id"], "name": p1["name"], "price": 100, "qty": 1},
                {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
            ],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        applied_names = [c["name"] for c in d.get("combos_applied", [])]
        assert "TEST_ITER14_DOTN_OUT" not in applied_names, f"Should NOT be applied out of window: {applied_names}"

        # PATCH combo to now-covering window
        r = admin_sess.patch(f"{API}/combos/{cid}", json={
            **body,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "start_time": "00:00", "end_time": "23:59"},
        }, timeout=15)
        assert r.status_code in (200, 201), r.text

        # Create a new matching order — now combo should apply
        r = admin_sess.post(f"{API}/orders", json={
            "order_type": "pick_up",
            "lines": [
                {"product_id": p1["id"], "name": p1["name"], "price": 100, "qty": 1},
                {"product_id": p2["id"], "name": p2["name"], "price": 100, "qty": 1},
            ],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        applied_names = [c["name"] for c in d.get("combos_applied", [])]
        assert "TEST_ITER14_DOTN_OUT" in applied_names, f"Should be applied in window: {applied_names}"
        # 25% of 200 subtotal = 50 (if TEST combo wins over overlapping seeded)
        assert d["combo_discount"] >= 50.0 - 0.01
    finally:
        admin_sess.delete(f"{API}/combos/{cid}", timeout=15)


# ---------- Auto-close ----------
def test_auto_close_non_manager_forbidden(bar_sess):
    r = bar_sess.post(f"{API}/orders/auto-close", json={"method": "card", "note": "test"}, timeout=15)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_auto_close_admin_closes_all_open(admin_sess, products):
    p1 = products[0]
    # Create 2 open orders
    ids = []
    for _ in range(2):
        r = admin_sess.post(f"{API}/orders", json={
            "order_type": "pick_up",
            "lines": [{"product_id": p1["id"], "name": p1["name"], "price": 60, "qty": 1}],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200
        ids.append(r.json()["id"])

    r = admin_sess.post(f"{API}/orders/auto-close", json={"method": "card", "note": "test"}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["closed"] >= 2, d

    for oid in ids:
        r = admin_sess.get(f"{API}/orders/{oid}", timeout=15)
        assert r.status_code == 200
        o = r.json()
        assert o["status"] == "paid"
        assert o.get("payment", {}).get("auto_closed") is True


# ---------- Merge ----------
def test_merge_orders(admin_sess, products):
    p1, p2 = products[0], products[1]

    def _mk():
        r = admin_sess.post(f"{API}/orders", json={
            "order_type": "pick_up",
            "lines": [
                {"product_id": p1["id"], "name": p1["name"], "price": 50, "qty": 1},
                {"product_id": p2["id"], "name": p2["name"], "price": 80, "qty": 1},
            ],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200, r.text
        return r.json()

    a = _mk()
    b = _mk()
    a_lines = len(a["lines"])
    b_lines = len(b["lines"])

    r = admin_sess.post(f"{API}/orders/merge", json={"source_id": a["id"], "target_id": b["id"]}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["line_count"] == a_lines + b_lines

    # Verify source voided with merged_into
    r = admin_sess.get(f"{API}/orders/{a['id']}", timeout=15)
    src = r.json()
    assert src["status"] == "voided"
    assert src.get("merged_into") == b["id"]

    # Verify target total recomputed
    r = admin_sess.get(f"{API}/orders/{b['id']}", timeout=15)
    tgt = r.json()
    assert len(tgt["lines"]) == a_lines + b_lines
    assert tgt["total"] > 0

    # Cleanup: pay target
    admin_sess.post(f"{API}/orders/{b['id']}/pay", json={"method": "cash", "amount": tgt["total"]}, timeout=15)


# ---------- Move-line ----------
def test_move_line_same_order_and_cross(admin_sess, products):
    p1, p2, p3 = products[0], products[1], products[2]

    def _mk_3lines():
        r = admin_sess.post(f"{API}/orders", json={
            "order_type": "dine_in", "guests": 3,
            "lines": [
                {"product_id": p1["id"], "name": p1["name"], "price": 50, "qty": 1, "seat": 1},
                {"product_id": p2["id"], "name": p2["name"], "price": 60, "qty": 1, "seat": 1},
                {"product_id": p3["id"], "name": p3["name"], "price": 70, "qty": 1, "seat": 1},
            ],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }, timeout=15)
        assert r.status_code == 200, r.text
        return r.json()

    src = _mk_3lines()

    # Same-order: move line 0 to seat 3
    r = admin_sess.post(f"{API}/orders/{src['id']}/move-line", json={"line_index": 0, "target_seat": 3}, timeout=15)
    assert r.status_code == 200, r.text
    r = admin_sess.get(f"{API}/orders/{src['id']}", timeout=15)
    o = r.json()
    assert o["lines"][0]["seat"] == 3

    # Cross-order: move line 0 -> other order, seat 2
    other = _mk_3lines()
    other_before = len(other["lines"])
    r = admin_sess.post(f"{API}/orders/{src['id']}/move-line",
                       json={"line_index": 0, "target_order_id": other["id"], "target_seat": 2}, timeout=15)
    assert r.status_code == 200, r.text

    r = admin_sess.get(f"{API}/orders/{src['id']}", timeout=15)
    src_after = r.json()
    assert len(src_after["lines"]) == 2

    r = admin_sess.get(f"{API}/orders/{other['id']}", timeout=15)
    tgt_after = r.json()
    assert len(tgt_after["lines"]) == other_before + 1
    # The moved line is appended at the end with seat=2
    assert tgt_after["lines"][-1]["seat"] == 2
    # Totals recomputed
    assert tgt_after["subtotal"] > other["subtotal"]

    # Cleanup — cancel via auto-close-like path: void via delete (admin)
    admin_sess.delete(f"{API}/orders/{src['id']}", timeout=15)
    admin_sess.delete(f"{API}/orders/{other['id']}", timeout=15)


# ---------- Regression: seeded combos still auto-apply ----------
def test_seeded_combos_present(admin_sess):
    r = admin_sess.get(f"{API}/combos", timeout=15)
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    # Iter14 seeded 3 advanced combos per problem statement
    expected_any = ["Cocktail Duo", "Beer & Bites", "Steak Night · any 2 mains"]
    found = [n for n in expected_any if n in names]
    assert len(found) >= 1, f"Expected at least one seeded combo, got: {names}"
