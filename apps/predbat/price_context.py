"""Finite, non-executable price context for the local Optimise experiment.

Inputs are indicative Optimise rates, NOT raw Agile tariff prices. No extrapolation,
terminal resale reward, network access or inverter commands are permitted here.
"""

from datetime import datetime, timedelta
from html import escape
import math


def context_curve(rows, reserve, capacity, charge_kw=3.68, discharge_kw=3.68, efficiency=0.95, wear=2.0):
    """Backward finite-horizon dispatch valuation on 33 battery energy levels.

    Grid charging and discharge have separate losses; wear is per stored kWh
    moved. The final state has exactly zero additional value. Coarse state-grid
    discretisation makes this an experimental valuation, not an exact optimiser.
    """
    if not 0 <= reserve < capacity or not 0 < efficiency <= 1 or min(charge_kw, discharge_kw, wear) < 0:
        raise ValueError("Invalid battery parameters")
    levels = [reserve + (capacity - reserve) * i / 32 for i in range(33)]
    costs = [0.0] * 33
    for row in reversed(rows):
        duration = row["minutes"] / 60
        if duration <= 0 or any(not math.isfinite(row[k]) for k in ("import", "export", "load", "pv")):
            raise ValueError("Invalid context row")
        if min(row["load"], row["pv"]) < 0:
            raise ValueError("Negative energy forecast")
        updated = []
        for initial in levels:
            candidates = []
            net_load = row["load"] - row["pv"]
            natural = initial - net_load / efficiency if net_load >= 0 else initial - net_load * efficiency
            choices = levels + [initial, min(capacity, max(reserve, natural)), min(capacity, initial + charge_kw * duration * efficiency), max(reserve, initial - discharge_kw * duration / efficiency)]
            for final in choices:
                position = (final - reserve) / (capacity - reserve) * 32
                index = min(31, int(position))
                future_cost = costs[index] + (costs[index + 1] - costs[index]) * (position - index)
                change = final - initial
                grid_battery = change / efficiency if change >= 0 else change * efficiency
                if grid_battery > charge_kw * duration + 1e-9 or -grid_battery > discharge_kw * duration + 1e-9:
                    continue
                net = row["load"] - row["pv"] + grid_battery
                cost = net * (row["import"] if net >= 0 else row["export"]) + abs(change) * wear
                candidates.append(cost + future_cost)
            updated.append(min(candidates))
        costs = updated
    return [costs[0] - value for value in costs]


def parse_context(snapshot, boundary, now, maximum_minutes=2160):
    """Accept only contiguous, fresh timestamped rows; stop at any coverage gap."""
    issued = datetime.fromisoformat(snapshot["issued_at"].replace("Z", "+00:00"))
    if issued.tzinfo is None or not timedelta(0) <= now - issued <= timedelta(hours=6):
        raise ValueError("Stale or future-dated forecast")
    result, cursor = [], boundary
    for raw in sorted(snapshot["rates"], key=lambda row: row["start"]):
        start = datetime.fromisoformat(raw["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(raw["end"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Timezone required")
        if end <= boundary:
            continue
        if not start <= cursor < end or end - start != timedelta(minutes=30):
            break
        start = cursor
        end = min(end, boundary + timedelta(minutes=maximum_minutes))
        if end <= start:
            break
        values = {key: float(raw[key]) for key in ("import", "export")}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError("Non-finite rate")
        band = raw["band"]
        if band not in ("very low", "low", "medium", "high"):
            raise ValueError("Invalid band")
        result.append(dict(values, start=start, end=end, minutes=int((end - start).total_seconds() / 60), band=band))
        cursor = end
    return result


def prepare_context(p):
    """Build one curve per calculation; never fall back to invented tail prices."""
    if getattr(p, "_price_context_ready", False):
        return p._price_context_curve
    p._price_context_ready = True
    p._price_context_curve = None
    p._price_context_model = None
    p.price_context_rows = []
    p.price_context_status = "Forecast unavailable or expired; existing battery valuation retained"
    original = p.forecast_minutes
    try:
        source = p.get_arg("optimise_context_source", None, indirect=False)
        snapshot = p.get_state_wrapper(source, attribute="context", default=None)
        boundary = p.midnight_utc + timedelta(minutes=p.optimise_price_boundary)
        rows = parse_context(snapshot, boundary, p.now_utc_real)
        if not rows:
            raise ValueError("No contiguous forecast")
        p.forecast_minutes = p.optimise_price_boundary - p.minutes_now + sum(row["minutes"] for row in rows)
        from forecast_dispatch import build_model, continuation_load

        loads = {minute: continuation_load(p, minute) for minute in range(0, p.forecast_minutes, 5)}
        usable = []
        absolute = p.optimise_price_boundary
        for row in rows:
            duration = row["minutes"]
            relative = absolute - p.minutes_now
            if duration % 5 or any(m not in loads for m in range(relative, relative + duration, 5)) or any(m not in p.pv_forecast_minute for m in range(absolute, absolute + duration)):
                break
            row["load"] = sum(loads[m] for m in range(relative, relative + duration, 5))
            row["pv"] = sum(p.pv_forecast_minute[m] for m in range(absolute, absolute + duration)) * p.inverter_loss
            usable.append(row)
            absolute += duration
        if not usable:
            raise ValueError("No energy coverage")
        parameters = dict(
            reserve=p.reserve,
            capacity=p.soc_max,
            charge_kw=min(3.68, p.battery_rate_max_charge * 60),
            discharge_kw=min(3.68, p.battery_rate_max_discharge * 60),
            efficiency=min(p.inverter_loss * p.battery_loss, p.inverter_loss * p.battery_loss_discharge),
            wear=p.metric_battery_cycle,
            inverter_kw=p.inverter_limit * 60,
            export_kw=p.export_limit * 60,
        )
        nominal = build_model(usable, **parameters)
        duration = sum(row["minutes"] for row in usable)
        downside = build_model([dict(row, pv=row["pv"] * 0.7, load=row["load"] + 2 * row["minutes"] / duration) for row in usable], **parameters)
        p._price_context_model = nominal
        p._price_context_curve = [0.75 * base + 0.25 * cautious for base, cautious in zip(nominal["curve"], downside["curve"])]
        p.price_context_rows = [dict(row, start=row["start"].isoformat(), end=row["end"].isoformat()) for row in usable]
        p.price_context_status = "Forecast simulation; not scheduled. Valuation: 75% nominal, 25% lower solar (-30%) and +2kWh demand. No value beyond final row."
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        p.log("Price context unavailable: {}".format(type(error).__name__))
    finally:
        p.forecast_minutes = original
    return p._price_context_curve


def context_html(rows, status):
    """Render forecast rows explicitly alongside the normal executable plan."""
    html = "<h3>Forecast context — not scheduled</h3><p>{}</p>".format(escape(status))
    html += "<table><tr><th>Time (with UTC offset)</th><th>Band</th><th>Indicative import p</th><th>Indicative export p</th><th>Load kWh</th><th>PV kWh</th></tr>"
    for row in rows:
        html += "<tr><td>{}</td><td>{}</td><td>{:.2f}</td><td>{:.2f}</td><td>{:.2f}</td><td>{:.2f}</td></tr>".format(escape(row["start"]), escape(row["band"]), row["import"], row["export"], row["load"], row["pv"])
    return html + "</table>"
