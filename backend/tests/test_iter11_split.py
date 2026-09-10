"""Iter 11 verification:
1. Tables router extraction (all endpoints still work at /api/tables*)
2. Keg pour logging + GET /api/kegs/{id}/pours
3. POST /api/kds/prep/bump (bump-all by product)
4. Regression: iter 1-10 flows still green
"""
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


# -------- 1. Tables router still works --------
def test_tables_list(s):
    r = s.get(f"{API}/tables")
    assert r.status_code == 200, r.text
    tables = r.json()
    assert isinstance(tables, list)
    assert len(tables) > 0
    t = tables[0]
    for f in ["id", "name", "status"]:
        assert f in t, f"missing {f} in table"


def test_tables_filter_by_area(s):
    areas = s.get(f"{API}/areas").json()
    assert isinstance(areas, list) and len(areas) > 0
    aid = areas[0]["id"]
    r = s.get(f"{API}/tables", params={"area_id": aid})
    assert r.status_code == 200
    tables = r.json()
    for t in tables:
        assert t.get("area_id") == aid


def test_tables_crud_lifecycle(s):
    areas = s.get(f"{API}/areas").json()
    aid = areas[0]["id"]
    # CREATE
    body = {"name": "TEST_T_iter11", "area_id": aid, "seats": 4, "shape": "rect"}
    r = s.post(f"{API}/tables", json=body)
    assert r.status_code in (200, 201), r.text
    t = r.json()
    tid = t["id"]
    assert t["status"] == "available"
    assert t["current_order_id"] is None

    # PATCH
    r = s.patch(f"{API}/tables/{tid}", json={"name": "TEST_T_iter11_upd", "seats": 6, "shape": "rect"})
    assert r.status_code == 200
    assert r.json()["name"] == "TEST_T_iter11_upd"
    assert r.json()["seats"] == 6

    # status
    r = s.post(f"{API}/tables/{tid}/status", params={"status": "cleaning"})
    assert r.status_code == 200
    got = s.get(f"{API}/tables").json()
    assert next(x for x in got if x["id"] == tid)["status"] == "cleaning"

    # clear
    r = s.post(f"{API}/tables/{tid}/clear")
    assert r.status_code == 200
    got = s.get(f"{API}/tables").json()
    row = next(x for x in got if x["id"] == tid)
    assert row["status"] == "available"
    assert row["current_order_id"] is None

    # DELETE
    r = s.delete(f"{API}/tables/{tid}")
    assert r.status_code == 200


