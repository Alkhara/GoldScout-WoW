# GoldScout Companion

A small Windows app that shares the drop rates GoldScout learns from your loot,
automatically, from the system tray. More at https://wowgoldscout.com.

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

It never shows notifications, so nothing pops up over your game. Click the tray
icon to open the window, which shows what GoldScout has learned and when it
last shared. The tray menu can pause automatic sharing, turn off starting with
Windows, check for updates, or quit. Closing the window keeps the companion running in the tray.

**Updates are one click.** When a new version is out, the window and the tray
menu show **Update**. The companion downloads it, checks it's the genuine signed
release, replaces itself in place and restarts, keeping your settings. If the new
version doesn't start, it puts the old one back. (Versions before 0.6.2 can't
update themselves: download the new exe once and replace the old one.)

If you choose **Not now**, nothing is uploaded. **Share now** then opens the
Share drop data form on GitHub with your export filled in instead.

## What it does and doesn't do

- It reads only GoldScout's saved data
  (`_forever_\WTF\Account\<account>\SavedVariables\GoldScout.lua`). It never
  changes game files and never touches the game while it's running.
- It uploads only GoldScout's drop data exports: creature and item IDs, kill and
  drop counts, levels and loot locations, plus a random ID for your GoldScout
  data. Never character, account or realm names.
- It keeps its settings in `%APPDATA%\GoldScout Companion\config.json`.

The exe is code-signed, so Windows shows the publisher. See the
[Privacy Policy](../docs/PRIVACY.md).

## Running from source

With Python 3.10 or later and `pip install pystray pillow`:
`python companion/app.py` (add `--tray` to start hidden). To build the exe:
`pip install pyinstaller`, then `python companion/build.py`.
