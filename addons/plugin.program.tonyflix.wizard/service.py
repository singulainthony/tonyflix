# TonyFlix Wizard service.
#  * First run: right after the wizard is installed (or on the next Kodi start), offer setup once.
#  * Safety net: if a skin switch was interrupted, the TonyFlix menus may still be on hold - build them.
import os
import sys

import xbmc
import xbmcaddon

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tonyflix import setup  # noqa: E402


def wait_until_idle(monitor):
    """Don't interrupt anything: nothing playing and no dialog open."""
    while not monitor.abortRequested():
        if not xbmc.Player().isPlaying() and not xbmc.getCondVisibility("System.HasActiveModalDialog"):
            return True
        if monitor.waitForAbort(2):
            return False
    return False


def main():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(3):       # let Kodi finish starting / the zip install finish
        return
    if xbmc.getSkinDir() == setup.SKIN_ID and xbmc.getCondVisibility(f"Skin.HasSetting({setup.HOLD_MENU_BUILD})"):
        setup.build_menus(wait=False)
        return
    state = setup.load_setup()
    if state.get("done") or state.get("declined") or xbmc.getSkinDir() == setup.SKIN_ID:
        return
    if wait_until_idle(monitor):
        xbmc.executebuiltin("RunScript(plugin.program.tonyflix.wizard,setup)")


if __name__ == "__main__":
    main()
