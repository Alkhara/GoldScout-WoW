# GoldScout

Website: https://wowgoldscout.com

A World of Warcraft: Forever addon that scans the auction house when you visit an
auctioneer and ranks what is most profitable for your character to farm or craft,
based on your level, class, faction and professions.

## What it does

- **Scans the auction house** automatically when you open it (at most every 10
  minutes), or when you press **Scan AH**. It reads the lowest price per unit and
  the quantity listed for every item, in a few seconds, using the same summary
  scan Auctionator uses on the Forever client.
- **Farm tab** ranks farms you can do at your level by estimated gold per hour:
  - mobs whose drops you've learned are valuable (from your own loot)
  - cloth from humanoids near your level
  - herbs, ore and leather you can gather with your Herbalism, Mining or Skinning skill
  - **Market** rows: crafting reagents (items the game marks "Crafting Reagent") selling on your auction house near your level
    that no farm covers yet, ranked by price per item. Gray (vendor trash), crafted and vendor-sold
    items are left out unless players have looted them from a mob. Their drop rate is learned
    as you loot them. Tick **Known rates** to hide them.
- **Craft tab** ranks every recipe you know by profit per craft: auction house
  price after the 5% cut, minus the cheapest cost of the materials (vendor price
  when they are sold by vendors, otherwise the auction house price).
- **Item tooltips** show the last auction house price, how many were listed,
  the average daily low, and the vendor price when known.
- **Experience check**: on the Farm tab the **Lvl** column is green when every
  mob in that farm gives you experience, yellow when only some do, and gray when
  they're all gray to you. Tick **Gives XP** to hide the no-experience farms.
  (Uses the classic gray-level rule; hidden at level 60.)
- **Hunt mode**: click a Farm row, then press **Hunt** (see below).
- **Learns from your loot**: every corpse you loot and pocket you pick, on any
  character, updates drop rates for that mob, combined with the community data
  players have shared. Mobs appear on the Farm tab as **Learned** from the first
  drop. The **Chance** column's color shows how many kills back the rate up:
  orange under 5, yellow 5-14, light green 15-49, green 50 or more. Until a mob
  has 15 kills, gold per hour uses a cautious rate so one lucky drop doesn't top
  the list.

## Hunt mode

Select a farm on the Farm tab and press **Hunt**:

1. **Waypoint.** GoldScout places Blizzard's own map waypoint at the nearest
   spawn hotspot and tracks it, so you get the standard on-screen arrow and
   distance. When you arrive it clears the waypoint (only if it is still the one
   GoldScout placed).
2. **Mob icons.** Mobs you're hunting get a small icon above their nameplate.
   Turn on enemy nameplates (default key V) to see them.
3. **Mob tooltips.** Mousing over a listed mob shows its valuable drop and
   chance, plus what you've looted from it yourself.
4. **Hunt panel.** A small movable panel shows time, kills or pickpockets, how
   many of the item you've gained, your drop rate against the expected rate,
   loot value, coin, and gold per hour. **Stop** ends the hunt and prints a
   summary; `/gscout hunt history` lists recent hunts.

Gathering, cloth and skinning rows have no single spot, so their hunts just
track loot.

## Staying within the rules

GoldScout only shows you information. It never moves your character, targets,
attacks, casts, loots, clicks, or sets raid markers for you; you do all of
that yourself. The waypoint is Blizzard's own, the same one you get by
ctrl-clicking the map. The nameplate icons and tooltip lines are visible only
to you. If the game hides a value from addons (Forever keeps Midnight's addon
restrictions), GoldScout skips it instead of working around it. It doesn't use
the combat log, send addon messages, or share data with anyone; everything
stays in your own SavedVariables.

## Install