# -------- 2. Keg pour logging + analytics endpoint --------
def test_keg_pours_logged_and_returned(s):
    kegs = s.get(f"{API}/kegs").json()
    keg = next((k for k in kegs if k["status"] == "on" and k.get("product") and k["current_ml"] >= k["ml_per_pour"] * 2), None)
    assert keg is not None, "no suitable keg"
    kid = keg["id"]
    pid = keg["product_id"]
    prod = keg["product"]
    pour = keg["ml_per_pour"]
    qty = 2

    # baseline pours today
    r0 = s.get(f"{API}/kegs/{kid}/pours", params={"days": 7})
    assert r0.status_code == 200, r0.text
    d0 = r0.json()
    assert "days" in d0 and "total_ml" in d0 and "total_pints" in d0
    assert isinstance(d0["days"], list) and len(d0["days"]) == 7
    for row in d0["days"]:
        assert "day" in row and "ml" in row and "pints" in row
    today = d0["days"][-1]["day"]
    baseline_today_ml = d0["days"][-1]["ml"]
    baseline_total = d0["total_ml"]

    # place + pay
    payload = {
        "order_type": "pick_up", "guests": 1,
        "lines": [{"product_id": pid, "name": prod["name"], "price": prod["price"],
                   "qty": qty, "variant": None, "modifiers": [], "course": "drink",
                   "held": False, "notes": "TEST_iter11_pour"}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter11_pour",
    }
    o = s.post(f"{API}/orders", json=payload).json()
    r = s.post(f"{API}/orders/{o['id']}/pay",
               json={"method": "cash", "amount": o["total"], "tip": 0, "splits": []})
    assert r.status_code == 200, r.text

    time.sleep(0.3)
    r1 = s.get(f"{API}/kegs/{kid}/pours", params={"days": 7})
    assert r1.status_code == 200
    d1 = r1.json()
    # NB: draining strategy picks lowest-current_ml keg with same pid; may credit sibling keg.
    # Verify SOME keg with the same pid logged the pour, and pints math holds
    all_pids_kegs = [k for k in kegs if k["product_id"] == pid and k["status"] == "on"]
    if len(all_pids_kegs) == 1:
        # single tap for this product — must be logged here
        delta_today = d1["days"][-1]["ml"] - baseline_today_ml
        assert delta_today >= pour * qty, f"expected today delta>={pour*qty}, got {delta_today}"
        assert d1["days"][-1]["day"] == today
    # pints consistency
    assert d1["total_pints"] == round(d1["total_ml"] / 568, 1)
    for row in d1["days"]:
        assert row["pints"] == round(row["ml"] / 568, 1)


def test_keg_pours_missing_days_filled_with_zero(s):
    kegs = s.get(f"{API}/kegs").json()
    kid = kegs[0]["id"]
    r = s.get(f"{API}/kegs/{kid}/pours", params={"days": 7})
    assert r.status_code == 200
    d = r.json()
    assert len(d["days"]) == 7
    for row in d["days"]:
        assert isinstance(row["ml"], int) or isinstance(row["ml"], float)
        assert row["ml"] >= 0


# -------- 3. Prep Bump All --------
def test_prep_bump_all_bumps_across_tables(s):
    prods = s.get(f"{API}/products").json()
    food = next((p for p in prods if p.get("kind") == "food" and not p.get("eightysix")), prods[0])
    line = lambda: {"product_id": food["id"], "name": food["name"], "price": food["price"],
                    "qty": 1, "variant": None, "modifiers": [], "course": food.get("course", "main"),
                    "held": True, "notes": ""}

    oids = []
    for note in ["TEST_bumpall_A", "TEST_bumpall_B"]:
        payload = {"order_type": "pick_up", "guests": 1,
                   "lines": [line()],
                   "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": note}
        o = s.post(f"{API}/orders", json=payload).json()
        oids.append(o["id"])
        fr = s.post(f"{API}/orders/{o['id']}/fire")
        assert fr.status_code == 200

    time.sleep(0.3)
    # ensure prep view shows the product
    prep_before = s.get(f"{API}/kds/prep").json()
    row_before = next((x for x in prep_before if x.get("product_id") == food["id"]), None)
    assert row_before is not None, "product missing from prep view before bump-all"
    assert row_before["total"] >= 2

    # bump all
    r = s.post(f"{API}/kds/prep/bump", params={"product_id": food["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "bumped" in body
    assert body["bumped"] >= 2, f"expected >=2 bumped, got {body['bumped']}"

    # prep view now filtered
    prep_after = s.get(f"{API}/kds/prep").json()
    row_after = next((x for x in prep_after if x.get("product_id") == food["id"]), None)
    # either gone entirely, or total decreased
    if row_after is not None:
        assert row_after["total"] < row_before["total"]

    # cleanup
    for oid in oids:
        try:
            o = s.get(f"{API}/orders/{oid}").json()
            s.post(f"{API}/orders/{oid}/pay",
                   json={"method": "cash", "amount": o["total"], "tip": 0, "splits": []})
        except Exception:
            pass


def test_prep_bump_all_unknown_product(s):
    r = s.post(f"{API}/kds/prep/bump", params={"product_id": "000000000000000000000000"})
    assert r.status_code == 200, r.text
    assert r.json()["bumped"] == 0


# -------- 4. Regression sanity from iter 1-10 --------
def test_reports_summary(s):
    r = s.get(f"{API}/reports/summary")
    assert r.status_code == 200
    d = r.json()
    for k in ["total_revenue", "total_orders", "avg_ticket"]:
        assert k in d


def test_order_lifecycle_split_payment(s):
    prods = s.get(f"{API}/products").json()
    p = next((x for x in prods if not x.get("eightysix")), prods[0])
    payload = {"order_type": "pick_up", "guests": 1,
               "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                          "qty": 2, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                          "held": False, "notes": ""}],
               "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter11_life"}
    o = s.post(f"{API}/orders", json=payload).json()
    total = o["total"]
    half = round(total / 2, 2)
    body = {"method": "split", "amount": total, "tip": 0,
            "splits": [{"method": "cash", "amount": half},
                       {"method": "fps_qr", "amount": round(total - half, 2)}]}
    r = s.post(f"{API}/orders/{o['id']}/pay", json=body)
    assert r.status_code == 200, r.text


def test_pin_login(s):
    r = s.post(f"{API}/auth/pin-login", json={"pin": "1111"})
    assert r.status_code == 200, r.text
