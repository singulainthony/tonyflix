# Installing third-party repositories and add-ons from their authors' own sources.
#
#  * Repositories (and Fen Light+, which has no repo) are downloaded from the URLs in
#    resources/data/install.json, unpacked into special://home/addons/ and enabled.
#  * Everything else goes through Kodi's own InstallAddon, so add-ons keep updating from
#    their repository. Kodi 21 always asks "Do you want to install ...?" for InstallAddon;
#    the wizard answers that prompt itself (Yes = button 11 of the Yes/No dialog).
import json
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

WIZARD = xbmcaddon.Addon("plugin.program.tonyflix.wizard")
DATA = os.path.join(xbmcvfs.translatePath(WIZARD.getAddonInfo("path")), "resources", "data")
ADDONS_DIR = xbmcvfs.translatePath("special://home/addons/")
DOWNLOADS = os.path.join(xbmcvfs.translatePath(WIZARD.getAddonInfo("profile")), "downloads")
YESNO_DIALOG = 10100
YES_BUTTON = 11
OK_DIALOG = 12002
PROGRESS_DIALOG = 10101


class InstallError(Exception):
    pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[TonyFlix wizard] {msg}", level)


def load_install():
    with open(os.path.join(DATA, "install.json"), encoding="utf-8") as f:
        return json.load(f)


def jsonrpc(method, params=None):
    req = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        req["params"] = params
    return json.loads(xbmc.executeJSONRPC(json.dumps(req)))


def is_installed(addon_id):
    return xbmc.getCondVisibility(f"System.HasAddon({addon_id})")


def is_enabled(addon_id):
    return xbmc.getCondVisibility(f"System.AddonIsEnabled({addon_id})")


def enable(addon_id):
    res = jsonrpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
    return res.get("result") == "OK"


# ------------------------------------------------------------------ downloads (via Kodi's curl/CA store)

def read_url(url):
    f = xbmcvfs.File(url)
    try:
        data = f.readBytes()
    finally:
        f.close()
    if not data:
        raise InstallError(f"could not download {url}")
    return bytes(data)


def download(url, name):
    os.makedirs(DOWNLOADS, exist_ok=True)
    dest = os.path.join(DOWNLOADS, name)
    with open(dest, "wb") as f:
        f.write(read_url(url))
    return dest


def find_zip_on_index(index_url, pattern):
    html = read_url(index_url).decode("utf-8", "replace")
    names = sorted(set(re.findall(pattern, html)), key=lambda n: [int(x) for x in re.findall(r"\d+", n)])
    if not names:
        raise InstallError(f"no {pattern} on {index_url}")
    return index_url.rstrip("/") + "/" + names[-1]   # highest version


