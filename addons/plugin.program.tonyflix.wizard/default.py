# TonyFlix Wizard entry point.
#   RunScript(plugin.program.tonyflix.wizard)                     -> setup (first time) or the TonyFlix menu
#   RunScript(plugin.program.tonyflix.wizard,setup)               -> full setup
#   RunScript(plugin.program.tonyflix.wizard,accounts)            -> sign-in step only
#   RunScript(plugin.program.tonyflix.wizard,repair)              -> re-apply configuration
#   RunScript(plugin.program.tonyflix.wizard,skin)                -> switch to the TonyFlix skin
#   RunScript(plugin.program.tonyflix.wizard,apply_profile=lite)  -> apply a profile without asking (lite|standard|auto)
#   RunScript(plugin.program.tonyflix.wizard,detect)              -> log detected hardware + suggestion
import os
import sys

import xbmcaddon

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tonyflix import installer, profiles, setup  # noqa: E402


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
        setup.account_setup(installer.load_install())
    elif "skin" in args:              # switch to the TonyFlix skin (if setup could not)
        installer.log(f"switch skin: {setup.switch_skin(installer.load_install()['skin']['id'])}")
    elif "repair" in args:
        setup.repair()
    elif "install" in args:           # install one add-on through Kodi (repair / diagnostics)
        try:
            installer.log(f"install {args['install']}: {installer.install_from_repo(args['install'])}")
        except installer.InstallError as e:
            installer.log(f"install {args['install']} FAILED: {e}")
    else:
        setup.menu()


if __name__ == "__main__":
    main()
