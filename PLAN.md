# TonyFlix — Build Plan

A lightweight, Netflix-style Kodi build for weak Android boxes (T95 Max class), limited to
movies and TV only. Catalogs and discovery come from TMDb and Trakt. Streams come from Real-Debrid.

## Decisions (locked)

| Area | Choice | Why |
|---|---|---|
| Kodi | **21.3 Omega**, pinned | Current stable. Kodi 22 "Piers" is only at RC1 (Oct 2026). |
| Skin | **skin.tonyflix**, a trimmed fork of Arctic Horizon 2 | Lightest Netflix-style base. Upstream was archived Oct 2024, so we maintain our own fork. |
| Catalog / discovery | **TMDbHelper** (jurialmunkey) | AH2 is already wired to it. Covers TMDb discover filters, watch providers, Trakt lists, and people/keyword search. Still maintained. |
| Player | **Umbrella** by default, **Fen Light AM** under "Play with…" | Umbrella is still updated. Fen Light AM is a fallback. Players can be swapped without touching the skin. |
| Extras | a4kSubtitles, on-demand trailers, scheduled auto-cleanup | |
| Distribution | `repository.tonyflix` plus a wizard, hosted on GitHub Pages | Installed like Diggz: add a source URL, install the repo, run the wizard. |
| Hardware | Unknown or mixed | The wizard detects RAM, CPU and architecture, then picks a **Lite** or **Standard** profile. |

## Architecture

```
┌──────────────────────── skin.tonyflix (AH2 fork) ────────────────────────┐
│ Home (hero + rows) · Movies · TV · Discover · Search · Info · Settings   │
│ No Live TV / Music / Pictures / Games / Weather / Add-on hubs            │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ plugin:// widget paths
┌───────────────▼────────────── TMDbHelper ────────────────────────────────┐
│ TMDb: trending, popular, discover filters, watch providers, people,      │
│       keywords, "more like this"                                          │
│ Trakt: continue watching, up next, watchlist, recommendations, lists     │
│ Cached locally → fast rows, no Kodi library scanning                     │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ players/*.json (TMDbHelper player files)
┌───────────────▼──────────────┐   ┌──────────────────────────────────────┐
│ Umbrella (default)           │   │ Fen Light AM ("Play with…")          │
│ Real-Debrid auth, sources    │   │ Real-Debrid auth                     │
└──────────────────────────────┘   └──────────────────────────────────────┘
  + a4kSubtitles · YouTube addon (trailers) · service.tonyflix.maintenance
```

Key speed rule: **no Kodi library.** Every row is a cached TMDbHelper plugin listing, so there is no
library scanning, no scraping on startup, and no artwork downloads in the background.

**Scrobbling:** only one addon may scrobble to Trakt (TMDbHelper/Kodi side). Scrobbling is turned
off in Umbrella and Fen Light AM so watches don't get logged twice.

## Netflix-style home (default rows)

1. Hero spotlight: a static backdrop plus title and plot. **No** video autoplay.
2. Continue Watching (Trakt in-progress)
3. Up Next (Trakt next episodes)
4. My List (Trakt watchlist, movies and shows mixed)
5. Trending Now (TMDb weekly)
6. Because You Watched … (Trakt recommendations)
7. Top on Netflix / Max / Disney+ / Prime / Hulu / Apple TV+ (TMDb watch providers; region = US by default, changeable in settings)
8. Genre rows (Action, Comedy, Sci-Fi, Horror, …), which the user can edit

The Lite profile shows about 6 rows and Standard about 10. Rows load **on demand as they come into view**, not all at startup.

## Discovery & search

- **Discover hub:** a filter screen where you set Type (movie/TV) × Genre(s) × Year range ×
  Min rating × Min votes × Runtime × Original language × Certification × Streaming service ×
  Sort. Results appear as a poster grid. Filter combos can be saved as home rows.
- **Search:** one box with tabs for Movies / Shows / People / Keywords. Picking a person shows their
  filmography. Picking a keyword (e.g. "heist") shows discover results for it.
- **Info screen:** play, trailer button, cast row (each person opens their filmography), and rows for
  "More Like This" and "Collection".

## Performance profile (weak hardware)

- `advancedsettings.xml`: video cache sized to the RAM profile (Lite ≈ 100 MB, Standard ≈ 200 MB);
  `imageres`/`fanartres` capped at 720; thumbnail extraction and the library disabled.
