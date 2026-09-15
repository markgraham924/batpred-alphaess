"""Experimental robust mapping from Agile shape to overlapping supplier prices.

Not calibrated confidence, settlement prices, or a production tariff adapter.
The overlap is a small same-issue sample; shadow testing is required.
"""
from datetime import datetime, timedelta, timezone
from statistics import median
import math


def map_proxy(issue, supplier_rows):
    """Fit separate median-slope import/export mappings on exact timestamp overlap."""
    supplier = {datetime.fromisoformat(row["start"]).astimezone(timezone.utc): row for row in supplier_rows}
    pairs = []
    for row in issue["prices"]:
        start = datetime.fromisoformat(row["date_time"]).astimezone(timezone.utc)
        if start in supplier and math.isfinite(float(row["agile_pred"])):
            pairs.append((float(row["agile_pred"]), supplier[start]))
    if len(pairs) < 12:
        raise ValueError("At least twelve overlapping supplier slots required")
    models = {}
    for channel in ("import", "export"):
        slopes = [(b[channel] - a[channel]) / (y - x) for i, (x, a) in enumerate(pairs) for y, b in pairs[i + 1 :] if abs(y - x) >= 1]
        if not slopes:
            raise ValueError("Insufficient price variation")
        slope = min(2.0, max(0.0, median(slopes)))
        intercept = median(row[channel] - slope * x for x, row in pairs)
        models[channel] = slope, intercept
    rates = []
    for row in issue["prices"]:
        start = datetime.fromisoformat(row["date_time"])
        price = float(row["agile_pred"])
        if not math.isfinite(price):
            raise ValueError("Invalid proxy price")
        values = {channel: round(slope * price + offset, 2) for channel, (slope, offset) in models.items()}
        band = "very low" if values["import"] < 5 else "low" if values["import"] < 15 else "medium" if values["import"] < 25 else "high"
        rates.append(dict(values, start=start.isoformat(), end=(start + timedelta(minutes=30)).isoformat(), band=band))
    return dict(issued_at=issue["created_at"], rates=rates, source="Agile G mapped to Optimise; experimental", overlap_slots=len(pairs))
