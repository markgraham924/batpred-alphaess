"""Integration regressions for the deployed fork on the current upstream interfaces."""

import sys
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "apps/predbat"))
import predbat  # noqa: F401
from const import EXPORT_MODE_FREEZE, EXPORT_MODE_TARGET
from ev_window import fixed_car_plan
from output import alphaess_plan_limits, alphaess_plan_mode
from tests.test_plan_why_reason import _setup_baseline
from unit_test import create_predbat
from utils import pack_export_limit


class PreservationTests(unittest.TestCase):
    """Exercise real publication, horizon scans and manual EV planning without HA controls."""

    def test_named_export_limits_keep_alphaess_columns(self):
        """Both current tuple modes retain physical-policy columns and car/towel columns."""
        for mode, target, rate, expected in [
            (EXPORT_MODE_TARGET, 5, 20, "Force Exp"),
            (EXPORT_MODE_FREEZE, 0, 20, "Mode 19"),
            (EXPORT_MODE_FREEZE, 0, -1, "Normal"),
            (EXPORT_MODE_TARGET, 99, 20, "Force Exp"),
        ]:
            p = create_predbat()
            pv, load = _setup_baseline(p)
            p.args.update(plan_alphaess_mode_column=True, plan_towel_schedule_column=True)
            p.charge_window_best, p.charge_limit_best = [], []
            p.export_window_best = [{"start": p.minutes_now, "end": p.minutes_now + 60, "average": rate}]
            p.export_limits_best = [pack_export_limit(mode, target)]
            p.rate_export = {m: rate for m in range(3000)}
            original_state = p.get_state_wrapper
            p.get_state_wrapper = lambda entity_id=None, **kw: {
                "sensor.alphaess_discharging_cutoff_soc": "6",
                "sensor.alphaess_charging_cutoff_soc": "100",
            }.get(entity_id, original_state(entity_id, **kw))
            p.run_prediction([], [], p.export_window_best, p.export_limits_best, False, end_record=p.end_record, save="best")
            html, raw = p.publish_html_plan(pv, pv, load, load, p.end_record, publish=False)
            self.assertIn("Charge limit %", html)
            self.assertIn("Towels", html)
            self.assertEqual(raw["rows"][0]["alphaess_mode"], expected)
            self.assertEqual(raw["rows"][0]["house_discharge_floor_percent"], 6)
            if mode == EXPORT_MODE_TARGET:
                self.assertEqual(raw["rows"][0]["forced_export_floor_percent"], max(9, target))

    def test_reward_scan_stays_inside_confirmed_horizon(self):
        """Real upstream scans preserve pre-event charging without unknown-tail prices."""
        p = create_predbat()
        p.minutes_now, p.forecast_minutes = 480, 240
        p.get_state_wrapper = lambda *a, **kw: "NEXT_OPTIMISE_APP"
        p.args.update(metric_octopus_import="sensor.rates", optimise_context_enable=False)
        imports = {m: (10 if m < 510 else 20) for m in range(480, 600)}
        exports = {m: 5 for m in range(480, 600)}
        p.rate_import_pre_saving = {m: 20 for m in range(540, 570)}
        p.rate_export_pre_saving = {m: 5 for m in range(540, 570)}
        imports.update({m: 120 for m in range(540, 570)})
        exports.update({m: 105 for m in range(540, 570)})
        imports.update({m: 999 for m in range(600, 720)})
        exports.update({m: 999 for m in range(600, 720)})
        p.rate_import, p.rate_export = imports, exports
        p.rate_import_saving_minutes = p.rate_export_saving_minutes = set(range(540, 570))
        p.rate_import_replicated = {m: "unknown" for m in range(600, 720)}
        p.rate_export_replicated = dict(p.rate_import_replicated)
        p.rate_import_base, p.rate_export_base = dict(imports), dict(exports)
        p.rate_low_threshold = p.rate_high_threshold = 0
        p.manual_all_times = []
        p.calc_pv_light_dark = lambda: {}
        self.assertTrue(p.apply_optimise_price_boundary())
        self.assertEqual(p.forecast_minutes, 120)
        self.assertIs(p.rate_import, imports)
        self.assertIs(p.rate_export, exports)
        self.assertLessEqual(p.rate_import_cost_threshold, 20)
        self.assertTrue(p.low_rates_tariff)
        self.assertTrue(all(w["end"] <= 600 for w in p.low_rates + p.low_rates_tariff + p.high_export_rates))
        self.assertTrue(all(not (w["start"] < 570 and w["end"] > 540) for w in p.low_rates))

    def test_expired_ev_override_stays_paused(self):
        """An armed completed manual window cannot fall through to automatic charging."""
        now = create_predbat().midnight_utc
        values = {"car_charging_override_enabled": "on", "car_charging_override_start": now.isoformat(), "car_charging_override_end": (now + timedelta(minutes=30)).isoformat()}
        p = SimpleNamespace(get_arg=lambda key, *a, **kw: values[key], midnight_utc=now, minutes_now=60, forecast_minutes=1440, car_charging_rate=[7.2], car_charging_loss=0.92, car_charging_limit=[64], car_charging_soc=[40])
        self.assertEqual(fixed_car_plan(p, 0), [])
        values["car_charging_override_enabled"] = "off"
        self.assertIsNone(fixed_car_plan(p, 0))

    def test_house_and_export_floors_are_independent(self):
        """Neither a grid charge target nor high SOC changes household/PV limits."""
        limits = alphaess_plan_limits("Force Chg", 60, None, 99, "6", "100")
        self.assertEqual(limits["grid_charge_target_percent"], 60)
        self.assertEqual(limits["pv_charge_cap_percent"], 100)
        self.assertEqual(limits["house_discharge_floor_percent"], 6)
        self.assertEqual(alphaess_plan_mode(False, False, False, False, 20)[0], "Normal")
        self.assertEqual(alphaess_plan_limits("Force Exp", None, 4, 80, "20")["forced_export_floor_percent"], 20)


if __name__ == "__main__":
    unittest.main()
