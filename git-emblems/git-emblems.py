"""
Nautilus extension: live git status emblems on folder icons.

Every folder that is a git repo root gets exactly one small emblem.
The emblem's color encodes the repo's state, with this priority:

  dirty  (uncommitted changes)         -> "git-dirty"   (orange)
  behind (upstream has unpulled work)  -> "git-behind"  (red)
  ahead  (local commits not pushed)    -> "git-ahead"   (green)
  clean  (in sync, nothing to do)      -> "git-clean"   (gray)

Cooperates with folder-icon.sh — emblems are composited by Nautilus on top of
whatever the folder's icon resolves to, including custom-icon PNGs.

Implementation:
  - update_file_info() runs `git status` synchronously on a cache miss.
    `git status` on a healthy repo is fast (typically tens of ms), so the
    first render of a parent directory containing N repos costs ~N quick
    git invocations. Subsequent renders are cache hits.
  - Each repo's .git/ (and refs/heads, refs/remotes) is watched via
    Gio.FileMonitor. Any change drops the cache entry and calls
    invalidate_extension_info() so Nautilus re-queries — the emblem
    refreshes within a fraction of a second.
  - Earlier versions tried to push the git call into a worker thread and
    rely on invalidate_extension_info() to trigger a re-render. In
    practice Nautilus didn't re-call update_file_info reliably after
    that invalidation, so most folders were left without an emblem.
    Going synchronous removes the race.
"""

import os
import subprocess
import threading
from urllib.parse import unquote, urlparse

import gi
gi.require_version('Nautilus', '3.0')
gi.require_version('Gio', '2.0')
gi.require_version('GLib', '2.0')
from gi.repository import Nautilus, GObject, GLib, Gio  # noqa: E402


GIT_BIN = 'git'
GIT_TIMEOUT_SEC = 2


class GitEmblemsProvider(GObject.GObject, Nautilus.InfoProvider):
    def __init__(self):
        super().__init__()
        self._cache = {}      # path -> list[str] emblem names
        self._files = {}      # path -> Nautilus.FileInfo (for invalidation)
        self._monitors = {}   # path -> [Gio.FileMonitor, ...]
        self._lock = threading.Lock()

    # ---- Nautilus entry point ----------------------------------------------

    def update_file_info(self, file):
        if file.get_uri_scheme() != 'file':
            return Nautilus.OperationResult.COMPLETE
        if not file.is_directory():
            return Nautilus.OperationResult.COMPLETE

        path = unquote(urlparse(file.get_uri()).path)
        # .git can be a directory (normal repo) or a file (worktree, submodule).
        if not os.path.exists(os.path.join(path, '.git')):
            return Nautilus.OperationResult.COMPLETE

        with self._lock:
            self._files[path] = file
            cached = self._cache.get(path)

        if cached is None:
            cached = self._compute_emblems(path)
            with self._lock:
                self._cache[path] = cached
            self._ensure_monitor(path)

        for emb in cached:
            file.add_emblem(emb)
        return Nautilus.OperationResult.COMPLETE

    # ---- file monitoring ----------------------------------------------------

    def _ensure_monitor(self, path):
        with self._lock:
            if path in self._monitors:
                return
            self._monitors[path] = []  # placeholder to dedupe concurrent calls

        # Resolve actual git directory — for worktrees / submodules, .git is
        # a file containing "gitdir: <path>" pointing elsewhere.
        git_path = os.path.join(path, '.git')
        if os.path.isfile(git_path):
            try:
                with open(git_path, 'r') as fh:
                    line = fh.readline().strip()
                if line.startswith('gitdir: '):
                    gd = line[len('gitdir: '):].strip()
                    if not os.path.isabs(gd):
                        gd = os.path.normpath(os.path.join(path, gd))
                    git_path = gd
            except OSError:
                pass

        monitors = []
        # .git/ root catches HEAD, index, FETCH_HEAD, packed-refs.
        # refs/heads + refs/remotes catch branch updates that don't touch root.
        for sub in ('', 'refs/heads', 'refs/remotes'):
            mon_path = os.path.join(git_path, sub) if sub else git_path
            if not os.path.isdir(mon_path):
                continue
            try:
                gfile = Gio.File.new_for_path(mon_path)
                monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
            except GLib.Error:
                continue
            monitor.connect('changed', self._on_git_changed, path)
            monitors.append(monitor)

        with self._lock:
            self._monitors[path] = monitors

    def _on_git_changed(self, monitor, gfile, other_file, event_type, path):
        with self._lock:
            self._cache.pop(path, None)
            file = self._files.get(path)
        if file is not None:
            GLib.idle_add(self._invalidate, file)

    def _invalidate(self, file):
        try:
            file.invalidate_extension_info()
        except Exception:
            pass
        return False  # don't repeat

    # ---- git ----------------------------------------------------------------

    def _compute_emblems(self, path):
        try:
            out = subprocess.check_output(
                [GIT_BIN, '-C', path, 'status', '--porcelain=v2', '--branch'],
                stderr=subprocess.DEVNULL, timeout=GIT_TIMEOUT_SEC,
            ).decode('utf-8', 'replace')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError):
            return []

        ahead = behind = 0
        dirty = False
        for line in out.splitlines():
            if line.startswith('# branch.ab '):
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        ahead = int(parts[2].lstrip('+'))
                        behind = int(parts[3].lstrip('-'))
                    except ValueError:
                        pass
            elif line and not line.startswith('#'):
                # Tracked-modified, staged, untracked (?), unmerged — all dirty.
                dirty = True

        if dirty:
            return ['git-dirty']
        if behind:
            return ['git-behind']
        if ahead:
            return ['git-ahead']
        return ['git-clean']
