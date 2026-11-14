# TonyFlix Wizard entry point.
#   RunScript(plugin.program.tonyflix.wizard)                     -> setup (first time) or the TonyFlix menu
#   RunScript(plugin.program.tonyflix.wizard,menu)                -> same
#   RunScript(plugin.program.tonyflix.wizard,setup)               -> full setup
#   RunScript(plugin.program.tonyflix.wizard,accounts)            -> Accounts screen (Trakt, Real-Debrid)
#   RunScript(plugin.program.tonyflix.wizard,exit)                -> close Kodi normally
#   RunScript(plugin.program.tonyflix.wizard,forceclose)          -> kill Kodi at once (asks first)
#   RunScript(plugin.program.tonyflix.wizard,repair)              -> re-apply configuration
#   RunScript(plugin.program.tonyflix.wizard,skin)                -> switch to the TonyFlix skin
#   RunScript(plugin.program.tonyflix.wizard,apply_profile=lite)  -> apply a profile without asking (lite|standard|auto)
#   RunScript(plugin.program.tonyflix.wizard,detect)              -> log detected hardware + suggestion
#   RunScript(plugin.program.tonyflix.wizard,install=<id>)        -> install one add-on through Kodi
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tonyflix import installer, profiles, setup, ui  # noqa: E402


def force_close():
    if not xbmcgui.Dialog().yesno(
            "TonyFlix", "Force close Kodi right now?[CR][CR]Use this only when Kodi is stuck or won't exit. "
                        "Anything Kodi hasn't saved yet (like where you stopped watching) may be lost.",
            nolabel="Cancel", yeslabel="Force close"):
        return
    installer.log("force close")
    # Python runs inside Kodi's own process, so this ends Kodi immediately (no clean shutdown).
    os._exit(0)


def main():
    args = dict(a.partition("=")[::2] for a in sys.argv[1:])
    if "apply_profile" in args:
        profiles.apply_profile(args["apply_profile"] or "auto")
    elif "detect" in args:
        cfg = profiles.load_profiles()
        hw = profiles.detect_hardware()
        profiles.log(f"hardware {hw} -> suggest {profiles.suggest_profile(hw, cfg['detection'])}")
    elif "setup" in args:
        setup.full_setup()
    elif "accounts" in args:
        ui.accounts_screen(installer.load_install()["accounts"])
    elif "exit" in args:
        xbmc.executebuiltin("Quit")
    elif "forceclose" in args:
        force_close()
    elif "repair" in args:
        setup.repair()
    elif "skin" in args:
        installer.log(f"switch skin: {setup.switch_skin()}")
    elif "install" in args:
        try:
            installer.log(f"install {args['install']}: {installer.install_from_repo(args['install'])}")
        except installer.InstallError as e:
            installer.log(f"install {args['install']} FAILED: {e}")
    else:
        setup.menu()


if __name__ == "__main__":
    main()
