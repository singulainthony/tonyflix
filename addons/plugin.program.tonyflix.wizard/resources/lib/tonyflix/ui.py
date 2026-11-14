# TonyFlix Wizard screens (resources/skins/Default/1080i/tonyflix-*.xml).
# They use only font13 and the wizard's own media, so they look the same under Estuary (first setup)
# and under the TonyFlix skin.
import threading
import time

import xbmc
import xbmcgui

from tonyflix import accounts, installer
from tonyflix.installer import log

PATH = installer.WIZARD.getAddonInfo("path")
BACK_ACTIONS = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)
GREEN, MUTED, DOT = "FF4ADE80", "FF8A8A94", "FF3A3A42"
# Kodi dialogs a person must see. If one stays open longer than the wizard needs to answer its own
# prompts, the setup cover steps aside (see SetupScreen._guard).
USER_DIALOGS = (10100, 12000, 12002, 10103, 10109)   # yes/no, select, ok, keyboard, numeric input


# ------------------------------------------------------------------ welcome

class Welcome(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.suggested = kwargs.get("suggested", "standard")
        self.profile = self.suggested
        self.result = None

    def onInit(self):
        self.setProperty(installer.OWN_WINDOW_PROPERTY, "1")
        self._refresh()
        self.setFocusId(300)

    def _refresh(self):
        rec = "   (recommended for this box)" if self.profile == self.suggested else ""
        self.getControl(301).setLabel(f"Speed setting:  [B]{self.profile.title()}[/B]{rec}")
        self.getControl(11).setLabel({
            "lite": "Fastest on budget boxes: 720p menus, smaller artwork, fewer rows. Select to switch.",
            "standard": "For 4 GB+ boxes: sharper menus and artwork, every row. Select to switch.",
        }[self.profile])

    def onClick(self, control_id):
        if control_id == 301:
            self.profile = "standard" if self.profile == "lite" else "lite"
            self._refresh()
        elif control_id == 300:
            self.result = self.profile
            self.close()
        elif control_id == 302:
            self.close()

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            self.close()


def ask_to_start(suggested):
    """The one question at the start of setup. Returns 'lite' / 'standard', or None for Not now."""
    w = Welcome("tonyflix-welcome.xml", PATH, "Default", "1080i", suggested=suggested)
    w.doModal()
    result = w.result
    del w
    return result


# ------------------------------------------------------------------ setup progress

class _Cover(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.ready = False

    def onInit(self):
        self.setProperty(installer.OWN_WINDOW_PROPERTY, "1")
        self.ready = True

    def onAction(self, action):
        pass      # never closes itself; keys belong to whatever Kodi prompt is open underneath


class SetupScreen:
    """Full-screen 'Setting up TonyFlix' cover. Shown modeless with a high zorder, so Kodi's install prompts
    (which the wizard answers itself) and progress boxes stay hidden underneath it. If a dialog a person
    must deal with stays open, the cover steps aside until it's gone."""

    def __init__(self):
        self.state = (0, "Starting...", "")
        self.win = None
        self.hidden = False
        self.stop = False
        self._open()
        self.thread = threading.Thread(target=self._guard, daemon=True)
        self.thread.start()

    def _open(self):
        w = _Cover("tonyflix-progress.xml", PATH, "Default", "1080i")
        w.show()
        end = time.time() + 3
        while not w.ready and time.time() < end:
            xbmc.sleep(50)
        self.win = w
        self._apply()

    def _close_window(self):
        if self.win:
            try:
                self.win.close()
            except RuntimeError:
                pass
            del self.win
            self.win = None

    def _apply(self):
        pct, step, detail = self.state
        try:
            self.win.getControl(20).setLabel(step)
            self.win.getControl(21).setWidth(max(1, int(800 * min(pct, 100) / 100)))
            self.win.getControl(22).setLabel(detail)
        except (RuntimeError, AttributeError):
            pass

    def update(self, pct, step, detail=""):
        self.state = (pct, step, detail)
        if not self.hidden:
            self._apply()

    def reopen(self):
        """After a skin change: Kodi closes python windows when it reloads the skin."""
        if not self.hidden:
            self._close_window()
            self._open()

    def _guard(self):
        open_since = None
        while not self.stop:
            dlg = xbmcgui.getCurrentWindowDialogId()
            if dlg in USER_DIALOGS:
                open_since = open_since or time.time()
                if not self.hidden and time.time() - open_since > 6:
                    log(f"setup screen steps aside for dialog {dlg}")
                    self.hidden = True
                    self._close_window()
            else:
                open_since = None
                if self.hidden:
                    self.hidden = False
                    self._open()
            xbmc.sleep(400)

    def close(self):
        self.stop = True
        self.thread.join(2)
        self._close_window()


# ------------------------------------------------------------------ accounts

class Accounts(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.accs = kwargs.get("accounts", [])
        self.intro = kwargs.get("intro")
        self.done_label = kwargs.get("done_label")

    def onInit(self):
        self.setProperty(installer.OWN_WINDOW_PROPERTY, "1")
        if self.intro:
            self.getControl(10).setLabel(self.intro)
        if self.done_label:
            self.getControl(200).setLabel(self.done_label)
        self.refresh()
        self.setFocusId(100)

    def refresh(self):
        lst = self.getControl(100)
        pos = max(0, lst.getSelectedPosition())
        lst.reset()
        for acc in self.accs:
            li = xbmcgui.ListItem(acc["name"], acc["why"])
            if not accounts.is_available(acc):
                props = {"status": f"[COLOR {MUTED}]Not installed[/COLOR]", "action": "",
                         "icon": "dot.png", "iconcolor": DOT}
            elif accounts.is_signed_in(acc):
                user = accounts.username(acc)
                props = {"status": f"[COLOR {GREEN}]Signed in{' as ' + user if user else ''}[/COLOR]",
                         "action": "Sign out", "icon": "check.png", "iconcolor": GREEN}
            else:
                props = {"status": f"[COLOR {MUTED}]Not signed in[/COLOR]", "action": "Sign in",
                         "icon": "dot.png", "iconcolor": DOT}
            li.setProperties(props)
            lst.addItem(li)
        lst.selectItem(min(pos, len(self.accs) - 1))

    def onClick(self, control_id):
        if control_id == 200:
            self.close()
            return
        if control_id != 100:
            return
        acc = self.accs[self.getControl(100).getSelectedPosition()]
        if not accounts.is_available(acc):
            return
        if accounts.is_signed_in(acc):
            # Trakt (TMDbHelper) asks "are you sure?" itself; the others don't.
            if acc["key"] == "trakt" or xbmcgui.Dialog().yesno(
                    "TonyFlix", f"Sign out of {acc['name']}?", nolabel="Cancel", yeslabel="Sign out"):
                accounts.sign_out(acc)
        else:
            accounts.sign_in(acc)
        self.refresh()

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            self.close()


def accounts_screen(accs, intro=None, done_label=None):
    w = Accounts("tonyflix-accounts.xml", PATH, "Default", "1080i",
                 accounts=accs, intro=intro, done_label=done_label)
    w.doModal()
    del w
    return {a["key"]: accounts.is_signed_in(a) for a in accs if accounts.is_available(a)}
