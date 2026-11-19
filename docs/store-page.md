# GoldScout: CurseForge page

Everything on GoldScout's CurseForge page. The description is its own file,
[curseforge-description.md](curseforge-description.md): open it, select all,
copy, and paste it into the project's description (Markdown editor). Nothing
in that file needs editing first.

**Keeping it current is part of every release.** Before a hand-made release,
bring the description up to date with that release's changes (new features in
their section, new commands in Commands), then set the line below to the new
version. `tools/release.py` won't release until it matches, and afterwards it
says whether the description changed, so you know when to paste it again.

**Description reviewed for:** v0.12.32

CurseForge doesn't allow download links to files hosted elsewhere, and wants
links to outside sites at the bottom of the page. So the description names
GoldScout Companion and what it does, but its only links are in **Links** at
the end, and they go to wowgoldscout.com pages, never straight to the exe.

**Name:** GoldScout
**Summary (one line):** Tells you what's worth farming or crafting on the character you're playing, using live auction house prices, updated hourly with the companion app.
**Categories:** Auction & Economy; Professions; Map & Minimap
**Game version:** WoW Forever (1.60.1)
**Logo:** `docs/logo/goldscout-logo-1024.png`
**License:** MIT (code); GoldScout Data License (community drop data)
**Website:** https://wowgoldscout.com
**Source:** https://github.com/Alkhara/GoldScout-WoW

---

## Screenshots

Upload these in this order, with these captions:

1. `docs/screenshots/20261117_Frame.JPG`: **Farm tab**: what this character can farm, ranked by gold per hour, with live auction prices.
2. `docs/screenshots/CraftFrame.JPG`: **Craft tab**: every recipe you know, ranked by profit after materials.
3. `docs/screenshots/Tracker.JPG`: **Hunt mode**: kills, drops and gold per hour while you farm.
4. `docs/screenshots/TaggedMobs.JPG`: **Hunt markers**: the mobs you're hunting, marked on their nameplates.
