#!/usr/bin/env bash
# Build fitness-mcp.dxt — a Claude Desktop Extension bundle.
#
# A DXT is a plain zip of the dxt/ folder (manifest.json + optional icon.png
# + optional README.md) with the .dxt extension. It does NOT bundle Python —
# the manifest's mcp_config spawns `uvx fitness-mcp@latest` on first launch,
# which fetches the package from PyPI.
#
# Usage:  scripts/build_dxt.sh   (from repo root)
# Output: dist/fitness-mcp-<version>.dxt

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

VERSION=$(/usr/bin/awk -F'"' '/^version = / {print $2; exit}' pyproject.toml)
MANIFEST_VERSION=$(python3 -c 'import json; print(json.load(open("dxt/manifest.json"))["version"])')

if [ "$VERSION" != "$MANIFEST_VERSION" ]; then
    echo "ERROR: version mismatch — pyproject.toml=$VERSION, manifest=$MANIFEST_VERSION" >&2
    exit 1
fi

mkdir -p dist
OUT="dist/fitness-mcp-${VERSION}.dxt"
rm -f "$OUT"

# zip -j strips directories so manifest.json ends up at the root of the archive,
# which is what Claude Desktop's loader expects.
( cd dxt && zip -q -r "../$OUT" . -x "*.DS_Store" )

echo "built: $OUT ($(du -h "$OUT" | awk '{print $1}'))"
echo
echo "inside:"
unzip -l "$OUT"
