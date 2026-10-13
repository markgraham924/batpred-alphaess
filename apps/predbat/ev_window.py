"""Explicit per-car windows shared by planning and recalculation checks."""
from datetime import datetime
import math


def override_state(base, car_n):
    """Read a stable fingerprint of the selected schedule, excluding live power."""
    return tuple(str(base.get_arg(key, "off" if key.endswith("enabled") else "", index=car_n)).lower()
                 for key in ("car_charging_override_enabled", "car_charging_override_start", "car_charging_override_end"))


def fixed_car_plan(base, car_n):
    """Return None for automatic selection, or the fixed (possibly empty) plan.

    An armed expired/invalid window remains paused until explicitly cancelled.
    Grid energy is bounded by rate, window duration and remaining vehicle target.
    Prices affect accounting only: they cannot move an explicit user window.
    """
    enabled, start_text, end_text = override_state(base, car_n)
    if enabled in ("off", "false", "no", "disabled", "0", ""):
        return None
    if enabled not in ("on", "true", "yes", "enabled", "1"):
        return []
    try:
        start = datetime.fromisoformat(start_text)
        end = datetime.fromisoformat(end_text)
        if start.tzinfo is None:
            start = start.replace(tzinfo=base.midnight_utc.tzinfo)
        if end.tzinfo is None:
            end = end.replace(tzinfo=base.midnight_utc.tzinfo)
        start = start.astimezone(base.midnight_utc.tzinfo)
        end = end.astimezone(base.midnight_utc.tzinfo)
        start_min = (start - base.midnight_utc).total_seconds() / 60
        end_min = (end - base.midnight_utc).total_seconds() / 60
        rate = float(base.car_charging_rate[car_n])
        loss = float(base.car_charging_loss)
        remaining = max(0.0, float(base.car_charging_limit[car_n]) - float(base.car_charging_soc[car_n]))
        if not all(math.isfinite(v) for v in (start_min, end_min, rate, loss, remaining)):
            return []
        if not 0 < end_min - start_min <= 1440 or rate <= 0 or not 0 < loss <= 1:
            return []
    except (ValueError, TypeError, AttributeError, IndexError):
        return []
    cursor = max(math.ceil(start_min), base.minutes_now)
    end_min = min(math.floor(end_min), base.minutes_now + base.forecast_minutes)
    plan = []
    while cursor < end_min and remaining > 0.001:
        stop = min(end_min, (math.floor(cursor / 30) + 1) * 30)
        kwh = min(rate * (stop - cursor) / 60, remaining / loss)
        stop = min(stop, math.ceil(cursor + kwh / rate * 60))
        price = base.rate_import.get(int(cursor), base.rate_min)
        plan.append({"start": cursor, "end": stop, "kwh": round(kwh, 3), "average": price,
                     "cost": round(price * kwh, 2), "octopus": False, "manual": True})
        remaining = max(0.0, remaining - kwh * loss)
        cursor = stop
    return plan
