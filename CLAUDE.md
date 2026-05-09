# nautilus-folder-icons

Small GNOME / Nautilus tool that composites a logo onto a folder's
face for individually-chosen folders, without touching the system
icon theme. Per-folder, on demand, fully reversible.

The companion project
[`nautilus-git-status`](https://github.com/iraum/nautilus-git-status)
overlays a live git emblem on every git-repo folder; its emblem
composites on top of whatever icon a folder has, so the two can be
used together without coordination.

## Layout

- `folder-icon.sh` — the script. Takes a target folder and a logo,
  produces a composited PNG, and attaches it to the folder via
  `gio set … metadata::custom-icon`.
- `README.md` — user-facing install and usage guide.
- `.gitignore` — ignores `*.png` and `*.svg` so personal logos and
  diagnostic screenshots don't get committed. The script auto-detects
  the system's Adwaita folder as its base, so no base PNG needs to be
  tracked.

## Usage

```bash
# Apply a logo to a folder (uses system Adwaita folder as base by default)
./folder-icon.sh ~/Projects/work ~/logos/acme.png

# Use a specific base image instead of the system default
FOLDER_BASE=/path/to/folder.png ./folder-icon.sh ~/Projects/work ~/logos/acme.png

# Larger/smaller logo overlay (default is 38% of base width)
./folder-icon.sh ~/Projects/work ~/logos/acme.png --scale 50

# Revert a folder to the default icon
./folder-icon.sh --reset ~/Projects/work
```

Generated icons land in `~/.local/share/icons/custom-folders/` as
`<folder-name>-<sha1[0:10]>.png`. The hash prevents collisions between two
folders that share a basename.

## Dependencies

- ImageMagick — either `magick` (IM7) or `convert` (IM6) is auto-detected.
  Not in OL9's default repos; it lives in `ol9_developer_EPEL`, which ships
  *disabled* even after `oracle-epel-release-el9` is installed:
  ```bash
  sudo dnf install -y oracle-epel-release-el9          # installs repo file
  sudo dnf config-manager --enable ol9_developer_EPEL  # enables it
  sudo dnf install -y ImageMagick
  ```
- `librsvg2-tools` (`sudo dnf install librsvg2-tools`) — used whenever the
  logo or base is an SVG. The script calls `rsvg-convert -w N -h N` to
  rasterize at the exact target pixel size (much sharper than letting
  ImageMagick read the SVG directly). Falls back to ImageMagick with
  `-background none -density 300` if `rsvg-convert` isn't on PATH.

## Platform notes

- Target platform is Oracle Linux 9 with GNOME. Adwaita on OL9 ships the
  full-color folder as PNGs only (no SVG); `/usr/share/icons/Adwaita/512x512/places/folder.png`
  is the default base the script falls back to.
- Nautilus 42+ removed the "click the icon in Properties" picker, so
  `gio set metadata::custom-icon` is the supported mechanism.
- OL9's `gio` does not accept the `-d` flag to delete an attribute. The
  portable form is `gio set -t unset <path> metadata::custom-icon` — that's
  what `--reset` calls.
- Changes appear immediately in Nautilus; if not, refresh the parent view (F5).

## Design choices worth preserving

- The script is per-folder on purpose — a theme-level override was rejected
  because the user wants most folders to keep the default look.
- Logo is composited below canvas center (default `OFFSET_PCT=8`, i.e. 8%
  of canvas height) so it sits on the folder face rather than overlapping
  the tab. Don't remove the offset.
- **Padding / size matching (important).** Adwaita's folder icon exists at
  multiple sizes, each hand-tuned. The `512x512` version has ~8.3%
  transparent padding per side; the `48x48` hand-tuned only ~4.1%.
  Nautilus can render a native folder at any pixel size because it goes
  through the theme engine. Our custom icon is a single PNG, so Nautilus
  loads it and scales it to fit the grid cell. **Two things matter:**
    1. **Canvas must stay at 512 (or larger).** Nautilus does **not**
       upscale a custom PNG above its native dimensions, so a 452×452
       canvas renders smaller than natives once the view grows past 452.
       An earlier version of this script trimmed the canvas tight to
       make the folder bigger; it produced the opposite effect at HiDPI
       / zoomed views.
    2. **Folder shape should fill the canvas.** At a fixed 512 canvas,
       the raw 8% padding makes the folder look smaller than natives
       (which are rendered at the 48x48 hand-tuned ratio).
  The script handles this with `-trim +repage -resize (100-2*MARGIN)% -extent 512x512`:
  trim the padding off the base, scale the folder shape up to fill
  ~94% of the canvas, then re-extent back to the full 512×512. Both
  conditions hold: canvas is large, content fills the canvas. Don't
  change one without understanding the other.
- A light unsharp mask (`-unsharp 0x1+0.5+0.02`) runs after compositing.
  It's there to keep the folder's profile edge line visible after
  Nautilus's downscale. Disable with `SHARPEN=0` if it ever causes
  visible haloing with a particular base.
- When changing the trim/offset tuning, re-run the script on every
  already-customized folder — the output filename is keyed only by the
  folder's path, so re-running just overwrites the cached PNG in place.
