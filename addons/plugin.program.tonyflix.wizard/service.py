# First-run prompt: after the wizard is installed on a fresh Kodi, offer setup once.
import os
import sys

import xbmc
import xbmcaddon

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tonyflix import setup  # noqa: E402


def main():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(12):    # let Kodi finish starting
        return
    state = setup.load_setup()
    if state.get("done") or state.get("declined") or xbmc.getSkinDir() == "skin.tonyflix":
        return
    # Don't interrupt anything: wait until nothing is playing and no dialog is open.
    while not monitor.abortRequested():
        if not xbmc.Player().isPlaying() and not xbmc.getCondVisibility("System.HasActiveModalDialog"):
            break
        if monitor.waitForAbort(5):
            return
    xbmc.executebuiltin("RunScript(plugin.program.tonyflix.wizard,setup)")


if __name__ == "__main__":
    main()