def unpack_addon(zip_path):
    """Unpack an add-on zip into special://home/addons/<id>, the id taken from its addon.xml."""
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.split("/")[0].startswith(("__MACOSX", "."))]
        roots = {n.split("/")[0] for n in names}
        if len(roots) != 1:
            raise InstallError(f"{os.path.basename(zip_path)}: unexpected layout")
        root = roots.pop()
        addon_id = ET.fromstring(zf.read(f"{root}/addon.xml")).get("id")
        if not addon_id or not re.match(r"^[\w.\-]+$", addon_id):
            raise InstallError(f"{os.path.basename(zip_path)}: bad add-on id")
        tmp = os.path.join(DOWNLOADS, f"unpack-{addon_id}")
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        base = os.path.realpath(tmp)
        for n in names:  # refuse path traversal
            if not os.path.realpath(os.path.join(tmp, n)).startswith(base + os.sep):
                raise InstallError(f"{os.path.basename(zip_path)}: unsafe path {n}")
        zf.extractall(tmp, members=names)
    dest = os.path.join(ADDONS_DIR, addon_id)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.move(os.path.join(tmp, root), dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return addon_id


def zip_dependencies(zip_path):
    """Non-Kodi imports declared in a zip's addon.xml (optional ones skipped)."""
    with zipfile.ZipFile(zip_path) as zf:
        xml = next(n for n in zf.namelist() if n.count("/") == 1 and n.endswith("/addon.xml")
                   and not n.startswith("__MACOSX"))
        root = ET.fromstring(zf.read(xml))
    return [i.get("addon") for i in root.iter("import")
            if i.get("optional", "false") != "true" and not i.get("addon", "").startswith(("xbmc.", "kodi."))]


def register_and_enable(addon_id, timeout=30):
    xbmc.executebuiltin("UpdateLocalAddons", True)
    end = time.time() + timeout
    while time.time() < end:
        if is_installed(addon_id):
            # Add-ons copied in by hand are registered disabled.
            if is_enabled(addon_id) or enable(addon_id):
                return True
        xbmc.sleep(500)
    raise InstallError(f"Kodi did not register {addon_id}")


def install_repository(repo):
    if is_installed(repo["id"]) and is_enabled(repo["id"]):
        return "already installed"
    url = repo.get("zip") or find_zip_on_index(repo["index"], repo["zip_pattern"])
    addon_id = unpack_addon(download(url, os.path.basename(url)))
    register_and_enable(addon_id)
    return url


def install_zip_addon(entry):
    if is_installed(entry["id"]) and is_enabled(entry["id"]):
        return "already installed"
    version = read_url(entry["version_url"]).decode().strip()
    if not re.match(r"^[0-9][0-9.]*$", version):
        raise InstallError(f"odd version '{version}' from {entry['version_url']}")
    url = entry["zip"].format(version=version)
    path = download(url, os.path.basename(url))
    for dep in zip_dependencies(path):          # e.g. script.module.requests for Fen Light+
        install_from_repo(dep)
    addon_id = unpack_addon(path)
    register_and_enable(addon_id)
    return f"{url}"


def refresh_repositories():
    """Ask Kodi to re-read every enabled repository (newly added ones included)."""
    xbmc.executebuiltin("UpdateAddonRepos", True)
    xbmc.sleep(5000)


def confirm_yes(tries=15):
    """Press Yes on the open Yes/No dialog like a remote: focus the Yes button, then ONE Select.
    (SendClick into this dialog made Kodi cancel the install that follows - the progress dialog
    reuses the same layout - while focus-then-Select installs cleanly.)
    Focus is set directly, never with arrow keys: under the TonyFlix skin the "Keep skin?" prompt
    opens with nothing focused and Left moves Yes -> No; the skin can also reload while the prompt
    is open, which resets focus. Returns True if Select was sent on Yes."""
    for _ in range(tries):
        if xbmcgui.getCurrentWindowDialogId() != YESNO_DIALOG:
            return False
        if xbmc.getInfoLabel("System.CurrentControlId") == str(YES_BUTTON):
            xbmc.executebuiltin("Action(Select)", True)
            return True
        xbmc.executebuiltin(f"SetFocus({YES_BUTTON})", True)
        xbmc.sleep(200)
    log(f"prompt '{xbmc.getInfoLabel('Control.GetLabel(1)')}': could not focus Yes")
    return False


def is_expected_prompt(kind):
    """Only answer prompts we expect. In Kodi 21 the install PROGRESS dialog uses the same
    DialogConfirm layout, and clicking into it cancels the download - so never click blindly."""
    if xbmcgui.getCurrentWindowDialogId() != YESNO_DIALOG:
        return False
    heading = xbmc.getInfoLabel("Control.GetLabel(1)")
    text = xbmc.getInfoLabel("Control.GetLabel(9)").lower()
    if kind == "install":
        return heading == xbmc.getLocalizedString(24076) or "download this add-on" in text
    if kind == "skin":
        return "skin" in text or "skin" in heading.lower()
    return False


def answer_once(kind, timeout=1.0):
    """If the expected prompt is showing, press Yes once and wait for it to close."""
    if not is_expected_prompt(kind):
        return False
    if not confirm_yes():
        return False
    end = time.time() + 5
    while time.time() < end and is_expected_prompt(kind):
        xbmc.sleep(200)
    return True


def dialog_text():
    return " ".join(xbmc.getInfoLabel(f"Control.GetLabel({i})") for i in (1, 9)).strip()


def install_from_repo(addon_id, timeout=300, monitor=None):
    """Kodi InstallAddon (dependencies resolved by Kodi), answering its confirmation prompts.
    Raises InstallError with Kodi's message if Kodi reports a failure."""
    if is_installed(addon_id):
        if not is_enabled(addon_id):
            enable(addon_id)
        return "already installed"
    monitor = monitor or xbmc.Monitor()
    xbmc.executebuiltin(f"InstallAddon({addon_id})")
    end = time.time() + timeout
    answers = {"install": 1, "skin": 2}   # prompts we may answer for this install, at most this often
    started = time.time()
    while time.time() < end:
        if answers["install"] and time.time() - started > 20 and not is_installed(addon_id) \
                and xbmcgui.getCurrentWindowDialogId() not in (YESNO_DIALOG, PROGRESS_DIALOG, OK_DIALOG):
            raise InstallError(f"{addon_id} is not available in any enabled repository")
        if monitor.abortRequested():
            raise InstallError("Kodi is shutting down")
        for kind in ("install", "skin"):
            if answers[kind] and answer_once(kind):
                answers[kind] -= 1
        dlg = xbmcgui.getCurrentWindowDialogId()
        if dlg == OK_DIALOG:
            # Kodi shows an OK dialog when an install fails (e.g. a dependency can't be met).
            msg = dialog_text()
            xbmc.executebuiltin("Action(Select)")
            close_by = time.time() + 5   # let it close so the next install doesn't see it
            while time.time() < close_by and xbmcgui.getCurrentWindowDialogId() == OK_DIALOG:
                xbmc.sleep(200)
            raise InstallError(msg or "Kodi reported an install error")
        if is_installed(addon_id) and is_enabled(addon_id):
            return "installed"
        xbmc.sleep(500)
    raise InstallError(f"timed out installing {addon_id}")
