# GoldScout Companion

A small Windows app that shares the drop rates GoldScout learns from your loot,
automatically, from the system tray, and brings current auction house prices
into GoldScout without scanning. More at https://wowgoldscout.com.

1. Download `GoldScoutCompanion.exe` from the latest
   [release](https://github.com/Alkhara/GoldScout-WoW/releases) and run it.
   There's nothing to install.
2. The first time, it explains what it shares and asks you to agree to the
   [Contributor Terms](../docs/CONTRIBUTOR_TERMS.md). Choose **I agree, share
   automatically**. Starting with Windows is on by default; untick it if you
   prefer.
3. That's it. It finds your WoW Forever folder by itself and sits in the tray.
   Whenever GoldScout saves new data (when you log out or type `/reload`), the
   companion checks it with the same rules the GoldScout data bot uses and
   uploads it.

Nothing pops up over your game. Its one notification says a new version is out,
once per version, and it waits until World of Warcraft is closed. Click the tray
icon to open the window, which shows what GoldScout has learned and when it
last shared. **Quit** in the window (or the tray menu) stops the companion until
you start it again. The tray menu can pause automatic sharing, turn auction prices off,
turn off starting with Windows, check for updates, or quit. Closing the window keeps the companion running in the tray.

**Updates are one click.** When a new version is out, the window and the tray
menu show **Update**. The companion downloads it, checks it's the genuine signed
release, replaces itself in place and restarts, keeping your settings. If the new
version doesn't start, it puts the old one back. (Versions before 0.6.2 can't
update themselves: download the new exe once and replace the old one.)

If you choose **Not now**, nothing is uploaded. **Share now** then opens the
Share drop data form on GitHub with your export filled in instead.

## Auction prices in GoldScout

About once an hour the companion saves the latest auction house prices for your
realms (from Blizzard's hourly snapshot) in a small `GoldScout_Prices` addon.
GoldScout uses them for every item you haven't scanned more recently yourself,
so your own scan still wins when it's newer. It also saves your realm's
Blackwater (goblin) auction house prices, which GoldScout shows as an extra
tooltip line without ever using them in place of your faction's. This works whether or not you share
drop data.

The game only reads addon files when you log in or `/reload`, so GoldScout has
the prices from your last login. When newer ones are waiting, GoldScout's window
shows **Load newer prices**, which reloads the interface for you.

Prices come for US, EU, Korean and Taiwanese realms. GoldScout works out which
auction house is yours from your realm's ruleset. If it can't, or to make sure,
scan the auction house once in GoldScout, then log out or `/reload`: the
companion compares your scan with your region's auction houses and uses the one
that clearly matches, within the hour (on your PC; nothing is uploaded).
Turn auction prices off from the tray menu; that also removes the
`GoldScout_Prices` folder.

## What it does and doesn't do

- It reads only GoldScout's saved data
  (`_forever_\WTF\Account\<account>\SavedVariables\GoldScout.lua`). The
  only thing it writes in the WoW folder is the `GoldScout_Prices` addon, and it
  never touches the game while it's running.
- It uploads only GoldScout's drop data exports: creature and item IDs, kill and
  drop counts, levels and loot locations, plus a random ID for your GoldScout
  data. Never character, account or realm names.
- It keeps its settings in `%APPDATA%\GoldScout Companion\config.json`.

The exe is code-signed, so Windows shows the publisher. See the
[Privacy Policy](../docs/PRIVACY.md).

## On a Mac

The companion runs on macOS too. A signed Mac app will come with a later
release; until then, run it from source (below). On a Mac:

- There's no tray icon. Closing the window keeps the companion running in the
  Dock; click its Dock icon to open the window again. **Settings** in the
  window holds what the tray menu has on Windows: automatic sharing, auction
  prices, **Open at login**, and checking for updates.
- It looks for WoW in `/Applications/World of Warcraft` and
  `~/Applications/World of Warcraft`; elsewhere, click **Change...**.
- It keeps its settings in `~/Library/Application Support/GoldScout Companion`.
  **Open at login** (in the app only) adds
  `~/Library/LaunchAgents/com.wowgoldscout.companion.plist`, and macOS may say
  a login item was added.
- The update notification is a macOS notification, still only while World of
  Warcraft is closed.

## Running from source

With Python 3.10 or later:

- Windows: `pip install pystray pillow`, then `python companion/app.py`.
- macOS: Python from [python.org](https://www.python.org/downloads/macos/)
  (it includes Tk; nothing else to install), then `python3 companion/app.py`.

Add `--tray` to start with the window hidden. Running from source never updates
itself or starts at login.

To build the app: `pip install pyinstaller`, then `python companion/build.py`.
On Windows that makes `GoldScoutCompanion.exe` (also `pip install pystray
pillow`); on a Mac, `GoldScout Companion.app` (add `--universal2` with
python.org's Python for one app that runs on Apple silicon and Intel). A local
Mac build is unsigned: the first time, Control-click it and choose **Open**.
