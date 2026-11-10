# GoldScout

**Find the best gold for your character in World of Warcraft: Forever.**

Website: **https://wowgoldscout.com**

GoldScout scans the auction house when you visit an auctioneer, then ranks what
your character can farm or craft for the most gold per hour: based on your
level, class, faction and professions. Log onto a level 10 druid herbalist or a
level 25 rogue, and you get advice that fits that character.

## Features

- **Farm tab:** farms ranked by estimated gold per hour, including mob drops,
  cloth, herbs, ore, leather, pickpocketing for rogues, and valuable crafting reagents
  selling on your auction house right now.
- **Craft tab:** every recipe you know, ranked by profit after the auction house
  cut and the cheapest cost of materials.
- **Hunt mode:** pick a farm and press Hunt. You get Blizzard's map waypoint to
  the spot, an icon over the mobs you're after, and a panel tracking kills,
  loot, drop rate and gold per hour.
- **Learns as you play:** every corpse you loot teaches GoldScout real drop
  rates, on all your characters.
- **Experience check:** see at a glance which farms still give you XP, so you
  can level and earn at the same time.
- **Price tooltips:** the latest auction price and listing count on every item.
- **Prices without scanning:** with the free
  [GoldScout Companion](companion/README.md) on Windows, GoldScout gets
  Blizzard's hourly auction house snapshot for your realm, and your own scans
  still win when they're newer.

## Install

Get GoldScout from CurseForge, Wago, or the
[Releases](https://github.com/Alkhara/GoldScout-WoW/releases) page here. For a
manual install, unzip the `GoldScout` folder into
`World of Warcraft\_forever_\Interface\AddOns\` and restart the game.

Then add the free [GoldScout Companion](https://wowgoldscout.com/companion) on
Windows: it brings auction prices into GoldScout every hour without scanning,
and shares your drop data so the Farm tab keeps getting better.

## Getting started

1. Open each of your profession windows once, so GoldScout learns your recipes.
2. Visit an auctioneer. GoldScout opens beside the auction house; press **Scan AH**.
3. Check the **Farm** and **Craft** tabs, pick something, and press **Hunt**.

Type `/gscout` to open the window any time. The full guide, with every command
and setting, is in [GoldScout/README.md](GoldScout/README.md).

## Help build the data

GoldScout uses no data from Wowhead or other sites: every drop rate comes from
players. The more people share, the better the Farm tab gets for everyone.

1. In game, type `/gscout export` and press **Ctrl+C**.
2. Paste it into the
   [Share drop data](https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml)
   form.

On Windows, [GoldScout Companion](https://wowgoldscout.com/companion) does it
for you: it runs quietly in the system tray, shares new data automatically
after you agree to the terms once, and brings in auction prices every hour.
Download `GoldScoutCompanion.exe` from the
[Releases](https://github.com/Alkhara/GoldScout-WoW/releases) page.

Exports contain no character or account names. Accepted data ships in the next
release. See the [Contributor Terms](docs/CONTRIBUTOR_TERMS.md) and
[Privacy Policy](docs/PRIVACY.md).

## Plays by the rules

GoldScout only shows you information. It never moves, targets, attacks, loots or
clicks anything for you, and it respects every limit Blizzard puts on addons.
It's free, and every feature is the same for everyone.

## Contributing

Bug reports and ideas are welcome in
[Issues](https://github.com/Alkhara/GoldScout-WoW/issues). To work on the code,
see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

The source code is MIT-licensed ([LICENSE](LICENSE)). The community drop data is
covered by the [GoldScout Data License](DATA_LICENSE.md): use it in GoldScout,
but don't extract or reuse it elsewhere without permission.