1. Copy the whole `GoldScout` folder into your Forever addons folder:
   `World of Warcraft\_forever_\Interface\AddOns\` (on Windows usually under
   `C:\Program Files (x86)\`)
   (the result should be `...\AddOns\GoldScout\GoldScout.toc`).
2. If the game is running, exit it completely and start it again. WoW only
   finds new addon folders at startup; after that, `/reload` picks up changes.
3. Make sure GoldScout is enabled in the AddOns list on the character screen.

## First run

1. Open each of your profession windows once (including Cooking and First Aid),
   so GoldScout learns your recipes.
2. Visit an auctioneer. GoldScout opens beside the auction house and scans.
3. Visit vendors that sell crafting supplies (thread, vials, spices, flux) so
   GoldScout learns their exact prices.
4. Type `/gscout` any time to open the window.

## Commands

| Command | What it does |
|---|---|
| `/gscout` | Show or hide the window |
| `/gscout farm`, `/gscout craft` | Open a tab |
| `/gscout scan` | Scan prices (the auction house must be open) |
| `/gscout hunt` | Show the hunt panel (or open the Farm tab to start one) |
| `/gscout hunt stop` | End the current hunt and print a summary |
| `/gscout hunt history` | List your last five hunts |
| `/gscout export` | Copy your learned drop data to share |
| `/gscout skills` | Show the skills and recipes GoldScout has read |
| `/gscout set kills 80` | Your kills per hour on same-level mobs (default 70) |
| `/gscout set nodes 25` | Herb or ore nodes per hour (default 25) |
| `/gscout set picks 110` | Pickpockets per hour (default 110) |
| `/gscout set autoscan off` | Stop scanning automatically |
| `/gscout set window off` | Stop opening beside the auction house |
| `/gscout set tooltip off` | Remove prices from item tooltips |
| `/gscout set waypoint off` | Hunts stop placing the map waypoint |
| `/gscout set markers off` | Hunts stop putting icons on nameplates |
| `/gscout set mobtips off` | Remove GoldScout lines from mob tooltips |
| `/gscout set learn off` | Stop learning drop rates from your loot |
| `/gscout reset prices` | Forget this faction's saved prices |
| `/gscout reset drops` | Forget the drop rates learned from your loot |

`/goldscout` works as well as `/gscout`.

## How the numbers work

- **Prices** are the lowest buyout per unit at the last scan. One cheap listing
  can make an item look cheaper than it really is; the **Listed** column shows
  how deep the market is, and rows with few listings warn you in the tooltip.
- **Each** is the expected value of one kill, node, skin or pickpocket: price
  after the 5% auction house cut times the drop chance or yield.
- **Est. /hour** multiplies that by your rate. Kills per hour go up for mobs
  well below your level and down for mobs above it. Tune the rates with
  `/gscout set` so they match how you play.
- **Mob drop rates and spawn spots** come only from players: your own loot,
  plus community data that players share with `/gscout export` and that ships
  with each release. Mobs show up on the Farm tab as **Learned** from their
  first drop, colored by confidence, and their hunts get a waypoint to where
  players find them.

## Sharing your data

`/gscout export` opens a window with your learned drop data: drops, kill
counts, mob levels and loot locations, with no character names. Copy it and
paste it into the **Share drop data** form on GitHub:
https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml

Your own client knows which of your exports the community data includes, so
your loot is never counted twice. By sharing it you agree to the [Contributor Terms](https://github.com/Alkhara/GoldScout-WoW/blob/main/docs/CONTRIBUTOR_TERMS.md).
Every shared export makes the rankings better for everyone.
- **Gathering zones** are the classic spawn zones. Forever expanded several
  zones, so treat them as a starting point.
- **Yields** (herbs per node, ore per node, leather per skin, cloth per kill)
  are rough averages.

## Limitations

- It can't tell how quickly something sells, only how many are listed.
- Pickpocket values count the junkbox contents, not the coin you also get.
- Enchants have no item to sell, so enchanting recipes are not ranked.
- Prices are per realm and faction; Alliance and Horde characters each need
  their own scan.

## Troubleshooting

- If nothing happens, type `/console scriptErrors 1` and `/reload` to see Lua
  errors, or install BugSack. Please send any error text along when reporting.
- A scan that gets no reply for 20 seconds stops and keeps what it received.
- Avoid searching the auction house yourself while a scan is running; the two
  searches share the same results list.
