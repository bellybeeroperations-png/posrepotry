"""Iteration 2 tests: Happy hour active/patch, category patch, split payment."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
HK = ZoneInfo("Asia/Hong_Kong")


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "polymuze111@gmail.com", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# -------- Happy Hour /active --------
class TestHappyHourActive:
    def test_active_returns_shape(self, h):
        r = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert "active" in data and "hk_time" in data and "weekday" in data
        assert isinstance(data["active"], list)
        assert isinstance(data["weekday"], int)

    def test_only_matching_rules_returned(self, h):
        # Get HK now
        active = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=h).json()
        wd = active["weekday"]
        # Create a rule for TODAY spanning full-day
        r_in = requests.post(f"{BASE_URL}/api/happy-hours", headers=h, json={
            "name": "TEST_HH_TODAY", "days": [wd],
            "start_time": "00:00", "end_time": "23:59",
            "percent_off": 15.0, "category_ids": [],
        })
        assert r_in.status_code == 200
        in_id = r_in.json()["id"]

        # Create a rule for a NON-today weekday
        other_wd = (wd + 3) % 7
        r_out = requests.post(f"{BASE_URL}/api/happy-hours", headers=h, json={
            "name": "TEST_HH_OTHER", "days": [other_wd],
            "start_time": "00:00", "end_time": "23:59",
            "percent_off": 15.0, "category_ids": [],
        })
        assert r_out.status_code == 200
        out_id = r_out.json()["id"]

        # Create a rule for TODAY but in a past 1-min window
        now_hk = datetime.now(HK)
        # pick a window that does not include now
        past_start = "00:00"
        past_end = "00:01"
        # Ensure current time > 00:01 for HK (it always will be unless midnight)
        cur_str = now_hk.strftime("%H:%M")
        if cur_str <= "00:01":
            past_start, past_end = "23:58", "23:59"
        r_time = requests.post(f"{BASE_URL}/api/happy-hours", headers=h, json={
            "name": "TEST_HH_TIMEOUT", "days": [wd],
            "start_time": past_start, "end_time": past_end,
            "percent_off": 15.0, "category_ids": [],
        })
        assert r_time.status_code == 200
        time_id = r_time.json()["id"]

        active2 = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=h).json()
        ids = {a["id"] for a in active2["active"]}
        assert in_id in ids, "today-window rule should be active"
        assert out_id not in ids, "wrong-day rule should NOT be active"
        assert time_id not in ids, "out-of-time rule should NOT be active"

        # cleanup
        for hid in (in_id, out_id, time_id):
            requests.delete(f"{BASE_URL}/api/happy-hours/{hid}", headers=h)

    def test_cross_midnight_rule(self, h):
        # rule that spans midnight 22:00 - 02:00
        active = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=h).json()
        wd = active["weekday"]
        now_hk = datetime.now(HK)
        cur = now_hk.strftime("%H:%M")
        r = requests.post(f"{BASE_URL}/api/happy-hours", headers=h, json={
            "name": "TEST_HH_XMID", "days": [wd],
            "start_time": "22:00", "end_time": "02:00",
            "percent_off": 20.0, "category_ids": [],
        })
        assert r.status_code == 200
        hid = r.json()["id"]
        active2 = requests.get(f"{BASE_URL}/api/happy-hours/active", headers=h).json()
        ids = {a["id"] for a in active2["active"]}
        should_be_active = cur >= "22:00" or cur <= "02:00"
        if should_be_active:
            assert hid in ids
        else:
            assert hid not in ids
        requests.delete(f"{BASE_URL}/api/happy-hours/{hid}", headers=h)


# -------- PATCH endpoints --------
class TestPatchEndpoints:
    def test_patch_happy_hour(self, h):
        r = requests.post(f"{BASE_URL}/api/happy-hours", headers=h, json={
            "name": "TEST_HH_PATCH", "days": [0],
            "start_time": "10:00", "end_time": "12:00",
            "percent_off": 10.0, "category_ids": [],
        })
        assert r.status_code == 200
        hid = r.json()["id"]
        pr = requests.patch(f"{BASE_URL}/api/happy-hours/{hid}", headers=h, json={
            "name": "TEST_HH_PATCHED", "days": [0, 1],
            "start_time": "11:00", "end_time": "13:00",
            "percent_off": 25.0, "category_ids": [],
        })
        assert pr.status_code == 200
        d = pr.json()
        assert d["name"] == "TEST_HH_PATCHED"
        assert d["percent_off"] == 25.0
        assert d["days"] == [0, 1]
        requests.delete(f"{BASE_URL}/api/happy-hours/{hid}", headers=h)

    def test_patch_category(self, h):
        r = requests.post(f"{BASE_URL}/api/categories", headers=h, json={
            "name": "TEST_CAT", "color": "#111111",
        })
        assert r.status_code == 200
        cid = r.json()["id"]
        pr = requests.patch(f"{BASE_URL}/api/categories/{cid}", headers=h, json={
            "name": "TEST_CAT_UPDATED", "color": "#222222",
        })
        assert pr.status_code == 200
        d = pr.json()
        assert d["name"] == "TEST_CAT_UPDATED"
        assert d["color"] == "#222222"
        requests.delete(f"{BASE_URL}/api/categories/{cid}", headers=h)


# -------- Split payment --------
class TestSplitPayment:
    def _make_order(self, headers):
        # pick any product
        prods = requests.get(f"{BASE_URL}/api/products", headers=headers).json()
        p = prods[0]
        r = requests.post(f"{BASE_URL}/api/orders", headers=headers, json={
            "order_type": "dine_in", "guests": 2,
            "lines": [{"product_id": p["id"], "name": p["name"],
                       "price": p["price"], "qty": 2, "course": "main"}],
            "service_charge_pct": 10.0,
        })
        assert r.status_code == 200
        return r.json()

    def test_split_insufficient_returns_400(self, h):
        o = self._make_order(h)
        total = o["total"]
        r = requests.post(f"{BASE_URL}/api/orders/{o['id']}/pay", headers=h, json={
            "method": "split", "amount": 0, "tip": 0,
            "splits": [{"method": "cash", "amount": round(total / 3, 2)}],
        })
        assert r.status_code == 400
        assert "Split total" in r.text

    def test_split_success(self, h):
        o = self._make_order(h)
        total = o["total"]
        half = round(total / 2, 2)
        r = requests.post(f"{BASE_URL}/api/orders/{o['id']}/pay", headers=h, json={
            "method": "split", "amount": 0, "tip": 0,
            "splits": [
                {"method": "cash", "amount": half},
                {"method": "card", "amount": total - half},
            ],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "paid"
        assert d["payment"]["method"] == "split"
        assert len(d["payment"]["splits"]) == 2
        # change should be 0 (within rounding)
        assert abs(d["payment"]["change"]) < 0.02

    def test_split_overpay_change(self, h):
        o = self._make_order(h)
        total = o["total"]
        r = requests.post(f"{BASE_URL}/api/orders/{o['id']}/pay", headers=h, json={
            "method": "split", "amount": 0, "tip": 0,
            "splits": [{"method": "cash", "amount": total + 20}],
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["payment"]["method"] == "split"
        assert abs(d["payment"]["change"] - 20) < 0.02
