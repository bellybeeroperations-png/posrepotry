"""Iteration 5 regression tests: defensive var inits in server.py.

Covers:
- _compute_totals via POST /api/orders with empty lines + discount_type='none'
- pay_order with method='wallet' returns 200 and payment.change == 0
- public_menu with `t = None` init: 404 on bad OID must not raise 500
"""
import os
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h():
    return {"Authorization": f"Bearer {_login('polymuze111@gmail.com', 'admin123')}"}


# ---------- _compute_totals defensive discount init ----------
class TestComputeTotalsDefaults:
    def test_empty_lines_zero_everything(self, admin_h):
        # POST an order with empty lines and discount_type='none' — every total must be 0
        payload = {
            "order_type": "dine_in", "guests": 1, "lines": [],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }
        r = requests.post(f"{BASE_URL}/api/orders", json=payload, headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["subtotal"] == 0
        assert d["discount"] == 0
        assert d["combo_discount"] == 0
        assert d["service_charge"] == 0
        assert d["total"] == 0
        # cleanup — void
        requests.patch(f"{BASE_URL}/api/orders/{d['id']}", json={"status": "voided"}, headers=admin_h)

    def test_discount_type_none_leaves_discount_zero(self, admin_h):
        # order with lines but discount_type='none' — discount must stay 0
        prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
        assert prods, "seed products required"
        p = prods[0]
        payload = {
            "order_type": "dine_in", "guests": 1,
            "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                       "qty": 2, "modifiers": [], "course": p.get("course", "main"),
                       "kind": p.get("kind", "food")}],
            "discount_type": "none", "discount_value": 50, "service_charge_pct": 10,
        }
        r = requests.post(f"{BASE_URL}/api/orders", json=payload, headers=admin_h)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["discount"] == 0, f"discount_type=none should leave discount=0, got {d['discount']}"
        assert d["subtotal"] == round(p["price"] * 2, 2)
        requests.patch(f"{BASE_URL}/api/orders/{d['id']}", json={"status": "voided"}, headers=admin_h)


# ---------- pay_order defensive change init ----------
class TestPayOrderWalletChange:
    def test_pay_wallet_returns_change_zero(self, admin_h):
        prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
        p = prods[0]
        payload = {
            "order_type": "dine_in", "guests": 1,
            "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                       "qty": 1, "modifiers": [], "course": p.get("course", "main"),
                       "kind": p.get("kind", "food")}],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }
        r = requests.post(f"{BASE_URL}/api/orders", json=payload, headers=admin_h)
        assert r.status_code == 200, r.text
        order = r.json()
        oid = order["id"]
        # pay with wallet — neither cash nor split — change branch untouched but must be 0
        pay = requests.post(f"{BASE_URL}/api/orders/{oid}/pay",
                            json={"method": "wallet", "amount": order["total"],
                                  "tip": 0, "splits": []},
                            headers=admin_h)
        assert pay.status_code == 200, pay.text
        # re-fetch order to confirm payment persisted
        after = requests.get(f"{BASE_URL}/api/orders/{oid}", headers=admin_h).json()
        assert after["status"] == "paid"
        assert after["payment"]["method"] == "wallet"
        assert after["payment"]["change"] == 0

    def test_pay_card_change_zero(self, admin_h):
        prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
        p = prods[0]
        payload = {
            "order_type": "dine_in", "guests": 1,
            "lines": [{"product_id": p["id"], "name": p["name"], "price": p["price"],
                       "qty": 1, "modifiers": [], "course": p.get("course", "main"),
                       "kind": p.get("kind", "food")}],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }
        r = requests.post(f"{BASE_URL}/api/orders", json=payload, headers=admin_h)
        order = r.json()
        oid = order["id"]
        pay = requests.post(f"{BASE_URL}/api/orders/{oid}/pay",
                            json={"method": "card", "amount": order["total"],
                                  "tip": 0, "splits": []},
                            headers=admin_h)
        assert pay.status_code == 200, pay.text
        after = requests.get(f"{BASE_URL}/api/orders/{oid}", headers=admin_h).json()
        assert after["payment"]["change"] == 0


# ---------- public_menu defensive t init ----------
class TestPublicMenuTInit:
    def test_public_menu_bad_oid_returns_404_not_500(self):
        # unauth
        r = requests.get(f"{BASE_URL}/api/public/menu/not-an-oid")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_public_menu_missing_oid_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/public/menu/507f1f77bcf86cd799439011")
        assert r.status_code == 404

    def test_public_menu_valid_table_returns_200(self, admin_h):
        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        assert tables
        r = requests.get(f"{BASE_URL}/api/public/menu/{tables[0]['id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["table"]["id"] == tables[0]["id"]
        assert "products" in d and "categories" in d
