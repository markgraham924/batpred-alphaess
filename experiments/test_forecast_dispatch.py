"""Offline regression coverage for the extended battery simulation."""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/predbat"))
from forecast_dispatch import build_model, simulate, continuation_load


def row(price=25, export=0, load=0.5, pv=0, minutes=30):
    """Create a half-hour forecast without any external connections."""
    return dict(minutes=minutes, **{"import": price}, export=export, load=load, pv=pv)


class ForecastDispatchTests(unittest.TestCase):
    """Validate energy accounting, future value and limits across realistic tails."""

    def test_diverse_scenarios(self):
        """All futures conserve energy, respect limits and carry continuous costs."""
        cases = {
            "expensive": [row(price=72)] * 72,
            "cheap_then_peak": [row(price=8)] * 12 + [row(price=40, load=0.8)] * 60,
            "sunny": [row(pv=2)] * 20 + [row(load=0.8)] * 52,
            "export": [row(export=30, load=0.2)] * 72,
            "negative": [row(price=-5)] * 12 + [row()] * 60,
            "extra_demand": [row(load=1.3, pv=0.1)] * 72,
            "partial": [row(minutes=10, load=0.2)] + [row()] * 71,
        }
        for name, rows in cases.items():
            with self.subTest(name=name):
                model = build_model(rows, 0.96, 16)
                path = simulate(model, 6.5, 123)
                total, energy = 123, 6.5
                for item in path:
                    self.assertAlmostEqual(item["soc_start"] * 0.16, energy)
                    energy = item["soc_end"] * 0.16
                    self.assertGreaterEqual(energy + 1e-8, 0.96)
                    self.assertLessEqual(energy, 16 + 1e-8)
                    self.assertLessEqual(abs(item["battery_power_kw"]), 3.68 + 1e-8)
                    self.assertFalse(item["grid_import"] and item["grid_export"])
                    self.assertAlmostEqual(item["grid_import"] - item["grid_export"], item["load"] - item["pv_used"] + item["battery_power_kw"] * item["minutes"] / 60)
                    self.assertLessEqual(item["grid_export"], 3.68 * item["minutes"] / 60 + 1e-8)
                    self.assertAlmostEqual(item["total_p"], total)
                    total += item["cost_p"]
                    self.assertTrue(item["forecast_only"])

    def test_future_prices_influence_near_term_value(self):
        """An expensive continuation values carried energy more than a cheap refill."""
        expensive = build_model([row(price=40)] * 48, 0.96, 16)
        cheap = build_model([row(price=5)] * 12 + [row(price=40)] * 36, 0.96, 16)
        self.assertGreater(expensive["curve"][16], cheap["curve"][16])
        path = simulate(cheap, 0.96)
        self.assertGreater(path[11]["soc_end"], path[0]["soc_start"])

    def test_solar_and_extra_load(self):
        """Solar reduces carry value; extra consumption increases it."""
        sunny = build_model([row(pv=2)] * 12 + [row()] * 36, 0.96, 16)
        poor = build_model([row(pv=0.1, load=0.8)] * 12 + [row(load=0.8)] * 36, 0.96, 16)
        self.assertGreater(poor["curve"][16], sunny["curve"][16])

    def test_daily_load_wrap_keeps_dated_extras(self):
        """A 60-hour view must not turn later house demand into zero or repeat EV extras."""
        p = SimpleNamespace(minutes_now=615, load_minutes={}, load_forecast={1: 1}, manual_load_adjust={}, plan_interval_minutes=30, load_scaling=1, load_inday_adjustment=1, load_scaling_dynamic={}, dynamic_load_baseline={})
        p.get_filtered_load_minute = lambda data, minute, **kwargs: (0.04 if minute == 5 else 0.03, 0)
        p.get_from_incrementing = lambda data, minute, **kwargs: 0.01 if 620 <= minute < 625 else 0
        p.inday_adjustment_at = lambda minute, scale: scale
        self.assertAlmostEqual(continuation_load(p, 5), 0.09)
        self.assertAlmostEqual(continuation_load(p, 1445), 0.04)
        self.assertAlmostEqual(continuation_load(p, 2885), 0.04)

    def test_invalid_data(self):
        """No NaN rates, impossible batteries or out-of-bounds initial states."""
        with self.assertRaises(ValueError):
            build_model([row(price=float("nan"))], 0.96, 16)
        with self.assertRaises(ValueError):
            build_model([row()], 16, 16)
        with self.assertRaises(ValueError):
            simulate(build_model([row()], 0.96, 16), 0.5)

    def test_external_load_profile(self):
        """Use the external forecast first, then its last daily profile, not double load."""
        p = SimpleNamespace(
            minutes_now=600,
            load_forecast_only=True,
            load_forecast={m: m * 0.01 for m in range(3001)},
            manual_load_adjust={},
            plan_interval_minutes=30,
            load_scaling=1,
            load_inday_adjustment=1,
            inday_adjustment_at=lambda minute, scale: scale,
            load_scaling_dynamic={},
            dynamic_load_baseline={},
        )
        p.get_from_incrementing = lambda data, minute, **kwargs: data[minute + 1] - data[minute]
        self.assertAlmostEqual(continuation_load(p, 100), 0.05)
        self.assertAlmostEqual(continuation_load(p, 3000), 0.05)
        self.assertAlmostEqual(continuation_load(p, 5000), 0.05)

    def test_shared_inverter_and_export_cap(self):
        """Solar and battery cannot each claim the whole inverter output capacity."""
        model = build_model([row(export=100, pv=1.5, load=0.1)], 0.96, 16, inverter_kw=2, export_kw=0.5)
        item = simulate(model, 16)[0]
        self.assertLessEqual(item["grid_export"], 0.25 + 1e-8)
        self.assertGreaterEqual(item["pv_used"], 0)
        self.assertLessEqual(item["pv_used"] - item["battery_power_kw"] * 0.5, 1 + 1e-8)


if __name__ == "__main__":
    unittest.main()
