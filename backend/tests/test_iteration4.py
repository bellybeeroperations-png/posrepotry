"""Iteration 4 tests: Public menu, PIN verify, Waitlist, Combos + engine."""
import os
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h():
    return {"Authorization": f"Bearer {_login('polymuze111@gmail.com', 'admin123')}"}


# ---------- Public menu ----------
class TestPublicMenu:
    def test_public_menu_no_auth(self, admin_h):
        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        assert tables, "seed tables required"
        tid = tables[0]["id"]
        r = requests.get(f"{BASE_URL}/api/public/menu/{tid}")  # no auth
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("table", "area", "categories", "products", "active_hh"):
            assert key in data
        assert data["table"]["id"] == tid
        assert isinstance(data["categories"], list) and len(data["categories"]) > 0
        assert isinstance(data["products"], list) and len(data["products"]) > 0
        # No _id in serialized docs
        for p in data["products"]:
            assert "_id" not in p
            assert p.get("active", True) is True
            assert p.get("eightysix", False) is False

    def test_public_menu_404(self):
        r = requests.get(f"{BASE_URL}/api/public/menu/507f1f77bcf86cd799439011")
        assert r.status_code == 404

    def test_public_menu_bad_id(self):
        r = requests.get(f"{BASE_URL}/api/public/menu/not-a-real-oid")
        assert r.status_code == 404


# ---------- PIN Verify ----------
class TestPinVerify:
    def test_wrong_pin(self):
        r = requests.post(f"{BASE_URL}/api/auth/pin-verify",
                          json={"pin": "0000", "required_roles": ["manager", "admin"]})
        assert r.status_code == 401

    def test_valid_pin_wrong_role(self):
        # server PIN 3333, but required_roles excludes server
        r = requests.post(f"{BASE_URL}/api/auth/pin-verify",
                          json={"pin": "3333", "required_roles": ["manager", "admin"]})
        assert r.status_code == 403

    def test_manager_pin_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/pin-verify",
                          json={"pin": "1111", "required_roles": ["manager", "admin"]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid"] is True
        assert d["role"] == "manager"
        assert d["name"]
        assert isinstance(d["user_id"], str)

    def test_admin_pin_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/pin-verify",
                          json={"pin": "9999", "required_roles": ["manager", "admin"]})
        assert r.status_code == 200
        assert r.json()["role"] == "admin"


# ---------- Waitlist ----------
class TestWaitlist:
    def test_full_flow(self, admin_h):
        # Add
        payload = {"name": "TEST_Alpha", "phone": "+85290000001",
                   "party_size": 3, "quoted_wait_min": 12}
        r = requests.post(f"{BASE_URL}/api/waitlist", headers=admin_h, json=payload)
        assert r.status_code == 200, r.text
        w = r.json()
        wid = w["id"]
        assert w["status"] == "waiting"
        assert w["name"] == "TEST_Alpha"
        assert "_id" not in w

        # List includes it
        lst = requests.get(f"{BASE_URL}/api/waitlist", headers=admin_h).json()
        assert any(x["id"] == wid for x in lst)

        # Notify (mocked SMS)
        n = requests.post(f"{BASE_URL}/api/waitlist/{wid}/notify", headers=admin_h)
        assert n.status_code == 200
        nd = n.json()
        assert nd.get("mocked_sms_to") == "+85290000001"
        assert "TEST_Alpha" in nd["message"]

        # After notify, still listed, status=notified
        lst2 = requests.get(f"{BASE_URL}/api/waitlist", headers=admin_h).json()
        me = next(x for x in lst2 if x["id"] == wid)
        assert me["status"] == "notified"
        assert me["notified_at"]

        # Seat -> removed from list
        s = requests.post(f"{BASE_URL}/api/waitlist/{wid}/seat", headers=admin_h)
        assert s.status_code == 200
        lst3 = requests.get(f"{BASE_URL}/api/waitlist", headers=admin_h).json()
        assert not any(x["id"] == wid for x in lst3)

    def test_cancel_removes(self, admin_h):
        r = requests.post(f"{BASE_URL}/api/waitlist", headers=admin_h,
                          json={"name": "TEST_Bravo", "phone": "+85290000002",
                                "party_size": 2, "quoted_wait_min": 10})
        wid = r.json()["id"]
        c = requests.delete(f"{BASE_URL}/api/waitlist/{wid}", headers=admin_h)
        assert c.status_code == 200
        lst = requests.get(f"{BASE_URL}/api/waitlist", headers=admin_h).json()
        assert not any(x["id"] == wid for x in lst)


