# nautilus-folder-icons

Two small GNOME / Nautilus tools that make file-manager folders more
informative:

1. **`folder-icon.sh`** — give an individual folder a custom icon: the
   default folder shape with your own logo composited onto its face. No
   theme changes, no extensions; the system icon theme is left
   untouched.
2. **`git-emblems/`** — a Nautilus extension that overlays a live
   git-status dot on every folder that's a git repository, plus a
   right-click `Git` submenu and a Properties → Git tab. Updates live
   as you commit, stage, or fetch.

Use either alone, or stack them — the git-status dot composites on top
of whatever icon `folder-icon.sh` produced, so you get a logo'd folder
with a live status indicator in the corner.

Built and tested on Oracle Linux 9 with GNOME, but should work on any
modern GNOME desktop (Fedora, Ubuntu, Debian with GNOME, etc.).

## folder-icon.sh: what it looks like

Pick any folder, point the script at a logo (PNG, JPG, or SVG), and the folder
will render like a normal folder — but with your logo sitting on its face. No
global theme changes, no logout/login, no desktop extensions.

## What you need

Two command-line tools:

**ImageMagick** — composites the images.

- Fedora / RHEL / Oracle Linux / CentOS:
  ```bash
  sudo dnf install -y ImageMagick
  ```
  On **Oracle Linux 9** specifically, ImageMagick lives in EPEL and the repo
  is disabled by default. You'll need three commands:
  ```bash
  sudo dnf install -y oracle-epel-release-el9
  sudo dnf config-manager --enable ol9_developer_EPEL
  sudo dnf install -y ImageMagick
  ```
- Ubuntu / Debian:
  ```bash
  sudo apt install imagemagick
  ```

**librsvg** (only needed if your logo is an SVG) — renders SVGs cleanly.

- Fedora / RHEL: `sudo dnf install librsvg2-tools`
- Ubuntu / Debian: `sudo apt install librsvg2-bin`

## Install

```bash
git clone https://github.com/iraum/nautilus-folder-icons.git
cd nautilus-folder-icons
chmod +x folder-icon.sh
```

That's it — no compilation, no dependencies beyond the two tools above.

## Using it

### Apply a logo to a folder

```bash
./folder-icon.sh /path/to/your/folder /path/to/your/logo.png
```

The folder's icon changes immediately in your file manager. If it doesn't,
press **F5** to refresh the window.

### Logo too big or too small?

Pass `--scale PCT` — the default is 38 (i.e. the logo takes up 38% of the
folder's width).

```bash
./folder-icon.sh ~/Projects/acme ~/logos/acme.svg --scale 50   # bigger logo
./folder-icon.sh ~/Projects/acme ~/logos/acme.svg --scale 25   # smaller logo
```

### Undo / revert to the default icon

```bash
./folder-icon.sh --reset /path/to/your/folder
```

This removes the custom-icon metadata, so the folder goes back to its normal
appearance. Safe to run any time — your files are never touched.

## How it works (briefly)

1. The script takes the default Adwaita folder icon (from
   `/usr/share/icons/Adwaita/512x512/places/folder.png`) as the base.
2. It trims the transparent padding around the folder shape and rescales
   the shape so it fills the canvas tightly — this makes your custom folder
   display at the same visual size as a native Nautilus folder.
3. It composites your logo on the folder's face, slightly below center so
   it sits on the flat part of the folder rather than overlapping the tab.
4. A light sharpening pass keeps the folder's edge line crisp when Nautilus
   scales the icon down to the grid cell.
5. The final PNG is saved to `~/.local/share/icons/custom-folders/`, and the
   folder is told to use it via `gio set … metadata::custom-icon`.

The generated icon is a file on disk keyed to the folder's absolute path, so
two different folders with the same name don't collide.

## Advanced / tuning

All tunables are environment variables you can set before the command:

| Variable      | Default | What it does                                                         |
| ------------- | ------- | -------------------------------------------------------------------- |
| `FOLDER_BASE` | auto    | Path to a different base folder image (PNG or SVG).                  |
| `CANVAS_SIZE` | 512     | Output canvas size in pixels. Larger = sharper at zoom, bigger file. |
| `MARGIN_PCT`  | 3       | Transparent margin around the folder shape, percent per side.        |
| `OFFSET_PCT`  | 8       | How far below center the logo sits, as % of canvas height.           |
| `SHARPEN`     | 1       | Set to `0` to disable the edge-sharpening pass.                      |
| `ICON_DIR`    | `~/.local/share/icons/custom-folders` | Where generated icons are stored. |

Example:

```bash
MARGIN_PCT=5 OFFSET_PCT=10 ./folder-icon.sh ~/Projects/acme ~/logos/acme.svg
```

## Troubleshooting

**The folder icon didn't change.** Press F5 in the file manager window. If
it's still stuck, close the window and reopen it. In stubborn cases:

```bash
nautilus -q && nautilus &
```

**"ImageMagick not found".** Install it — see [What you need](#what-you-need).

**"No base folder icon found".** Your system doesn't have Adwaita installed
in the usual place. Supply your own base:

```bash
FOLDER_BASE=/path/to/some/folder.png ./folder-icon.sh ...
```

**The custom folder looks smaller than the native ones.** Try raising
`CANVAS_SIZE` (e.g. `CANVAS_SIZE=1024`) — some HiDPI setups scale custom
icons differently from themed ones, and a larger native canvas helps.

**My logo has a white/colored background instead of blending.** Your logo
PNG needs transparency. Re-export it from your design tool with a
transparent background, or save as SVG.

## git-emblems: live git status indicators

The Nautilus extension in [`git-emblems/`](./git-emblems/) overlays a
single small status dot on every folder that is a git repository,
color-coded by state:

| Color  | State                                                   |
|--------|---------------------------------------------------------|
| Orange | Dirty — staged / modified / untracked / unmerged files. |
| Red    | Behind — upstream has commits not in local branch.       |
| Green  | Ahead — local commits not yet pushed.                    |
| White  | Clean — in sync, nothing to do.                          |

Priority when several apply: dirty > behind > ahead > clean (so a
green dot really does mean "only thing pending is a push", and a
white dot means everything is in sync). The dot updates live as you
commit, stage, or fetch — each repo's `.git/` is watched via
`Gio.FileMonitor`, no polling.

Right-click any repo folder for a **Git** submenu showing the
headline status (e.g. `Git — dirty — 3 changes (main)`) and a full
breakdown of branch, upstream, ahead/behind, origin URL, and last
commit. The same details also live under **Properties → Git** if you
prefer that surface.

Fully independent of `folder-icon.sh`: the dot sits on top of
whatever icon the folder already has, including the custom-icon PNGs
that script produces.

Install:

```bash
sudo dnf install -y nautilus-python   # one-time; needs ol9_developer_EPEL
cd git-emblems && ./install.sh
```

See [`git-emblems/README.md`](./git-emblems/README.md) for the full
write-up.

## License

MIT — do what you like, no warranty. See `LICENSE` if present, otherwise
treat it as MIT.
