#!/usr/bin/env bash
# folder-icon.sh — give an individual folder a custom icon (default folder + centered logo).
# Leaves the global icon theme untouched; only the folders you run this on change.
#
# Usage:
#   folder-icon.sh <folder> <logo> [--scale PCT]   apply icon (logo sized to PCT% of base, default 38)
#   folder-icon.sh --reset <folder>                restore default icon
#
# Inputs:
#   <logo> and the base folder image may be PNG, JPG, or SVG. SVGs are rasterized
#   at the target pixel size with rsvg-convert for sharp output.
#
# Env overrides:
#   FOLDER_BASE=/path/to/folder.{png,svg}   use a specific base folder image
#   ICON_DIR=/path/to/dir                   where generated icons are stored
#                                           (default ~/.local/share/icons/custom-folders)
#   CANVAS_SIZE=512     output canvas size in pixels. Keep at 512 (or
#                       higher) so Nautilus can render the icon sharply at
#                       HiDPI and zoomed-in views — it doesn't upscale
#                       custom PNGs beyond their native dimensions.
#   MARGIN_PCT=3        transparent margin around the folder shape, as a
#                       percentage of canvas width per side. Default 3 —
#                       the folder shape is rescaled to fill the canvas
#                       with only this much margin, matching the
#                       proportions of Adwaita's hand-tuned small icons.
#   OFFSET_PCT=8        how far below the canvas center the logo sits, as
#                       a percentage of canvas height. Moves the logo off
#                       the folder tab and onto the face.
#   SHARPEN=1           apply a light unsharp mask to the final output to
#                       preserve the edge line through Nautilus's
#                       downscale. Set SHARPEN=0 to disable.

set -euo pipefail

ICON_DIR="${ICON_DIR:-$HOME/.local/share/icons/custom-folders}"
mkdir -p "$ICON_DIR"

# --- reset mode ------------------------------------------------------------
if [[ "${1:-}" == "--reset" ]]; then
  target="${2:?folder path required}"
  # OL9's gio doesn't accept the -d flag; -t unset is the portable way to
  # clear a metadata attribute.
  gio set -t unset "$target" metadata::custom-icon
  echo "Reset: $target"
  exit 0
fi

# --- args ------------------------------------------------------------------
folder="${1:?usage: $0 <folder> <logo> [--scale PCT]}"
logo="${2:?usage: $0 <folder> <logo> [--scale PCT]}"
scale=38
if [[ "${3:-}" == "--scale" ]]; then
  scale="${4:?--scale requires a number}"
fi

[[ -d "$folder" ]] || { echo "Not a folder: $folder" >&2; exit 1; }
[[ -f "$logo"   ]] || { echo "Logo not found: $logo" >&2; exit 1; }

# --- locate base folder icon ----------------------------------------------
find_base() {
  local c
  for c in \
    "/usr/share/icons/Adwaita/512x512/places/folder.png" \
    "/usr/share/icons/Adwaita/scalable/places/folder.svg" \
    "/usr/share/icons/Adwaita/256x256/places/folder.png"; do
    [[ -e "$c" ]] && { echo "$c"; return; }
  done
  find /usr/share/icons -type f \( -name 'folder.svg' -o -name 'folder.png' \) \
    -not -path '*symbolic*' 2>/dev/null | head -n1
}
base="${FOLDER_BASE:-$(find_base)}"
[[ -n "$base" ]] || { echo "No base folder icon found. Set FOLDER_BASE=/path/to/folder.{png,svg}" >&2; exit 1; }

# --- pick imagemagick binary ----------------------------------------------
if command -v magick >/dev/null; then IM=(magick)
elif command -v convert >/dev/null; then IM=(convert)
else
  echo "ImageMagick not found. On Oracle Linux 9:" >&2
  echo "  sudo dnf install -y oracle-epel-release-el9" >&2
  echo "  sudo dnf config-manager --enable ol9_developer_EPEL" >&2
  echo "  sudo dnf install -y ImageMagick" >&2
  exit 1
fi

# --- scratch area ---------------------------------------------------------
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# is_svg <path>  — true if the file appears to be SVG (by extension or content).
is_svg() {
  local f="$1"
  [[ "${f,,}" == *.svg || "${f,,}" == *.svgz ]] && return 0
  head -c 512 "$f" 2>/dev/null | grep -qi '<svg' && return 0
  return 1
}

# rasterize <input> <px> <out.png>
# Renders input to a square PNG of the requested size with transparency.
# For SVGs, prefers rsvg-convert (sharp); falls back to ImageMagick.
rasterize() {
  local in="$1" px="$2" out="$3"
  if is_svg "$in"; then
    if command -v rsvg-convert >/dev/null; then
      rsvg-convert -w "$px" -h "$px" -a -o "$out" "$in"
      return
    fi
    # Fallback: ImageMagick with high density so the SVG rasterizes cleanly.
    "${IM[@]}" -background none -density 300 "$in" \
      -resize "${px}x${px}" -gravity center -extent "${px}x${px}" "$out"
    return
  fi
  "${IM[@]}" "$in" -resize "${px}x${px}" "$out"
}

# --- compose --------------------------------------------------------------
abs_folder="$(realpath "$folder")"
hash="$(printf '%s' "$abs_folder" | sha1sum | cut -c1-10)"
out="$ICON_DIR/$(basename "$abs_folder")-$hash.png"

canvas_size="${CANVAS_SIZE:-512}"
margin_pct="${MARGIN_PCT:-3}"
offset_pct="${OFFSET_PCT:-8}"
sharpen="${SHARPEN:-1}"

# 1. Rasterize base, trim its transparent padding, rescale the folder shape
#    so it fills the canvas with only a small margin, then re-extent back to
#    a fixed high-resolution canvas. Why the round trip:
#    - Nautilus doesn't upscale custom PNG icons above their native size, so
#      the canvas must stay large (512+) to look sharp at HiDPI / zoomed
#      views.
#    - The raw 512x512 Adwaita folder has ~8% transparent padding per side;
#      native folders use the hand-tuned 48x48 (~4% padding) which renders
#      larger at display. Shrinking our padding to match fixes the
#      "smaller than natives" look.
rasterize "$base" "$canvas_size" "$tmp/base_raw.png"
content_size=$(( canvas_size * (100 - 2 * margin_pct) / 100 ))
"${IM[@]}" "$tmp/base_raw.png" -trim +repage \
  -resize "${content_size}x${content_size}" \
  -background none -gravity center \
  -extent "${canvas_size}x${canvas_size}" \
  "$tmp/base.png"

# 2. Derive logo pixel size and vertical offset from the canvas.
bw=$canvas_size
bh=$canvas_size
logo_px=$(( bw * scale / 100 ))
offset_y=$(( bh * offset_pct / 100 ))

rasterize "$logo" "$logo_px" "$tmp/logo.png"

# 3. Composite. A light unsharp mask preserves the edge line after Nautilus
#    downscales the icon into the grid cell; skipped when SHARPEN=0.
sharpen_args=()
[[ "$sharpen" == "1" ]] && sharpen_args=(-unsharp 0x1+0.5+0.02)

"${IM[@]}" "$tmp/base.png" \
  \( "$tmp/logo.png" \) \
  -gravity center -geometry "+0+${offset_y}" -composite \
  "${sharpen_args[@]}" \
  "$out"

gio set -t string "$abs_folder" metadata::custom-icon "file://$out"
echo "Applied $out"
echo "Reset with:  $0 --reset '$abs_folder'"
