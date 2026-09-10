"""Iter 10 verification: Kegs CRUD, auto-decrement on pay, prep-view aggregation, regression."""
import os
import time
import pytest
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
API = f"{BASE}/api"
CREDS = {"email": "polymuze111@gmail.com", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json=CREDS, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        sess.headers["Authorization"] = f"Bearer {tok}"
    return sess


# -------- Kegs list / seed --------
def test_kegs_list_seeded(s):
    r = s.get(f"{API}/kegs")
    assert r.status_code == 200, r.text
    kegs = r.json()
    assert isinstance(kegs, list)
    assert len(kegs) >= 6, f"expected >=6 seeded kegs, got {len(kegs)}"
    keg = kegs[0]
    for f in ["id", "name", "product_id", "size_ml", "current_ml", "ml_per_pour",
              "threshold_pct", "status", "pct_remaining", "alert"]:
        assert f in keg, f"missing field {f} in keg {keg}"
    assert "product" in keg
    # first keg = Tap 01 · Tsingtao at ~8%
    tap01 = next((k for k in kegs if k["name"].startswith("Tap 01")), None)
    assert tap01 is not None
    assert 6 <= tap01["pct_remaining"] <= 10, f"pct_remaining={tap01['pct_remaining']}"
    assert tap01["alert"] is True


# -------- Keg CRUD --------
def test_keg_create_new_blown_delete(s):
    prods = s.get(f"{API}/products").json()
    p = prods[0]
    body = {"name": "TEST_Keg_iter10", "product_id": p["id"],
            "size_ml": 20000, "ml_per_pour": 500, "threshold_pct": 15.0}
    r = s.post(f"{API}/kegs", json=body)
    assert r.status_code in (200, 201), r.text
    keg = r.json()
    kid = keg["id"]
    assert keg["current_ml"] == 20000
    assert keg["status"] == "on"

    # blown
    r = s.post(f"{API}/kegs/{kid}/blown")
    assert r.status_code == 200
    assert r.json()["status"] == "blown"
    assert r.json()["current_ml"] == 0

    # new (reset)
    r = s.post(f"{API}/kegs/{kid}/new")
    assert r.status_code == 200
    assert r.json()["current_ml"] == 20000
    assert r.json()["status"] == "on"

    # delete
    r = s.delete(f"{API}/kegs/{kid}")
    assert r.status_code == 200


# -------- Auto-decrement on payment --------
def test_keg_auto_decrement_on_pay(s):
    kegs = s.get(f"{API}/kegs").json()
    # pick an 'on' keg with a beer product
    keg = next((k for k in kegs if k["status"] == "on" and k["product"] and k["current_ml"] >= k["ml_per_pour"] * 2), None)
    assert keg is not None, "no suitable keg for pay test"
    pid = keg["product_id"]
    prod = keg["product"]
    before_ml = keg["current_ml"]
    pour = keg["ml_per_pour"]
    qty = 2

    payload = {
        "order_type": "pick_up", "guests": 1,
        "lines": [{"product_id": pid, "name": prod["name"], "price": prod["price"],
                   "qty": qty, "variant": None, "modifiers": [], "course": "drink",
                   "held": False, "notes": "TEST_iter10_keg"}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter10",
    }
    r = s.post(f"{API}/orders", json=payload)
    assert r.status_code in (200, 201), r.text
    order = r.json()
    oid = order["id"]
    total = order["total"]

    r = s.post(f"{API}/orders/{oid}/pay",
               json={"method": "cash", "amount": total, "tip": 0, "splits": []})
    assert r.status_code == 200, r.text

    # verify decrement — because multiple kegs may share a product_id,
    # accept decrement on any keg with the same product_id.
    kegs_after = s.get(f"{API}/kegs").json()
    before_total = sum(k["current_ml"] for k in kegs if k["product_id"] == pid and k["status"] == "on")
    after_total = sum(k["current_ml"] for k in kegs_after if k["product_id"] == pid)
    delta = before_total - after_total
    assert delta == pour * qty, f"expected total delta {pour*qty}, got {delta}"


def test_keg_blown_when_hits_zero(s):
    # create a tiny keg and pay one order to zero it out
    prods = s.get(f"{API}/products").json()
    beer = next((p for p in prods if p.get("kind") == "drink" or "beer" in (p.get("name","").lower())), prods[0])
    body = {"name": "TEST_tiny_keg", "product_id": beer["id"],
            "size_ml": 500, "ml_per_pour": 500, "threshold_pct": 10.0}
    r = s.post(f"{API}/kegs", json=body); assert r.status_code in (200,201)
    kid = r.json()["id"]

    payload = {
        "order_type": "pick_up", "guests": 1,
        "lines": [{"product_id": beer["id"], "name": beer["name"], "price": beer["price"],
                   "qty": 1, "variant": None, "modifiers": [], "course": "drink",
                   "held": False, "notes": ""}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter10_tiny",
    }
    o = s.post(f"{API}/orders", json=payload).json()
    r = s.post(f"{API}/orders/{o['id']}/pay",
               json={"method": "cash", "amount": o["total"], "tip": 0, "splits": []})
    assert r.status_code == 200

    kegs = s.get(f"{API}/kegs").json()
    k = next(k for k in kegs if k["id"] == kid)
    assert k["current_ml"] == 0
    assert k["status"] == "blown"

    # cleanup
    s.delete(f"{API}/kegs/{kid}")


# -------- Prep View --------
def test_prep_view_aggregates_across_tables(s):
    # Fire two orders with same product on different tables/order types
    prods = s.get(f"{API}/products").json()
    food = next((p for p in prods if p.get("kind") == "food"), prods[0])
    line = lambda: {"product_id": food["id"], "name": food["name"], "price": food["price"],
                    "qty": 2, "variant": None, "modifiers": [], "course": food.get("course", "main"),
                    "held": True, "notes": ""}

    created_oids = []
    for note in ["TEST_prep_A", "TEST_prep_B"]:
        payload = {"order_type": "pick_up", "guests": 1,
                   "lines": [line()],
                   "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": note}
        r = s.post(f"{API}/orders", json=payload)
        assert r.status_code in (200, 201), r.text
        o = r.json()
        created_oids.append(o["id"])
        # fire the order
        fr = s.post(f"{API}/orders/{o['id']}/fire")
        assert fr.status_code == 200, fr.text

    time.sleep(0.5)
    r = s.get(f"{API}/kds/prep")
    assert r.status_code == 200, r.text
    prep = r.json()
    assert isinstance(prep, list)
    row = next((x for x in prep if x.get("product_id") == food["id"]), None)
    assert row is not None, f"product not in prep: {[x.get('name') for x in prep]}"
    assert row["total"] >= 4, f"expected total>=4, got {row['total']}"
    assert isinstance(row["tables"], list) and len(row["tables"]) >= 1
    for t in row["tables"]:
        assert "name" in t and "qty" in t

    # cleanup: pay them off so we don't pollute
    for oid in created_oids:
        try:
            o = s.get(f"{API}/orders/{oid}").json()
            s.post(f"{API}/orders/{oid}/pay",
                   json={"method": "cash", "amount": o["total"], "tip": 0, "splits": []})
        except Exception:
            pass


# -------- Regression --------
def test_reports_summary_shape(s):
    r = s.get(f"{API}/reports/summary")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ["total_revenue", "total_orders", "avg_ticket"]:
        assert k in d, f"missing {k}"


def test_full_order_lifecycle(s):
    prods = s.get(f"{API}/products").json()
    p = next((x for x in prods if not x.get("eightysix")), prods[0])
    payload = {"order_type": "pick_up", "guests": 1,
               "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                          "qty": 1, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                          "held": False, "notes": ""}],
               "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter10_life"}
    o = s.post(f"{API}/orders", json=payload).json()
    assert o.get("id")
    # fire
    r = s.post(f"{API}/orders/{o['id']}/fire"); assert r.status_code == 200
    # pay
    r = s.post(f"{API}/orders/{o['id']}/pay",
               json={"method": "octopus", "amount": o["total"], "tip": 0, "splits": []})
    assert r.status_code == 200, r.text
    paid = r.json()
    assert paid.get("status") == "paid"


def test_split_payment(s):
    prods = s.get(f"{API}/products").json()
    p = next((x for x in prods if not x.get("eightysix")), prods[0])
    payload = {"order_type": "pick_up", "guests": 1,
               "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                          "qty": 2, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                          "held": False, "notes": ""}],
               "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter10_split"}
    o = s.post(f"{API}/orders", json=payload).json()
    total = o["total"]
    half = round(total / 2, 2)
    other = round(total - half, 2)
    body = {"method": "split", "amount": total, "tip": 0,
            "splits": [{"method": "cash", "amount": half},
                       {"method": "fps_qr", "amount": other}]}
    r = s.post(f"{API}/orders/{o['id']}/pay", json=body)
    assert r.status_code == 200, r.text
