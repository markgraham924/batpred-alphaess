"""Terminal battery target must not weaken physical constraints."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "apps/predbat"))
from forecast_dispatch import build_model, simulate


class TerminalTargetTests(unittest.TestCase):
    """Exercise attainable, expensive and impossible target scenarios."""

    def test_attainable_target(self):
        """Reach at least 50% even with profitable exports near the end."""
        rows = [dict(minutes=30, load=0.4, pv=0, **{"import": 18 if i < 8 else 35, "export": 30}) for i in range(24)]
        model = build_model(rows, 0.96, 16, terminal_soc=50)
        for initial in (0.96, 8, 16):
            path = simulate(model, initial)
            self.assertGreaterEqual(path[-1]["soc_end"], 50 - 1e-6)
            self.assertTrue(all(abs(row["battery_power_kw"]) <= 3.68 + 1e-8 for row in path))

    def test_unreachable_target_respects_power(self):
        """A short horizon cannot force physically impossible charging."""
        row = dict(minutes=5, load=0, pv=0, **{"import": 20, "export": 0})
        path = simulate(build_model([row], 0.96, 16, terminal_soc=50), 0.96)
        self.assertLess(path[-1]["soc_end"], 50)
        self.assertLessEqual(path[-1]["battery_power_kw"], 3.68 + 1e-8)

    def test_default_unchanged(self):
        """The new terminal preference is opt-in."""
        rows = [dict(minutes=30, load=0.4, pv=0, **{"import": 25, "export": 20})] * 24
        a, b = build_model(rows, 0.96, 16), build_model(rows, 0.96, 16, terminal_soc=0)
        self.assertEqual(a["costs"], b["costs"])
        for target in (-1, 101, float("nan")):
            with self.assertRaises(ValueError):
                build_model(rows, 0.96, 16, terminal_soc=target)


if __name__ == "__main__":
    unittest.main()
