# Pure file-selection rules (no Kodi imports, so they can be tested offline).
# Every function only RETURNS paths; deleting happens in cleaner.py.
import os
import re
import time

DAY = 86400
# Log files Kodi itself manages (rotated on every start). On Android/Linux they live in temp.
PROTECTED_LOG = re.compile(r"^kodi(\.old)?\.log$", re.I)
CRASHLOG = re.compile(r"^kodi_(crashlog|stacktrace)[^/]*\.(log|txt)$", re.I)
# Files add-ons may still have open (e.g. common plugin cache's commoncache.db in temp).
PROTECTED_EXT = (".db", ".db-journal", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".lock", ".pid")


def inside(child, parent):
    """True if `child` is `parent` or below it (after resolving symlinks)."""
    c, p = os.path.realpath(child), os.path.realpath(parent)
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def _files(folder, recursive=False):
    if not os.path.isdir(folder):
        return
    if recursive:
        for root, _dirs, names in os.walk(folder):
            for n in names:
                yield os.path.join(root, n)
    else:
        for n in os.listdir(folder):
            p = os.path.join(folder, n)
            if os.path.isfile(p):
                yield p


def _older_than(path, seconds, now):
    try:
        return now - os.path.getmtime(path) > seconds
    except OSError:
        return False


def old_packages(packages_dir, min_age_hours=24, now=None):
    """Add-on zip backups Kodi keeps after installs/updates (addons/packages/*.zip)."""
    now = now or time.time()
    return [p for p in _files(packages_dir)
            if p.lower().endswith(".zip") and _older_than(p, min_age_hours * 3600, now)]


def old_temp_files(temp_dir, min_age_hours=24, now=None):
    """Leftovers in special://temp, never Kodi's own log files."""
    now = now or time.time()
    out = []
    for p in _files(temp_dir, recursive=True):
        name = os.path.basename(p)
        if PROTECTED_LOG.match(name) or name.lower().endswith(PROTECTED_EXT):
            continue
        if _older_than(p, min_age_hours * 3600, now):
            out.append(p)
    return out


def old_crashlogs(folders, max_age_days=14, now=None):
    """kodi_crashlog-*.log / kodi_stacktrace-* older than max_age_days."""
    now = now or time.time()
    out = []
    for folder in folders:
        for p in _files(folder):
            if CRASHLOG.match(os.path.basename(p)) and _older_than(p, max_age_days * DAY, now):
                out.append(p)
    return out


def is_due(last_run, interval_days, now=None):
    now = now or time.time()
    return not last_run or now - last_run >= interval_days * DAY


def texture_cutoff(max_age_days, now=None):
    """'YYYY-MM-DD HH:MM:SS' for the Textures.GetTextures lastused filter.
    Kodi stores lastused in UTC (verified on 21.3: a texture used at 19:02 EST reads 00:02)."""
    now = now or time.time()
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(now - max_age_days * DAY))
