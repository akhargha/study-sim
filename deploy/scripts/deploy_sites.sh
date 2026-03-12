#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT_DIR/apps/sites"
DST="/var/www/study-sim"

sudo mkdir -p "$DST"
sudo chown -R "$USER:$USER" "$DST"

rsync -av --delete "$SRC/shared/" "$DST/shared/"
for site_dir in "$SRC"/*; do
  site_name="$(basename "$site_dir")"
  if [[ "$site_name" == "shared" ]]; then
    continue
  fi
  rsync -av --delete "$site_dir/" "$DST/$site_name/"
done

echo "Sites deployed to $DST"
