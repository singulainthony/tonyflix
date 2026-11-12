#!/usr/bin/env python3
"""Offline tests for service.tonyflix.maintenance file rules (no Kodi needed).

Builds a throwaway folder tree with back-dated files and checks exactly which
paths each rule selects for deletion. Usage: python3 tools/test_maintenance_rules.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addons" / "service.tonyflix.maintenance" / "resources" / "lib"))
from tfmaint import rules  # noqa: E402

NOW = time.time()
DAY = 86400
fails = 0


def make(path, age_days, content="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    t = NOW - age_days * DAY
    os.utime(path, (t, t))
    return str(path)


def check(label, got, want):
    global fails
    ok = sorted(map(os.path.basename, got)) == sorted(want)
    fails += not ok
    print(f"{'ok ' if ok else 'BAD'} {label}: {sorted(map(os.path.basename, got))}" + ("" if ok else f"  (want {sorted(want)})"))


def main():
    base = Path(tempfile.mkdtemp())
    home, outside = base / ".kodi", base / "shared-logs"
    pk, tmp = home / "addons" / "packages", home / "temp"

    make(pk / "old-addon-1.0.zip", 3)
    make(pk / "fresh-addon-2.0.zip", 0.1)
    make(pk / "notes.txt", 30)
    check("packages: only zips older than a day", rules.old_packages(str(pk), now=NOW), ["old-addon-1.0.zip"])

    make(tmp / "kodi.log", 10)
    make(tmp / "kodi.old.log", 10)
    make(tmp / "commoncache.db", 10)
    make(tmp / "commoncache.db-journal", 10)
    make(tmp / "archive_cache" / "old-extract.bin", 5)
    make(tmp / "stale-download.tmp", 2)
    make(tmp / "just-written.tmp", 0.01)
    check("temp: old files, never kodi logs / databases / fresh files", rules.old_temp_files(str(tmp), now=NOW),
          ["old-extract.bin", "stale-download.tmp"])

    make(home / "kodi_crashlog-20261001_120000.log", 40)
    make(home / "kodi_crashlog-20261110_120000.log", 1)
    make(home / "kodi_stacktrace-20261001.txt", 40)
    make(home / "kodi.log", 40)
    make(home / "my_notes.log", 40)
    check("crash logs: only kodi_crashlog/stacktrace older than 14 days", rules.old_crashlogs([str(home)], now=NOW),
          ["kodi_crashlog-20261001_120000.log", "kodi_stacktrace-20261001.txt"])

    outside.mkdir(parents=True)
    (home / "linked-temp").symlink_to(outside)
    global fails
    cases = {
        "inside: temp under home": rules.inside(str(tmp), str(home)) is True,
        "inside: home itself": rules.inside(str(home), str(home)) is True,
        "inside: shared folder is NOT inside": rules.inside(str(outside), str(home)) is False,
        "inside: symlink escaping home is NOT inside": rules.inside(str(home / "linked-temp"), str(home)) is False,
        "inside: sibling with same prefix is NOT inside": rules.inside(str(base / ".kodi-other"), str(home)) is False,
        "is_due: never run": rules.is_due(None, 7, now=NOW) is True,
        "is_due: 3 days ago (weekly)": rules.is_due(NOW - 3 * DAY, 7, now=NOW) is False,
        "is_due: 8 days ago (weekly)": rules.is_due(NOW - 8 * DAY, 7, now=NOW) is True,
        "texture_cutoff format": len(rules.texture_cutoff(30, now=NOW)) == 19,
        "texture_cutoff is UTC": rules.texture_cutoff(0, now=NOW) == time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW)),
    }
    for k, v in cases.items():
        fails += not v
        print(f"{'ok ' if v else 'BAD'} {k}")
    print("FAILED" if fails else "ALL PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
