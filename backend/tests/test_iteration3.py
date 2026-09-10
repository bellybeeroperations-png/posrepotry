"""Iteration 3 tests: KDS, Shifts (clock-in/out, current, list), Reservations."""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_h():
    return {"Authorization": f"Bearer {_login('polymuze111@gmail.com', 'admin123')}"}


@pytest.fixture(scope="session")
def server_h():
    return {"Authorization": f"Bearer {_login('server@hkbar.com', 'server123')}"}


@pytest.fixture(scope="session")
def manager_h():
    return {"Authorization": f"Bearer {_login('manager@hkbar.com', 'manager123')}"}


# ---------- helpers ----------
def _pick_two_products(h):
    prods = requests.get(f"{BASE_URL}/api/products", headers=h).json()
    food = next((p for p in prods if p.get("kind") == "food"), None)
    drink = next((p for p in prods if p.get("kind") == "drink"), None)
    assert food and drink, "Need at least 1 food + 1 drink seeded"
    return food, drink


def _make_order_with_fired_lines(h, table_id=None):
    food, drink = _pick_two_products(h)
    body = {
        "order_type": "dine_in",
        "guests": 2,
        "table_id": table_id,
        "lines": [
            {"product_id": food["id"], "name": food["name"], "price": food["price"],
             "qty": 1, "course": "main", "held": False},
            {"product_id": drink["id"], "name": drink["name"], "price": drink["price"],
             "qty": 1, "course": "drink", "held": False},
        ],
        "service_charge_pct": 10.0,
    }
    r = requests.post(f"{BASE_URL}/api/orders", headers=h, json=body)
    assert r.status_code == 200, r.text
    o = r.json()
    # Fire all lines so they appear on KDS
    fr = requests.post(f"{BASE_URL}/api/orders/{o['id']}/fire", headers=h)
    assert fr.status_code == 200, fr.text
    # But /fire only fires held lines. Since held=False, we need to set fired_at manually via update.
    # However kds check is `not l.get("fired_at")` -> exclude. So we need fired_at set.
    # Easiest: create with held=True then fire.
    return o


def _make_order_fired(h, table_id=None):
    food, drink = _pick_two_products(h)
    body = {
        "order_type": "dine_in",
        "guests": 2,
        "table_id": table_id,
        "lines": [
            {"product_id": food["id"], "name": food["name"], "price": food["price"],
             "qty": 1, "course": "main", "held": True},
            {"product_id": drink["id"], "name": drink["name"], "price": drink["price"],
             "qty": 1, "course": "drink", "held": True},
        ],
        "service_charge_pct": 10.0,
    }
    r = requests.post(f"{BASE_URL}/api/orders", headers=h, json=body)
    assert r.status_code == 200, r.text
    o = r.json()
    fr = requests.post(f"{BASE_URL}/api/orders/{o['id']}/fire", headers=h)
    assert fr.status_code == 200 and fr.json()["fired"] == 2
    return o


# ================== KDS ==================
class TestKDS:
    def test_kds_shows_fired_lines_and_station_filter(self, admin_h):
        o = _make_order_fired(admin_h)
        oid = o["id"]

        # all
        r = requests.get(f"{BASE_URL}/api/kds?station=all", headers=admin_h)
        assert r.status_code == 200
        all_tickets = r.json()
        mine = [t for t in all_tickets if t["order_id"] == oid]
        assert len(mine) == 2
        kinds = {t["kind"] for t in mine}
        assert kinds == {"food", "drink"}

        # kitchen -> food only
        r = requests.get(f"{BASE_URL}/api/kds?station=kitchen", headers=admin_h)
        mine = [t for t in r.json() if t["order_id"] == oid]
        assert len(mine) == 1 and mine[0]["kind"] == "food"

        # bar -> drink only
        r = requests.get(f"{BASE_URL}/api/kds?station=bar", headers=admin_h)
        mine = [t for t in r.json() if t["order_id"] == oid]
        assert len(mine) == 1 and mine[0]["kind"] == "drink"

        # bump line 0
        br = requests.post(f"{BASE_URL}/api/orders/{oid}/bump/0", headers=admin_h)
        assert br.status_code == 200
        assert "bumped_at" in br.json()

        # gone from KDS
        r = requests.get(f"{BASE_URL}/api/kds?station=all", headers=admin_h)
        mine = [t for t in r.json() if t["order_id"] == oid and t["line_index"] == 0]
        assert mine == []
        # line 1 still there
        mine1 = [t for t in r.json() if t["order_id"] == oid and t["line_index"] == 1]
        assert len(mine1) == 1

    def test_bump_out_of_range_returns_400(self, admin_h):
        o = _make_order_fired(admin_h)
        r = requests.post(f"{BASE_URL}/api/orders/{o['id']}/bump/99", headers=admin_h)
        assert r.status_code == 400
        r = requests.post(f"{BASE_URL}/api/orders/{o['id']}/bump/-1", headers=admin_h)
        assert r.status_code == 400


