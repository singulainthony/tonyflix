# The TonyFlix setup flow: one welcome screen -> install (behind a full-screen progress cover) -> configure
# -> profile -> skin -> Accounts screen -> close Kodi.
import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

from tonyflix import config, installer, profiles, ui
from tonyflix.installer import InstallError, log

SETUP_FILE = os.path.join(xbmcvfs.translatePath(installer.WIZARD.getAddonInfo("profile")), "setup.json")
TITLE = "TonyFlix"
SKIN_ID = "skin.tonyflix"
HOLD_MENU_BUILD = "TonyFlix.HoldMenuBuild"
BUILD_MENUS = ("RunScript(script.skinshortcuts,type=buildxml&mainmenuID=300&levels=5"
               "&group=mainmenu|powermenu|searchmenu)")


def load_setup():
    try:
        with open(SETUP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_setup(**changes):
    state = load_setup()
    state.update(changes)
    os.makedirs(os.path.dirname(SETUP_FILE), exist_ok=True)
    with open(SETUP_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)


def is_android():
    return xbmc.getCondVisibility("System.Platform.Android")


def suggested_profile():
    cfg = profiles.load_profiles()
    return profiles.suggest_profile(profiles.detect_hardware(), cfg["detection"])


# ------------------------------------------------------------------ skin

def choose_profile(dialog):
    """Profile picker for the TonyFlix menu (setup itself asks on the welcome screen)."""
    suggested, reasons = suggested_profile()
    why = ", ".join(reasons) if reasons else "this box looks capable"
    items = [
        xbmcgui.ListItem("Lite" + ("  (recommended)" if suggested == "lite" else ""),
                         "Fastest on weak boxes: 720p menus, small artwork, 6 rows per tab"),
        xbmcgui.ListItem("Standard" + ("  (recommended)" if suggested == "standard" else ""),
                         "4 GB+ boxes: 1080p menus, sharper artwork, all rows"),
    ]
    idx = dialog.select(f"Speed setting - suggested: {suggested.title()} ({why})", items,
                        preselect=0 if suggested == "lite" else 1, useDetails=True)
    return None if idx < 0 else ("lite" if idx == 0 else "standard")


def build_menus(wait=True):
    """Let Skin Shortcuts build the TonyFlix menus. It writes its include file and then reloads the skin;
    a skin reload closes any window that is open (the wizard's screens too), so by default wait for it."""
    includes = xbmcvfs.translatePath("special://skin/1080i/script-skinshortcuts-includes.xml")

    def mtime():
        try:
            return os.path.getmtime(includes)
        except OSError:
            return 0

    before = mtime()
    xbmc.executebuiltin(f"Skin.Reset({HOLD_MENU_BUILD})")
    xbmc.executebuiltin(BUILD_MENUS)
    if not wait:
        return
    end = time.time() + 40
    while time.time() < end and mtime() <= before:
        if before and time.time() > end - 30:   # menus already existed and nothing changed: no reload coming
            return
        xbmc.sleep(300)
    xbmc.sleep(1500)                           # the reload follows the write
    end = time.time() + 20
    while time.time() < end and not xbmc.getCondVisibility("Window.IsActive(home)"):
        xbmc.sleep(300)
    xbmc.sleep(1500)
    log("menus built")


def switch_skin(skin_id=SKIN_ID, timeout=90):
    """Make TonyFlix the active skin, answering Kodi's 'switch to this skin?' / 'Keep skin?' prompts.

    While switching, TonyFlix is told not to build its menus (HOLD_MENU_BUILD): building them reloads the
    skin, and a reload while 'Keep skin?' is open closes it unanswered, so Kodi reverts. The menus are
    built right after the switch has stuck. Kodi sometimes offers the switch itself after installing a
    skin; we only request it after a few quiet seconds, because a second request while Kodi's own switch
    is loading also causes a revert."""
    if xbmc.getSkinDir() == skin_id:
        return True
    profiles.apply_skin([HOLD_MENU_BUILD], [], {})   # written to TonyFlix's settings file (not active yet)
    end = time.time() + timeout
    quiet_since = time.time()
    requests = 0
    while time.time() < end:
        if installer.answer_once("skin"):
            log(f"answered skin prompt; skin now {xbmc.getSkinDir()}")
            quiet_since = time.time()
            xbmc.sleep(500)
            continue
        if xbmc.getSkinDir() == skin_id:
            xbmc.sleep(2500)    # "Keep skin?" follows the switch
            if xbmcgui.getCurrentWindowDialogId() != installer.YESNO_DIALOG and xbmc.getSkinDir() == skin_id:
                build_menus()
                return True
            quiet_since = time.time()
            continue
        if xbmcgui.getCurrentWindowDialogId() == installer.YESNO_DIALOG:
            quiet_since = time.time()
        elif requests < 3 and time.time() - quiet_since > (3 if not requests else 5):
            log("requesting the skin switch")
            installer.jsonrpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": skin_id})
            requests += 1
            quiet_since = time.time()
        xbmc.sleep(400)
    log(f"switch_skin timed out; skin is {xbmc.getSkinDir()}")
    return xbmc.getSkinDir() == skin_id


def install_skin(skin):
    """The skin's dependencies one by one first, then the skin (retried once): Kodi resolves
    dependencies against its repo cache, which can be mid-refresh right after repos were added."""
    for dep in skin.get("requires", []):
        try:
            installer.install_from_repo(dep)
        except InstallError as e:
            log(f"skin dependency {dep}: {e} (Kodi will try again with the skin)")
    try:
        return installer.install_from_repo(skin["id"])
    except InstallError as e:
        log(f"skin install failed ({e}); retrying in 10s")
        xbmc.sleep(10000)
        return installer.install_from_repo(skin["id"])


# ------------------------------------------------------------------ setup

def full_setup():
    inst = installer.load_install()
    suggested, reasons = suggested_profile()
    log(f"suggested profile {suggested} ({', '.join(reasons) or 'capable box'})")
    profile = ui.ask_to_start(suggested)
    if not profile:
        save_setup(declined=True)
        return

    plan = ([(f"Adding {r['name']}", "repo", r) for r in inst["repositories"]] +
            [("Checking for the latest versions", "refresh", None)] +
            [(f"Installing {a['name']}", "addon", a) for a in inst["addons"]] +
            [(f"Installing {z['name']}", "zip", z) for z in inst["zip_addons"]] +
            [("Setting up players and add-ons", "config", None),
             (f"Tuning Kodi for this box ({profile.title()})", "profile", None),
             ("Installing the TonyFlix look", "skin", inst["skin"]),
             ("Switching to TonyFlix", "switch", inst["skin"])])
    problems = []
    screen = ui.SetupScreen()
    try:
        # Kodi's default "official repositories only" would install the OLD TMDbHelper 5.x from the
        # official Kodi repo instead of 6.x from jurialmunkey's repo (the skin needs 6.x).
        installer.jsonrpc("Settings.SetSettingValue", {"setting": "addons.updatemode", "value": 1})
        # Settings some add-ons need BEFORE their first start (before anything that depends on them installs).
        for a in inst["addons"]:
            if a.get("preseed") and not installer.setting_of(*a.get("preseed_unless_setting", [None, None])):
                installer.preseed_settings(a["id"], a["preseed"])
        for n, (label, kind, item) in enumerate(plan):
            screen.update(int(100 * n / len(plan)), label, f"Step {n + 1} of {len(plan)}")
            log(label)
            try:
                if kind == "repo":
                    installer.install_repository(item)
                    if item["id"] == "repository.tonyflix":     # the wizard itself came from a zip
                        installer.adopt_into_repository(installer.WIZARD.getAddonInfo("id"), item["id"])
                elif kind == "refresh":
                    installer.refresh_repositories([r["id"] for r in inst["repositories"]])
                elif kind == "addon":
                    installer.install_from_repo(item["id"])
                elif kind == "zip":
                    installer.install_zip_addon(item)
                elif kind == "config":
                    config.apply_all()
                elif kind == "profile":
                    profiles.apply_profile(profile)
                elif kind == "skin":
                    install_skin(item)
                elif kind == "switch":
                    if installer.is_installed(item["id"]):
                        if not switch_skin(item["id"]):
                            problems.append("couldn't switch to the TonyFlix look")
                        screen.reopen()      # Kodi closes python windows when it reloads the skin
            except InstallError as e:
                problems.append(f"{item['name'] if item else label}: {e}")
        screen.update(100, "Almost done", "")
    finally:
        screen.close()

    save_setup(done=True, declined=False, when=time.strftime("%Y-%m-%d %H:%M"), profile=profile, problems=problems)
    if problems:
        xbmcgui.Dialog().ok(TITLE, "Setup finished, but some parts didn't install:[CR]- " +
                            "[CR]- ".join(problems[:6]) +
                            "[CR][CR]Open TonyFlix > Run full setup again to retry them.")
    signed = ui.accounts_screen(
        inst["accounts"],
        intro="Last step: sign in so TonyFlix can play and remember what you watch. A code appears on the TV: "
              "enter it on your phone. You can also do this later from the power menu > Accounts.",
        done_label="Finish")
    save_setup(accounts={k: "yes" if v else "no" for k, v in signed.items()})
    finish()


def finish():
    """Settings like the GUI resolution only take effect after Kodi restarts. Kodi's RestartApp only works on
    Windows and Linux (Android reports Linux too), so elsewhere Kodi closes and you open it again."""
    restart = not is_android() and xbmc.getCondVisibility("System.Platform.Windows | System.Platform.Linux")
    screen = ui.SetupScreen()
    screen.update(100, "You're all set!",
                  "Kodi will restart now." if restart else "Kodi will close now. Open it again to start TonyFlix.")
    xbmc.sleep(4000)
    screen.close()
    xbmc.executebuiltin("RestartApp" if restart else "Quit")


def repair():
    """Re-apply TonyFlix configuration; sign-ins and your own settings are kept."""
    report = config.apply_all()
    profile = profiles.current_profile() or "auto"
    profiles.apply_profile(profile)
    xbmcgui.Dialog().notification(TITLE, f"Settings re-applied ({profile} profile)", time=4000)
    log(f"repair: {len(report)} items, {profile} profile")


def menu():
    dialog = xbmcgui.Dialog()
    state = load_setup()
    if not state.get("done"):
        full_setup()
        return
    options = [
        ("Accounts", "Trakt and Real-Debrid: sign in or out"),
        ("Speed setting", f"Now: {(profiles.current_profile() or '?').title()}. Lite or Standard"),
        ("Repair TonyFlix settings", "Re-apply players and add-on settings (keeps sign-ins)"),
        ("Clean up now", "Remove old thumbnails, package backups and temp files"),
        ("Run full setup again", "Reinstall anything missing"),
    ]
    items = [xbmcgui.ListItem(a, b) for a, b in options]
    idx = dialog.select("TonyFlix", items, useDetails=True)
    if idx == 0:
        ui.accounts_screen(installer.load_install()["accounts"])
    elif idx == 1:
        profile = choose_profile(dialog)
        if profile:
            profiles.apply_profile(profile)
            finish()
    elif idx == 2:
        repair()
    elif idx == 3:
        xbmc.executebuiltin("RunScript(service.tonyflix.maintenance)")
    elif idx == 4:
        full_setup()
