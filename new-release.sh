#!/bin/bash
# ytdlp-studio:new-release-sh v1
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$HERE/scripts/new_release.py" "$@"
