#!/bin/bash
# Build a self-contained installer from this checkout, then run it locally.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
EDITION=""
if [[ "${1:-}" == --gertboard && $# == 1 ]]; then
    EDITION="-gertboard"
elif [[ $# != 0 ]]; then
    printf 'Usage: bash install.sh [--gertboard]\n' >&2
    exit 2
fi
STAGE="$(mktemp -d)"
trap 'rm -rf -- "$STAGE"' EXIT
/usr/bin/python3 "$ROOT/tools/build_release.py" --output "$STAGE"
VERSION="$(cat "$ROOT/VERSION")"
bash "$STAGE/raspi-gpio-tool${EDITION}-${VERSION}/install.sh"
