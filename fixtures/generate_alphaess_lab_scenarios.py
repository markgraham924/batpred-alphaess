"""Generate synthetic price-driven Predbat lab scenarios; writes only local YAML."""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from pytz import timezone
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
base = yaml.safe_load((root / "templates/alphaess_local.yaml").read_text(encoding="utf-8-sig"))
forecast = yaml.safe_load((root / "fixtures/alphaess-lab-predbat.yaml").read_text(encoding="utf-8-sig"))
now = datetime.now(timezone("Europe/London"))
start = now.replace(minute=now.minute // 30 * 30, second=0, microsecond=0)
end = start + timedelta(hours=2)
args.output.mkdir(parents=True, exist_ok=True)
for scenario in ("charge", "export"):
    config = yaml.safe_load(yaml.safe_dump(base))
    app = config["pred_bat"]
    app.update(forecast)
    app.pop("template", None)
    app.update(set_read_only=True, num_cars=0, mode="Control charge & discharge", set_export_freeze=False, set_charge_freeze=False, load_ml_enable=False, forecast_hours=24, calculate_plan_every=5)
    app["rates_import"] = [{"start": "00:00:00", "end": "00:00:00", "rate": 35}]
    app["rates_export"] = [{"start": "00:00:00", "end": "00:00:00", "rate": 0}]
    if scenario == "charge":
        app["rates_import_override"] = [{"start": start.strftime("%H:%M:%S"), "end": end.strftime("%H:%M:%S"), "rate": -10}]
    else:
        app["rates_export_override"] = [{"start": start.strftime("%H:%M:%S"), "end": end.strftime("%H:%M:%S"), "rate": 150}]
    with (args.output / f"{scenario}-apps.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
print(f"Fictional window {start.isoformat()} to {end.isoformat()}; both configs start read-only.")
