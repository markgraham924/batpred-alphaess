"""Regression checks for missing Optimise rates and UTC/BST coverage."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fetch import Fetch
from kraken import KrakenAPI


class OptimiseCoverageTests(unittest.TestCase):
    """Keep unconfirmed rates distinguishable from supplier prices."""

    def setUp(self):
        """Construct an isolated rate-replication consumer."""
        self.now = datetime(2026, 9, 11, tzinfo=timezone.utc)
        self.periods = [{"valid_from": self.now.isoformat(), "valid_to": (self.now + timedelta(minutes=30)).isoformat()}]
        self.subject = SimpleNamespace(
            midnight_utc=self.now,
            forecast_minutes=60,
            get_arg=lambda *a, **kw: "sensor.rates" if a[0].startswith("metric_octopus") else False,
            get_state_wrapper=lambda _, attribute, default: "E-TOU-NEXT_OPTIMISE-G" if attribute == "tariff_code" else self.periods,
        )

    def test_only_confirmed_minutes_keep_original_rates(self):
        """Do not copy yesterday into a missing future period."""
        rates, quality = Fetch.rate_replicate(self.subject, {-1440: 8, **{m: 32 for m in range(30)}})
        self.assertEqual(32, rates[0])
        self.assertNotIn(0, quality)
        self.assertEqual(26.38, rates[30])
        self.assertEqual("unknown", quality[30])
        self.assertEqual(26.38, rates[1440])

    def test_unconfirmed_export_is_zero(self):
        """Missing export prices cannot create an arbitrage opportunity."""
        rates, quality = Fetch.rate_replicate(self.subject, {}, is_import=False)
        self.assertEqual(0, rates[60])
        self.assertEqual("unknown", quality[60])

    def test_old_periods_do_not_validate_current_rates(self):
        """An old nonempty response is not current coverage."""
        self.periods[0]["valid_from"] = "2026-09-09T00:00:00Z"
        self.periods[0]["valid_to"] = "2026-09-10T00:00:00Z"
        rates, quality = Fetch.rate_replicate(self.subject, {0: 8})
        self.assertEqual("unknown", quality[0])
        self.assertEqual(26.38, rates[0])

    def test_bst_timestamp_is_same_instant(self):
        """01:00 BST and midnight UTC must validate the same minute."""
        self.periods[0] = {"valid_from": "2026-09-11T01:00:00+01:00", "valid_to": "2026-09-11T01:30:00+01:00"}
        rates, quality = Fetch.rate_replicate(self.subject, {0: 18})
        self.assertEqual(18, rates[0])
        self.assertNotIn(0, quality)

    def test_coverage_stops_at_first_gap(self):
        """Far-future periods cannot conceal a gap in the usable horizon."""
        self.periods.append({"valid_from": "2026-09-11T02:00:00Z", "valid_to": "2026-09-11T03:00:00Z"})
        coverage = KrakenAPI.rate_coverage(self.periods, self.now)
        self.assertEqual("2026-09-11T00:30:00+00:00", coverage["confirmed_until"])
        self.assertTrue(coverage["current_rate_available"])

    def test_empty_coverage_is_explicit(self):
        """No prices never mean a healthy current rate."""
        self.assertFalse(KrakenAPI.rate_coverage([], self.now)["current_rate_available"])

    def test_non_optimise_repetition_unchanged(self):
        """Other tariffs retain their previous replication path."""
        self.subject.get_state_wrapper = lambda *a, **kw: "OTHER"
        self.subject.metric_future_rate_offset_import = 0
        self.subject.metric_future_rate_offset_export = 0
        self.subject.future_energy_rates_import = {}
        self.subject.future_energy_rates_export = {}
        rates, quality = Fetch.rate_replicate(self.subject, {0: 8})
        self.assertEqual(8, rates[1440])
        self.assertEqual("copy", quality[1440])


if __name__ == "__main__":
    unittest.main()
