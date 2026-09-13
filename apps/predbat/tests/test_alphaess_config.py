# -----------------------------------------------------------------------------
# Predbat Home Battery System
# Copyright Trefor Southwell 2026 - All Rights Reserved
# This application maybe used for personal use only and not for commercial use
# -----------------------------------------------------------------------------
# Test AlphaESS config and INVERTER_DEF registration
# -----------------------------------------------------------------------------

"""Tests for the AlphaESS component registration, INVERTER_DEF entry and APPS_SCHEMA keys."""

from datetime import UTC, datetime, timedelta

import predbat  # noqa: F401  (import first - avoids circular import: config.py does `from predbat import THIS_VERSION`)
from config import INVERTER_DEF, APPS_SCHEMA
from components import COMPONENT_LIST
from output import active_history_blocks, alphaess_plan_mode, slot_has_flagged_minute, status_has_ev_hold, towel_schedule_for_slot


def test_alphaess_component_registered():
    """The component is registered in phase 1 with its event filter and auth gate."""
    failed = False
    entry = COMPONENT_LIST.get("alphaess")
    if not entry:
        print("ERROR: alphaess not in COMPONENT_LIST")
        assert False, "test_alphaess_component_registered"
    if entry.get("event_filter") != "predbat_alphaess_":
        print(f"ERROR: event_filter {entry.get('event_filter')}")
        failed = True
    if entry.get("phase") != 1:
        print(f"ERROR: phase {entry.get('phase')}")
        failed = True
    if not entry.get("can_restart"):
        print("ERROR: alphaess should be restartable")
        failed = True
    # Without required_or the component would start for every Predbat instance, since all
    # individual args are optional.
    if entry.get("required_or") != ["app_id"]:
        print(f"ERROR: required_or {entry.get('required_or')}")
        failed = True
    for arg, config_key, default in [
        ("app_id", "alphaess_app_id", None),
        ("app_secret", "alphaess_app_secret", None),
        ("inverter_sn", "alphaess_inverter_sn", None),
        ("automatic", "alphaess_automatic", False),
        ("automatic_ignore_pv", "alphaess_automatic_ignore_pv", False),
        ("control_enable", "alphaess_control_enable", True),
        ("battery_rate_max", "alphaess_battery_rate_max", None),
        ("api_delay", "alphaess_api_delay", 2),
        ("min_write_interval", "alphaess_min_write_interval", 300),
    ]:
        info = entry["args"].get(arg)
        if not info:
            print(f"ERROR: arg {arg} missing")
            failed = True
            continue
        if info.get("config") != config_key:
            print(f"ERROR: arg {arg} config {info.get('config')} != {config_key}")
            failed = True
        if default is not None and info.get("default") != default:
            print(f"ERROR: arg {arg} default {info.get('default')} != {default}")
            failed = True
    assert not failed, "test_alphaess_component_registered"


def test_alphaess_control_enable_defaults_true():
    """An inverter component that does not drive the inverter is not what a user expects."""
    failed = False
    info = COMPONENT_LIST["alphaess"]["args"]["control_enable"]
    if info.get("default") is not True:
        print(f"ERROR: control_enable default {info.get('default')} should be True")
        failed = True
    assert not failed, "test_alphaess_control_enable_defaults_true"


def test_alphaess_inverter_def_complete():
    """AlphaESSCloud declares every key the other cloud inverter types declare."""
    failed = False
    entry = INVERTER_DEF.get("AlphaESSCloud")
    if not entry:
        print("ERROR: AlphaESSCloud not in INVERTER_DEF")
        assert False, "test_alphaess_inverter_def_complete"
    # Keys inverter.py reads through .get() with a default are opt-in capabilities a type is meant
    # to omit - AlphaESS's Freeze Export holds SoC via the rate entities rather than switching to a
    # feed-in work mode, so it must NOT declare support_feedin_first.
    optional_keys = {"support_feedin_first"}
    reference = set(INVERTER_DEF["SunsynkCloud"].keys()) - optional_keys
    missing = reference - set(entry.keys())
    if missing:
        print(f"ERROR: AlphaESSCloud missing keys {sorted(missing)}")
        failed = True
    expected = {
        "has_rest_api": False,
        "has_mqtt_api": False,
        "output_charge_control": "power",
        "has_charge_enable_time": True,
        "has_discharge_enable_time": True,
        "has_target_soc": True,
        "has_reserve_soc": True,
        # No pause endpoint exists, so Predbat expresses freeze through the rate entities.
        "has_timed_pause": False,
        # Anything else makes inverter.py replace the published select entities with its
        # own dummies and the window never reaches the component.
        "charge_time_format": "HH:MM:SS",
        "soc_units": "%",
        "time_button_press": True,
        "support_charge_freeze": True,
        "support_discharge_freeze": True,
        # Wrap-around behaviour is undocumented for timeChaf1/timeChae1, so Predbat splits.
        "can_span_midnight": False,
        "target_soc_used_for_discharge": True,
    }
    for key, value in expected.items():
        if entry.get(key) != value:
            print(f"ERROR: AlphaESSCloud[{key}] = {entry.get(key)} != {value}")
            failed = True
    assert not failed, "test_alphaess_inverter_def_complete"


def test_alphaess_controller_inverter_def():
    """The guarded Home Assistant service profile encodes Mode 19 semantics."""
    entry = INVERTER_DEF.get("AlphaESSController")
    assert entry, "AlphaESSController not in INVERTER_DEF"
    expected = {
        "output_charge_control": "none",
        "charge_control_immediate": True,
        "has_charge_enable_time": False,
        "has_discharge_enable_time": False,
        "has_target_soc": False,
        "support_charge_freeze": False,
        "support_discharge_freeze": True,
        "target_soc_used_for_discharge": True,
    }
    for key, value in expected.items():
        assert entry.get(key) == value, "AlphaESSController[{}] = {} != {}".format(key, entry.get(key), value)


