"""Contract regressions for the portable local controller configuration."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import yaml

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "apps/predbat"))
from unit_test import create_predbat
from inverter import Inverter
from web import WebInterface


class AlphaESSLocalTests(unittest.TestCase):
    """Exercise actual inverter mapping with a different battery and power rating."""

    def setUp(self):
        """Use the shipped template and actual Predbat argument resolution."""
        self.p = create_predbat()
        self.p.args = yaml.safe_load((ROOT / "templates/alphaess_local.yaml").read_text(encoding="utf-8-sig"))["pred_bat"]
        self.ha = self.p.ha_interface
        self.ha.dummy_items.update(
            {
                "sensor.alphaess_battery_soc": 55,
                "sensor.alphaess_battery_capacity": 10.1,
                "sensor.alphaess_native_reserve": 12,
                "sensor.alphaess_effective_export_floor": 17,
                "sensor.alphaess_max_power": 5000,
                "sensor.alphaess_max_charge_power": 3000,
                "sensor.alphaess_max_discharge_power": 5000,
                "sensor.alphaess_battery_power": 800,
                "sensor.alphaess_grid_power": -400,
                "sensor.alphaess_pv_power": 1200,
                "sensor.alphaess_load_power": 1600,
            }
        )
        self.inv = Inverter(self.p, 0, quiet=True)
        self.inv.update_status(self.p.minutes_now, quiet=True)
        self.ha.service_store_enable = True
        self.ha.get_service_store()
        self.p.last_service_hash = {}
        self.p.args["charge_end_time"] = ["23:55:00"]
        self.p.args["discharge_end_time"] = ["22:30:00"]

    def test_numeric_sensor_settings_and_signs(self):
        """Capacity, native reserve and unequal power limits come from the device."""
        self.assertAlmostEqual(self.inv.soc_max, 10.1)
        self.assertEqual(self.inv.reserve_percent, 17)
        self.assertAlmostEqual(self.inv.battery_rate_max_charge * 60000, 3000)
        self.assertAlmostEqual(self.inv.battery_rate_max_discharge * 60000, 5000)
        self.assertEqual(self.inv.battery_power, 800)
        self.assertEqual(self.inv.grid_power, 400)

    def test_grid_sign_through_dashboard(self):
        """Actual inverter and aggregate publication label import and export correctly."""
        self.p.inverters = [self.inv]
        self.p.dashboard_index = ["test"]
        web = SimpleNamespace(base=self.p)
        for sensor_power, expected_power, icon in [(1200, -1200, "transmission-tower-import"), (-1800, 1800, "transmission-tower-export")]:
            with self.subTest(sensor_power=sensor_power):
                self.ha.dummy_items["sensor.alphaess_grid_power"] = sensor_power
                self.p.fetch_inverter_data(quick=True)
                self.assertEqual(self.p.grid_power, expected_power)
                self.p.publish_inverter_data()
                self.assertEqual(self.ha.get_state("predbat.grid_power"), expected_power / 1000)
                self.assertIn(icon, WebInterface.get_grid_power_icon(web))

    def test_charge_export_and_freeze_payloads(self):
        """Real semantic calls preserve requested rates and window end times."""
        self.p.args["charge_rate"] = [1400]
        self.p.args["discharge_rate"] = [1700]
        self.inv.adjust_charge_immediate(85)
        calls = self.ha.get_service_store()
        self.assertEqual(calls[-1], ["alphaess_local/charge_start", {"power": "1400", "target_soc": "85", "end_time": "23:55:00"}])
        self.inv.adjust_export_immediate(20)
        calls = self.ha.get_service_store()
        self.assertEqual(calls[-1], ["alphaess_local/discharge_start", {"power": "1700", "target_soc": "20", "end_time": "22:30:00"}])
        self.inv.adjust_export_immediate(100, freeze=True)
        self.assertEqual(self.ha.get_service_store()[-1], ["alphaess_local/mode19_start", {"target_soc": "100", "end_time": "22:30:00"}])

    def test_repeated_stops_are_delivered(self):
        """A repeated stop stays deliverable after external changes or reconnects."""
        for _ in range(2):
            self.inv.adjust_charge_immediate(0)
            self.inv.adjust_export_immediate(100)
            self.assertEqual(self.ha.get_service_store(), [["alphaess_local/charge_stop", {}], ["alphaess_local/discharge_stop", {}]])


if __name__ == "__main__":
    unittest.main()
