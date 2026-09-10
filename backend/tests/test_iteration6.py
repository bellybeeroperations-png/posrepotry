"""Iteration 6 regression tests: 86 product, multi-tier HH, HK payments."""
import os
import requests
import pytest
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
HK = timezone(timedelta(hours=8))


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h():
    return {"Authorization": f"Bearer {_login('polymuze111@gmail.com', 'admin123')}"}


@pytest.fixture
def any_table(admin_h):
    tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
    assert tables
    return tables[0]


@pytest.fixture
def any_product(admin_h):
    prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
    assert prods
    return prods[0]


# ---------- 86 ----------
class TestEightySix:
    def test_toggle_on_then_off_and_public_menu_hides(self, admin_h, any_product, any_table):
        pid = any_product["id"]
        # On
        r = requests.post(f"{BASE_URL}/api/products/{pid}/eightysix",
                          params={"on": "true"}, headers=admin_h)
        assert r.status_code == 200, r.text
        assert r.json()["eightysix"] is True

        # Public menu excludes
        pub = requests.get(f"{BASE_URL}/api/public/menu/{any_table['id']}").json()
        ids = {p["id"] for p in pub["products"]}
        assert pid not in ids, "86'd product must be excluded from public menu"

        # Admin product list still includes (needed for grid overlay)
        admin_prods = requests.get(f"{BASE_URL}/api/products", headers=admin_h).json()
        found = next((p for p in admin_prods if p["id"] == pid), None)
        assert found and found.get("eightysix") is True

        # Un-86
        r2 = requests.post(f"{BASE_URL}/api/products/{pid}/eightysix",
                           params={"on": "false"}, headers=admin_h)
        assert r2.status_code == 200
        assert r2.json()["eightysix"] is False
        pub2 = requests.get(f"{BASE_URL}/api/public/menu/{any_table['id']}").json()
        assert pid in {p["id"] for p in pub2["products"]}


# ---------- Multi-tier Happy Hour ----------
class TestMultiTierHH:
    def test_two_concurrent_rules_both_active_pick_max_percent(self, admin_h):
        # get current HK weekday
        act = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=admin_h).json()
        wday = act["weekday"]
        now_hk = datetime.now(HK)
        # window: now-30min .. now+30min
        start = (now_hk - timedelta(minutes=30)).strftime("%H:%M")
        end = (now_hk + timedelta(minutes=30)).strftime("%H:%M")
        cats = requests.get(f"{BASE_URL}/api/categories", headers=admin_h).json()
        assert cats
        cat_id = cats[0]["id"]

        rule_ids = []
        for name, pct in [("TEST_MT_15", 15), ("TEST_MT_25", 25)]:
            r = requests.post(f"{BASE_URL}/api/happy-hours", headers=admin_h, json={
                "name": name, "start_time": start, "end_time": end,
                "percent_off": pct, "days": [wday], "category_ids": [cat_id],
            })
            assert r.status_code == 200, r.text
            rule_ids.append(r.json()["id"])

        try:
            act2 = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=admin_h).json()
            names = [h["name"] for h in act2["active"]]
            assert "TEST_MT_15" in names and "TEST_MT_25" in names, f"both rules should be active; got {names}"
            # engine returns raw list; frontend picks max — verify both percents present
            pcts = [h["percent_off"] for h in act2["active"] if h["name"].startswith("TEST_MT_")]
            assert max(pcts) == 25
        finally:
            for rid in rule_ids:
                requests.delete(f"{BASE_URL}/api/happy-hours/{rid}", headers=admin_h)


# ---------- HK Payment methods ----------
class TestHKPayments:
    METHODS = ["cash", "card", "octopus", "fps_qr", "alipayhk",
               "wechatpay_hk", "payme", "unionpay"]

    def _make_order(self, admin_h, prod):
        payload = {
            "order_type": "dine_in", "guests": 1,
            "lines": [{"product_id": prod["id"], "name": prod["name"], "price": prod["price"],
                       "qty": 1, "modifiers": [], "course": prod.get("course", "main"),
                       "kind": prod.get("kind", "food")}],
            "discount_type": "none", "discount_value": 0, "service_charge_pct": 10,
        }
        r = requests.post(f"{BASE_URL}/api/orders", json=payload, headers=admin_h)
        assert r.status_code == 200, r.text
        return r.json()

    @pytest.mark.parametrize("method", METHODS)
    def test_pay_method(self, admin_h, any_product, method):
        order = self._make_order(admin_h, any_product)
        pay = requests.post(f"{BASE_URL}/api/orders/{order['id']}/pay",
                            json={"method": method, "amount": order["total"], "tip": 0, "splits": []},
                            headers=admin_h)
        assert pay.status_code == 200, f"{method}: {pay.text}"
        after = requests.get(f"{BASE_URL}/api/orders/{order['id']}", headers=admin_h).json()
        assert after["status"] == "paid"
        assert after["payment"]["method"] == method

    def test_pay_split_with_hk_methods(self, admin_h, any_product):
        order = self._make_order(admin_h, any_product)
        half = round(order["total"] / 2, 2)
        rem = round(order["total"] - half, 2)
        splits = [
            {"method": "octopus", "amount": half},
            {"method": "fps_qr", "amount": rem},
        ]
        pay = requests.post(f"{BASE_URL}/api/orders/{order['id']}/pay",
                            json={"method": "split", "amount": order["total"],
                                  "tip": 0, "splits": splits},
                            headers=admin_h)
        assert pay.status_code == 200, pay.text
        after = requests.get(f"{BASE_URL}/api/orders/{order['id']}", headers=admin_h).json()
        assert after["status"] == "paid"
        assert after["payment"]["method"] == "split"
        assert len(after["payment"].get("splits", [])) == 2