- GUI: renders at 1080p even on 4K TVs. Animations shortened, blur, video backgrounds and auto-trailers turned off.
- Artwork: posters at TMDb `w342` and backdrops at `w780`, never `original`.
- Playback: MediaCodec (Surface) hardware decoding, with "adjust refresh rate" off by default.
- Turned off: RSS, weather, visualisations, music/pictures/PVR/games, addon auto-update nag dialogs.
- Maintenance service (weekly, plus a manual button): clears the thumbnail cache and `Textures13.db`,
  `packages/`, `temp/` and stale TMDbHelper cache, and prunes old logs.

## Wizard flow (`plugin.program.tonyflix.wizard`)

1. Detect the hardware (RAM, cores, arm/arm64) and suggest Lite or Standard.
2. Install the third-party repos **from their official URLs**, then install the addons through Kodi.
   TonyFlix hosts only its own code and never re-hosts other people's addons.
3. Apply the TonyFlix config (skin, widgets, players, advancedsettings, addon defaults).
4. Guided setup: Trakt auth (TMDbHelper), Real-Debrid auth (Umbrella, then Fen Light AM),
   an optional YouTube API key for trailers.
5. Restart Kodi.
6. Later: "Update build" keeps the user's auth and custom rows and refreshes everything else.

## Repo layout

```
Kodi-Build/
  PLAN.md
  addons/
    skin.tonyflix/                    # AH2 fork (CC BY-NC-SA 4.0, credited)
    plugin.program.tonyflix.wizard/
    service.tonyflix.maintenance/
    repository.tonyflix/
  build/
    profiles/{lite,standard}/         # advancedsettings, guisettings fragments, widget sets
    players/                          # TMDbHelper player JSONs (umbrella, fenlight_am)
    addon_defaults/                   # settings.xml defaults for TMDbHelper/Umbrella/etc.
  tools/
    build_repo.py                     # zips addons, writes addons.xml + .md5 into docs/
    package_build.py                  # makes the build config zip the wizard downloads
  docs/                               # GitHub Pages output (repo + build zips)
```

## Phases

| # | Phase | Output |
|---|---|---|
| 0 | Scaffold + repo tooling | Folder layout, `build_repo.py`, `repository.tonyflix` |
| 1 | Skin fork and trim | AH2 imported, unused windows/features removed, TonyFlix branding |
| 2 | Home and rows | Netflix home, hero, TMDbHelper widget paths, Lite/Standard row sets |
| 3 | Discover and search | Filter hub, multi-search, info-screen rows |
| 4 | Players | Umbrella + Fen Light+ player JSONs, scrobbling deduplicated |
| 5 | Performance profile | advancedsettings / GUI defaults per profile |
| 6 | Maintenance service | Scheduled and manual cleanup |
| 7 | Wizard | Install, configure, guided auth, update |
| 8 | Test | Kodi 21.3 on this Mac (skin/wizard logic), then on the real box |

## Progress

**Phases 0–1 done (2026-11-11):**

- `tools/build_repo.py` builds `docs/` for GitHub Pages: zips, `.sha256` files, `addons.xml` and its `.md5`, and an index page.
  Set `base_url` in `tools/config.json` before publishing.
- `tools/import_upstream.py` imports AH2 (`omega` branch, commit 8423735; `main` is Kodi 20 only) and removes PVR, music, games, pictures and
  weather windows, library hubs and non-English languages.
- `tools/check_skin.py` is a static checker for includes, variables, expressions and textures.
  Run it after every skin edit:
  `python3 tools/check_skin.py addons/skin.tonyflix --baseline tools/ah2_baseline.txt`
  (the baseline holds the 15 problems that already exist upstream; the target is "0 new").
- `tools/optimize_textures.py` shrinks the skin from 52.6 MB to 18.8 MB (the zip is 13.6 MB). Gradient overlays are 4× smaller
  (about 16× less GPU memory). PNGs are re-saved losslessly and checked pixel-identical to upstream.
- Menus now contain only Movies and TV (opening the TMDbHelper hubs) and TMDb search. Settings that are expensive on
  low-power boxes (background video, extra-fanart slideshow, TMDbHelper blur and crop, PVR lookups) are turned off
  once on first run. All animations are 25% shorter.
