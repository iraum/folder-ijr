# git-emblems

A small Nautilus extension that surfaces git status in three places,
all driven by the same data:

- **Emblems** — a single combined indicator composited onto the
  folder icon for every git repo, updated live. Encodes both **status**
  (outer disk color) and **ownership tier** (small inner dot color).
- **Right-click menu** — a `Git — <state>` submenu with the
  one-line headline plus the full breakdown.
- **Properties → Git tab** — the same breakdown rendered as a
  Properties dialog page with selectable text.

Independent of `folder-icon.sh` — overlays sit on top of whatever
icon a folder already has, including the custom-icon PNGs produced
by that script.

## What it shows

Every git repo root gets exactly **one** emblem with two layers:

**Outer disk — status.** Fills the emblem with the status color; when
several states are true at once, the most actionable one wins (dirty
beats behind beats ahead).

| Color   | Meaning                                            |
|---------|----------------------------------------------------|
| orange  | Working tree has uncommitted / unstaged changes.   |
| red     | Upstream has commits not in local branch.          |
| green   | Local branch has commits not in upstream.          |
| white   | Repo is in sync with upstream, working tree clean. |

**Inner dot — ownership tier.** A small black-outlined dot in the
center of the status disk identifies which of your git profiles the
repo belongs to. The status color stays visible as a ring around it.
Tier is resolved (in order) from the owner slug in `git remote get-url
origin`, then `git config user.name`, then `git config user.email`.
The mapping lives in `~/.config/nautilus-folder-icons/git-emblems.conf`
(see [Configuring ownership](#configuring-ownership)).

| Center dot | Tier      | What it means                                     |
|------------|-----------|---------------------------------------------------|
| gold       | primary   | Your main profile — repos you own.                |
| cyan       | secondary | Your second profile.                              |
| purple     | tertiary  | Your third profile.                               |
| (none)     | external  | Doesn't match any of your profiles — plain status disk only. |

**No-remote signal.** When a tiered repo has no remote configured
(`git remote` returns nothing), the inner dot's outline switches to a
bolder crimson stroke instead of the normal soft black. This flags
repos that exist purely on your machine — owned but not pushed
anywhere yet — without changing the tier color. External repos don't
participate in this signal: they have no inner dot to outline.

So a green disk with a gold center means "ahead under primary" — your
main profile has unpushed commits. The same gold center with a red
outline means "this is yours, primary tier, and there's no remote at
all". A plain white disk (no center dot) is a clean third-party clone.

Emblems update live: each repo's `.git/` directory is watched via
`Gio.FileMonitor`, so commits, stages, fetches, and branch switches
trigger a re-render within a fraction of a second. The config file is
watched too — edit it and the emblems re-tier without restarting
Nautilus. No polling, no systemd timer.

## Configuring ownership

`install.sh` seeds `~/.config/nautilus-folder-icons/git-emblems.conf`
on first run. Format is one line per tier:

```ini
# Comma-separated identifiers per tier. Matched case-insensitively
# against the origin owner slug, then user.name, then user.email.
primary   = iraum, iraumbo@gmail.com
secondary = x42i
tertiary  = iraum-oracle
```

Anything not listed is rendered as `external`. Save the file and
emblems repaint within a fraction of a second; no restart needed.

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
- **Identity** — the slug used to assign the tier and the resulting
  tier name (e.g. `iraum (primary)` or `some-org (external)`). When
  the repo has no remote, `, no remote` is appended.
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
- `icons/emblem-git-*.svg` → `~/.local/share/icons/hicolor/scalable/emblems/`
  (28 emblems: 4 statuses × 3 tiers × 2 remote-states + 4 statuses × external)
- A starter `git-emblems.conf` → `~/.config/nautilus-folder-icons/`,
  but only if no config exists already (it never overwrites yours).

…then refreshes the GTK icon cache and restarts Nautilus if it's
already running. Re-run the installer any time you edit
`icons/generate.py` to regenerate the SVGs first
(`python3 icons/generate.py`).

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

The right-click menu and the Properties → Git tab are separate
interfaces on the same class — `Nautilus.MenuProvider` and
`Nautilus.PropertyPageProvider` respectively. Both run their own
`git status` / `git log` / `git remote` calls fresh at the moment
of interaction (right-click or dialog open), independent of the
emblem cache. Cheap at human-scale interaction rates and avoids any
staleness concerns.

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
- **After install/upgrade, Nautilus must reload extensions.** The
  installer runs `nautilus -q`, which is enough on most setups. With
  `--gapplication-service` (the modern default) an active window can
  keep the process alive — if the new surface doesn't appear, force
  a fresh process:

  ```bash
  pkill -u $USER nautilus && sleep 1 && nautilus &
  ```

## Uninstall

```bash
rm ~/.local/share/nautilus-python/extensions/git-emblems.py
rm ~/.local/share/icons/hicolor/scalable/emblems/emblem-git-*.svg
rm -rf ~/.config/nautilus-folder-icons      # only if you also want to drop the config
gtk-update-icon-cache -f ~/.local/share/icons/hicolor
nautilus -q
```