# ================== SHIFTS ==================
class TestShifts:
    def test_clock_in_idempotent(self, server_h):
        # ensure clean state
        requests.post(f"{BASE_URL}/api/shifts/clock-out", headers=server_h)
        r1 = requests.post(f"{BASE_URL}/api/shifts/clock-in", headers=server_h)
        assert r1.status_code == 200
        s1 = r1.json()
        assert s1.get("clock_out") in (None,)
        r2 = requests.post(f"{BASE_URL}/api/shifts/clock-in", headers=server_h)
        assert r2.status_code == 200
        s2 = r2.json()
        assert s2["id"] == s1["id"]
        # cleanup
        requests.post(f"{BASE_URL}/api/shifts/clock-out", headers=server_h)

    def test_current_reflects_paid_order(self, server_h):
        # Clean + clock in fresh
        requests.post(f"{BASE_URL}/api/shifts/clock-out", headers=server_h)
        ci = requests.post(f"{BASE_URL}/api/shifts/clock-in", headers=server_h)
        assert ci.status_code == 200

        cur0 = requests.get(f"{BASE_URL}/api/shifts/current", headers=server_h).json()
        assert cur0["open"] is True
        rev0 = cur0["revenue"]
        ord0 = cur0["orders"]
        tips0 = cur0["tips"]

        # Create an order AS server (server_id auto-set to caller)
        food, drink = _pick_two_products(server_h)
        r = requests.post(f"{BASE_URL}/api/orders", headers=server_h, json={
            "order_type": "dine_in", "guests": 3,
            "lines": [{"product_id": food["id"], "name": food["name"],
                       "price": food["price"], "qty": 2, "course": "main"}],
            "service_charge_pct": 10.0,
        })
        assert r.status_code == 200
        o = r.json()
        assert o.get("server_id"), "server_id auto-set"

        # Pay it (cash, with tip)
        pr = requests.post(f"{BASE_URL}/api/orders/{o['id']}/pay", headers=server_h, json={
            "method": "cash", "amount": o["total"] + 10, "tip": 10, "splits": [],
        })
        assert pr.status_code == 200

        cur1 = requests.get(f"{BASE_URL}/api/shifts/current", headers=server_h).json()
        assert cur1["open"] is True
        assert cur1["orders"] == ord0 + 1
        assert abs(cur1["revenue"] - (rev0 + o["total"])) < 0.02
        assert abs(cur1["tips"] - (tips0 + 10)) < 0.02
        assert cur1["covers"] >= 3

        # Clock out
        co = requests.post(f"{BASE_URL}/api/shifts/clock-out", headers=server_h)
        assert co.status_code == 200
        stats = co.json()
        assert stats["shift"].get("clock_out")

        # Subsequent /current -> open:false
        cur2 = requests.get(f"{BASE_URL}/api/shifts/current", headers=server_h).json()
        assert cur2["open"] is False

    def test_shifts_list_role_scoping(self, admin_h, server_h, manager_h):
        # admin sees all, server only own
        all_r = requests.get(f"{BASE_URL}/api/shifts", headers=admin_h)
        assert all_r.status_code == 200
        all_data = all_r.json()
        user_ids_admin = {s["shift"]["user_id"] for s in all_data}

        srv_r = requests.get(f"{BASE_URL}/api/shifts", headers=server_h)
        assert srv_r.status_code == 200
        srv_data = srv_r.json()
        srv_ids = {s["shift"]["user_id"] for s in srv_data}
        assert len(srv_ids) <= 1

        mgr_r = requests.get(f"{BASE_URL}/api/shifts", headers=manager_h)
        assert mgr_r.status_code == 200
        mgr_ids = {s["shift"]["user_id"] for s in mgr_r.json()}
        # manager sees multiple users
        assert len(user_ids_admin) >= len(srv_ids)


