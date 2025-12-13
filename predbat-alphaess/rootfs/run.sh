#!/usr/bin/env sh
set -e

echo "Starting Predbat AlphaESS add-on"

# Set up configuration paths
CONFIG_DIR="/config/predbat"
APPS_FILE="$CONFIG_DIR/apps.yaml"

mkdir -p "$CONFIG_DIR"

# Copy default config if not exists
if [ ! -f "$APPS_FILE" ]; then
  echo "No apps.yaml found; copying default"
  cp /opt/predbat/apps/predbat/config/apps.yaml "$APPS_FILE"
fi

# Set environment variable for Predbat
export PREDBAT_APPS_FILE="$APPS_FILE"

# Change to working directory
cd /opt/predbat/apps/predbat

# Launch Predbat standalone runner
echo "Launching Predbat from $(pwd)"
exec python3 hass.py