- Not yet tested in a running Kodi. That happens in Phase 8, or earlier if wanted.

**Smoke test on Kodi 21.3 macOS, clean profile (2026-11-11), passed:** TonyFlix loads and the menus show only
Search, Movies and TV. The Movies and TV TMDb hubs show real content and artwork. The info screen shows full
details, ratings and streaming-service icons. Search and Skin Settings open. There were no Python errors or
skin crashes. Skin load time on the Mac was about 70 ms (for reference only; the T95 needs its own measurement).
Bugs found and fixed:
- `xbmc.gui` 5.16.0 → 5.17.0. AH2 `main` targets Kodi 20, so Kodi 21 refused the skin. Upstream `omega` differs only in this line.
- Added the `script.module.tmdbhelper.sync.trakt` dependency. TMDbHelper 6.x split Trakt out, and every Trakt row popped a "sync provider" dialog.
- Removed the weather widget left in `shortcuts/template.xml` and fixed Kodi 21's `favouritesbrowser` window name.
  `check_skin.py` now also scans `template.xml`.

**The wizard must (learned from the smoke test):**
1. **Enable** every add-on it installs. Kodi registers add-ons copied in by hand as *disabled*.
2. Set the skin by writing `lookandfeel.skin` to `guisettings.xml` and then restarting. Switching skins live opens
   "Keep this skin?", which reverts on a timeout.
3. Preset the TMDbHelper sync providers to `trakt` (`sync_provider_watched`, `_watchlist`, `_collection`,
   and `sync_provider_scrobbling` = `["trakt"]`).
4. Write add-on settings one at a time from a single process. Writing them in parallel lost a value.

**For Phase 2:**
- The hub's top spotlight is empty without Trakt login, so use TMDb trending (no login needed) for the hero.
- Hide Trakt rows until the user has logged in.
- Stop rows scrolling underneath the top menu bar.

**Dev tools added:** `tools/fetch_deps.py` resolves and downloads dependencies from jurialmunkey's repo and the official
Kodi repo. Kodi data is backed up and restored around every test run.

**Phase 2 done (2026-11-11): Netflix-style home**

- Tabs are **Home · Movies · TV** (and Search). Each tab has a hero billboard (backdrop, title, ratings, plot,
  Play / More Information) and Netflix-style rows. With FlixArt (now the default), the focused title's backdrop
  and info fill the top of the screen while you browse rows.
- Rows are defined in `build/home_rows.json` (Home 12, Movies 14, TV 17; 6 per tab on Lite). Run
  `python3 tools/gen_home.py` after editing. It writes `Includes_TonyFlix_Home.xml`, `Timers.xml` and the hero
  defaults in `overrides.xml`. `shortcuts/template.xml` pulls each tab's rows in through `TonyFlix_Rows_<tab>`.
- All TMDbHelper paths were verified live (provider IDs, `with_genres` + `with_id=True`, Trakt routes).
- How loading works, measured on the Mac with the debug log:
  - **Boot:** 4 plugin calls (hero plus the first 3 Home rows). Before the fix it was 19.
  - **Tabs:** rows load only after a tab has been focused for 1 s, so skimming past a tab costs nothing.
    Returning to a tab costs 0 calls.
  - **Scrolling:** rows load 3 ahead of focus.
  - **Trakt rows:** only load when Trakt is linked (`TMDbHelper.TraktIsAuth` or `Skin.HasSetting(TonyFlix.TraktLinked)`).
    An unlinked Trakt call pops a blocking login dialog; the first test call took 225 s.
  - **Empty rows** (for example an empty watchlist) are hidden by a skin timer after 3 s.
  - **Lite** (`Skin.SetBool(TonyFlix.Lite)`): non-lite rows are hidden and never fetched.
- Kodi behaviour this depends on: a list's `$VAR` content path is only re-read while the list is **visible**, and lists
  with a fixed path load at window open **even when hidden**. Fixed paths caused about 50 calls at boot.
- Hubs: removed the TVDb "Academy Awards" row (it prompted to install a module), and the hub menu bar now hides while
  browsing rows (it used to overlap them).
- First-run defaults are now v3: FlixArt, open on the Home tab.

