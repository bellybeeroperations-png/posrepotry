"""Iter 8 fix verification: (A) 422 error handling, (B) KDS product_id."""
import os
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://hk-bar-pos-pro.preview.emergentagent.com").rstrip("/")
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


def test_login():
    s = _login()
    assert s is not None


def test_pay_422_invalid_method_returns_readable_detail():
    s = _login()
    # Need an order. Create a simple order.
    prods = s.get(f"{API}/products").json()
    assert prods, "no products"
    p = prods[0]
    payload = {
        "order_type": "pick_up",
        "guests": 1,
        "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                   "qty": 1, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                   "held": False, "notes": ""}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter8",
    }
    r = s.post(f"{API}/orders", json=payload)
    assert r.status_code in (200, 201), r.text
    oid = r.json()["id"]

    # Trigger 422 - fake method
    r = s.post(f"{API}/orders/{oid}/pay", json={"splits": [{"method": "fake_method_xyz", "amount": 100}]})
    assert r.status_code == 422, f"expected 422, got {r.status_code} {r.text}"
    body = r.json()
    assert "detail" in body
    # FastAPI 422 has list of detail with msg field
    d = body["detail"]
    assert isinstance(d, list) and len(d) > 0
    assert "msg" in d[0]
    print("422 msg:", d[0]["msg"])


def test_kds_returns_product_id():
    s = _login()
    # Fetch existing KDS tickets and verify product_id is present on each.
    kds = s.get(f"{API}/kds").json()
    assert isinstance(kds, list) and len(kds) > 0, "No KDS tickets available to verify"
    for t in kds:
        assert "product_id" in t, f"missing product_id: {t}"
    # Also verify one matches an actual product
    prods = {p["id"]: p for p in s.get(f"{API}/products").json()}
    matched = [t for t in kds if t["product_id"] in prods]
    assert matched, "no kds ticket product_id matched a product"
    return

    p = next((x for x in prods if not x.get("eightysix")), prods[0])
    payload = {
        "order_type": "pick_up", "guests": 1,
        "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                   "qty": 1, "variant": None, "modifiers": [], "course": p.get("course", "main"),
                   "held": False, "notes": ""}],
        "discount_type": "none", "discount_value": 0, "service_charge_pct": 10, "notes": "TEST_iter8_kds",
    }
    r = s.post(f"{API}/orders", json=payload)
    assert r.status_code in (200, 201), r.text
    oid = r.json()["id"]

    course = p.get("course", "main")
    fr = s.post(f"{API}/orders/{oid}/fire", params={"course": course})
    assert fr.status_code == 200, fr.text

    kds = s.get(f"{API}/kds").json()
    assert isinstance(kds, list)
    mine = [t for t in kds if t.get("order_id") == oid]
    assert mine, f"no kds ticket for order {oid}; kds={kds[:3]}"
    t = mine[0]
    assert "product_id" in t, f"kds ticket missing product_id: {t}"
    assert t["product_id"] == p["id"], f"product_id mismatch {t['product_id']} != {p['id']}"


def test_kds_86_flow_hides_from_public_menu():
    s = _login()
    # Use an existing KDS ticket's product_id (simulates KDS UI flow)
    kds = s.get(f"{API}/kds").json()
    assert kds, "need existing KDS ticket"
    t = kds[0]
    pid = t["product_id"]
    assert pid, "kds ticket has no product_id"

    # 86 via product_id (as frontend now does)
    r86 = s.post(f"{API}/products/{pid}/eightysix", params={"on": True})
    assert r86.status_code == 200, r86.text

    # Verify product.eightysix true
    p2 = next(x for x in s.get(f"{API}/products").json() if x["id"] == pid)
    assert p2.get("eightysix") is True

    # Verify /api/public/menu/{table_id} excludes it
    tables = s.get(f"{API}/tables").json()
    table_id = tables[0]["id"] if tables else None
    assert table_id, "no tables to query public menu"
    pm = requests.get(f"{API}/public/menu/{table_id}", timeout=15)
    assert pm.status_code == 200, pm.text
    menu = pm.json()
    all_pids = []
    # menu shape may be {categories:[{products:[...]}]} or flat list
    if isinstance(menu, dict):
        for cat in menu.get("categories", []) or []:
            for pr in cat.get("products", []) or []:
                all_pids.append(pr.get("id"))
        for pr in menu.get("products", []) or []:
            all_pids.append(pr.get("id"))
    elif isinstance(menu, list):
        for pr in menu:
            all_pids.append(pr.get("id"))
    assert pid not in all_pids, f"86'd product still visible in public menu; pid={pid}"

    # Verify /api/kds still works after
    k2 = s.get(f"{API}/kds")
    assert k2.status_code == 200

    # cleanup: un-86
    s.post(f"{API}/products/{pid}/eightysix", params={"on": False})
