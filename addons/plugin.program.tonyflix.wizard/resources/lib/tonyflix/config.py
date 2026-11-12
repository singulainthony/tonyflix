# Applying TonyFlix configuration to installed add-ons: TMDbHelper player files,
# hidden bundled players, and add-on default settings (resources/data/defaults.json).
import json
import os
import re
import shutil

import xbmc
import xbmcaddon
import xbmcvfs

from tonyflix.installer import DATA, is_installed, log

TMDBH = "plugin.video.themoviedb.helper"


def _tmdbh_data(sub):
    path = xbmcvfs.translatePath(f"special://profile/addon_data/{TMDBH}/{sub}/")
    os.makedirs(path, exist_ok=True)
    return path


def install_players(report):
    """Copy TonyFlix player files and hide TMDbHelper's bundled extras (UPnP, YouTube...)."""
    if not is_installed(TMDBH):
        report.append("players: TMDbHelper not installed - skipped")
        return
    src = os.path.join(DATA, "players")
    dst = _tmdbh_data("players")
    for name in sorted(os.listdir(src)):
        if name.endswith(".json"):
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
            report.append(f"player {name}")
    bundled = xbmcvfs.translatePath(f"special://home/addons/{TMDBH}/resources/players/")
    reconf = _tmdbh_data("reconfigured_players")
    with open(os.path.join(src, "disable_bundled.txt"), encoding="utf-8") as f:
        names = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    for name in names:
        path = os.path.join(bundled, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        try:
            data = json.loads(raw)
        except ValueError:
            data = json.loads(re.sub(r"//.*", "", raw))
        data["disabled"] = "true"
        with open(os.path.join(reconf, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        report.append(f"hid bundled player {name}")


def apply_addon_defaults(report):
    """One setting at a time, one add-on at a time (parallel setSetting calls clobber each other)."""
    with open(os.path.join(DATA, "defaults.json"), encoding="utf-8") as f:
        defaults = json.load(f)
    for aid, settings in defaults.items():
        if aid.startswith("_") or not isinstance(settings, dict):
            continue
        if not is_installed(aid):
            report.append(f"defaults: {aid} not installed - skipped")
            continue
        addon = xbmcaddon.Addon(aid)
        for sid, value in settings.items():
            if not sid.startswith("_"):
                addon.setSetting(sid, str(value))
                report.append(f"{aid}: {sid}")
    log(f"add-on defaults applied ({len(report)} items)")


def apply_all():
    report = []
    install_players(report)
    apply_addon_defaults(report)
    return report
