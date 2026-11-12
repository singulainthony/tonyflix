# Manual cleanup:  RunScript(service.tonyflix.maintenance)            -> progress dialog + summary
#                  RunScript(service.tonyflix.maintenance,silent)     -> no dialogs (for the wizard/tests)
#                  RunScript(service.tonyflix.maintenance,thumb_age_days=0,silent)  -> override age
import os
import sys

import xbmcaddon
import xbmcgui

sys.path.insert(0, os.path.join(xbmcaddon.Addon().getAddonInfo("path"), "resources", "lib"))
from tfmaint import cleaner  # noqa: E402


def main():
    args = dict(a.partition("=")[::2] for a in sys.argv[1:])
    silent = "silent" in args
    age = int(args["thumb_age_days"]) if args.get("thumb_age_days", "").isdigit() else None
    if silent:
        cleaner.Cleaner().run(age)
        return
    dlg = xbmcgui.DialogProgress()
    dlg.create("TonyFlix", "Cleaning up...")
    report = cleaner.Cleaner(progress=lambda pct, text: dlg.update(pct, text)).run(age)
    dlg.close()
    xbmcgui.Dialog().ok("TonyFlix clean-up", cleaner.summary(report))


if __name__ == "__main__":
    main()
