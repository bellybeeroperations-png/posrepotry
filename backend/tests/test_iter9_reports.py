"""Iter 9 verification: reports_summary shape unchanged + core order+pay sanity."""
import os
import requests

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "https://hk-bar-pos-pro.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
CREDS = {"email": "polymuze111@gmail.com", "password": "admin123"}


def _login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=CREDS, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


def _make_order(s):
    prods = s.get(f"{API}/products").json()
    p = next((x for x in prods if not x.get("eightysix")), prods[0])
    payload = {
        "order_type": "pick_up", "guests": 1,
        "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                   "qty": 1, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                   "held": False, "notes": ""}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter9",
    }
    r = s.post(f"{API}/orders", json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_reports_summary_shape():
    s = _login()
    r = s.get(f"{API}/reports/summary")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ["total_revenue", "total_orders", "avg_ticket",
              "by_hour", "by_category", "by_payment", "by_staff"]:
        assert k in d, f"missing key {k}"
    for item in d["by_hour"]:
        assert "hour" in item and "revenue" in item
    for item in d["by_category"]:
        assert "name" in item and "revenue" in item
    for item in d["by_payment"]:
        assert "name" in item and "revenue" in item
    for item in d["by_staff"]:
        assert "name" in item and "revenue" in item
    print("summary:", {k: (len(v) if isinstance(v, list) else v) for k, v in d.items()})


def test_pay_octopus_and_fps_qr():
    s = _login()
    for method in ("octopus", "fps_qr"):
        o = _make_order(s)
        oid, total = o["id"], o["total"]
        r = s.post(f"{API}/orders/{oid}/pay", json={"method": method, "amount": total, "splits": [{"method": method, "amount": total}]})
        assert r.status_code == 200, f"{method} pay failed: {r.status_code} {r.text}"
        got = s.get(f"{API}/orders/{oid}").json()
        assert got.get("status") == "paid", f"{method} order not paid: {got.get('status')}"


def test_reports_revenue_matches_paid_totals():
    s = _login()
    # Pay a fresh order and confirm summary includes it
    before = s.get(f"{API}/reports/summary").json()
    o = _make_order(s)
    oid, total = o["id"], o["total"]
    r = s.post(f"{API}/orders/{oid}/pay", json={"method": "cash", "amount": total, "splits": [{"method": "cash", "amount": total}]})
    assert r.status_code == 200, r.text
    after = s.get(f"{API}/reports/summary").json()
    delta = round(after["total_revenue"] - before["total_revenue"], 2)
    assert abs(delta - round(total, 2)) < 0.01, f"revenue delta {delta} != order total {total}"


def test_kds_has_product_id():
    s = _login()
    kds = s.get(f"{API}/kds").json()
    assert isinstance(kds, list)
    for t in kds:
        assert "product_id" in t
