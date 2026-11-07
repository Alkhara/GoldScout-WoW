# GoldScout: store page draft (CurseForge and Wago)

**Name:** GoldScout
**Summary (one line):** Tells you what's worth farming or crafting on the character you're playing, using live auction house prices.
**Categories:** Auction & Economy; Professions; Map & Minimap
**Game version:** WoW Forever (1.60.1)
**License:** MIT

---

## Description

**What should *this* character be doing for gold right now?** GoldScout answers that for whichever character you're logged in on: its level, class, faction and professions, priced against your own auction house.

### Live prices, no setup
Open the auction house and GoldScout scans every listing's lowest price and quantity in a few seconds, using the same light summary scan Auctionator uses. Prices are kept per realm and faction and show on item tooltips.

### Farm tab
Ranks farms by estimated gold per hour for your character:
- herbs, ore and leather your Herbalism, Mining or Skinning skill can gather
- cloth from humanoids near your level
- mobs whose drops you've learned are valuable, from your own loot

The **Lvl** column is green when the mobs still give you experience, yellow when only some do and gray when none do. Tick **Gives XP** to level and earn at the same time.

### Craft tab
Ranks every recipe you know by profit per craft: auction house price after the cut, minus the cheapest cost of the materials (vendor prices are learned automatically).

### Hunt mode
Pick a farm and press **Hunt**:
- Blizzard's own waypoint arrow to where you usually find those mobs
- an icon over the mobs you're hunting (enemy nameplates on)
- a live panel: kills, drops, your drop rate, loot value and gold per hour
- a summary and history when you stop

### Gets smarter as you play
Every corpse you loot teaches GoldScout what that mob really drops, on all your characters. Share your data with `/gscout export` and it goes into the next release for everyone.

### Data sources
All mob drop rates and spawn locations are collected in game by GoldScout players. Nothing is copied from third-party sites.

### Plays by the rules
GoldScout only shows information. It never moves, targets, attacks, loots or marks anything for you, and it doesn't use the combat log or send data anywhere. It's free, with no paid features, ever.

---

## Commands
`/gscout` window · `/gscout scan` · `/gscout hunt` · `/gscout skills` · `/gscout set kills 80` · `/gscout help`

## Screenshots to take before publishing
1. The Farm tab beside the auction house, with the XP colors showing.
2. Hunt mode: the waypoint arrow plus the hunt panel mid-farm.
3. A mob tooltip with GoldScout lines, and a nameplate icon.
4. The Craft tab with a profitable recipe's tooltip open.

## Links (fill in)
- Source: GitHub (make the repo public, or link a public mirror)
- Support the project: Ko-fi / Patreon link here only, never in game
