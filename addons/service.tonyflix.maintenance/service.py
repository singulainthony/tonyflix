# TonyFlix maintenance service: runs the cleanup every `interval_days` (default 7),
# only while nothing is playing and the box has been idle for a few minutes, so it
# never competes with browsing or playback. Runs sooner if the box is low on space.
import os
import sys

import xbmc
import xbmcaddon

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tfmaint import cleaner, rules  # noqa: E402

STARTUP_DELAY = 300   # leave the first minutes after boot alone
CHECK_EVERY = 600     # seconds between "is it time?" checks
IDLE_SECONDS = 180    # user must be idle this long


def main():
    monitor = xbmc.Monitor()
    state = cleaner.load_state()
    cleaner.log(f"service started (last run: {state.get('last_run', 'never')}; first check in {STARTUP_DELAY}s)")
    if monitor.waitForAbort(STARTUP_DELAY):
        return
    while not monitor.abortRequested():
        addon = xbmcaddon.Addon()
        enabled = addon.getSetting("enabled") != "false"
        interval = cleaner.setting_int("interval_days", 7)
        state = cleaner.load_state()
        free = cleaner.free_space_mb()
        due = rules.is_due(state.get("last_run"), interval) or (0 <= free < cleaner.LOW_SPACE_MB)
        idle = xbmc.getCondVisibility(f"System.IdleTime({IDLE_SECONDS})") and not xbmc.Player().isPlaying()
        if enabled and due and idle:
            report = cleaner.Cleaner(monitor).run()
            if addon.getSetting("notify") == "true" and not report["stopped"]:
                xbmc.executebuiltin(f"Notification(TonyFlix,{cleaner.summary(report).split(':')[0]},4000)")
        if monitor.waitForAbort(CHECK_EVERY):
            break


if __name__ == "__main__":
    main()
