#!/usr/bin/env bash
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HERMES_HOME/plugins"

mkdir -p "$DST"

copy_dir() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
    local backup="${dst}.backup.$(date +%Y%m%d%H%M%S)"
    mv "$dst" "$backup"
    echo "backed up: $backup"
  fi
  cp -a "$src" "$dst"
  echo "installed: $dst"
}

copy_dir "$SRC_DIR/plugins/model-providers/xai" "$DST/model-providers/xai"
copy_dir "$SRC_DIR/plugins/web/xai" "$DST/web/xai"
copy_dir "$SRC_DIR/plugins/image_gen/xai" "$DST/image_gen/xai"
copy_dir "$SRC_DIR/plugins/video_gen/xai" "$DST/video_gen/xai"
copy_dir "$SRC_DIR/plugins/xai-proxy-tools" "$DST/xai-proxy-tools"
copy_dir "$SRC_DIR/plugins/xai-proxy-tts" "$DST/xai-proxy-tts"
copy_dir "$SRC_DIR/plugins/transcription/xai-proxy" "$DST/transcription/xai-proxy"

cat <<'EOF'

Installed hermes-xai-proxy.

Next:
  1) add XAI_PROXY_BASE_URL / XAI_PROXY_API_KEY to $HERMES_HOME/.env
  2) enable:
       hermes plugins enable xai-proxy-model
       hermes plugins enable xai-proxy-web
       hermes plugins enable xai-proxy-image
       hermes plugins enable xai-proxy-video
       hermes plugins enable xai-proxy-tools --allow-tool-override
       hermes plugins enable xai-proxy-tts
       hermes plugins enable xai-proxy-stt
  3) merge config.example.yaml into $HERMES_HOME/config.yaml
  4) restart Hermes

EOF