def test_alphaess_apps_schema_keys():
    """Every alphaess_* key a user may set is declared with the right type."""
    failed = False
    expected = {
        "alphaess_app_id": "string",
        "alphaess_app_secret": "string",
        "alphaess_inverter_sn": "string|string_list",
        "alphaess_automatic": "boolean",
        "alphaess_automatic_ignore_pv": "boolean",
        "alphaess_control_enable": "boolean",
        "alphaess_battery_rate_max": "float",
        "alphaess_api_delay": "float",
        "alphaess_min_write_interval": "integer",
        "plan_alphaess_mode_column": "boolean",
        "plan_towel_schedule_column": "boolean",
        "plan_alphaess_high_soc_enter": "float",
        "plan_alphaess_high_soc_exit": "float",
    }
    for key, kind in expected.items():
        entry = APPS_SCHEMA.get(key)
        if not entry:
            print(f"ERROR: APPS_SCHEMA missing {key}")
            failed = True
            continue
        if entry.get("type") != kind:
            print(f"ERROR: APPS_SCHEMA[{key}] type {entry.get('type')} != {kind}")
            failed = True
    assert not failed, "test_alphaess_apps_schema_keys"


def test_alphaess_plan_mode_mapping():
    """Plan labels follow controller priority and high-SoC hysteresis."""
    cases = [
        # charge, car, force export, freeze export, SoC, previous high-SoC, label, resulting high-SoC
        (True, True, True, True, 100, False, "Force Chg", True),
        (False, True, True, True, 80, False, "EV Hold", False),
        (False, False, True, True, 80, False, "Force Exp", False),
        (False, False, False, True, 80, False, "Mode 19", False),
        (False, False, False, False, 95, False, "Mode 19", True),
        (False, False, False, False, 94, True, "Mode 19", True),
        (False, False, False, False, 92, True, "Normal", False),
    ]
    for charge, car, force_export, freeze_export, soc, prior_high_soc, expected_mode, expected_high_soc in cases:
        mode, _title, _color, high_soc = alphaess_plan_mode(
            charge,
            car,
            force_export,
            freeze_export,
            soc,
            prior_high_soc,
        )
        assert mode == expected_mode
        assert high_soc is expected_high_soc


def test_towel_schedule_plan_column_mapping():
    """Scheduled towel blocks map only to overlapping Predbat rows."""
    start = datetime(2026, 8, 31, 1, 0, tzinfo=UTC)
    schedules = [
        (
            "Front",
            [
                {
                    "start": start.isoformat(),
                    "end": (start + timedelta(minutes=30)).isoformat(),
                    "effective_rate_pence": 8,
                    "reason": "grid import",
                }
            ],
        ),
        ("Rear", []),
    ]
    label, title, color = towel_schedule_for_slot(start, start + timedelta(minutes=30), schedules)
    assert label == "Front"
    assert "8p/kWh" in title
    assert "grid import" in title
    assert color == "#D8B4FE"

    label, _title, color = towel_schedule_for_slot(start + timedelta(minutes=30), start + timedelta(minutes=60), schedules)
    assert label == ""
    assert color == "#FFFFFF"


def test_actual_towel_history_mapping():
    """Recorded radiator transitions remain visible after the live schedule clears."""
    start = datetime(2026, 9, 3, 0, 0, tzinfo=UTC)
    records = [
        {"state": "off", "last_updated": (start - timedelta(hours=1)).isoformat()},
        {"state": "on", "last_updated": (start + timedelta(hours=1, minutes=30)).isoformat()},
        {"state": "off", "last_updated": (start + timedelta(hours=6)).isoformat()},
    ]
    blocks = active_history_blocks(records, start, start + timedelta(days=1))
    assert blocks == [
        {
            "start": (start + timedelta(hours=1, minutes=30)).isoformat(),
            "end": (start + timedelta(hours=6)).isoformat(),
            "reason": "recorded actual run",
            "actual": True,
        }
    ]
    label, title, color = towel_schedule_for_slot(start + timedelta(hours=2), start + timedelta(hours=2, minutes=30), [("Rear", blocks)])
    assert label == "Rear"
    assert "recorded actual run" in title
    assert color == "#D8B4FE"


def test_actual_ev_hold_history_mapping():
    """Historical car energy alone does not imply that battery hold was active."""
    assert status_has_ev_hold("Hold charging, Hold for car")
    assert not status_has_ev_hold("Charging")
    assert not status_has_ev_hold("Demand")
    flagged = set(range(60, 90))
    assert slot_has_flagged_minute(60, 90, flagged)
    assert not slot_has_flagged_minute(90, 120, flagged)


def run_alphaess_config_tests(my_predbat):
    """Run all AlphaESS config/INVERTER_DEF tests."""
    failed = False
    for name, fn in [
        ("component_registered", test_alphaess_component_registered),
        ("control_enable_default", test_alphaess_control_enable_defaults_true),
        ("inverter_def", test_alphaess_inverter_def_complete),
        ("apps_schema", test_alphaess_apps_schema_keys),
        ("plan_mode_mapping", test_alphaess_plan_mode_mapping),
        ("towel_schedule_column", test_towel_schedule_plan_column_mapping),
        ("towel_actual_history", test_actual_towel_history_mapping),
        ("ev_hold_actual_history", test_actual_ev_hold_history_mapping),
    ]:
        try:
            if fn():
                print(f"  FAILED: alphaess_config.{name}")
                failed = True
        except Exception as e:
            print(f"  EXCEPTION in alphaess_config.{name}: {e}")
            import traceback

            traceback.print_exc()
            failed = True
    return failed
