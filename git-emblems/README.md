# git-emblems

A small Nautilus extension that overlays **live git status emblems** on
folders that are git repositories. Independent of `folder-icon.sh` —
emblems sit on top of whatever icon a folder already has, including the
custom-icon PNGs produced by that script.

## What it shows

| Emblem            | Meaning                                              |
|-------------------|------------------------------------------------------|
| `git-dirty`       | Working tree has uncommitted / unstaged changes.     |
| `git-ahead`       | Local branch has commits not in upstream.            |
| `git-behind`      | Upstream has commits not in local branch.            |
| `github-remote`   | `origin` URL contains `github.com`.                  |

Emblems update live: each repo's `.git/` directory is watched via
`Gio.FileMonitor`, so commits, stages, fetches, and branch switches
trigger a re-render within a fraction of a second. No polling, no
systemd timer.

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

…then refreshes the GTK icon cache and restarts Nautilus.

## How it works

Nautilus calls `update_file_info()` on every visible folder. The
extension:

1. Returns immediately from `update_file_info()` — it only reads a
   cache.
2. On a cache miss, queues the path to a single worker thread that runs
   `git status --porcelain=v2 --branch` (2-second timeout) and `git
   remote get-url origin`.
3. Stores the resulting emblem list and asks Nautilus to refresh that
   one file via `invalidate_extension_info()` from the GLib main loop.
4. Sets up a `Gio.FileMonitor` on `.git/`, `.git/refs/heads`, and
   `.git/refs/remotes` so the next change drops the cache and
   recomputes.

This keeps the UI thread fast and bounds the worst case at one
short-running `git` process per visible repo per change.

## Notes / limits

- Only marks the **repo root** (the folder that contains `.git/`).
  Nested folders inside a repo are left alone.
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
rm ~/.local/share/icons/hicolor/scalable/emblems/emblem-git-{dirty,ahead,behind}.svg
rm ~/.local/share/icons/hicolor/scalable/emblems/emblem-github-remote.svg
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
nautilus -q
```
