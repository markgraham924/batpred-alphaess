#!/usr/bin/env sh
set -e

echo "Starting Predbat AlphaESS add-on"
APPS_FILE="${APPS_FILE:-/config/predbat/apps.yaml}"
mkdir -p /config/predbat
if [ ! -f "$APPS_FILE" ]; then
  echo "No apps.yaml found; copying default"
  cp /opt/predbat/apps/predbat/config/apps.yaml "$APPS_FILE"
fi
export PREDBAT_APPS_FILE="$APPS_FILE"

# Launch Predbat standalone runner
exec python3 /opt/predbat/apps/predbat/hass.py
