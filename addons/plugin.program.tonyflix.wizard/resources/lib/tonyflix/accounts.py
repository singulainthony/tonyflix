# Accounts: TonyFlix only opens each add-on's own device-code sign-in (you approve on your phone at
# trakt.tv/activate or real-debrid.com/device) and its own sign-out. It never sees or stores passwords or
# tokens: it only checks whether a sign-in exists (non-empty check; values are never logged).
import time

import xbmc
import xbmcaddon
import xbmcgui

from tonyflix.installer import is_installed, log, other_dialog_open

HOME = xbmcgui.Window(10000)
NO_DIALOG = 9999   # getCurrentWindowDialogId() when no dialog is open


def _read(source):
    """Value of a {"property": ...} or {"setting": [addon, id]} source, '' if unset or 'empty'."""
    if not source:
        return ""
    if source.get("property"):
        value = HOME.getProperty(source["property"])
    else:
        aid, sid = source["setting"]
        try:
            value = xbmcaddon.Addon(aid).getSetting(sid)
        except RuntimeError:     # add-on not installed / disabled
            value = ""
    return "" if value in source.get("empty", []) else value


def is_available(acc):
    return is_installed(acc["requires"])


def is_signed_in(acc):
    return bool(_read(acc["status"]))


def username(acc):
    return _read(acc.get("username"))


def sign_in(acc, timeout=600):
    """Open the add-on's sign-in and wait until it succeeds or the user closes it. Returns True/False."""
    if not is_available(acc):
        return False
    xbmc.executebuiltin(acc["sign_in"])
    monitor = xbmc.Monitor()
    saw_dialog, quiet_since = False, None
    started = time.time()
    while time.time() - started < timeout and not monitor.abortRequested():
        if is_signed_in(acc):
            _after_sign_in(acc)
            log(f"{acc['key']}: signed in")
            return True
        if other_dialog_open():
            saw_dialog, quiet_since = True, None
        elif saw_dialog:
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since > 4:    # the sign-in dialog was closed without signing in
                break
        elif time.time() - started > 20:         # no sign-in dialog appeared at all
            break
        xbmc.sleep(500)
    ok = is_signed_in(acc)
    if ok:
        _after_sign_in(acc)
    return ok


def _after_sign_in(acc):
    if acc.get("on_sign_in"):
        xbmc.executebuiltin(acc["on_sign_in"])
    window = acc.get("close_after_sign_in")
    if window:   # e.g. Umbrella opens its settings page after signing in; close it again
        end = time.time() + 6
        while time.time() < end:
            if xbmc.getCondVisibility(f"Window.IsActive({window})"):
                xbmc.sleep(300)
                xbmc.executebuiltin(f"Dialog.Close({window},true)")
                break
            xbmc.sleep(250)


def sign_out(acc, timeout=20):
    """Sign out through the add-on itself. Returns True when the sign-in is gone."""
    if not is_signed_in(acc):
        return True
    spec = acc.get("sign_out_settings")
    if spec:
        guard = spec.get("guard_property")
        if guard:
            HOME.setProperty(guard, "false")
        addon = xbmcaddon.Addon(spec["addon"])
        for sid in spec["clear"]:        # one at a time: parallel setSetting calls clobber each other
            addon.setSetting(sid, "")
        if guard:
            HOME.setProperty(guard, "true")
    else:
        xbmc.executebuiltin(acc["sign_out"])
    end = time.time() + timeout
    saw_dialog, quiet_since = False, None
    while time.time() < end and is_signed_in(acc):
        if other_dialog_open():
            saw_dialog, quiet_since = True, None
        elif saw_dialog:      # the add-on asked "are you sure?" and the answer was no
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since > 2:
                break
        xbmc.sleep(400)
    done = not is_signed_in(acc)
    if done and acc.get("on_sign_out"):
        xbmc.executebuiltin(acc["on_sign_out"])
    log(f"{acc['key']}: {'signed out' if done else 'still signed in'}")
    return done
