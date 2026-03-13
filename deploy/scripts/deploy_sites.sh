#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT_DIR/apps/sites"
DST="/var/www/study-sim"

sudo mkdir -p "$DST"
sudo chown -R "$USER:$USER" "$DST"

for site_dir in "$SRC"/*; do
  site_name="$(basename "$site_dir")"

  if [[ "$site_name" == "shared" ]]; then
    continue
  fi

  # Deploy the site-specific files
  rsync -av --delete "$site_dir/" "$DST/$site_name/"

  # Deploy the shared assets into each site root
  mkdir -p "$DST/$site_name/shared"
  rsync -av --delete "$SRC/shared/" "$DST/$site_name/shared/"
done

echo "Sites deployed to $DST"