# ---------- Combos ----------
def _two_products(admin_h):
    prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
    assert len(prods) >= 2
    return prods[0], prods[1]


class TestCombos:
    def test_crud_and_engine(self, admin_h):
        pA, pB = _two_products(admin_h)

        # Create combo
        cbody = {
            "name": "TEST_ComboAB",
            "product_ids": [pA["id"], pB["id"]],
            "discount_type": "percent",
            "discount_value": 15,
            "active": True,
        }
        c = requests.post(f"{BASE_URL}/api/combos", headers=admin_h, json=cbody)
        assert c.status_code == 200, c.text
        cid = c.json()["id"]

        # GET list contains it
        lst = requests.get(f"{BASE_URL}/api/combos", headers=admin_h).json()
        assert any(x["id"] == cid for x in lst)

        # Order with BOTH products -> combo applies
        order_body = {
            "order_type": "dine_in",
            "guests": 2,
            "service_charge_pct": 10.0,
            "lines": [
                {"product_id": pA["id"], "name": pA["name"], "price": pA["price"],
                 "qty": 1, "course": "main"},
                {"product_id": pB["id"], "name": pB["name"], "price": pB["price"],
                 "qty": 1, "course": "main"},
            ],
        }
        r = requests.post(f"{BASE_URL}/api/orders", headers=admin_h, json=order_body)
        assert r.status_code == 200, r.text
        o = r.json()
        oid_both = o["id"]
        subtotal = pA["price"] + pB["price"]
        assert abs(o["subtotal"] - round(subtotal, 2)) < 0.01
        expected_combo = round(subtotal * 0.15, 2)
        assert abs(o["combo_discount"] - expected_combo) < 0.05, o
        assert any(ca["name"] == "TEST_ComboAB" for ca in o["combos_applied"])
        # total = (subtotal - combo_discount) * 1.10
        expected_total = round((subtotal - expected_combo) * 1.10, 2)
        assert abs(o["total"] - expected_total) < 0.05, (o, expected_total)

        # Order with only ONE product -> no combo
        order_body_1 = {
            "order_type": "dine_in",
            "guests": 1,
            "service_charge_pct": 10.0,
            "lines": [
                {"product_id": pA["id"], "name": pA["name"], "price": pA["price"],
                 "qty": 1, "course": "main"},
            ],
        }
        r1 = requests.post(f"{BASE_URL}/api/orders", headers=admin_h, json=order_body_1)
        assert r1.status_code == 200
        o1 = r1.json()
        oid_one = o1["id"]
        assert o1["combo_discount"] == 0
        assert o1["combos_applied"] == []

        # Deactivate combo -> subsequent orders won't apply
        up = requests.patch(f"{BASE_URL}/api/combos/{cid}", headers=admin_h,
                            json={**cbody, "active": False})
        assert up.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/orders", headers=admin_h, json=order_body)
        assert r2.status_code == 200
        o2 = r2.json()
        oid_deact = o2["id"]
        assert o2["combo_discount"] == 0
        assert o2["combos_applied"] == []

        # Cleanup: delete combo + orders
        requests.delete(f"{BASE_URL}/api/combos/{cid}", headers=admin_h)
        # (orders are open; leave or void via admin — for cleanliness, mark voided)
        for oid in (oid_both, oid_one, oid_deact):
            requests.delete(f"{BASE_URL}/api/orders/{oid}", headers=admin_h)

        # Verify combo deleted
        lst2 = requests.get(f"{BASE_URL}/api/combos", headers=admin_h).json()
        assert not any(x["id"] == cid for x in lst2)
