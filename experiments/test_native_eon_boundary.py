"""Verify native PR sensor output respects the deployed custom planning boundary."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from eon_optimise import EonOptimiseAPI
from fetch import Fetch
from plan import Plan
from tests import test_optimise_horizon as horizon_tests


class NativeBoundaryTests(unittest.TestCase):
    """Connect native published prices to the existing custom boundary policy."""

    def fixture(self, export_gap=False):
        """Build native sensors and the actual deployed rate replication inputs."""
        now = datetime(2026, 9, 21, 8, tzinfo=timezone.utc)
        base = MagicMock()
        base.prefix = "predbat"
        api = EonOptimiseAPI(base, enabled=True, email="test@example.invalid", password="test")
        api.fetched_at = now
        for channel in ("import", "export"):
            api.rates[channel] = [
                {
                    "valid_from": (now + timedelta(minutes=30 * i)).isoformat(),
                    "valid_to": (now + timedelta(minutes=30 * (i + 1))).isoformat(),
                    "value_inc_vat": 20 if channel == "import" else 10,
                    "source_quality": "current" if i == 0 else "forecast",
                }
                for i in range(96)
                if not (export_gap and channel == "export" and i == 3)
            ]
        self.assertTrue(api.publish(now))
        sensors = {call.args[0]: call.args[2] for call in base.dashboard_item.call_args_list}
        p = horizon_tests.OptimiseHorizonTests().subject()
        p.forecast_minutes = 2880
        p.midnight_utc = now.replace(hour=0)
        args = {"optimise_context_enable": True, "metric_octopus_import": api.entity("import_rates"), "metric_octopus_export": api.entity("export_rates")}
        p.get_arg = lambda key, default=None, **kwargs: args.get(key, default)
        p.get_state_wrapper = lambda entity, attribute, default=None: sensors[entity].get(attribute, default)
        for channel in ("import", "export"):
            rates = {minute: 20 if channel == "import" else 10 for minute in range(480, 3360)}
            rates, quality = Fetch.rate_replicate(p, rates, is_import=channel == "import")
            setattr(p, "rate_" + channel, rates)
            setattr(p, "rate_" + channel + "_replicated", quality)
        return p

    def test_native_feed_keeps_twenty_four_hour_control_boundary(self):
        """A longer native forecast cannot extend the executable window past one day."""
        p = self.fixture()
        self.assertTrue(Plan.apply_optimise_price_boundary(p))
        self.assertEqual(p.forecast_minutes, 1440)
        self.assertEqual(p.optimise_price_boundary, p.minutes_now + 1440)

    def test_native_export_gap_still_shortens_control_window(self):
        """A missing native export interval cannot be concealed by later prices."""
        p = self.fixture(export_gap=True)
        Plan.apply_optimise_price_boundary(p)
        self.assertEqual(p.forecast_minutes, 90)
