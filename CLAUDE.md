# folder-ijr

Small utility for giving individual GNOME/Nautilus folders a custom icon: the
default folder shape with a logo composited onto its face. Only the folders the
user explicitly runs the script on are changed — the system icon theme is not
modified.

## Layout

- `folder-icon.sh` — the script. Takes a target folder and a logo, produces a
  composited PNG, and attaches it to the folder via
  `gio set … metadata::custom-icon`.
- `README.md` — user-facing install and usage guide.
- `.gitignore` — ignores `*.png` so personal logos and diagnostic
  screenshots don't get committed. The script auto-detects the system's
  Adwaita folder as its base, so no base PNG needs to be tracked.
- `git-emblems/` — independent Nautilus Python extension that overlays
  a single live git-status dot on every git-repo folder. Color encodes
  state with a fixed priority: dirty (orange) > behind (red) > ahead
  (green) > clean (white). Exactly one emblem per repo; no stacking.
  Adds a "Git" submenu to the right-click context menu (headline +
  full breakdown) and a matching "Git" tab to the Properties dialog.
  Sits on top of `folder-icon.sh` output without modifying it. Has its
  own README and installer; see `git-emblems/README.md`. Requires the
  `nautilus-python` package from EPEL — same repo as ImageMagick.

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

## git-emblems usage

```bash
# 1. Install the Nautilus Python binding (one-time, system-wide)
sudo dnf install -y nautilus-python   # ol9_developer_EPEL

# 2. Install / refresh the extension and emblem icons
cd git-emblems && ./install.sh
```

The installer drops `git-emblems.py` into
`~/.local/share/nautilus-python/extensions/`, copies the four
`emblem-git-*.svg` files into
`~/.local/share/icons/hicolor/scalable/emblems/`, refreshes the GTK
icon cache, and bounces Nautilus if it's already running. Open any
parent folder in Nautilus to see the dots; right-click a repo folder
→ Properties → Git for the rich view.

## git-emblems dependencies

- `nautilus-python` — Nautilus extension binding for Python via
  gobject-introspection. Lives in `ol9_developer_EPEL` (same repo as
  ImageMagick), not enabled by default — see the folder-icon.sh
  install steps for the two `dnf` commands that enable it.
- GTK 3 (for the Properties → Git tab) and Nautilus 3.0 extension
  API. Nautilus 40 on OL9 ships `libnautilus-extension` 3.0; this
  is what `gi.require_version('Nautilus', '3.0')` matches. On
  Nautilus 43+ the API version is 4.0 — the extension would need an
  updated `require_version` and likely GTK 4 widgets there.

## git-emblems design choices worth preserving

- **`update_file_info()` is synchronous.** An earlier version pushed
  `git status` into a worker thread and relied on
  `invalidate_extension_info()` to make Nautilus re-call
  `update_file_info` once the cache was filled. In practice Nautilus
  didn't re-query reliably after that signal, so most folders never
  got their emblem applied (symptom: 2 of ~20 repos marked). Going
  synchronous removes the race. The cost is one short `git status`
  per visible repo on first render — tens of milliseconds each on a
  healthy repo — and every render after that is a cache hit.
- **Single emblem per repo, fixed priority.** dirty > behind > ahead
  > clean. The user explicitly chose color-only over multi-emblem
  stacks. Don't reintroduce stacking; it conflicts with that
  decision. If a github-remote indicator (or similar) is wanted
  back, make it a *separate* corner emblem so the four status
  colors stay mutually exclusive.
- **`.git` as a file is supported** (worktrees and submodules — a
  text file with `gitdir: <path>`). The recognition check is
  `os.path.exists(.git)`, not `isdir`. The `Gio.FileMonitor` follows
  the `gitdir:` pointer when `.git` is a file so live updates still
  work for worktrees.
- **Emblem visual size is tuned by SVG content, not canvas.** All
  four dots are radius 10 inside a 64×64 viewBox (~31% of canvas).
  Nautilus scales the SVG to whatever pixel size the emblem cell
  needs — shrink or grow the *content* within the 64-canvas, never
  the canvas itself, so the rendered output stays sharp and the
  four dots remain visually identical in size.
- **Cache + monitor pair is per-repo path.** `_cache`,
  `_files`, and `_monitors` are dicts keyed by absolute folder path.
  Don't replace path keys with FileInfo refs — Nautilus FileInfo
  objects can be transient, but the path is stable, and we want
  monitor callbacks to find the latest live FileInfo for that path
  via `_files[path]`.
- **Properties → Git tab does its own git calls,** not the cached
  emblem result. The dialog is opened on-demand, so a fresh
  `git status` / `git log` / `git remote` is cheap and gives the
  most accurate snapshot. Don't try to share state with the
  emblem cache — different surfaces, different lifetimes.
- **Right-click menu also queries fresh.** `MenuProvider.get_file_items`
  runs the same `_gather_git_info` as the Properties tab. Menu
  generation happens at right-click rate (human-scale), so a single
  `git status` per click is cheap. Items are kept `sensitive=True`
  even though they're display-only — disabling them dims the text
  to the point that the headline becomes hard to read.
- **Nautilus must fully reload to pick up extension changes.** The
  installer runs `nautilus -q`, but with `--gapplication-service`
  (modern default) an active window can keep the process alive and
  the old extension stays loaded. Symptom: install reports success
  but the new surface doesn't appear. Recovery is
  `pkill -u $USER nautilus && sleep 1 && nautilus &`. Don't put
  `pkill` in `install.sh` — it's user-scoped on this box but a
  surprising default for a setup script.
