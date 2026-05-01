# git-emblems

A small Nautilus extension that overlays **live git status emblems** on
folders that are git repositories. Independent of `folder-icon.sh` —
emblems sit on top of whatever icon a folder already has, including the
custom-icon PNGs produced by that script.

## What it shows

Every git repo root gets exactly **one** small dot, color-coded by
status. When several states are true at once, the most actionable one
wins (dirty beats behind beats ahead).

| Emblem        | Color   | Meaning                                          |
|---------------|---------|--------------------------------------------------|
| `git-dirty`   | orange  | Working tree has uncommitted / unstaged changes. |
| `git-behind`  | red     | Upstream has commits not in local branch.        |
| `git-ahead`   | green   | Local branch has commits not in upstream.        |
| `git-clean`   | gray    | Repo is in sync with upstream, working tree clean. |

Emblems update live: each repo's `.git/` directory is watched via
`Gio.FileMonitor`, so commits, stages, fetches, and branch switches
trigger a re-render within a fraction of a second. No polling, no
systemd timer.

## Right-click menu

Right-click any repo folder → top-level **Git — <state>** item. The
label is a one-line headline:

- `Git — clean (main)`
- `Git — dirty — 5 changes (main)`
- `Git — ↑2 ahead (main)`
- `Git — ↓3 behind (main)`

Hover the item to open a submenu with the full breakdown — branch,
upstream tracking with ahead/behind, status counts, origin URL, and
last commit. Same data as the Properties → Git tab; one less click
to get there.

## Properties → Git tab

Right-click any repo folder → **Properties** → **Git** tab. Shows:

- **Status** — clean / dirty (with staged / modified / untracked /
  unmerged counts) / ahead / behind.
- **Branch** — current branch name (or `(detached)`).
- **Upstream** — tracked remote branch with ahead/behind counts.
- **Origin** — `origin` remote URL.
- **Last commit** — subject line and relative time.

The text is selectable, so you can copy any of it.

## Install

```bash
# 1. Install the Nautilus Python binding (one-time, system-wide)
sudo dnf install -y nautilus-python   # needs ol9_developer_EPEL enabled

# 2. Drop the extension and emblem icons in place
./install.sh
```

The installer copies:

- `git-emblems.py` → `~/.local/share/nautilus-python/extensions/`
- `icons/emblem-*.svg` → `~/.local/share/icons/hicolor/scalable/emblems/`

…then refreshes the GTK icon cache and restarts Nautilus if it's
already running.

## How it works

Nautilus calls `update_file_info()` on every visible folder. The
extension:

1. Skips anything that isn't a local directory containing a `.git`
   (directory or file — worktrees and submodules count).
2. On a cache miss, runs `git status --porcelain=v2 --branch`
   synchronously (2-second timeout) and stores the resulting emblem.
   `git status` on a healthy repo is fast — tens of milliseconds —
   so the first render of a parent dir with N repos costs ~N quick
   git invocations. Subsequent renders are cache hits.
3. Sets up a `Gio.FileMonitor` on `.git/`, `.git/refs/heads`, and
   `.git/refs/remotes`. Any change drops the cache entry and calls
   `invalidate_extension_info()` so Nautilus re-renders.

The Properties → Git tab is implemented as a separate
`Nautilus.PropertyPageProvider` on the same class; it runs its own
`git status` / `git log` / `git remote` calls when the dialog opens.

## Notes / limits

- Only marks the **repo root** (the folder containing a `.git`
  directory or file). Nested folders inside a repo are left alone.
- "Behind" only updates when something local actually fetches —
  Nautilus is not going to run `git fetch` for you. Pair with a
  separate periodic fetcher (e.g., a systemd user timer) if you want
  upstream changes reflected without manual fetches.
- Emblems are a Nautilus concept — they don't appear in
  file-picker dialogs from other apps.
- Verified on Oracle Linux 9 with Nautilus 40 (`libnautilus-extension`
  API 3.0) and `nautilus-python` 1.2.3.

## Uninstall

```bash
rm ~/.local/share/nautilus-python/extensions/git-emblems.py
rm ~/.local/share/icons/hicolor/scalable/emblems/emblem-git-{clean,dirty,ahead,behind}.svg
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
nautilus -q
```
