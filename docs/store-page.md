# GoldScout: store page text (CurseForge and Wago)

Keep both store pages identical: paste the sections below into each site's
fields. The description is written in Markdown.

**Name:** GoldScout
**Summary (one line):** Tells you what's worth farming or crafting on the character you're playing, using live auction house prices.
**Categories:** Auction & Economy; Professions; Map & Minimap
**Game version:** WoW Forever (1.60.1)
**Logo:** `docs/logo/goldscout-logo-1024.png`
**License:** MIT (code); GoldScout Data License (community drop data)
**Website:** https://wowgoldscout.com
**Source:** https://github.com/Alkhara/GoldScout-WoW

---

## Description

**What should *this* character be doing for gold right now?** GoldScout answers that for whichever character you're logged in on: its level, class, faction and professions, priced against your own auction house.

### Live prices, no setup
Press **Scan AH** at the auction house and GoldScout reads every item's lowest price and quantity in a few seconds. It never scans on its own, so buying something stays quick. Prices are kept per realm and faction and show on item tooltips.

### Farm tab
Farms ranked by estimated gold per hour for your character:
- mobs with valuable drops, using real drop rates from players
- cloth from humanoids up to your level
- herbs, ore and leather your Herbalism, Mining or Skinning skill can gather
- valuable crafting reagents, the mob-dropped materials professions always need, selling on your auction house right now, even before anyone has learned where they drop

The **Lvl** column is green when the mobs still give you experience, yellow when only some do and gray when none do. Tick **Gives XP** to level and earn at the same time.

### Craft tab
Every recipe you know, ranked by profit per craft: auction house price after the cut, minus the cheapest cost of the materials. Vendor prices are learned automatically.

### Hunt mode
Pick a farm and press **Hunt**:
- Blizzard's own waypoint arrow to where players find those mobs
- an icon over the mobs you're hunting (turn on enemy nameplates)
- a live panel: kills, drops, your drop rate, loot value and gold per hour
- a summary and history when you stop

### Gets smarter the more people play
Every corpse you loot teaches GoldScout what that mob really drops, on all your characters. Share what you've learned and it goes into the next release for everyone. The more players share, the better everyone's Farm tab gets.

**GoldScout Companion** (Windows, optional) shares for you: it runs quietly in the system tray, never shows pop-ups over your game, and uploads new data after you agree once. Download it from the GitHub releases page. Without it, `/gscout export` and the Share drop data form on GitHub do the same job.

### Honest data
Every drop rate and spawn point comes from GoldScout players looting in game. Nothing is copied from Wowhead or any other site.

### Plays by the rules
GoldScout only shows information. It never moves, targets, attacks, loots or marks anything for you, and it respects every limit Blizzard puts on addons. The addon is free, and every in-game feature is the same for everyone.

### Commands
`/gscout` opens the window · `/gscout scan` · `/gscout hunt` · `/gscout export` · `/gscout skills` · `/gscout set kills 80` · `/gscout help`

Website: https://wowgoldscout.com · Full guide: https://github.com/Alkhara/GoldScout-WoW/blob/main/GoldScout/README.md

---

## Screenshots

Upload these in this order, with these captions:

1. `docs/screenshots/Frame.JPG`: **Farm tab**: what this character can farm, ranked by gold per hour, with live auction prices.
2. `docs/screenshots/CraftFrame.JPG`: **Craft tab**: every recipe you know, ranked by profit after materials.
3. `docs/screenshots/Tracker.JPG`: **Hunt mode**: kills, drops and gold per hour while you farm.
4. `docs/screenshots/TaggedMobs.JPG`: **Hunt markers**: the mobs you're hunting, marked on their nameplates.
