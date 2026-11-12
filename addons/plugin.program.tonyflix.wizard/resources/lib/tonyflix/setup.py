# The TonyFlix setup flow: install -> configure -> profile -> skin -> accounts -> restart.
import json
import os
import time

import xbmc
import xbmcgui
import xbmcvfs

from tonyflix import accounts, config, installer, profiles
from tonyflix.installer import InstallError, log

SETUP_FILE = os.path.join(xbmcvfs.translatePath(installer.WIZARD.getAddonInfo("profile")), "setup.json")
TITLE = "TonyFlix"


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


# ------------------------------------------------------------------ steps

def choose_profile(dialog):
    cfg = profiles.load_profiles()
    hw = profiles.detect_hardware()
    suggested, reasons = profiles.suggest_profile(hw, cfg["detection"])
    why = ", ".join(reasons) if reasons else "this box looks capable"
    items = [
        xbmcgui.ListItem("Lite" + ("  (recommended)" if suggested == "lite" else ""),
                         "Fastest on weak boxes: 720p menus, small artwork, 6 rows per tab"),
        xbmcgui.ListItem("Standard" + ("  (recommended)" if suggested == "standard" else ""),
                         "4 GB+ boxes: 1080p menus, sharper artwork, all rows"),
    ]
    idx = dialog.select(f"Performance profile - suggested: {suggested.title()} ({why})", items,
                        preselect=0 if suggested == "lite" else 1, useDetails=True)
    return None if idx < 0 else ("lite" if idx == 0 else "standard")


def switch_skin(skin_id, timeout=120):
    """Make TonyFlix the active skin, answering Kodi's 'switch to this skin?' / 'Keep skin?' prompts.
    Kodi usually starts the switch itself after installing the skin. Only if nothing happens for a
    while do we request it - never while Kodi's own switch may still be loading: a second request
    reloads the skin, which closes 'Keep skin?' unanswered and makes Kodi revert."""
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
                return True
            quiet_since = time.time()
            continue
        if xbmcgui.getCurrentWindowDialogId() == installer.YESNO_DIALOG:
            quiet_since = time.time()
        # 20 s before the first request (Kodi may be switching on its own); 5 s after a revert. On a
        # brand-new install the first TonyFlix load always reverts: Skin Shortcuts builds the menus and
        # reloads the skin, which closes 'Keep skin?'. The second load (menus built) sticks.
        elif requests < 3 and time.time() - quiet_since > (5 if requests else 20):
            log("requesting the skin switch")
            installer.jsonrpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": skin_id})
            requests += 1
            quiet_since = time.time()
        xbmc.sleep(500)
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


def full_setup():
    dialog = xbmcgui.Dialog()
    inst = installer.load_install()
    if not dialog.yesno(TITLE, "Set up TonyFlix on this box?[CR][CR]This installs the TonyFlix skin, TMDbHelper, "
                               "Umbrella, Fen Light+ and subtitles from their official sources, tunes Kodi for this "
                               "hardware, then helps you sign in to Trakt and Real-Debrid. Takes a few minutes.",
                        nolabel="Not now", yeslabel="Set up"):
        save_setup(declined=True)
        return
    profile = choose_profile(dialog)
    if not profile:
        return

    problems = []
    bar = xbmcgui.DialogProgressBG()
    bar.create(TITLE, "Starting...")
    steps = len(inst["repositories"]) + len(inst["zip_addons"]) + len(inst["addons"]) + 4
    n = 0

    def step(msg):
        nonlocal n
        n += 1
        bar.update(int(100 * n / steps), TITLE, msg)
        log(msg)

    try:
        # Kodi's default "official repositories only" would install the OLD TMDbHelper 5.x from the
        # official Kodi repo instead of 6.x from jurialmunkey's repo (the skin needs 6.x).
        installer.jsonrpc("Settings.SetSettingValue", {"setting": "addons.updatemode", "value": 1})
        for repo in inst["repositories"]:
            step(f"Adding repository: {repo['name']}")
            try:
                installer.install_repository(repo)
            except InstallError as e:
                problems.append(f"{repo['name']}: {e}")
        step("Refreshing repositories")
        installer.refresh_repositories()
        for a in inst["addons"]:
            step(f"Installing {a['name']}")
            try:
                installer.install_from_repo(a["id"])
            except InstallError as e:
                problems.append(f"{a['name']}: {e}")
        # After the repo add-ons: they bring in shared modules (requests) Fen Light+ needs.
        for entry in inst["zip_addons"]:
            step(f"Installing {entry['name']}")
            try:
                installer.install_zip_addon(entry)
            except InstallError as e:
                problems.append(f"{entry['name']}: {e}")
        step("Configuring players and add-ons")
        config.apply_all()
        step(f"Applying the {profile.title()} profile")
        profiles.apply_profile(profile)
        step("Installing the TonyFlix skin")
        try:
            install_skin(inst["skin"])
            if not switch_skin(inst["skin"]["id"]):
                problems.append("could not switch to the TonyFlix skin")
        except InstallError as e:
            problems.append(f"skin: {e}")
    finally:
        bar.close()

    save_setup(done=True, declined=False, when=time.strftime("%Y-%m-%d %H:%M"), profile=profile, problems=problems)
    if problems:
        dialog.ok(TITLE, "Setup finished with problems:[CR]- " + "[CR]- ".join(problems[:6]) +
                  "[CR][CR]You can run the wizard again to retry.")
    account_setup(inst)
    finish()


