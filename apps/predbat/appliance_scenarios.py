"""Read-only appliance load scenarios against Predbat's battery cost model."""

from datetime import datetime, timedelta, timezone
import math

from forecast_dispatch import build_model, interpolate, options, simulate


DEFAULT_PROFILES = {
    "dishwasher_eco": {"duration_minutes": 306, "energy_kwh": [0.06, 0.20, 0.09, 0.04, 0.04, 0.04, 0.04, 0.05, 0.08, 0.04, 0.02]},
    "dishwasher_quick": {"duration_minutes": 65, "energy_kwh": [0.20, 0.15, 0.02]},
    "washing_machine_usual": {"duration_minutes": 150, "energy_kwh": [0.04, 0.25, 0.13, 0.05, 0.04]},
    "tumble_dryer_standard": {"duration_minutes": 60, "energy_kwh": [0.48, 0.43]},
}


def _aware(value):
    """Parse an ISO timestamp only when the source supplies a timezone."""
    if isinstance(value, datetime):
        return value if value.tzinfo else None
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else None


def validate_profiles(source):
    """Accept validated observed bins, falling back per programme if needed."""
    profiles = {}
    for name, fallback in DEFAULT_PROFILES.items():
        value = source.get(name) if isinstance(source, dict) else None
        if not isinstance(value, dict) or value.get("sample_count", 0) < 5:
            profiles[name] = dict(fallback, quality="initial_estimate")
            continue
        bins = value.get("energy_kwh")
        duration = value.get("duration_minutes")
        if (
            not isinstance(duration, (int, float)) or not 20 <= duration <= 600
            or not isinstance(bins, list) or len(bins) != math.ceil(duration / 30)
            or any(not isinstance(item, (int, float)) or not math.isfinite(item) or item < 0 for item in bins)
            or not 0.03 <= sum(bins) <= 8
        ):
            profiles[name] = dict(fallback, quality="initial_estimate")
            continue
        profiles[name] = {"duration_minutes": int(duration), "energy_kwh": bins, "quality": "observed"}
    return profiles


def combined_rows(plan_rows, continuation_rows, now, horizon_hours=120):
    """Join contiguous near-term and estimated continuation rows without padding gaps."""
    rows = []
    horizon = now + timedelta(hours=horizon_hours)
    for source, provenance in ((plan_rows, "eon_forecast"), (continuation_rows, "agilepredict_modelled")):
        for entry in source or []:
            if not isinstance(entry, dict):
                continue
            start = _aware(entry.get("start") or entry.get("time"))
            end = _aware(entry.get("end")) or (start + timedelta(minutes=30) if start else None)
            if start is None or end is None or end <= start or end <= now or start >= horizon:
                continue
            values = (
                entry.get("import", entry.get("import_rate")),
                entry.get("export", entry.get("export_rate")),
                entry.get("load", entry.get("load_forecast")),
                entry.get("pv", entry.get("pv_forecast")),
            )
            if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
                continue
            if values[2] < 0 or values[3] < 0:
                continue
            if start < now:
                # The current partial slot cannot be scored at half-hour precision.
                continue
            row = {"start": start, "end": end, "minutes": (end - start).total_seconds() / 60,
                   "import": values[0], "export": values[1], "load": values[2], "pv": values[3],
                   "provenance": provenance}
            if row["minutes"] == 30:
                rows.append(row)
    rows.sort(key=lambda item: item["start"])
    if not rows:
        return []
    contiguous = [rows[0]]
    for row in rows[1:]:
        if row["start"] < contiguous[-1]["end"]:
            continue
        if row["start"] != contiguous[-1]["end"]:
            break
        contiguous.append(row)
    return contiguous


def _score_window(model, path, start_index, bins):
    """Reoptimise the changed window and unchanged suffix from baseline start SoC."""
    end_index = start_index + len(bins)
    modified = [dict(model["rows"][start_index + i], load=model["rows"][start_index + i]["load"] + extra) for i, extra in enumerate(bins)]
    reserve, capacity, *_ = model["parameters"]
    levels = [reserve + (capacity - reserve) * index / 32 for index in range(33)]
    costs = [model["costs"][end_index]]
    for row in reversed(modified):
        following = costs[-1]
        costs.append([min(choice["objective"] + interpolate(following, choice["energy"], reserve, capacity)
                          for choice in options(row, level, *model["parameters"])) for level in levels])
    costs.reverse()
    initial = path[start_index]["soc_start"] / 100 * capacity
    objective = min(choice["objective"] + interpolate(costs[1], choice["energy"], reserve, capacity)
                    for choice in options(modified[0], initial, *model["parameters"]))
    baseline = interpolate(model["costs"][start_index], initial, reserve, capacity)

    # Recover metered cost for the altered window and its changed battery state.
    energy = initial
    changed_bill = 0.0
    for index, row in enumerate(modified):
        choice = min(options(row, energy, *model["parameters"]),
                     key=lambda item: item["objective"] + interpolate(costs[index + 1], item["energy"], reserve, capacity))
        changed_bill += choice["cost"]
        energy = choice["energy"]
    suffix = {"rows": model["rows"][end_index:], "costs": model["costs"][end_index:], "parameters": model["parameters"]}
    changed_bill += sum(row["cost_p"] for row in simulate(suffix, energy))
    original_bill = sum(row["cost_p"] for row in path[start_index:])
    return round(objective - baseline, 3), round(changed_bill - original_bill, 3)


def appliance_scenarios(plan_rows, continuation_rows, now, soc_kwh, parameters, profile_source=None):
    """Price all 30-minute appliance starts within a bounded five-day horizon."""
    if now.tzinfo is None or not math.isfinite(soc_kwh):
        raise ValueError("Expected aware time and finite battery energy")
    rows = combined_rows(plan_rows, continuation_rows, now)
    if not rows or rows[-1]["end"] - rows[0]["start"] < timedelta(hours=12):
        raise ValueError("Insufficient contiguous forecast coverage")
    model = build_model(rows, **parameters)
    path = simulate(model, soc_kwh)
    profiles = validate_profiles(profile_source)
    results = {}
    for name, profile in profiles.items():
        bins = profile["energy_kwh"]
        candidates = []
        for index in range(len(rows) - len(bins) + 1):
            start = rows[index]["start"]
            finish = start + timedelta(minutes=profile["duration_minutes"])
            if finish > now + timedelta(hours=120):
                break
            cost, bill = _score_window(model, path, index, bins)
            provenance = "agilepredict_modelled" if any(row["provenance"] == "agilepredict_modelled" for row in rows[index:index + len(bins)]) else "eon_forecast"
            candidates.append({"start": start.isoformat(), "finish": finish.isoformat(),
                               "marginal_cost_p": cost, "bill_impact_p": bill, "provenance": provenance})
        results[name] = {**profile, "candidates": candidates}
    return {"version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
            "horizon_end": rows[-1]["end"].isoformat(),
            "forecast_intervals": [
                {"start": row["start"].isoformat(), "provenance": row["provenance"]}
                for row in rows
            ],
            "profiles": results}
