# TonyFlix maintenance: the actual cleanup, run by the service (weekly, when idle) or manually.
import json
import os
import shutil
import time

import xbmc
import xbmcaddon
import xbmcvfs

from tfmaint import rules

ADDON = xbmcaddon.Addon("service.tonyflix.maintenance")
STATE = os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")), "state.json")
TEXTURE_BATCH = 2000          # max textures removed per run (keeps a run short on slow boxes)
LOW_SPACE_MB = 500            # below this, run even if not due and use a shorter thumbnail age
LOW_SPACE_THUMB_DAYS = 7


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[TonyFlix maintenance] {msg}", level)


def path(special):
    return xbmcvfs.translatePath(special)


def jsonrpc(method, params):
    return json.loads(xbmc.executeJSONRPC(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})))


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def free_space_mb():
    try:
        return shutil.disk_usage(path("special://home/")).free // (1024 * 1024)
    except OSError:
        return -1


def setting_int(key, default):
    try:
        return int(ADDON.getSetting(key) or default)
    except ValueError:
        return default


class Cleaner:
    def __init__(self, monitor=None, progress=None):
        self.monitor = monitor or xbmc.Monitor()
        self.player = xbmc.Player()
        self.progress = progress      # callable(percent, text) or None
        self.report = {"textures": 0, "packages": 0, "temp": 0, "crashlogs": 0, "bytes": 0,
                       "stopped": "", "errors": []}

    # Stop as soon as the user starts watching something or Kodi is shutting down.
    def interrupted(self):
        if self.monitor.abortRequested():
            self.report["stopped"] = "Kodi exiting"
        elif self.player.isPlaying():
            self.report["stopped"] = "playback started"
        return bool(self.report["stopped"])

    def _step(self, pct, text):
        if self.progress:
            self.progress(pct, text)

    def _delete_files(self, files, key):
        for p in files:
            if self.interrupted():
                return
            try:
                size = os.path.getsize(p)
                os.remove(p)
                self.report[key] += 1
                self.report["bytes"] += size
            except OSError as e:
                self.report["errors"].append(f"{os.path.basename(p)}: {e}")

    def clean_textures(self, max_age_days):
        cutoff = rules.texture_cutoff(max_age_days)
        res = jsonrpc("Textures.GetTextures", {"properties": ["cachedurl"],
                                               "filter": {"field": "lastused", "operator": "lessthan", "value": cutoff}})
        textures = res.get("result", {}).get("textures", [])[:TEXTURE_BATCH]
        thumbs = path("special://thumbnails/")
        for i, tex in enumerate(textures):
            if i % 25 == 0:
                if self.interrupted():
                    return
                self._step(10 + int(60 * i / max(len(textures), 1)), f"Old thumbnails: {i}/{len(textures)}")
            cached = os.path.join(thumbs, tex.get("cachedurl", ""))
            size = os.path.getsize(cached) if tex.get("cachedurl") and os.path.isfile(cached) else 0
            # RemoveTexture deletes the database row AND the cached file - safe while Kodi runs.
            if jsonrpc("Textures.RemoveTexture", {"textureid": tex["textureid"]}).get("result") == "OK":
                self.report["textures"] += 1
                self.report["bytes"] += size

    def run(self, thumb_age_days=None):
        start = time.time()
        free_before = free_space_mb()
        low_space = 0 <= free_before < LOW_SPACE_MB
        thumb_days = setting_int("thumb_age_days", 30) if thumb_age_days is None else thumb_age_days
        if low_space:
            thumb_days = min(thumb_days, LOW_SPACE_THUMB_DAYS)
        log(f"starting (free {free_before} MB, thumbnails older than {thumb_days} days)")

        self._step(5, "Add-on package backups")
        self._delete_files(rules.old_packages(path("special://home/addons/packages/")), "packages")
        if not self.interrupted():
            self.clean_textures(thumb_days)
        home, temp = path("special://home/"), path("special://temp/")
        # Safety: only ever touch temp if it is Kodi's own folder (inside special://home),
        # never a shared system location.
        temp_ok = rules.inside(temp, home)
        if not temp_ok:
            self.report["errors"].append(f"temp folder {temp} is outside Kodi's home - skipped")
        if not self.interrupted() and temp_ok:
            self._step(75, "Temporary files")
            self._delete_files(rules.old_temp_files(temp), "temp")
        if not self.interrupted():
            self._step(90, "Old crash logs")
            folders = [home] + ([temp] if temp_ok else [])
            self._delete_files(rules.old_crashlogs(folders), "crashlogs")

        self.report.update(seconds=round(time.time() - start, 1), free_before_mb=free_before,
                           free_after_mb=free_space_mb(), thumb_age_days=thumb_days, low_space=low_space)
        state = load_state()
        if not self.report["stopped"]:
            state["last_run"] = time.time()
        state["last_report"] = self.report
        save_state(state)
        log(f"done: {self.report}")
        self._step(100, "Done")
        return self.report


def summary(report):
    mb = report["bytes"] / (1024 * 1024)
    text = (f"Freed {mb:.1f} MB: {report['textures']} old thumbnails, {report['packages']} package backups, "
            f"{report['temp']} temp files, {report['crashlogs']} crash logs.")
    if report["stopped"]:
        text += f" Stopped early ({report['stopped']}); the rest runs next time."
    return text
