"""
Nautilus extension: live git status emblems on folder icons.

Every folder that is a git repo root gets exactly one small emblem.
The emblem's color encodes the repo's state, with this priority:

  dirty  (uncommitted changes)         -> "git-dirty"   (orange)
  behind (upstream has unpulled work)  -> "git-behind"  (red)
  ahead  (local commits not pushed)    -> "git-ahead"   (green)
  clean  (in sync, nothing to do)      -> "git-clean"   (white)

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
gi.require_version('Gtk', '3.0')
from gi.repository import Nautilus, GObject, GLib, Gio, Gtk  # noqa: E402


GIT_BIN = 'git'
GIT_TIMEOUT_SEC = 2


class GitEmblemsProvider(GObject.GObject,
                         Nautilus.InfoProvider,
                         Nautilus.PropertyPageProvider,
                         Nautilus.MenuProvider):
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

    # ---- Properties dialog: "Git" tab --------------------------------------

    def get_property_pages(self, files):
        if len(files) != 1:
            return []
        f = files[0]
        if f.get_uri_scheme() != 'file' or not f.is_directory():
            return []
        path = unquote(urlparse(f.get_uri()).path)
        if not os.path.exists(os.path.join(path, '.git')):
            return []

        info = self._gather_git_info(path)
        page = self._build_property_page(info)
        page.show_all()
        label = Gtk.Label(label='Git')
        label.show()
        return [Nautilus.PropertyPage(
            name='GitEmblems::git', label=label, page=page,
        )]

    def _gather_git_info(self, path):
        info = {
            'branch': None, 'upstream': None,
            'ahead': 0, 'behind': 0,
            'staged': 0, 'modified': 0, 'untracked': 0, 'unmerged': 0,
            'origin_url': None, 'last_commit': None,
        }
        out = self._run_git(path, ['status', '--porcelain=v2', '--branch'])
        for line in out.splitlines():
            if line.startswith('# branch.head '):
                info['branch'] = line[len('# branch.head '):].strip()
            elif line.startswith('# branch.upstream '):
                info['upstream'] = line[len('# branch.upstream '):].strip()
            elif line.startswith('# branch.ab '):
                parts = line.split()
                try:
                    info['ahead'] = int(parts[2].lstrip('+'))
                    info['behind'] = int(parts[3].lstrip('-'))
                except (IndexError, ValueError):
                    pass
            elif line.startswith('1 ') or line.startswith('2 '):
                # "<XY> ..." — X is index status, Y is worktree status.
                fields = line.split(None, 2)
                if len(fields) >= 2 and len(fields[1]) >= 2:
                    if fields[1][0] != '.':
                        info['staged'] += 1
                    if fields[1][1] != '.':
                        info['modified'] += 1
            elif line.startswith('? '):
                info['untracked'] += 1
            elif line.startswith('u '):
                info['unmerged'] += 1

        url = self._run_git(path, ['remote', 'get-url', 'origin']).strip()
        info['origin_url'] = url or None
        last = self._run_git(
            path, ['log', '-1', '--pretty=format:%s  —  %cr'],
        ).strip()
        info['last_commit'] = last or None
        return info

    def _run_git(self, path, args):
        try:
            return subprocess.check_output(
                [GIT_BIN, '-C', path] + args,
                stderr=subprocess.DEVNULL, timeout=GIT_TIMEOUT_SEC,
            ).decode('utf-8', 'replace')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError):
            return ''

    # ---- Right-click menu --------------------------------------------------

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        f = files[0]
        if f.get_uri_scheme() != 'file' or not f.is_directory():
            return []
        path = unquote(urlparse(f.get_uri()).path)
        if not os.path.exists(os.path.join(path, '.git')):
            return []

        info = self._gather_git_info(path)
        top = Nautilus.MenuItem(
            name='GitEmblems::menu',
            label='Git — ' + self._menu_headline(info),
            tip='Git status for this repo',
        )
        submenu = Nautilus.Menu()
        for it in self._build_menu_items(info):
            submenu.append_item(it)
        top.set_submenu(submenu)
        return [top]

    def get_background_items(self, file):
        # Right-click on the folder background of an already-open repo.
        return self.get_file_items([file])

    def _menu_headline(self, info):
        branch = info['branch'] or '—'
        n_changed = info['staged'] + info['modified'] + info['untracked'] + info['unmerged']
        if n_changed:
            noun = 'change' if n_changed == 1 else 'changes'
            return f'dirty — {n_changed} {noun} ({branch})'
        if info['behind'] and info['ahead']:
            return f'↑{info["ahead"]} ↓{info["behind"]} ({branch})'
        if info['behind']:
            return f'↓{info["behind"]} behind ({branch})'
        if info['ahead']:
            return f'↑{info["ahead"]} ahead ({branch})'
        return f'clean ({branch})'

    def _build_menu_items(self, info):
        rows = []
        rows.append(('branch', f'Branch: {info["branch"] or "(unknown)"}'))
        if info['upstream']:
            up = info['upstream']
            if info['ahead'] or info['behind']:
                up += f'  (↑{info["ahead"]} ↓{info["behind"]})'
            rows.append(('upstream', f'Upstream: {up}'))
        parts = []
        if info['staged']:    parts.append(f'{info["staged"]} staged')
        if info['modified']:  parts.append(f'{info["modified"]} modified')
        if info['untracked']: parts.append(f'{info["untracked"]} untracked')
        if info['unmerged']:  parts.append(f'{info["unmerged"]} unmerged')
        rows.append(('status', 'Status: ' + (', '.join(parts) if parts else 'clean')))
        if info['origin_url']:
            rows.append(('origin', f'Origin: {info["origin_url"]}'))
        if info['last_commit']:
            rows.append(('last', f'Last commit: {info["last_commit"]}'))

        items = []
        for key, label in rows:
            it = Nautilus.MenuItem(name=f'GitEmblems::menu::{key}', label=label)
            # Display-only: not actionable, but kept enabled so the text
            # renders at full contrast rather than dimmed-out gray.
            items.append(it)
        return items

    # ---- Properties dialog page builder ------------------------------------

    def _build_property_page(self, info):
        # Status line — same priority as the emblem.
        if info['staged'] or info['modified'] or info['untracked'] or info['unmerged']:
            status = 'Dirty'
            parts = []
            if info['staged']:    parts.append(f"{info['staged']} staged")
            if info['modified']:  parts.append(f"{info['modified']} modified")
            if info['untracked']: parts.append(f"{info['untracked']} untracked")
            if info['unmerged']:  parts.append(f"{info['unmerged']} unmerged")
            status += '  —  ' + ', '.join(parts)
        elif info['behind']:
            status = f"Behind upstream by {info['behind']}"
        elif info['ahead']:
            status = f"Ahead of upstream by {info['ahead']}"
        else:
            status = 'Clean'

        rows = [('Status', status), ('Branch', info['branch'] or '(unknown)')]
        if info['upstream']:
            up = info['upstream']
            if info['ahead'] or info['behind']:
                up += f"  (ahead {info['ahead']}, behind {info['behind']})"
            rows.append(('Upstream', up))
        if info['origin_url']:
            rows.append(('Origin', info['origin_url']))
        if info['last_commit']:
            rows.append(('Last commit', info['last_commit']))

        grid = Gtk.Grid(
            column_spacing=18, row_spacing=8,
            margin_start=18, margin_end=18,
            margin_top=18, margin_bottom=18,
        )
        for r, (key, val) in enumerate(rows):
            k = Gtk.Label(label=key, xalign=0.0)
            k.get_style_context().add_class('dim-label')
            v = Gtk.Label(label=val, xalign=0.0, selectable=True)
            v.set_line_wrap(True)
            v.set_line_wrap_mode(2)  # PANGO_WRAP_WORD_CHAR
            grid.attach(k, 0, r, 1, 1)
            grid.attach(v, 1, r, 1, 1)
        return grid
