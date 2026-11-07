# GoldScout Companion

A small Windows app that shares the drop rates GoldScout learned from your loot,
without copying and pasting in game.

1. Download `GoldScoutCompanion.exe` from the latest
   [release](https://github.com/Alkhara/GoldScout-WoW/releases) and run it.
   There's nothing to install.
2. It finds your WoW Forever folder by itself. If it can't, click **Change...**
   and choose your World of Warcraft folder.
3. It shows what GoldScout has learned (mobs, kills, pickpockets, item drops)
   and checks it with the same rules the GoldScout data bot uses.
4. Click **Share on GitHub**. The Share drop data form opens with your export
   filled in; tick the two boxes and press **Create**.

Leave it open while you play and it notices new data, telling you when there's
more worth sharing. GoldScout saves its data when you log out or type
`/reload`, so new loot shows up after that.

## What it does and doesn't do

- It reads only GoldScout's saved data
  (`_forever_\WTF\Account\<account>\SavedVariables\GoldScout.lua`). It never
  changes game files and never touches the game while it's running.
- It doesn't connect to the internet itself. Sharing opens the form in your
  browser, and nothing is sent until you press Create there.
- It remembers your WoW folder and when you last shared, in
  `%APPDATA%\GoldScout Companion\config.json`.

Windows may warn that the app is from an unknown publisher, because it isn't
code-signed yet. Click **More info**, then **Run anyway**.

See the [Privacy Policy](../docs/PRIVACY.md) and
[Contributor Terms](../docs/CONTRIBUTOR_TERMS.md).

## Running from source

With Python 3.10 or later: `python companion/app.py`. To build the exe:
`pip install pyinstaller`, then `python companion/build.py`.
