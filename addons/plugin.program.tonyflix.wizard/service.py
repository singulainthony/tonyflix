# TonyFlix Wizard service.
#  * First run: right after the wizard is installed (or on the next Kodi start), offer setup once.
#  * Safety net: if a skin switch was interrupted, the TonyFlix menus may still be on hold - build them.
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tonyflix import config, setup  # noqa: E402
from tonyflix.installer import log  # noqa: E402


def wait_until_idle(monitor):
    """Don't interrupt anything: nothing playing and no dialog open."""
    while not monitor.abortRequested():
        if not xbmc.Player().isPlaying() and not xbmc.getCondVisibility("System.HasActiveModalDialog"):
            return True
        if monitor.waitForAbort(2):
            return False
    return False


def sync_on_start():
    """Cheap checks at every Kodi start on a set-up box."""
    from tonyflix import installer
    # Trakt rows follow the real sign-in, wherever it was made (Accounts screen or TMDbHelper's own settings).
    if xbmc.getSkinDir() == setup.SKIN_ID:
        linked = bool(installer.setting_of("script.module.tmdbhelper.sync.trakt", "token"))
        xbmc.executebuiltin(f"Skin.{'SetBool' if linked else 'Reset'}(TonyFlix.TraktLinked)")
    # A player add-on installed since last time (e.g. TMDb Movies): add it to the Play list.
    config.hook_addon_players()


def main():
    monitor = xbmc.Monitor()
    if monitor.waitForAbort(3):       # let Kodi finish starting / the zip install finish
        return
    if xbmc.getSkinDir() == setup.SKIN_ID and xbmc.getCondVisibility(f"Skin.HasSetting({setup.HOLD_MENU_BUILD})"):
        setup.build_menus(wait=False)
        return
    state = setup.load_setup()
    if state.get("done"):
        sync_on_start()
        # An update changed TonyFlix's add-on settings (e.g. the default player): apply them once, quietly.
        wanted = config.defaults_version()
        if state.get("defaults_version") != wanted and not monitor.waitForAbort(20) and wait_until_idle(monitor):
            from tonyflix import installer
            problems = setup.install_missing(installer.load_install())
            report = config.apply_all()
            setup.save_setup(defaults_version=wanted)
            log(f"TonyFlix settings v{wanted} applied after an update ({len(report)} items)")
            if problems:
                log("update problems: " + "; ".join(problems))
                xbmcgui.Dialog().notification("TonyFlix", "Some add-ons couldn't be added. Power menu > TonyFlix > "
                                              "Run full setup again.", time=8000)
        return
    if state.get("declined") or xbmc.getSkinDir() == setup.SKIN_ID:
        return
    if wait_until_idle(monitor):
        xbmc.executebuiltin("RunScript(plugin.program.tonyflix.wizard,setup)")


if __name__ == "__main__":
    main()
