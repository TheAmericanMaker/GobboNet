#!/usr/bin/env bash
# Extract and decode the search relay from launch.bat's base64 -EncodedCommand blob.
# PowerShell -EncodedCommand is base64-of-UTF-16LE.
set -euo pipefail
ROOT="${GOBBONET_ROOT:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
BAT="$ROOT/launch.bat"
[ -f "$BAT" ] || { echo "launch.bat not found at $BAT" >&2; exit 1; }
grep -o 'EncodedCommand "[A-Za-z0-9+/=]*"' "$BAT" \
  | sed 's/EncodedCommand "//; s/"$//' \
  | python3 -c 'import base64,sys; sys.stdout.write(base64.b64decode(sys.stdin.read().strip()).decode("utf-16-le"))' \
  > search-relay.ps1
echo "decoded -> search-relay.ps1 ($(wc -l < search-relay.ps1) lines)"
