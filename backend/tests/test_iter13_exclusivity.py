"""Iter 13 — Promo/Combo/Order-discount mutual exclusivity.

Rules verified:
  1. A product line already priced at happy-hour (hh_pct > 0) skips combos and
     the order-level manual discount.
  2. A product locked by a matched combo cannot be double-locked by another
     overlapping combo.
  3. Order-level manual discount base = subtotal of lines NOT locked by HH or a
     combo.
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
import pytest

BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))
from routers.orders import _compute_totals


def _line(pid, price, qty=1, hh_pct=0):
    return {"product_id": pid, "name": pid, "price": price, "qty": qty, "hh_pct": hh_pct}


def test_hh_line_skips_order_discount_and_combos():
    """A pint priced at HH should NOT feed a combo NOR the -20% cash discount."""
    lines = [_line("beer", 40, hh_pct=20), _line("burger", 100)]
    combos = [{
        "name": "Beer+Burger", "product_ids": ["beer", "burger"],
        "discount_type": "cash", "discount_value": 30, "active": True,
    }]
    t = _compute_totals(lines, "percent", 20, 10, combos)
    # subtotal 140. HH-locked beer excluded from combo -> combo doesn't match.
    # Order 20% applies only to burger (100) -> disc = 20.
    assert t["subtotal"] == 140.00
    assert t["combo_discount"] == 0
    assert t["discount"] == 20.00
    assert "beer" in t["hh_locked_product_ids"]
    assert t["combo_locked_product_ids"] == []


def test_combo_locks_lines_from_manual_discount():
    """Combo-locked products must not shrink the order-level discount base."""
    lines = [_line("A", 100), _line("B", 200), _line("C", 50)]
    combos = [{
        "name": "AB Deal", "product_ids": ["A", "B"],
        "discount_type": "cash", "discount_value": 40, "active": True,
    }]
    t = _compute_totals(lines, "percent", 10, 10, combos)
    # subtotal 350; combo matches locking A+B -> combo_discount 40.
    # Order 10% applies only to C (50) -> discount = 5.
    assert t["subtotal"] == 350.00
    assert t["combo_discount"] == 40.00
    assert t["discount"] == 5.00
    assert set(t["combo_locked_product_ids"]) == {"A", "B"}


def test_two_overlapping_combos_only_best_wins():
    """Second combo sharing any product must be skipped (mutual exclusivity)."""
    lines = [_line("X", 100), _line("Y", 100), _line("Z", 100)]
    combos = [
        {"name": "Small", "product_ids": ["X", "Y"],
         "discount_type": "cash", "discount_value": 10, "active": True},
        {"name": "Big", "product_ids": ["Y", "Z"],
         "discount_type": "cash", "discount_value": 50, "active": True},
    ]
    t = _compute_totals(lines, "none", 0, 10, combos)
    # "Big" wins (50), locks Y+Z; "Small" needs Y -> overlap -> skipped.
    assert t["combo_discount"] == 50.00
    assert len(t["combos_applied"]) == 1
    assert t["combos_applied"][0]["name"] == "Big"
    assert set(t["combo_locked_product_ids"]) == {"Y", "Z"}


def test_no_promotion_no_lock():
    """Baseline: nothing locked, order discount applies to full subtotal."""
    lines = [_line("A", 100, qty=2)]
    t = _compute_totals(lines, "percent", 25, 10, [])
    assert t["subtotal"] == 200.00
    assert t["discount"] == 50.00  # 25% of 200
    assert t["combo_discount"] == 0
    assert t["hh_locked_product_ids"] == []


def test_cash_discount_capped_to_unlocked_subtotal():
    """Cash discount larger than the un-promoted subtotal must be capped."""
    lines = [_line("HHItem", 100, hh_pct=15), _line("Regular", 30)]
    t = _compute_totals(lines, "cash", 200, 10, [])
    # HHItem locked. Unlocked base = 30. Cash discount clamped to 30.
    assert t["discount"] == 30.00
    assert t["subtotal"] == 130.00
