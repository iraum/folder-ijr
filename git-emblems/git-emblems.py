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

Design:
  - update_file_info() is called by Nautilus on every visible folder. It must
    return fast, so it only consults a cache. On a miss, it enqueues a job
    for a worker thread.
  - A single worker thread runs `git status --porcelain=v2 --branch` per repo
    (with a 2s timeout) and stashes the result. When done it asks Nautilus to
    refresh that file's extension info from the GLib main loop.
  - Each repo gets a Gio.FileMonitor on its `.git/` directory. Any change
    (commit, stage, fetch, branch switch) drops the cache entry and triggers
    Nautilus to re-render that folder's emblems.
"""

import os
import queue
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
        self._cache = {}        # path -> list[str] emblem names
        self._inflight = set()  # paths currently being computed
        self._files = {}        # path -> Nautilus.FileInfo (for invalidation)
        self._monitors = {}     # path -> Gio.FileMonitor on .git/
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    # ---- Nautilus entry point ----------------------------------------------

    def update_file_info(self, file):
        if file.get_uri_scheme() != 'file':
            return Nautilus.OperationResult.COMPLETE
        if not file.is_directory():
            return Nautilus.OperationResult.COMPLETE

        path = unquote(urlparse(file.get_uri()).path)
        if not os.path.isdir(os.path.join(path, '.git')):
            return Nautilus.OperationResult.COMPLETE

        with self._lock:
            self._files[path] = file
            cached = self._cache.get(path)
            inflight = path in self._inflight

        if cached is not None:
            for emb in cached:
                file.add_emblem(emb)
            return Nautilus.OperationResult.COMPLETE

        if not inflight:
            with self._lock:
                self._inflight.add(path)
            self._queue.put(path)
        return Nautilus.OperationResult.COMPLETE

    # ---- worker -------------------------------------------------------------

    def _worker_loop(self):
        while True:
            path = self._queue.get()
            try:
                emblems = self._compute_emblems(path)
            except Exception:
                emblems = []
            with self._lock:
                self._cache[path] = emblems
                self._inflight.discard(path)
            GLib.idle_add(self._after_compute, path)

    def _after_compute(self, path):
        self._ensure_monitor(path)
        with self._lock:
            file = self._files.get(path)
        if file is not None:
            try:
                file.invalidate_extension_info()
            except Exception:
                pass
        return False  # don't repeat the idle callback

    # ---- file monitoring ----------------------------------------------------

    def _ensure_monitor(self, path):
        with self._lock:
            if path in self._monitors:
                return
        git_dir = os.path.join(path, '.git')
        try:
            gfile = Gio.File.new_for_path(git_dir)
            monitor = gfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
        except GLib.Error:
            return
        monitor.connect('changed', self._on_git_changed, path)
        # Also watch refs/ and refs/remotes/ for fetch/push activity that
        # doesn't touch .git/ root entries.
        sub_monitors = [monitor]
        for sub in ('refs/heads', 'refs/remotes'):
            sub_path = os.path.join(git_dir, sub)
            if not os.path.isdir(sub_path):
                continue
            try:
                sgfile = Gio.File.new_for_path(sub_path)
                smon = sgfile.monitor_directory(Gio.FileMonitorFlags.NONE, None)
                smon.connect('changed', self._on_git_changed, path)
                sub_monitors.append(smon)
            except GLib.Error:
                pass
        with self._lock:
            self._monitors[path] = sub_monitors

    def _on_git_changed(self, monitor, gfile, other_file, event_type, path):
        # Drop cache and ask Nautilus to refresh the folder's emblems.
        with self._lock:
            self._cache.pop(path, None)
            file = self._files.get(path)
        if file is None:
            return
        # Recompute on the worker; UI refresh follows in _after_compute.
        with self._lock:
            if path in self._inflight:
                return
            self._inflight.add(path)
        self._queue.put(path)

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
                dirty = True

        # Single emblem, prioritized: dirty beats behind beats ahead beats clean.
        if dirty:
            return ['git-dirty']
        if behind:
            return ['git-behind']
        if ahead:
            return ['git-ahead']
        return ['git-clean']
