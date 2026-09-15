"""Isolated tests of the real scheduling callback without starting HA or threads."""

import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import time
import traceback
import unittest


class SlotPlanningTests(unittest.TestCase):
    """Boundary execution must not depend on a new optimisation finishing."""

    def setUp(self):
        """Compile only the production scheduling methods into an isolated class."""
        tree = ast.parse((Path(__file__).parents[1] / "apps/predbat/predbat.py").read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "PredBat")
        methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in ("slot_plan_key", "run_time_loop")]
        module = ast.Module(body=[ast.ClassDef(name="Scheduler", bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
        scope = dict(time=time, traceback=traceback)
        exec(compile(ast.fix_missing_locations(module), "<actual scheduler>", "exec"), scope)
        self.scheduler = scope["Scheduler"]()
        p = self.scheduler
        p.ha_interface = SimpleNamespace(websocket_active=True, db_primary=False)
        p.check_entity_refresh = Mock()
        p.prediction_started = p.update_pending = False
        p.plan_valid = True
        p.num_cars = 0
        p.get_arg = lambda key, default=None, **kwargs: True if key == "slot_aligned_planning" else default
        p.update_time = Mock()
        p.now_utc_real = p.plan_last_updated = datetime.now(timezone.utc)
        p._last_slot_plan_key = p.slot_plan_key()
        p._slot_ev_state = ()
        p.charge_window_best = [{"start": 0, "end": 30}, {"start": 30, "end": 60}]
        p.charge_limit_best = [8, 10]
        p.export_window_best = []
        p.export_limits_best = []
        p.car_charging_slots = [[{"start": 0, "end": 30}, {"start": 30, "end": 60}]]
        p.minutes_now = 30
        p.control_ledger = SimpleNamespace(begin_cycle=Mock())
        p.fetch_inverter_data = Mock(return_value=True)
        p.execute_plan = Mock(return_value=("Demand", ""))
        p.record_final_run_status = Mock()
        p.update_pred = Mock()
        p.log = p.expose_config = p.record_status = Mock()

    def test_boundary_keys(self):
        """Only two routine calculation events per half-hour, including midnight."""
        for minute, expected in ((0, -2), (2, -2), (3, 3), (27, 3), (28, 28), (30, 28), (32, 28), (33, 33), (58, 58), (60, 58)):
            with patch.object(time, "time", return_value=minute * 60):
                self.assertEqual(self.scheduler.slot_plan_key(), expected)

    def test_retained_execution_prunes_expired_window(self):
        """Execute the new slot and publish status without rerunning the optimiser."""
        p = self.scheduler
        p.run_time_loop({})
        p.update_pred.assert_not_called()
        p.execute_plan.assert_called_once()
        p.control_ledger.begin_cycle.assert_called_once()
        p.record_final_run_status.assert_called_once_with("Demand", "")
        self.assertEqual(p.charge_window_best, [{"start": 30, "end": 60}])
        self.assertEqual(p.charge_limit_best, [10])
        self.assertEqual(p.car_charging_slots, [[{"start": 30, "end": 60}]])
        self.assertFalse(p.prediction_started)

    def test_new_event_replans(self):
        """The next event triggers one full calculation."""
        p = self.scheduler
        p._last_slot_plan_key -= 5
        p.run_time_loop({})
        p.update_pred.assert_called_once_with(scheduled=True)

    def test_midnight_rebases(self):
        """Do not execute yesterday's minute-indexed plan after midnight."""
        p = self.scheduler
        p.plan_last_updated -= timedelta(days=1)
        p.run_time_loop({})
        p.update_pred.assert_called_once()
        p.execute_plan.assert_not_called()

    def test_busy_does_not_overlap(self):
        """Never run two calculations or control checks concurrently."""
        p = self.scheduler
        p.prediction_started = True
        p.run_time_loop({})
        p.update_pred.assert_not_called()
        p.execute_plan.assert_not_called()

    def test_ev_change_replans(self):
        """A new car connection need not wait until the next scheduled calculation."""
        p = self.scheduler
        p.num_cars = 1
        p.run_time_loop({})
        p.update_pred.assert_called_once()


if __name__ == "__main__":
    unittest.main()
