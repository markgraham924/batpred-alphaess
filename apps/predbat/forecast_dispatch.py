"""Bounded forecast dispatch simulation; deliberately has no control or network API."""

import math


def interpolate(costs, energy, reserve, capacity):
    """Interpolate the finite battery-state grid without extrapolation."""
    position = min(32.0, max(0.0, (energy - reserve) / (capacity - reserve) * 32))
    index = min(31, int(position))
    return costs[index] + (costs[index + 1] - costs[index]) * (position - index)


def options(row, initial, reserve, capacity, charge_kw, discharge_kw, efficiency, wear, inverter_kw, export_kw):
    """Generate bounded battery transfers and their metered energy cost."""
    duration = row["minutes"] / 60
    pv_used = min(row["pv"], inverter_kw * duration)
    net_load = row["load"] - pv_used
    maximum = min(capacity, initial + min(charge_kw, inverter_kw) * duration * efficiency)
    discharge_room = max(0, min(inverter_kw * duration - pv_used, export_kw * duration + row["load"] - pv_used))
    minimum = max(reserve, initial - min(discharge_kw * duration, discharge_room) / efficiency)
    natural = initial - (net_load / efficiency if net_load >= 0 else net_load * efficiency)
    natural = min(maximum, max(minimum, natural))
    # Try natural self-consumption first, so equal-cost alternatives avoid forced modes.
    choices = [natural, initial, maximum, minimum] + [reserve + (capacity - reserve) * i / 32 for i in range(33)]
    for final in choices:
        if not minimum - 1e-9 <= final <= maximum + 1e-9:
            continue
        change = final - initial
        battery_ac = change / efficiency if change >= 0 else change * efficiency
        grid = net_load + battery_ac
        curtailed = max(0, -grid - export_kw * duration)
        grid += curtailed
        cost = grid * (row["import"] if grid >= 0 else row["export"])
        mode = "Normal" if abs(final - natural) < 1e-8 else "Force Chg" if change > 1e-8 else "Force Exp" if change < -1e-8 else "Hold"
        if abs(change) < 1e-8 and net_load <= 0:
            mode = "Mode 19"
        yield dict(energy=final, grid=grid, battery_ac=battery_ac, pv_used=pv_used - curtailed, cost=cost, objective=cost + abs(change) * wear, mode=mode)


def build_model(rows, reserve, capacity, charge_kw=3.68, discharge_kw=3.68, efficiency=0.95, wear=0.5, inverter_kw=3.68, export_kw=3.68):
    """Solve all tail starting states and retain continuation costs for path recovery."""
    parameters = (reserve, capacity, charge_kw, discharge_kw, efficiency, wear, inverter_kw, export_kw)
    if not all(math.isfinite(v) for v in parameters) or not 0 <= reserve < capacity or not 0 < efficiency <= 1 or min(charge_kw, discharge_kw, wear, inverter_kw, export_kw) < 0:
        raise ValueError("Invalid battery parameters")
    costs = [[0.0] * 33]
    for row in reversed(rows):
        if not 0 < row["minutes"] <= 30 or any(not math.isfinite(row[k]) for k in ("import", "export", "load", "pv")) or min(row["load"], row["pv"]) < 0:
            raise ValueError("Invalid forecast row")
        following = costs[-1]
        costs.append([min(item["objective"] + interpolate(following, item["energy"], reserve, capacity) for item in options(row, reserve + (capacity - reserve) * i / 32, *parameters)) for i in range(33)])
    costs.reverse()
    return dict(rows=rows, costs=costs, parameters=parameters, curve=[costs[0][0] - value for value in costs[0]])


def simulate(model, initial, initial_cost=0.0):
    """Recover an indicative path from the actual selected near-term terminal SoC."""
    reserve, capacity, *_ = model["parameters"]
    if not math.isfinite(initial) or not reserve - 1e-6 <= initial <= capacity + 1e-6:
        raise ValueError("Boundary SoC outside battery limits")
    energy = min(capacity, max(reserve, initial))
    total = initial_cost
    result = []
    for index, row in enumerate(model["rows"]):
        following = model["costs"][index + 1]
        choice = min(options(row, energy, *model["parameters"]), key=lambda item: item["objective"] + interpolate(following, item["energy"], reserve, capacity))
        result.append(
            dict(
                row,
                forecast_only=True,
                mode=choice["mode"],
                soc_start=energy / capacity * 100,
                soc_end=choice["energy"] / capacity * 100,
                cost_p=choice["cost"],
                total_p=total,
                grid_import=max(0, choice["grid"]),
                grid_export=max(0, -choice["grid"]),
                pv_used=choice["pv_used"],
                battery_power_kw=choice["battery_ac"] * 60 / row["minutes"],
            )
        )
        energy = choice["energy"]
        total += choice["cost"]
    return result


def continuation_load(p, relative):
    """Repeat the filtered daily household profile, keeping dated extra loads separate."""
    absolute = p.minutes_now + relative
    if getattr(p, "load_forecast_only", False):
        # The external household model is authoritative while covered. Beyond its
        # end repeat its last full daily profile, not a padded zero or raw EV load.
        if not p.load_forecast or max(p.load_forecast) - min(p.load_forecast) < 1440:
            raise ValueError("External load forecast lacks a complete daily profile")
        source = absolute
        while source + 5 > max(p.load_forecast):
            source -= 1440
        if source < min(p.load_forecast):
            raise ValueError("No continuation household profile")
        base = sum(p.get_from_incrementing(p.load_forecast, source + offset, backwards=False) for offset in range(5))
        load = max(0, base + p.manual_load_adjust.get(absolute, 0) * 5 / p.plan_interval_minutes) * p.load_scaling
        load *= p.inday_adjustment_at(absolute, p.load_inday_adjustment) * p.load_scaling_dynamic.get(absolute, 1.0)
        return max(load, p.dynamic_load_baseline.get(absolute, 0))
    base, _ = p.get_filtered_load_minute(p.load_minutes, relative % 1440, historical=True, step=5)
    extra = sum(p.get_from_incrementing(p.load_forecast, absolute + offset, backwards=False) for offset in range(5)) if p.load_forecast else 0
    extra += p.manual_load_adjust.get(absolute, 0) * 5 / p.plan_interval_minutes
    load = max(0, base + extra) * p.load_scaling * p.inday_adjustment_at(absolute, p.load_inday_adjustment) * p.load_scaling_dynamic.get(absolute, 1.0)
    return max(load, p.dynamic_load_baseline.get(absolute, 0))


def publish_continuation(p, initial, cost):
    """Return display-only rows; never append to executable window collections."""
    model = getattr(p, "_price_context_model", None)
    if model is None:
        return []
    try:
        rows = simulate(model, initial, cost)
    except (ValueError, TypeError):
        p.log("Forecast display unavailable: invalid boundary state")
        return []
    return [dict(row, start=row["start"].isoformat(), end=row["end"].isoformat()) for row in rows]
