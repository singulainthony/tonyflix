# Account sign-in: TonyFlix only opens each add-on's own device-code sign-in
# (you approve on your phone at trakt.tv/activate or real-debrid.com/device).
# It never sees or stores passwords or tokens; it only checks whether sign-in happened.
import time

import xbmc
import xbmcaddon
import xbmcgui

from tonyflix.installer import is_installed, log

HOME = xbmcgui.Window(10000)
NO_DIALOG = 9999   # getCurrentWindowDialogId() when no dialog is open


def is_done(acc):
    if acc.get("done_if_property"):
        return bool(HOME.getProperty(acc["done_if_property"]))
    if acc.get("done_if_setting"):
        aid, sid = acc["done_if_setting"]
        try:
            return bool(xbmcaddon.Addon(aid).getSetting(sid))   # non-empty check only, value never logged
        except RuntimeError:
            return False
    return False


def sign_in(acc, timeout=600):
    """Open the add-on's sign-in and wait until it succeeds or the user closes it.
    Returns True / False / None (None = success can't be detected, e.g. Fen Light+)."""
    if not is_installed(acc["requires"]):
        return False
    xbmc.executebuiltin(acc["action"])
    monitor = xbmc.Monitor()
    saw_dialog, quiet_since = False, None
    end = time.time() + timeout
    while time.time() < end and not monitor.abortRequested():
        if is_done(acc):
            if acc.get("on_done"):
                xbmc.executebuiltin(acc["on_done"])
            log(f"{acc['key']}: signed in")
            return True
        dialog_up = xbmcgui.getCurrentWindowDialogId() != NO_DIALOG
        if dialog_up:
            saw_dialog, quiet_since = True, None
        elif saw_dialog:
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since > 4:   # the sign-in dialog was closed
                break
        elif time.time() > end - timeout + 20:   # no sign-in dialog appeared within 20 s
            break
        xbmc.sleep(500)
    if acc.get("done_if_property") or acc.get("done_if_setting"):
        ok = is_done(acc)
        if ok and acc.get("on_done"):
            xbmc.executebuiltin(acc["on_done"])
        return ok
    return None