**Known issue (upstream):** Kodi 21.3 sometimes segfaults when the skin unloads (quit or `ReloadSkin`) while
TMDbHelper Python list items are alive (`CGUIListItem::~CGUIListItem` → `~CGUIControlGroup`). This was seen with
plain AH2 as well. Watch for it on the box. During testing, restart Kodi instead of using `ReloadSkin()`.

**Phase 3 done (2026-11-11): discovery**

- **Discover tab** (Home · Movies · TV · Discover). It has 18 rows; 6 show on Lite. Rows from top to bottom:
  - **Find Something** buttons: *Filter Movies*, *Filter Shows* (TMDbHelper's full filter builder), *Keywords*,
    *People* and *Saved*.
  - **Your Saved Searches**, with the results of the focused saved search in the row underneath.
  - **Shows by Service / Movies by Service**: fixed logo tiles for Netflix, Max, Disney+, Prime Video, Hulu, Apple TV+,
    Paramount+ and Peacock. They make no plugin calls.
  - Hidden Gems, Critically Acclaimed, Movie/TV genres, Coming Soon, New on Streaming, Hidden Gem Series,
    Acclaimed Series, Limited Series, Anime, Heists, Time Travel and All-Time Classics.
- The filter builder is TMDbHelper's own (`info=user_discover`). It covers genres included and excluded, keywords,
  cast and crew, companies and networks, streaming service and region, release dates, certification, rating and
  vote count, runtime, language and country, and sort order, and it can **Save** a search. Saved searches appear
  on the Discover tab automatically.
- `gen_home.py` now supports three row kinds: `path`, `items` (fixed tiles or buttons with actions) and `stack`
  (results of the focused item in the row above). It also supports four styles: `poster`, `landscape`, `square`
  and `buttons`.
- Search has a **Keywords** option ("heist" lists heist, bank heist, art heist and so on, and each opens discover
  results). Rows no longer slide behind the search bar, and the titles no longer say "TMDb …".
- **Info screens:** the list "Recommendations" is now **More Like This**. The info screen used to request about 15
  TMDbHelper lists every time it opened (the Info.Disable settings only hid rows after their data had been
  fetched). `Includes_TonyFlix_Info.xml` now requests only enabled rows, so a movie needs 4–6 (cast,
  More Like This, similar, keywords, plus collection and director when they exist). Trakt-only rows are requested
  only when Trakt is linked. First-run defaults v4 turn off posters, fanart, reviews, crew, Trakt lists, year,
  genre, studio, writer and YouTube.
- Select dialogs (including the filter builder): Right now goes straight to the buttons instead of the scrollbar.
- `tools/dev_kodi.py in|out|sync|status` swaps a test profile in and out of the desktop Kodi safely.

**Phase 4 done (2026-11-11): playback**

- **Players:** Umbrella 6.8.00 (default) and **Fen Light+ 2.5.4** (backup). Fen Light+ replaces Fen Light AM,
  whose official GitHub is gone. Fen Light+ is actively maintained (updated 2026-11-11).
  - Umbrella installs from `https://umbrellaplug.github.io` (repository.umbrella 2.2.6, Omega section). Its YouTube
    dependency is optional.
  - Fen Light+ has no Kodi repository. The wizard installs `plugin.video.fenlight-<ver>.zip` from
    `https://thejason40.github.io/packages` (the latest version number is in `packages/fen_light_version`).
    Fen Light's built-in updater already points at thejason40.
- `build/players/umbrella.json` and `build/players/fenlight_plus.json` are TMDbHelper player files. The wizard copies
  them to `addon_data/plugin.video.themoviedb.helper/players/`.
- `build/players/disable_bundled.txt` lists TMDbHelper's bundled UPnP, YouTube and IMDb-trailers players, which get
  hidden through `reconfigured_players/`, so the chooser shows only Umbrella and Fen Light+.
- `build/addon_defaults/defaults.json` holds the settings the wizard applies: TMDbHelper's default players
  (`umbrella.json play_movie` / `play_episode`) and Trakt sync providers, and Umbrella's scrobbling pinned to Local.
  Fen Light+ already defaults to local watched-tracking. **TMDbHelper is the only Trakt scrobbler.**
- **Info screen:** added a **Play with…** button under Play (press Left on the info screen). It opens the player
  chooser for movies and episodes.
- Tested on the Mac:
  - **Play** (movie): Umbrella received `action=play&title=Model%20Citizen&year=2026&imdb=tt13884466&tmdb=1792170&premiered=2026-11-03`.
  - **Episode:** Umbrella received full show IDs, season, episode, show title and air date, and TMDbHelper queued the next
    episode.
  - **Play with → Fen Light+:** `mode=playback.media&media_type=movie&tmdb_id=1792170`.
  - Both players start, then stop with a notification because no Real-Debrid account is linked on the test profile.
- **Not tested yet** (needs Real-Debrid on the box): actual stream playback, TMDbHelper's Trakt scrobbling during
  external playback, and Umbrella's next-episode handoff.
- **Open item for the wizard phase:** Umbrella finds most sources through an external scraper package installed
  separately from its own repo. Decide with the user what the wizard installs. Real-Debrid cloud and premium
  sources work without one.
- Known harmless log noise: four `GetDirectory - Error getting Fullscreen` lines on Home load. They come from the hidden
  per-tab placeholder that skinshortcuts needs; the failure is instant and makes no Python or network calls.

**Phase 5 done (2026-11-11): performance profiles**

- `build/profiles/profiles.json` contains `common` plus the **Lite** / **Standard** profiles, and the detection rules.
  - **Kodi GUI settings:**
    - Cache: 64 MB at 4x read-ahead (Lite) or 128 MB at 10x (Standard).
    - `videoscreen.limitgui` caps the menu at 720p (Lite) or 1080p (Standard). This setting is Android only.
    - zeroconf, UPnP, AirPlay, the web server, RSS and GUI sounds are off; the screensaver is Dim; refresh-rate
      switching is off; Kodi's own thumbnail and flag extraction is off.
  - **advancedsettings:** splash off, curl timeouts, and `imageres`/`fanartres` (540/720 on Lite, 720/1080 on
    Standard). Kodi 21 no longer reads `<cache>`; the cache moved to the GUI settings above.
  - **TMDbHelper:** `artwork_quality` is 3 on Lite (w342 posters, w780 backdrops) and 2 on Standard (w500/w1280).
    The default was 0, which requested original backdrops, often 4K. fanart.tv lookups stay off; online ratings
    are off on Lite.
  - **Skin, Lite only:** `TonyFlix.Lite` (6 rows per tab), no autoscrolling text, simple info background, no focus
    glow.
  - **Detection:** suggest Lite when RAM is under 2.5 GB, there are fewer than 4 cores, Kodi is 32-bit, the GPU is weak
    (Mali-T720 / G31 and similar, read from `System.VideoEncoderInfo`), or the chip is weak (`/proc/cpuinfo`, for
    example `sun50iw6` = H6, `sm1` = S905X3). Both T95 Max variants → Lite. A Shield Pro or Fire TV 4K Max →
    Standard.
- `tools/validate_profiles.py` checks every value against Kodi 21.3's own definitions (`settings.xml`, `android.xml`,
  and the C++ option lists), TMDbHelper's `settings.xml`, and the skin. It also writes
  `build/profiles/{lite,standard}/advancedsettings.xml`.
