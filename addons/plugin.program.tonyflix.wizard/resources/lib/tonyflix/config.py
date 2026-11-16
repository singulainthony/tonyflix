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


def hook_addon_players(report=None):
    """Player add-ons the user installed themselves (install.json 'addon_players') ship their own TMDbHelper
    player file: copy it into TMDbHelper (as the add-on's own "export player" option does) so it shows up in
    the Play list. Re-copied only when missing or changed."""
    from tonyflix.installer import load_install
    report = report if report is not None else []
    if not is_installed(TMDBH):
        return report
    for entry in load_install().get("addon_players", []):
        if not is_installed(entry["addon"]):
            continue
        src = os.path.join(xbmcvfs.translatePath(f"special://home/addons/{entry['addon']}/"), entry["file"])
        if not os.path.isfile(src):
            report.append(f"{entry['name']}: player file not found")
            continue
        dst = os.path.join(_tmdbh_data("players"), os.path.basename(src))
        with open(src, "rb") as f:
            data = f.read()
        if os.path.isfile(dst):
            with open(dst, "rb") as f:
                if f.read() == data:
                    continue
        with open(dst, "wb") as f:
            f.write(data)
        report.append(f"player {entry['name']} (from the add-on)")
        log(f"added {entry['name']} to the Play list")
    return report


def defaults_version():
    with open(os.path.join(DATA, "defaults.json"), encoding="utf-8") as f:
        return json.load(f).get("_version", 1)


def sync_skin_flags(report):
    """TonyFlix.DefaultPlayer: shows the skin's "Play with..." button only when Play has a default player."""
    from tonyflix import profiles
    has_default = is_installed(TMDBH) and bool(xbmcaddon.Addon(TMDBH).getSetting("default_player_movies"))
    flag = ["TonyFlix.DefaultPlayer"]
    profiles.apply_skin(flag if has_default else [], [] if has_default else flag, {})
    report.append(f"skin: default player {'set' if has_default else 'none (Play asks)'}")


def retire(report):
    """Add-ons TonyFlix no longer uses (install.json 'retired'): remove their TMDbHelper player files and
    DISABLE the add-ons. Disabling is reversible and keeps their settings and sign-ins."""
    from tonyflix.installer import is_enabled, jsonrpc, load_install
    retired = load_install().get("retired", {})
    if is_installed(TMDBH):
        players = _tmdbh_data("players")
        for name in retired.get("players", []):
            path = os.path.join(players, name)
            if os.path.exists(path):
                os.remove(path)
                report.append(f"removed player {name}")
    for aid in retired.get("addons", []):
        if is_installed(aid) and is_enabled(aid):
            jsonrpc("Addons.SetAddonEnabled", {"addonid": aid, "enabled": False})
            report.append(f"disabled {aid}")
    if any(r.startswith(("removed", "disabled")) for r in report):
        log("retired: " + ", ".join(r for r in report if r.startswith(("removed", "disabled"))))


def apply_all():
    report = []
    retire(report)
    install_players(report)
    hook_addon_players(report)
    apply_addon_defaults(report)
    sync_skin_flags(report)
    return report
