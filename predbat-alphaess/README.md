# Predbat AlphaESS Add-on

Home Assistant add-on to run Predbat with AlphaESS support.

## Installation

- In Home Assistant: Settings → Add-ons → Add-on Store → Custom repositories → add `https://github.com/markgraham924/batpred-alphaess`.
- Find "Predbat AlphaESS Add-on" → Install → Start.
- On first start, a default `/config/predbat/apps.yaml` is created. Edit it to match your environment (set `ha_url`, `ha_key`, entities, and `inverter_type: "AE3"`).

## Ingress / Web UI

- Predbat web interface runs on port `5052`. With ingress enabled, open the add-on and click "Open Web UI".

## Configuration

- User config lives at `/config/predbat/apps.yaml`.
- The runner uses `PREDBAT_APPS_FILE` to point to this file.

## Source

- Bundles `apps/predbat` from this repository into the container under `/opt/predbat/apps/predbat`.