def account_setup(inst):
    dialog = xbmcgui.Dialog()
    results = {}
    for acc in inst["accounts"]:
        if accounts.is_done(acc):
            results[acc["key"]] = True
            continue
        ask = (f"Sign in to {acc['name']} now?[CR]{acc['why']}.[CR][CR]A code will appear - enter it on your phone. "
               f"TonyFlix never sees your password.")
        if not dialog.yesno(TITLE, ask, nolabel="Later", yeslabel="Sign in"):
            results[acc["key"]] = "skipped"
            continue
        results[acc["key"]] = accounts.sign_in(acc)
    save_setup(accounts={k: ("yes" if v is True else "no" if v is False else str(v)) for k, v in results.items()})
    return results


def can_restart():
    # Kodi's RestartApp builtin is only implemented on Windows and Linux (Android reports Linux too,
    # so is_android() is checked first by the caller).
    return xbmc.getCondVisibility("System.Platform.Windows | System.Platform.Linux")


def finish():
    dialog = xbmcgui.Dialog()
    if is_android() or not can_restart():
        dialog.ok(TITLE, "All done! Kodi will now close so every setting takes effect.[CR]Open Kodi again to start TonyFlix.")
        xbmc.executebuiltin("Quit")
    else:
        dialog.ok(TITLE, "All done! Kodi will now restart so every setting takes effect.")
        xbmc.executebuiltin("RestartApp")


def repair():
    """Re-apply TonyFlix configuration; sign-ins and your own settings are kept."""
    report = config.apply_all()
    profile = profiles.current_profile() or "auto"
    profiles.apply_profile(profile)
    xbmcgui.Dialog().ok(TITLE, f"TonyFlix settings re-applied ({len(report)} items, {profile} profile).")


def menu():
    dialog = xbmcgui.Dialog()
    state = load_setup()
    if not state.get("done"):
        full_setup()
        return
    options = [
        ("Change performance profile", "Lite or Standard"),
        ("Sign in to accounts", "Trakt, Real-Debrid"),
        ("Repair TonyFlix settings", "Re-apply players and add-on settings (keeps sign-ins)"),
        ("Clean up now", "Remove old thumbnails, package backups and temp files"),
        ("Run full setup again", "Reinstall anything missing"),
    ]
    items = [xbmcgui.ListItem(a, b) for a, b in options]
    idx = dialog.select(f"TonyFlix ({profiles.current_profile() or '?'} profile)", items, useDetails=True)
    if idx == 0:
        profile = choose_profile(dialog)
        if profile:
            profiles.apply_profile(profile)
            finish()
    elif idx == 1:
        account_setup(installer.load_install())
    elif idx == 2:
        repair()
    elif idx == 3:
        xbmc.executebuiltin("RunScript(service.tonyflix.maintenance)")
    elif idx == 4:
        full_setup()
