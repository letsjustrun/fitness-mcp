# fitness-mcp — Desktop Extension (DXT)

Double-click `fitness-mcp.dxt` to install this server into Claude Desktop. The app will prompt you for your **Garmin Personal API Token** during install; no further setup is required.

## How to build the `.dxt`

A DXT is a plain zip of this folder with the `.dxt` extension.

```bash
cd /path/to/GarminMCP
scripts/build_dxt.sh
# output: dist/fitness-mcp-0.1.0.dxt
```

The build script packages `manifest.json` and `icon.png` (if present). It does **not** bundle Python — install assumes `uvx` is on your PATH and fetches the package from PyPI on first run.

## What the user sees

Claude Desktop reads the `user_config` block in `manifest.json` and shows:

- **Garmin Personal API Token** (required, masked)
- **Custom CA Bundle** (optional file picker, for corporate TLS-inspected networks)
- **Log level** (dropdown, defaults INFO)

Clicking install writes the config into Claude Desktop's own store (not into our repo) and spawns `uvx fitness-mcp@latest` on first chat.

## Updating

Bump `version` in both `manifest.json` and `pyproject.toml`, rebuild, and re-publish on the Releases page. Users who installed the DXT get an "Update available" badge in Claude Desktop.
