"""Iter 17 tests — Combo hints, Substitutes, Delivery, Preauth."""
import os
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://hk-bar-pos-pro.preview.emergentagent.com").rstrip("/")
# Test credentials come from env; never commit real creds to source.
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "polymuze111@gmail.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def products(api):
    return api.get(f"{BASE_URL}/api/products").json()


@pytest.fixture(scope="module")
def tables(api):
    return api.get(f"{BASE_URL}/api/tables").json()


# ---------- Combo hints ----------
class TestComboHints:
    def test_combo_hints_flow(self, api, products, tables):
        hk_sour = next((p for p in products if p["name"] == "Hong Kong Sour"), None)
        assert hk_sour, "Seed product 'Hong Kong Sour' missing"
        table = next((t for t in tables if t.get("status") != "occupied"), tables[0])

        order_payload = {
            "order_type": "dine_in",
            "table_id": table["id"],
            "guests": 2,
            "lines": [{
                "product_id": hk_sour["id"],
                "name": hk_sour["name"],
                "price": hk_sour["price"],
                "qty": 1, "course": hk_sour.get("course", "drink"),
                "seat": 1,
            }],
            "service_charge_pct": 10.0,
        }
        cr = api.post(f"{BASE_URL}/api/orders", json=order_payload)
        assert cr.status_code == 200, cr.text
        order_id = cr.json()["id"]
        try:
            hr = api.get(f"{BASE_URL}/api/floorplan/combo-hints")
            assert hr.status_code == 200, hr.text
            data = hr.json()
            entry = next((e for e in data if e["table_id"] == table["id"]), None)
            assert entry, f"no combo hint for table {table['id']}, got {data}"
            hints = entry["hints"]
            assert hints, "hints empty"
            names = [h["combo_name"] for h in hints]
            assert "Cocktail Duo" in names, f"Cocktail Duo missing from {names}"
            duo = next(h for h in hints if h["combo_name"] == "Cocktail Duo")
            assert duo["product_name"] in ("Old Fashioned", "Johnnie Walker Black"), \
                f"unexpected trigger {duo['product_name']}"
            assert duo["discount"] > 0
        finally:
            api.delete(f"{BASE_URL}/api/orders/{order_id}")


# ---------- Substitutes ----------
class TestSubstitutes:
    def test_substitutes_when_86d(self, api, products):
        target = next((p for p in products if p["name"] == "Hong Kong Sour"), products[0])
        pid = target["id"]
        assert api.post(f"{BASE_URL}/api/products/{pid}/eightysix", params={"on": "true"}).status_code == 200
        try:
            r = api.get(f"{BASE_URL}/api/products/{pid}/substitutes")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["blocked_reason"] == "eighty_sixed"
            subs = data["substitutes"]
            assert 1 <= len(subs) <= 3
            for s in subs:
                assert s["category_id"] == target["category_id"]
                assert not s.get("eightysix", False)
        finally:
            api.post(f"{BASE_URL}/api/products/{pid}/eightysix", params={"on": "false"})


# ---------- Delivery ----------
class TestDelivery:
    def test_simulate_and_inbox(self, api):
        r = api.post(f"{BASE_URL}/api/delivery/simulate")
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["order_type"] == "delivery"
        assert o["delivery"]["platform"] in ("foodpanda", "deliveroo", "keeta")
        assert o["status"] == "open"
        for l in o["lines"]:
            assert l.get("fired_at"), "line must be auto-fired"
        inbox = api.get(f"{BASE_URL}/api/delivery/inbox").json()
        assert any(x["id"] == o["id"] for x in inbox), "simulate order missing from inbox"

    def test_ingest_manual(self, api, products):
        food = next((p for p in products if p.get("kind") == "food"), products[0])
        payload = {
            "platform": "deliveroo",
            "external_id": "MANUAL-1",
            "customer_name": "Test",
            "items": [{"product_id": food["id"], "qty": 2}],
        }
        r = api.post(f"{BASE_URL}/api/delivery/ingest", json=payload)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["service_charge_pct"] == 0
        assert o["service_charge"] == 0
        assert o["subtotal"] == food["price"] * 2
        assert o["total"] == food["price"] * 2


# ---------- Preauth ----------
class TestPreauth:
    def test_preauth_basic(self, api):
        r = api.post(f"{BASE_URL}/api/tabs/preauth", json={
            "customer_name": "Alice", "card_last4": "4242",
            "hold_amount": 500, "party_size": 2,
        })
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == "open"
        assert o["lines"] == []
        pa = o["preauth"]
        assert pa["customer_name"] == "Alice"
        assert pa["card_last4"] == "4242"
        assert pa["hold_amount"] == 500
        assert pa["opened_at"]

    def test_preauth_invalid_last4(self, api):
        r = api.post(f"{BASE_URL}/api/tabs/preauth", json={
            "customer_name": "Bob", "card_last4": "12",
            "hold_amount": 100, "party_size": 1,
        })
        assert r.status_code == 422

    def test_preauth_with_table(self, api, tables):
        # find an available table
        table = next((t for t in tables if t.get("status") == "available"), None)
        if not table:
            # free the first table
            table = tables[0]
        r = api.post(f"{BASE_URL}/api/tabs/preauth", json={
            "customer_name": "Carol", "card_last4": "9999",
            "hold_amount": 300, "party_size": 3, "table_id": table["id"],
        })
        assert r.status_code == 200, r.text
        o = r.json()
        order_id = o["id"]
        try:
            t = api.get(f"{BASE_URL}/api/tables").json()
            tb = next(x for x in t if x["id"] == table["id"])
            assert tb["status"] == "occupied"
            assert tb["current_order_id"] == order_id
        finally:
            api.delete(f"{BASE_URL}/api/orders/{order_id}")
