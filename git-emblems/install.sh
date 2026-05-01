#!/usr/bin/env bash
# Install git-emblems Nautilus extension and emblem icons.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
EMBLEM_DIR="$HOME/.local/share/icons/hicolor/scalable/emblems"

# 1. nautilus-python (binding) must be installed system-wide.
if ! rpm -q nautilus-python >/dev/null 2>&1; then
  echo "nautilus-python is not installed. Install with:"
  echo "  sudo dnf install -y nautilus-python"
  echo "(Requires the ol9_developer_EPEL repo enabled — see project README.)"
  exit 1
fi

# 2. Drop the extension in place.
mkdir -p "$EXT_DIR"
cp -f "$SCRIPT_DIR/git-emblems.py" "$EXT_DIR/git-emblems.py"
echo "installed extension -> $EXT_DIR/git-emblems.py"

# 3. Install emblem icons.
mkdir -p "$EMBLEM_DIR"
cp -f "$SCRIPT_DIR/icons/"emblem-*.svg "$EMBLEM_DIR/"
echo "installed emblems  -> $EMBLEM_DIR/"

# 4. Refresh GTK icon cache so Nautilus can find the new emblems.
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
fi

# 5. Restart Nautilus so the extension loads.
if pgrep -x nautilus >/dev/null 2>&1; then
  echo "restarting nautilus..."
  nautilus -q || true
  sleep 1
  (nohup nautilus >/dev/null 2>&1 &) || true
fi

echo "done. Open a folder containing git repos to see emblems."