- **New add-on `plugin.program.tonyflix.wizard` 0.1.0** (the core of Phase 7):
  - `resources/lib/tonyflix/profiles.py` detects the hardware and applies `common` + the chosen profile.
    - GUI settings go through internal JSON-RPC; IDs a platform lacks are skipped.
    - It writes `advancedsettings.xml`, backing up any existing file TonyFlix didn't create.
    - Add-on settings are applied one at a time.
    - Skin settings use builtins when TonyFlix is active; otherwise they are written to
      `addon_data/skin.tonyflix/settings.xml`.
    - It records the result in `state.json`.
  - Entry points: `RunScript(plugin.program.tonyflix.wizard)` (chooser dialog, then restart),
    `…,apply_profile=lite|standard|auto`, and `…,detect`.
  - Its `resources/data/` is copied from `build/` by `build_repo.py` and `dev_kodi.py sync`, so `build/` remains
    the single source of truth.
- **Tested in Kodi 21.3 (Mac):**
  - Applying Lite and then Standard: every GUI, advancedsettings, TMDbHelper and skin value was read back and
    matched. The only skips were the Android-only `limitgui` and a debug setting locked by the dev log file.
  - Values persisted across a restart, and Kodi logged loading TonyFlix's `advancedsettings.xml`.
  - `tools/test_wizard_profiles.py` (runs offline, no Kodi needed) passed all 11 checks: 7 hardware cases plus the
    skin-settings file mode.
