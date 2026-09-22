#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-/opt/data}"
DST="$HERMES_HOME/plugins"
STAMP="$(date +%Y%m%d%H%M%S)"

backup_dir() {
  local path="$1"
  if [[ -e "$path" ]]; then
    mv "$path" "${path}.backup.${STAMP}"
    echo "backed up: ${path}.backup.${STAMP}"
  fi
}

backup_dir "$DST/model-providers/xai"
backup_dir "$DST/web/xai"
backup_dir "$DST/image_gen/xai"
backup_dir "$DST/video_gen/xai"
backup_dir "$DST/xai-proxy-tools"
backup_dir "$DST/xai-proxy-tts"
backup_dir "$DST/transcription/xai-proxy"

echo "Moved hermes-xai-proxy plugin files to timestamped backups. Config/env entries were left untouched."
