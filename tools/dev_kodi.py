#!/usr/bin/env python3
"""Dev helper: run TonyFlix in the desktop Kodi WITHOUT touching your real profile.

  python3 tools/dev_kodi.py in  <test-profile-dir>   # back up real profile, put test profile in place
  python3 tools/dev_kodi.py out <test-profile-dir>   # quit Kodi, move test profile out, restore real profile
  python3 tools/dev_kodi.py sync                     # copy TonyFlix add-ons (skin, wizard) into the active test profile
  python3 tools/dev_kodi.py status

Safety rules: refuses to run while Kodi is running (except `out`, which asks
Kodi to quit first), refuses to overwrite an existing backup, and verifies the
restored profile's add-on count matches what was backed up. Kodi's log files
are saved and restored too, because every launch rotates them.
macOS paths; adjust PROFILE/LOGS for other systems.
"""
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
PROFILE = HOME / "Library" / "Application Support" / "Kodi"
BACKUP = PROFILE.with_name("Kodi.tonyflix-backup")
LOGS = HOME / "Library" / "Logs"
LOGFILES = ("kodi.log", "kodi.old.log")
MARKER = "_tonyflix_backup.json"
ROOT = Path(__file__).resolve().parent.parent
SKIN_SRC = ROOT / "addons" / "skin.tonyflix"
GENERATED = ("1080i/script-skinshortcuts-includes.xml", "1080i/script-skinviewtypes-includes.xml")


def kodi_running():
    return subprocess.run(["pgrep", "-x", "Kodi"], capture_output=True).returncode == 0


def rpc_quit():
    try:
        with socket.create_connection(("127.0.0.1", 9090), timeout=3) as s:
            s.sendall(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Application.Quit"}).encode())
    except OSError:
        pass
    for _ in range(40):
        if not kodi_running():
            return True
        time.sleep(1)
    return False


def addon_count(profile):
    return len([p for p in (profile / "addons").iterdir() if p.is_dir()]) if (profile / "addons").is_dir() else 0


def cmd_in(test):
    if kodi_running():
        sys.exit("Kodi is running - quit it first.")
    if BACKUP.exists():
        sys.exit(f"{BACKUP} already exists - a previous session was not restored. Run `out` first.")
    if not test.is_dir():
        sys.exit(f"test profile {test} not found")
    count = addon_count(PROFILE)
    PROFILE.rename(BACKUP)
    saved = BACKUP / "_saved_logs"
    saved.mkdir()
    for name in LOGFILES:
        if (LOGS / name).exists():
            shutil.copy2(LOGS / name, saved / name)
    (BACKUP / MARKER).write_text(json.dumps({"addons": count, "time": time.ctime()}))
    test.rename(PROFILE)
    print(f"Real profile ({count} add-ons) backed up to {BACKUP}; test profile active.")


def cmd_out(test):
    if not BACKUP.exists():
        sys.exit("No backup found - nothing to restore.")
    if kodi_running() and not rpc_quit():
        sys.exit("Kodi did not quit (a modal dialog may be open). Close it and retry.")
    if test.exists():
        sys.exit(f"{test} already exists - refusing to overwrite it")
    expected = json.loads((BACKUP / MARKER).read_text())["addons"]
    PROFILE.rename(test)
    saved = BACKUP / "_saved_logs"
    for name in LOGFILES:
        if (saved / name).exists():
            shutil.move(str(saved / name), LOGS / name)
    shutil.rmtree(saved, ignore_errors=True)
    (BACKUP / MARKER).unlink()
    BACKUP.rename(PROFILE)
    got = addon_count(PROFILE)
    status = "OK" if got == expected else f"MISMATCH (expected {expected})"
    print(f"Real profile restored: {got} add-ons - {status}. Test profile saved to {test}.")


def cmd_sync():
    if not BACKUP.exists():
        sys.exit("Test profile is not active (run `in` first) - refusing to touch the real profile.")
    sys.path.insert(0, str(ROOT / "tools"))
    from build_repo import load_config, sync_wizard_data
    sync_wizard_data(load_config())
    excludes = sum((["--exclude", g] for g in GENERATED), [])
    for src in sorted((ROOT / "addons").iterdir()):
        if not (src / "addon.xml").is_file() or src.name.startswith("repository."):
            continue
        dst = PROFILE / "addons" / src.name
        subprocess.run(["rsync", "-a", "--delete", *excludes, f"{src}/", f"{dst}/"], check=True)
        print(f"Synced {src.name} into test profile.")


def cmd_status():
    print(f"Kodi running: {kodi_running()}")
    print(f"Test profile active: {BACKUP.exists()}  (backup: {BACKUP})")
    print(f"Active profile add-ons: {addon_count(PROFILE)}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("in", "out", "sync", "status"):
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd in ("in", "out"):
        if len(sys.argv) != 3:
            sys.exit(f"usage: dev_kodi.py {cmd} <test-profile-dir>")
        (cmd_in if cmd == "in" else cmd_out)(Path(sys.argv[2]).expanduser().resolve())
    elif cmd == "sync":
        cmd_sync()
    else:
        cmd_status()


if __name__ == "__main__":
    main()