- **Not measured yet:** real speed on the T95. That needs the box.

**Phase 6 done (2026-11-11): maintenance service**

- **New add-on `service.tonyflix.maintenance` 1.0.0.**
  - **Automatic runs:** a background service runs the cleanup every 7 days (configurable), but only when nothing
    is playing and the box has been idle for 3 minutes. It also runs early when free space drops below 500 MB
    (and then clears thumbnails older than 7 days).
  - **Manual runs:**
    - `RunScript(service.tonyflix.maintenance)` shows a progress dialog and a summary.
    - `…,silent` runs with no dialogs.
    - `…,thumb_age_days=N` overrides the thumbnail age.
  - **Settings:** enabled, interval, thumbnail age (default 30 days), and a notification when done.
- **What it cleans:**
  - **Thumbnails** not shown for N days, removed through Kodi's own `Textures.RemoveTexture`. That deletes both the
    database row and the file, so it's safe while Kodi is running. At most 2,000 per run.
  - **Add-on package backups** older than a day (`addons/packages/*.zip`).
  - **Temp files** older than a day. It never touches `kodi.log` / `kodi.old.log` or database, lock or pid files.
  - **Kodi crash logs** older than 14 days.
- **Safety:**
  - Temp is only cleaned when it sits inside Kodi's home folder. This guard fired correctly on macOS, where temp is
    `~/.kodi/temp`; on Android, temp is inside `.kodi`.
  - It stops as soon as playback starts or Kodi begins to exit.
- **Bug found and fixed:** Kodi stores texture `lastused` in **UTC**. The first version compared it with local time,
  which meant nothing was ever "old" west of UTC.
- **Tests:**
  - `tools/test_maintenance_rules.py` (offline) passes 13/13: file selection, protected files, the
    symlink/prefix guard, scheduling and the UTC cutoff.
  - In Kodi 21.3 on the Mac:
    - It removed all 547 cached thumbnails (54 MB) in 0.5 s and deleted the planted old package zip.
    - Home re-cached its artwork straight away.
    - A run started during playback stopped with "playback started" and removed nothing.
    - The service starts at boot with no errors.
- **Not tested live:** the automatic weekly trigger. Its scheduling logic is unit-tested; a live run means waiting
  through the 5-minute boot delay and 3 minutes of idle time.

**Phase 7 done (2026-11-11): setup wizard**

- **`plugin.program.tonyflix.wizard` 0.2.5.** The family installs `repository.tonyflix` (Install from zip), then
  installs TonyFlix Wizard from that repository (Program add-ons). The wizard's first-run service then offers setup
  after about 12 s. It can also be opened from Add-ons → Program add-ons.
  - **Flow:**
    1. "Set up TonyFlix on this box?"
    2. Choose a profile. The suggested Lite or Standard is preselected, with the reason shown.
    3. Set `addons.updatemode` = 1. Without it Kodi installs the old TMDbHelper 5.x from the official repo instead
       of jurialmunkey's 6.x.
    4. Add the third-party repositories from their authors' URLs (`build/install.json`):
       - jurialmunkey: TMDbHelper, sync.trakt, skin helpers
       - Umbrella
       - a4kSubtitles
    5. Install the add-ons through Kodi's own `InstallAddon`, so they keep auto-updating from those repos.
    6. Install Fen Light+ from thejason40's own zip and its version file (it has no Kodi repo), after its
       dependencies.
    7. Install the player JSONs and add-on defaults.
    8. Apply the chosen profile.
    9. Install the skin. Its dependencies are installed one at a time first.
    10. Switch to the TonyFlix skin.
    11. Offer optional sign-ins (Later is allowed): Trakt (TMDbHelper), Real-Debrid in Umbrella, Real-Debrid in
        Fen Light+.
    12. Close Kodi on Android and macOS. Kodi's `RestartApp` only works on Windows and Linux, where Kodi restarts
        instead.
  - **Menu (after setup):** change profile, sign in to accounts, repair settings (keeps sign-ins), clean up now,
    run full setup again.
  - **Command-line entry points:** `…,setup` / `accounts` / `repair` / `skin` / `install=<id>` / `apply_profile=` /
    `detect`.
  - **Results** are saved to `addon_data/plugin.program.tonyflix.wizard/setup.json` (profile, problems,
    account status).
  - TonyFlix never re-hosts anyone else's add-on, and the wizard installs no scraper packages. Umbrella's own
    settings handle those.
