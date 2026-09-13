"""Published-price horizon and terminal reserve regressions."""
import unittest
from types import SimpleNamespace
from plan import Plan


class OptimiseHorizonTests(unittest.TestCase):
    """Exercise real planner entry policy and metric with isolated fixtures."""

    def subject(self, boundary=600, tariff="NEXT_OPTIMISE_APP"):
        """Create a non-midnight fixture with unknown tail prices."""
        p = SimpleNamespace(
            minutes_now=480,
            forecast_minutes=240,
            soc_max=15.6,
            reserve=0.624,
            best_soc_keep=0,
            plan_valid=True,
            rate_import={m: 10 if m < boundary else 26.38 for m in range(480, 720)},
            rate_export={m: 5 if m < boundary else 0 for m in range(480, 720)},
            rate_import_replicated={m: "unknown" for m in range(boundary, 720)},
            rate_export_replicated={},
            rate_import_cost_threshold=20,
            rate_export_cost_threshold=0,
            get_arg=lambda *a, **kw: "sensor.rates",
            get_state_wrapper=lambda *a, **kw: tariff,
            record_status=lambda *a, **kw: None,
            log=lambda *a: None,
            time_abs_str=str,
            calc_pv_light_dark=lambda: {},
            set_rate_thresholds=lambda: None,
        )
        p.rate_scan = lambda r, **kw: (setattr(p, "rate_min", min(r.values())), setattr(p, "rate_max", max(r.values())))
        p.rate_scan_export = lambda r, **kw: setattr(p, "scanned_exports", r)
        p.rate_scan_window = lambda r, *a, **kw: ([{"start": 480, "end": 800, "average": 10}], 0, 10)
        return p

    def test_contiguous_horizon_and_windows(self):
        """Only priced minutes influence scans or scheduled windows."""
        p = self.subject()
        self.assertTrue(Plan.apply_optimise_price_boundary(p))
        self.assertEqual(p.forecast_minutes, 120)
        self.assertEqual(p.rate_max, 10)
        self.assertEqual(p.low_rates[0]["end"], 600)
        self.assertAlmostEqual(p.optimise_terminal_reserve, 3.12)
        self.assertEqual(Plan.record_length(p, [], [], 0), 120)

    def test_export_gap_also_limits(self):
        """Import coverage cannot conceal missing export prices."""
        p = self.subject()
        p.rate_export_replicated[510] = "unknown"
        Plan.apply_optimise_price_boundary(p)
        self.assertEqual(p.forecast_minutes, 30)

    def test_missing_current_prices_fail_closed(self):
        """No simulation against a fabricated current tariff."""
        p = self.subject(480)
        with self.assertRaises(ValueError):
            Plan.apply_optimise_price_boundary(p)
        self.assertFalse(p.plan_valid)

    def test_higher_existing_reserve_respected(self):
        """The terminal target never lowers the configured reserve."""
        p = self.subject()
        p.best_soc_keep = 4
        Plan.apply_optimise_price_boundary(p)
        self.assertEqual(p.optimise_terminal_reserve, 4)

    def test_other_tariffs_unchanged(self):
        """Ordinary tariffs keep their configured horizon."""
        p = self.subject(tariff="OTHER")
        self.assertFalse(Plan.apply_optimise_price_boundary(p))
        self.assertEqual(p.forecast_minutes, 240)
        self.assertTrue(p.plan_valid)

    def test_new_prices_extend_horizon(self):
        """A fresh fetch may extend, rather than permanently shorten, the plan."""
        p = self.subject()
        Plan.apply_optimise_price_boundary(p)
        p.forecast_minutes = 240
        p.rate_import_replicated = {m: "unknown" for m in range(660, 720)}
        Plan.apply_optimise_price_boundary(p)
        self.assertEqual(p.forecast_minutes, 180)

    def metric(self, soc, value=900):
        """Score a candidate independent of placeholder terminal energy value."""
        p = SimpleNamespace(
            minutes_now=480,
            battery_value_rate=lambda m: value,
            metric_battery_value_scaling=1,
            iboost_value_scaling=1,
            optimise_price_boundary=600,
            optimise_terminal_reserve=3.12,
            rate_max=20,
            pv_metric10_weight=0.2,
            pv_metric90_weight=0.2,
            carbon_enable=False,
            metric_self_sufficiency=0,
            metric_battery_cycle=0,
        )
        return Plan.compute_metric(p, 120, soc, soc, 10, 10, 0, 0, 0, 0, 0, 0, 0, 0, soc90=soc, cost90=10)

    def test_no_reward_for_surplus_end_charge(self):
        """Filling past the target gets no invented future profit."""
        self.assertEqual(self.metric(3.12)[0], self.metric(15.6)[0])
        self.assertEqual(self.metric(3.12)[0], 10)

    def test_depletion_penalised(self):
        """A depleted boundary is worse than meeting the reserve target."""
        self.assertGreater(self.metric(0.624)[0], self.metric(3.12)[0])

    def test_placeholder_value_cannot_change_ranking(self):
        """Unknown tail values cannot incentivise earlier charging."""
        self.assertEqual(self.metric(4, value=1), self.metric(4, value=900))


if __name__ == "__main__":
    unittest.main()
