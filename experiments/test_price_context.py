"""Offline finite forecast regressions; no HA or charger connections."""
import unittest
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/predbat"))
from price_context import context_curve, parse_context, context_html
from proxy_context import map_proxy
from types import SimpleNamespace
from plan import prepare_terminal_curve


def rows(price=25, export=0, load=0.2, pv=0, count=72):
    """Build explicit half-hour energy and price rows."""
    return [dict(minutes=30, **{"import": price}, export=export, load=load, pv=pv) for _ in range(count)]


class ContextTests(unittest.TestCase):
    """Check bounded economics, unavailable forecasts and display semantics."""

    def test_unavailable_retains_existing_value(self):
        """Missing trial data must not erase the legacy stored-energy value."""
        curve = [float(i) for i in range(33)]
        p = SimpleNamespace(forecast_minutes=1440, get_arg=lambda *a, **k: True, get_state_wrapper=lambda *a, **k: None, log=lambda *a: None, _terminal_curve_key=(None, None), _terminal_curve=curve)
        self.assertEqual(prepare_terminal_curve(p), curve)
        self.assertIsNone(p._price_context_curve)
        self.assertIn("existing battery valuation retained", p.price_context_status)

    def test_no_beyond_forecast(self):
        """No remaining demand/export opportunity means zero additional value."""
        self.assertEqual(context_curve([], 0.936, 15.6), [0.0] * 33)
        self.assertEqual(context_curve(rows(load=0), 0.936, 15.6), [0.0] * 33)

    def test_expensive_vs_cheap_refill(self):
        """A real cheap refill opportunity lowers the value of carried energy."""
        expensive = context_curve(rows(load=0.5), 0.936, 15.6)
        cheap = context_curve(rows(price=5, load=0.5, count=12) + rows(load=0.5, count=60), 0.936, 15.6)
        self.assertGreater(expensive[16], cheap[16])

    def test_solar_lowers_value(self):
        """Surplus generation before demand lowers carry-over value."""
        scarce = context_curve(rows(load=0.5), 0.936, 15.6)
        sunny = context_curve(rows(load=0, pv=2, count=12) + rows(load=0.5, count=60), 0.936, 15.6)
        self.assertGreater(scarce[16], sunny[16])

    def test_power_bound(self):
        """A single slot cannot monetise an entire battery."""
        curve = context_curve(rows(price=72, load=8, count=1), 0.936, 15.6)
        self.assertLessEqual(curve[-1], 3.68 * 0.5 * 72)

    def test_negative_import(self):
        """Space can be valuable during negative pricing; do not clamp its sign."""
        curve = context_curve(rows(price=-5, load=0, count=12), 0.936, 15.6)
        self.assertLess(curve[-1], 0)

    def test_timestamp_coverage(self):
        """Stop at first gap, cap at 36h, reject stale data and never repeat."""
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        boundary = now + timedelta(hours=24)
        values = []
        for i in range(80):
            values.append(dict(start=(boundary + timedelta(minutes=30 * i)).isoformat(), end=(boundary + timedelta(minutes=30 * (i + 1))).isoformat(), **{"import": 20}, export=16, band="medium"))
        snapshot = dict(issued_at=now.isoformat(), rates=values)
        self.assertEqual(len(parse_context(snapshot, boundary, now)), 72)
        snapshot["rates"] = values[:2] + values[3:]
        self.assertEqual(len(parse_context(snapshot, boundary, now)), 2)
        with self.assertRaises(ValueError):
            parse_context(snapshot, boundary, now + timedelta(hours=7))

    def test_html(self):
        """Rows are visibly predictions, escaped, and not labelled as commands."""
        value = dict(rows(count=1)[0], start="<test>", band="high")
        html = context_html([value], "Indicative")
        self.assertIn("not scheduled", html)
        self.assertIn("&lt;test&gt;", html)
        self.assertNotIn("Force Chg", html)

    def test_partial_first_slot(self):
        """A calculation at :20 can use the last ten minutes of a forecast slot."""
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        snapshot = dict(issued_at=now.isoformat(), rates=[dict(start=(now + timedelta(days=1)).isoformat(), end=(now + timedelta(days=1, minutes=30)).isoformat(), **{"import": 20}, export=16, band="medium")])
        result = parse_context(snapshot, now + timedelta(days=1, minutes=20), now)
        self.assertEqual(result[0]["minutes"], 10)

    def test_proxy_mapping(self):
        """Learn separate import/export offsets without treating Agile as Optimise."""
        start = datetime(2026, 9, 13, tzinfo=timezone.utc)
        supplier, proxy = [], []
        for index in range(16):
            instant = start + timedelta(minutes=index * 30)
            supplier.append(dict(start=instant.isoformat(), **{"import": index + 5}, export=index + 1))
            proxy.append(dict(date_time=instant.astimezone(timezone(timedelta(hours=1))).isoformat(), agile_pred=index + 10))
        mapped = map_proxy(dict(created_at=start.isoformat(), prices=proxy), supplier)
        self.assertEqual(mapped["rates"][0]["import"], 5)
        self.assertEqual(mapped["rates"][0]["export"], 1)
        with self.assertRaises(ValueError):
            map_proxy(dict(created_at=start.isoformat(), prices=proxy), supplier[:5])


if __name__ == "__main__":
    unittest.main()