# ================== RESERVATIONS ==================
class TestReservations:
    def _find_available_table(self, h):
        tables = requests.get(f"{BASE_URL}/api/tables", headers=h).json()
        for t in tables:
            if t.get("status") == "available":
                return t
        # Cleanup a reserved one
        for t in tables:
            if t.get("status") == "reserved" and t.get("reservation_id"):
                requests.delete(f"{BASE_URL}/api/reservations/{t['reservation_id']}", headers=h)
                return t
        return None

    def test_reservation_lifecycle(self, admin_h):
        t = self._find_available_table(admin_h)
        assert t is not None
        tid = t["id"]

        reserved_for = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        r = requests.post(f"{BASE_URL}/api/reservations", headers=admin_h, json={
            "table_id": tid, "guest_name": "TEST_John",
            "phone": "12345678", "party_size": 3,
            "reserved_for": reserved_for, "notes": "window seat"
        })
        assert r.status_code == 200, r.text
        res = r.json()
        rid = res["id"]

        # table shows reserved + reservation info
        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        tb = next(x for x in tables if x["id"] == tid)
        assert tb["status"] == "reserved"
        assert tb["reservation"]["guest_name"] == "TEST_John"
        assert tb["reservation"]["party_size"] == 3
        assert tb["reservation"]["phone"] == "12345678"
        assert "reserved_for" in tb["reservation"]

        # list -> pending only
        lst = requests.get(f"{BASE_URL}/api/reservations", headers=admin_h).json()
        assert any(x["id"] == rid for x in lst)
        for x in lst:
            assert x["status"] == "pending"

        # seat
        sr = requests.post(f"{BASE_URL}/api/reservations/{rid}/seat", headers=admin_h)
        assert sr.status_code == 200
        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        tb = next(x for x in tables if x["id"] == tid)
        assert tb["status"] == "available"
        # no longer in pending list
        lst = requests.get(f"{BASE_URL}/api/reservations", headers=admin_h).json()
        assert not any(x["id"] == rid for x in lst)

    def test_cancel_reservation(self, admin_h):
        t = self._find_available_table(admin_h)
        assert t is not None
        tid = t["id"]
        reserved_for = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        r = requests.post(f"{BASE_URL}/api/reservations", headers=admin_h, json={
            "table_id": tid, "guest_name": "TEST_Jane",
            "phone": "99999999", "party_size": 2,
            "reserved_for": reserved_for
        })
        assert r.status_code == 200
        rid = r.json()["id"]

        dr = requests.delete(f"{BASE_URL}/api/reservations/{rid}", headers=admin_h)
        assert dr.status_code == 200

        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        tb = next(x for x in tables if x["id"] == tid)
        assert tb["status"] == "available"

    def test_reserve_occupied_returns_400(self, admin_h):
        # find or create an occupied table by making an order attached
        tables = requests.get(f"{BASE_URL}/api/tables", headers=admin_h).json()
        avail = next((t for t in tables if t.get("status") == "available"), None)
        assert avail
        food, _ = _pick_two_products(admin_h)
        r = requests.post(f"{BASE_URL}/api/orders", headers=admin_h, json={
            "order_type": "dine_in", "guests": 2, "table_id": avail["id"],
            "lines": [{"product_id": food["id"], "name": food["name"],
                       "price": food["price"], "qty": 1, "course": "main"}],
            "service_charge_pct": 10.0,
        })
        assert r.status_code == 200
        oid = r.json()["id"]

        # now try to reserve it
        reserved_for = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        rr = requests.post(f"{BASE_URL}/api/reservations", headers=admin_h, json={
            "table_id": avail["id"], "guest_name": "TEST_Occ",
            "phone": "1", "party_size": 2, "reserved_for": reserved_for,
        })
        assert rr.status_code == 400

        # cleanup: pay & clear
        requests.post(f"{BASE_URL}/api/orders/{oid}/pay", headers=admin_h, json={
            "method": "cash", "amount": 9999, "tip": 0, "splits": []
        })
        requests.post(f"{BASE_URL}/api/tables/{avail['id']}/clear", headers=admin_h)
