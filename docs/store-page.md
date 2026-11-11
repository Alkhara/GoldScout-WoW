# GoldScout: store page text (CurseForge and Wago)

Keep both store pages identical: paste the sections below into each site's
fields. The description is written in Markdown.

CurseForge doesn't allow download links to files hosted elsewhere, and wants
links to outside sites at the bottom of the page. So the description names
GoldScout Companion and what it does, but its only links are in **Links** at
the end, and they go to wowgoldscout.com pages, never straight to the exe.

**Name:** GoldScout
**Summary (one line):** Tells you what's worth farming or crafting on the character you're playing, using live auction house prices, updated hourly with the free companion app.
**Categories:** Auction & Economy; Professions; Map & Minimap
**Game version:** WoW Forever (1.60.1)
**Logo:** `docs/logo/goldscout-logo-1024.png`
**License:** MIT (code); GoldScout Data License (community drop data)
**Website:** https://wowgoldscout.com
**Source:** https://github.com/Alkhara/GoldScout-WoW

---

## Description

**What should *this* character be doing for gold right now?** GoldScout answers that for whichever character you're logged in on: its level, class, faction and professions, priced against your own auction house.

> **Get the most out of GoldScout: add GoldScout Companion.** The free Windows app brings auction house prices into GoldScout every hour, without scanning, and shares your drop data automatically so the Farm tab keeps getting better. Get it from the GoldScout website (link at the bottom of this page).

### Live prices, two ways
- **Every hour, without scanning:** with GoldScout Companion running, GoldScout gets Blizzard's hourly auction house snapshot for your realm and faction, plus the Blackwater (goblin) auction house as an extra tooltip line.
- **Right now, with one click:** press **Scan AH** at the auction house and GoldScout reads every item's lowest price and quantity in a few seconds. Your own scan always wins when it's newer.

Prices are kept per realm and faction and show on item tooltips. Until you have your own, GoldScout starts with regional estimates from Blizzard's data that ship with every release, so the Farm list works the moment you install it.

### Farm tab
Farms ranked by estimated gold per hour for your character:
- mobs with valuable drops, using real drop rates from players
- cloth from humanoids up to your level
- herbs, ore and leather your Herbalism, Mining or Skinning skill can gather
- fishing, zone by zone, for open water and each kind of fishing pool, from what players actually fish up
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

**GoldScout Companion** shares for you: it runs quietly in the system tray, never shows pop-ups over your game, and uploads new data after you agree once. It only reads GoldScout's saved data and writes one small data addon; it never touches the running game. Without it, `/gscout export` and the Share drop data form do the same job.

### Honest data
Every drop rate and spawn point comes from GoldScout players looting in game. Nothing is copied from Wowhead or any other site.

### Plays by the rules
GoldScout only shows information. It never moves, targets, attacks, loots or marks anything for you, and it respects every limit Blizzard puts on addons. The addon is free, and every in-game feature is the same for everyone.

### Languages
English, Deutsch, Français, 한국어 and 繁體中文, following your game's language. The translations are new: corrections are welcome on GitHub.

### Commands
`/gscout` opens the window · `/gscout scan` · `/gscout hunt` · `/gscout export` · `/gscout skills` · `/gscout set kills 80` · `/gscout help`

---

### Links
- **GoldScout Companion** (free, Windows): https://wowgoldscout.com/companion
- Website: https://wowgoldscout.com
- Full guide: https://github.com/Alkhara/GoldScout-WoW/blob/main/GoldScout/README.md

*Auction data from the Blizzard Entertainment Game Data API. GoldScout is not affiliated with or endorsed by Blizzard Entertainment.*

---

## Screenshots

Upload these in this order, with these captions:

1. `docs/screenshots/Frame.JPG`: **Farm tab**: what this character can farm, ranked by gold per hour, with live auction prices.
2. `docs/screenshots/CraftFrame.JPG`: **Craft tab**: every recipe you know, ranked by profit after materials.
3. `docs/screenshots/Tracker.JPG`: **Hunt mode**: kills, drops and gold per hour while you farm.
4. `docs/screenshots/TaggedMobs.JPG`: **Hunt markers**: the mobs you're hunting, marked on their nameplates.
