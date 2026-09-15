"""Seven-day continuation coverage, solar provenance and physical limits."""

import sys
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/predbat"))
from price_context import prepare_context, parse_context
from forecast_dispatch import simulate


class SevenDayTests(unittest.TestCase):
    """Exercise the full six-day tail independently of HA and inverter services."""

    def fixture(self):
        """Supply eight days of rates and seven calendar days of solar."""
        now = datetime(2026, 9, 15, 10, 15, tzinfo=timezone.utc)
        midnight = now.replace(hour=0, minute=0)
        rates = [dict(start=(midnight + timedelta(minutes=30 * i)).isoformat(), end=(midnight + timedelta(minutes=30 * (i + 1))).isoformat(), **{"import": 10 if i % 48 < 12 else 30}, export=20, band="medium") for i in range(384)]
        snapshot = dict(issued_at=now.isoformat(), rates=rates)
        solar = [dict(period_start=(midnight + timedelta(minutes=30 * i)).isoformat(), pv_estimate=2 if 18 <= i % 48 <= 30 else 0) for i in range(336)]
        args = {"optimise_context_source": "price", "optimise_context_pv_sources": ["solar"], "optimise_context_terminal_soc": 50}
        p = SimpleNamespace(
            forecast_minutes=1440,
            minutes_now=615,
            midnight_utc=midnight,
            now_utc_real=now,
            optimise_price_boundary=2055,
            get_arg=lambda key, default=None, **kw: args.get(key, default),
            get_state_wrapper=lambda entity, **kw: snapshot if entity == "price" else solar,
            pv_forecast_minute={i: 0.01 for i in range(5760)},
            inverter_loss=0.95,
            battery_loss=0.95,
            battery_loss_discharge=0.95,
            reserve=0.96,
            soc_max=16,
            battery_rate_max_charge=3.68 / 60,
            battery_rate_max_discharge=3.68 / 60,
            inverter_limit=3.68 / 60,
            export_limit=3.68 / 60,
            metric_battery_cycle=0.5,
            log=lambda *a: None,
        )
        return p, snapshot, solar

    def test_full_week_and_limits(self):
        """Reach exactly 168h including first 24h, retain reserve and power caps."""
        p, _, _ = self.fixture()
        with patch("forecast_dispatch.continuation_load", return_value=0.05):
            self.assertIsNotNone(prepare_context(p))
        rows = p._price_context_model["rows"]
        self.assertEqual(sum(r["minutes"] for r in rows), 8640)
        self.assertEqual(rows[-1]["end"], p.now_utc_real + timedelta(days=7))
        self.assertEqual(p.forecast_minutes, 1440)
        self.assertAlmostEqual(rows[0]["pv"], 15 * 0.01 * 0.95)
        self.assertGreater(sum(r["pv"] for r in rows if r["start"].day >= 19), 0)
        self.assertEqual(sum(r["pv_assumed_zero_minutes"] for r in rows), 615)
        self.assertIn("10.2 hours", p.price_context_status)
        result = simulate(p._price_context_model, 8)
        self.assertGreaterEqual(result[-1]["soc_end"], 50)
        self.assertTrue(all(6 - 1e-7 <= r["soc_end"] <= 100 for r in result))
        self.assertTrue(all(abs(r["battery_power_kw"]) <= 3.68 + 1e-7 for r in result))

    def test_gap_and_short_feed_are_not_filled(self):
        """A requested week never turns a price gap into invented prices."""
        p, snapshot, _ = self.fixture()
        boundary = p.now_utc_real + timedelta(days=1)
        snapshot["rates"] = snapshot["rates"][:100]
        rows = parse_context(snapshot, boundary, p.now_utc_real)
        self.assertLess(sum(r["minutes"] for r in rows), 8640)
        snapshot["rates"].pop(75)
        rows = parse_context(snapshot, boundary, p.now_utc_real)
        self.assertEqual(rows[-1]["end"], p.midnight_utc + timedelta(minutes=75 * 30))

    def test_invalid_solar_fails_closed(self):
        """A nonfinite solar estimate must not influence stored energy value."""
        p, _, solar = self.fixture()
        solar[0]["pv_estimate"] = float("nan")
        with patch("forecast_dispatch.continuation_load", return_value=0.05):
            self.assertIsNone(prepare_context(p))
        self.assertEqual(p.forecast_minutes, 1440)


if __name__ == "__main__":
    unittest.main()