- **Kodi 21 behaviour the wizard works around** (all found in live runs):
  - **Install prompts:**
    - `InstallAddon` always asks "Add-on required → download?". Clicking with `SendClick`, or pressing an extra
      key, can land on the install progress dialog that follows, which uses the same layout, and cancels the
      download. The wizard only answers prompts it recognises: it focuses Yes with `SetFocus(11)`, sends one
      `Select`, and waits for the prompt to close.
  - **Skin switch:**
    - Under the TonyFlix skin, "Keep skin?" opens with nothing focused, and pressing Left moves from Yes to No.
      So focus is always set directly, never with arrow keys.
    - On a brand-new install, the first TonyFlix load always reverts. Skin Shortcuts builds the menus and reloads
      the skin, which closes "Keep skin?" unanswered. The wizard requests the switch again 5 s later and that one
      sticks.
    - It never requests a switch while one Kodi started may still be loading. A duplicate request also causes a
      revert.
  - **Dependencies:**
    - Right after repositories are added, Kodi's dependency pass can miss an add-on that is in a repo
      (`script.texturemaker`). `build_repo.py` now writes the skin's dependencies into the wizard's `install.json`,
      the wizard installs them one by one, and the skin install is retried once.
  - **Zip packaging:**
    - The a4k repo zip contains `__MACOSX/` entries, which are skipped. Zip add-ons are unpacked with a
      path-traversal check and then registered and enabled.
- **End-to-end test (Kodi 21.3, Mac, 8 runs):**
  - **Setup:** each run starts from an empty profile with only `repository.tonyflix` served from a local copy of the
    repo. A driver answers the dialogs the way a remote would. The prompts for the wizard's own installs are left for
    the wizard to answer.
  - **Final run (8):**
    - Done in about 110 s with no problems.
    - After reopening Kodi:
      - TonyFlix is the active skin.
      - Installed add-ons and their sources: TMDbHelper 6.21.5 (jurialmunkey), sync.trakt 1.2.9, Umbrella 6.8.00,
        a4kSubtitles 3.26.1, Fen Light+ 2.5.4 (with requests), TonyFlix Maintenance and skin (tonyflix repo),
        texturemaker / skinvariables (jurialmunkey).
      - Both player files and `advancedsettings.xml` are written. `setup.json` has no problems.
      - The maintenance service started. The only log error is the known harmless Skin Shortcuts
        "Error getting Fullscreen".
  - **Not tested live:** actually signing in during setup (each sign-in was answered Later; the sign-in entry
    points themselves were checked in Phase 4), and the Android path (`Quit` instead of restart).
- **Before the family can use it:** publish `docs/` on GitHub Pages and set `base_url` in `tools/config.json`, then
  run `python3 tools/build_repo.py --clean`. Until then, `docs/repository.tonyflix-1.0.0.zip` points to the
  placeholder URL.

**Next phase:** Phase 8 (testing on the real T95 box: hosting, install from zip, speed measurements).

**Follow-up idea:** pack `media/` into `Textures.xbt` with Kodi's TexturePacker, which loads faster on Android.
This needs TexturePacker built from the Kodi source tree.

## Known risks / to verify during build

- **Real-Debrid on Kodi:** there have been reports of RD tightening third-party access. If that happens,
  the player layer is the only part that changes.
- **Third-party repo URLs** (Umbrella, Fen Light AM, a4k) must be checked when the wizard is
  written. They move often.
- **Trailers:** the YouTube Kodi addon now needs each user to supply their own API key. The wizard
  explains this, and the trailer button hides itself until a key is set.
- **Kodi 22 port:** this is our job later, because AH2 upstream is archived.
- **Licensing:** AH2 is CC BY-NC-SA 4.0. The fork must stay non-commercial, credit jurialmunkey and keep the same license.
- **Testing limit:** I can run Kodi 21.3 on macOS to check the skin and wizard, but performance on the T95 Max
  can only be measured on the box itself.
