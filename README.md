<p align="center">
  <img src="docs/logo/goldscout-logo-400.png" alt="GoldScout logo" width="120">
</p>

<h1 align="center">GoldScout</h1>

<p align="center">
  <b>What should <i>this</i> character farm for gold right now?</b><br>
  A free World of Warcraft: Forever addon that ranks farms and crafts by gold per hour,<br>
  for the character you're playing, priced from your own auction house.
</p>

<p align="center">
  <a href="https://www.curseforge.com/projects/1790110"><img src="https://img.shields.io/curseforge/dt/1790110?label=CurseForge&logo=curseforge&color=f16436" alt="CurseForge downloads"></a>
  <a href="https://github.com/Alkhara/GoldScout-WoW/releases/latest"><img src="https://img.shields.io/github/v/release/Alkhara/GoldScout-WoW?label=release&color=d99a2b" alt="Latest release"></a>
  <a href="https://github.com/Alkhara/GoldScout-WoW/actions/workflows/tests.yml"><img src="https://github.com/Alkhara/GoldScout-WoW/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/code-MIT-blue" alt="MIT License"></a>
  <a href="https://wowgoldscout.com"><img src="https://img.shields.io/badge/website-wowgoldscout.com-f2c255" alt="Website"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/languages-English%20%7C%20Deutsch%20%7C%20Fran%C3%A7ais%20%7C%20%ED%95%9C%EA%B5%AD%EC%96%B4%20%7C%20%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87-2b7bb9" alt="Languages: English, Deutsch, Français, 한국어, 繁體中文">
  <img src="https://img.shields.io/badge/auction%20prices-US%20%7C%20EU%20%7C%20KR%20%7C%20TW-2b7bb9" alt="Auction prices for US, EU, KR and TW realms">
</p>

<p align="center">
  <img src="docs/screenshots/Frame.JPG" alt="The GoldScout Farm tab: farms ranked by gold per hour for a level 31 rogue" width="760">
</p>

Log onto a level 12 druid herbalist or a level 31 rogue, open GoldScout, and you
get advice that fits that character: its level, class, faction and professions,
priced against your own realm's auction house.

## Features

- **Farm tab:** farms ranked by estimated gold per hour: mob drops, cloth,
  herbs, ore and leather your skills can gather, pickpocketing for rogues, and
  crafting reagents selling on your auction house right now.
- **Experience check:** see at a glance which farms still give you XP, so you
  can level and earn at the same time.
- **Craft tab:** every recipe you know, ranked by profit after the auction house
  cut and the cheapest cost of materials.
- **Hunt mode:** pick a farm and press **Hunt** for Blizzard's map waypoint to
  the spot, a marker over every mob that drops it, and a live panel of kills,
  loot, drop rate and gold per hour.
- **Price tooltips:** the latest auction price and listing count on every item,
  plus what it goes for at the Blackwater (goblin) auction houses.
- **Learns as you play:** every corpse you loot teaches GoldScout real drop
  rates, on all your characters.
- **Your language:** English, Deutsch, Français, 한국어 and 繁體中文, following
  your game's language. Mob and item names come from the game itself.

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/CraftFrame.JPG" alt="Craft tab: recipes ranked by profit"></td>
    <td width="50%"><img src="docs/screenshots/TaggedMobs.JPG" alt="Hunt markers over the mobs you're hunting"></td>
  </tr>
  <tr>
    <td align="center"><b>Craft tab:</b> every recipe you know, by profit</td>
    <td align="center"><b>Hunt mode:</b> the mobs you're after, marked</td>
  </tr>
</table>

## Prices every hour, without scanning

Press **Scan AH** at any auctioneer and GoldScout reads the whole auction house
in a few seconds. Or let the free **[GoldScout Companion](https://wowgoldscout.com/companion)**
do it for you: about once an hour it brings Blizzard's auction house snapshot
for your realm into GoldScout, for US, EU, Korean and Taiwanese realms. Your own
scans still win when they're newer. Until you have either, GoldScout uses
regional estimates that ship with each release, so the Farm list works the
moment you install it.

The companion runs quietly in the system tray on Windows, never pops up over
your game, and also shares what GoldScout learns from your loot, so the Farm
tab keeps getting better for everyone. (A macOS version runs from source; a
signed Mac app is planned.)

## Install

1. Get GoldScout from [CurseForge](https://www.curseforge.com/projects/1790110),
   [Wago](https://addons.wago.io/addons/QKyqnaK7) or the
   [Releases](https://github.com/Alkhara/GoldScout-WoW/releases/latest) page.
   For a manual install, unzip the `GoldScout` folder into
   `World of Warcraft\_forever_\Interface\AddOns\` and restart the game.
2. Optional but recommended: download `GoldScoutCompanion.exe` from the
   [latest release](https://github.com/Alkhara/GoldScout-WoW/releases/latest)
   and launch it. There's nothing to install; it finds your WoW folder itself.

## Getting started

Type `/gscout`: the Farm list is ranked straight away, and a short checklist
shows what's left to set up, ticking itself off as you go.

1. Prices for your own auction house: the companion brings them in, or press
   **Scan AH** at any auctioneer.
2. If you craft, open each of your profession windows once, so the **Craft**
   tab knows your recipes.
3. Pick a farm and press **Hunt**.

Type `/gscout` to open the window any time. The full guide, with every command
and setting, is in [GoldScout/README.md](GoldScout/README.md).

## Help build the data

GoldScout uses no data from Wowhead or any other site: every drop rate comes
from players looting in game. The more people share, the better the Farm tab
gets for everyone.

- **Automatically:** [GoldScout Companion](https://wowgoldscout.com/companion)
  shares new data after you agree to the terms once.
- **By hand:** type `/gscout export` in game, press **Ctrl+C**, and paste it
  into the [Share drop data](https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml)
  form.

Exports contain no character or account names. Accepted data ships in the next
weekly release. See the [Contributor Terms](docs/CONTRIBUTOR_TERMS.md) and
[Privacy Policy](docs/PRIVACY.md).

## Plays by the rules

GoldScout only shows you information. It never moves, targets, attacks, loots
or clicks anything for you, and it respects every limit Blizzard puts on addons.
It's free, and every feature is the same for everyone. Auction data comes from
the Blizzard Entertainment Game Data API; GoldScout is a fan project, not
affiliated with or endorsed by Blizzard Entertainment.

## Contributing

Bug reports and ideas are welcome in
[Issues](https://github.com/Alkhara/GoldScout-WoW/issues). **Translations are
new**, so if a word reads wrong in your language, open an issue or edit the
matching `GoldScout/Locale_<language>.lua`. To work on the code, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

The source code is MIT-licensed ([LICENSE](LICENSE)). The community drop data is
covered by the [GoldScout Data License](DATA_LICENSE.md): use it in GoldScout,
but don't extract or reuse it elsewhere without permission.
