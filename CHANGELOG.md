# What's new in GoldScout

Each release's section here becomes its release notes on GitHub and
CurseForge. Add to **Unreleased** as changes land, written for players; when
releasing, rename it to the version (`## v1.2.3`). Daily community data
releases add their own line automatically.

## Unreleased

## v0.12.57

- **No more high-level dungeon farms at your level:** inside dungeons the game hides a mob's level, so most dungeon mobs have none in GoldScout's data. With **Show dungeon drops** on, the Farm tab listed them at your own level, so a level 31 character saw Stratholme bosses. A mob of unknown level is now listed only with **All levels** on, without a level.

## v0.12.56

- **Kill rates count the hunt between kills:** GoldScout now also times kills up to ten minutes apart in the same zone, so looking for the next one and waiting for respawns count. A mob there are only a few of no longer looks as quick to farm as a crowded camp. Kill times start over with this version so shared data follows the new rule; until enough players have timed a mob the new way, gold per hour uses the old times.

## v0.12.55

- **Cleaner dungeon drop rates from rogues:** before v0.12.48, a Pick Pocket inside a dungeon counted as a kill, and those kills stayed in your saved loot. On an account that picks pockets, GoldScout now shares only the dungeon loot recorded from this version on. Your own Farm tab and drop rates still use everything you've looted.

## v0.12.54

- **Fast-loot add-ons no longer make drops look rarer:** when another add-on emptied a corpse before GoldScout could read its loot, the kill could be counted as one that dropped nothing. GoldScout now leaves such a kill out.
- Updated drop data from the community.

## v0.12.50

- **Real kill rates for gold per hour:** GoldScout now times your solo kills (from one kill to the next, leaving out breaks of over three minutes), and shared drop data includes those times. Once enough players have timed a mob, gold per hour uses the pace players really kill it, instead of the same 70 kills an hour for every mob: on the Farm tab (unless you set your own kills per hour), in the website's gold guides and on its mob and item pages.
- Updated drop data from the community.

## v0.12.48

- **Pickpocketing in dungeons counts as pickpocketing:** inside dungeons the game hides which mob a Pick Pocket hit, so its loot was counted as a kill. GoldScout now counts the loot window that opens right after the cast as that mob's pockets.
- **Names for mobs you loot without targeting them,** such as a boss your group killed, when the game shares the name.
- Updated drop data from the community.

## v0.12.43

- **Shared drop data that was turned away now goes in:** a saved pickpocket count could be written as "-0", and the community data refused the whole share. GoldScout now writes it as 0, and shares already sent that way are accepted.
- **Pocket loot left out of kill drops:** besides junkboxes, the pocket watches, Lucky Charms, Boot Knives, Intricate Baubles, Empty Sea Snail Shells and Syndicate Emblems that rogues' pickpockets put in kill loot no longer count as mob drops.
- **Fewer stray error reports:** an error in another add-on's tooltip hook (such as Auctioneer's) while a GoldScout tooltip opens is no longer saved as a GoldScout error.
- Updated drop data from the community.

## v0.12.41

- **No more "GoldScout was blocked" warning after loading:** v0.12.40 watched the combat log to spot your Pick Pocket casts, and the game only lets its own interface do that, so it warned that GoldScout had been blocked. GoldScout now spots the cast without the combat log, and pickpocketing is still recorded the same way.
- Updated drop data from the community.

## v0.12.40

- **Pickpocketing is recorded right, however you macro it:** GoldScout now sees your Pick Pocket cast itself, so pockets you pick without targeting the mob count as pickpockets, not kills. When Cheap Shot or Ambush closes the pickpocket window before you empty it, the pocket loot ends up on the corpse with the mob's own; that corpse is now left out of your drop rates instead of making the mob look like it drops junkboxes. Junkboxes already shared as kill loot are left out of the community data too.
- **Fewer false error reports:** when another add-on's events loop until the game runs out of room ("C stack overflow"), GoldScout no longer logs it as its own error just because the last event in the loop was one GoldScout listens to.
- Updated drop data from the community.

## v0.12.39

- **Fewer false error reports:** when the game blocks a Blizzard window's own action (the guild window, for one) and blames GoldScout, GoldScout no longer logs or reports it. Blocks of things GoldScout itself does, like scanning the auction house, still are.
- Updated drop data from the community.

## v0.12.36

- **Dungeon farms are hidden unless you want them:** a new setting, **Show dungeon drops** (Settings › Farm list, or `/gscout set dungeons on`), adds farms on mobs inside dungeons and raids to the Farm list. They're off by default: you run those with a group and a lockout, so their gold per hour doesn't compare with farming on your own.
- **Long shots on the Flip tab:** one item listed far above its usual price (say Simple Wildflowers at 100g) could top the Flip tab as a huge flip you'd never sell. Flips that sell for over 3 times the item's regional price are now long shots: hidden unless you tick **Long shots** on the Flip tab, then listed after the others with an orange **!** and their usual price in the tooltip. Some are real gaps between the factions, so they're there when you want them. The same Blackwater flips, long shots included, are now on the website for every realm type: [wowgoldscout.com/flips](https://wowgoldscout.com/flips).
- **Dungeon mobs get their zone:** inside dungeons the game gives addons no map position, so GoldScout recorded no zone either, and those farms said "where players loot it". GoldScout now records which dungeon they're in. Shared drop data fills in their zones as players run dungeons with this version.
- Updated drop data from the community.

## v0.12.34

- **No more "script ran too long" from the Farm tab:** with over 2,400 mobs in the community data, building the Farm list could still take longer on a slower PC than WoW lets one script run. It's now built a few milliseconds at a time over a few frames; the list you last saw stays up until the new one is ready.
- **Item names no longer turn into "Item 1234":** the game forgets items again while GoldScout looks at thousands of them, so names could flicker and then stay as numbers. GoldScout now remembers each item's name and details for the rest of your session.
- Updated drop data from the community.

## v0.12.32

- **Flip tab: buy at Blackwater, sell on your auction house.** The new tab lists items that are cheap on your realm's Blackwater (goblin) auction house and sell for more on your faction's, with the profit each after the cut, the margin, and how many are listed on both. It needs prices for both auction houses: GoldScout Companion saves them every hour, or scan at each. `/gscout flip` opens it.
- **Bag items worth listing now show an auction house hammer, not a gold coin:** junk-selling addons such as Scrap mark items to sell to a vendor with a gold coin, which is the opposite advice, and the two were easy to mix up.
- Updated drop data from the community.

## v0.12.31

- **The Farm tab's Each column is now Per kill:** it was never an item's price, but what one kill (or node, skin, catch or pickpocket) is worth on average from that item, its price times its drop chance. The item's own price is in the row's tooltip.
- Updated drop data from the community.

## v0.12.29

- **The Farm tab opens about three times faster:** with over 2,000 mobs in the community data, building the Farm list could freeze the game for half a second, and on slower PCs stop with "script ran too long". It now values each item and each mob's loot once per update instead of once per row.
- Updated drop data from the community.

## v0.12.28

- **GoldScout Companion has a dark mode on Windows:** its window, title bar included, follows Windows' app mode (Settings › Personalization › Colors), and switches when you change it. On a Mac it already followed your Mac's appearance.
- **A gold coin on bag items worth listing:** crafting reagents and green or better items that sell for at least double their vendor price on your auction house, after the cut, get a small gold coin in your bags (Blizzard's bags and Bagnon), and their tooltip says what they're worth on each. Gray junk, quest items and bound items never do. It needs your own realm's prices, from a scan or GoldScout Companion. Turn it off in Settings › Interface, or with `/gscout set bagcoins off`.

## v0.12.27

- **Sharing survives a new PC:** after moving your game to a new PC or reinstalling Windows, GoldScout Companion could stop sharing with "This GoldScout data is registered to another copy of the companion", because the key it shares with stayed on the old PC. GoldScout now keeps a private recovery key in its saved data (never in your exports), and the companion uses it to get a new sharing key on its own. It protects you from your first share with this version of GoldScout and the companion.
- Updated drop data from the community.

## v0.12.25

- **Sharing works with French, Chinese and Korean names:** a name with a curly apostrophe, a no-break space before ":", guillemets or full-width punctuation made GoldScout Companion refuse the whole export ("the name contains a character that isn't allowed"). GoldScout now writes that punctuation plainly, names saved by older versions included, and the companion and the data bot tidy any odd character instead of refusing the export.
- Updated drop data from the community.

## v0.12.24

- **Drop rates count what dropped, not just what you took:** loot left on a corpse (full bags, or junk you skip) used to count the kill but not the drop, so those items looked rarer than they are. GoldScout now records everything a corpse shows when you open it, taken or not; going back for it later still counts it once. The hunt panel still counts what reaches your bags.
- Updated drop data from the community.

## v0.12.23

- **Companion:** fixed "Couldn't check for updates (CERTIFICATE_VERIFY_FAILED)" on some Windows PCs. Windows hadn't yet downloaded the root certificate GitHub uses, so the update check couldn't reach GitHub; the companion now also trusts Mozilla's list of certificates, bundled with the app.

## v0.12.22

- **Every drop from a mob, one right-click away:** target a mob, right-click its portrait and choose **Drop rates**. A window lists everything GoldScout players have looted from it, your own loot included: each item's drop chance, what it's worth and what it adds per kill, with pickpocketing listed separately. `/gscout drops` opens it for your target too.
- Updated drop data from the community.

## v0.12.20

- **GoldScout en español:** GoldScout now speaks Spanish on Spanish game clients (Spain and Latin America). It's a new translation; corrections are welcome on GitHub.
- Fixed a Lua error from Blizzard's Sell tab ("attempt to compare nil with number") when a price scan ran while an item sat in the Sell tab: the scan now pauses while the Sell tab is open and carries on when you leave it.

## v0.12.19

- **Drop data for about 200 mobs is back:** v0.12.18 left out mobs recorded only by players who joined in the last few days. They're back, with everything shared since: drop rates for over 1,400 mobs.
- Updated drop data from the community.

## v0.12.18

- **The hunt tracker splits what you earn:** the item you're hunting (its value and gold per hour on its own), other loot such as vendor trash, coin, and the total with its gold per hour. The chat summary when a hunt ends shows the same.
- **The hunting area shows with OpenMap:** with OpenMap's seamless map, the green hunting area was hidden under its map art. It now shows on OpenMap's map too, including when the area is in a zone next to the one you're looking at.
- Updated drop data from the community.

## v0.12.16

- **By item ranks items by what they earn themselves:** with **Count all loot** on, every item row used to add its mob's vendor trash and other drops to its gold per hour, so a cheap drop from a mob with good trash could top the list. Now an item row counts only its item, and its tooltip says what the mob's other loot adds. The **By mob** view counts everything a mob drops, as before.
- **Count all loot is now on for everyone,** since it only changes the By mob view. Turn it off in Settings › Farm list, or with `/gscout set allloot off`.
- Updated drop data from the community.

## v0.12.14

- **Share on the website:** `/gscout export` now points to wowgoldscout.com/share, where you paste your export and press Share. No GitHub account needed, and you can put your name on the leaderboard from there too; the GitHub form still works. The site also shows the community goals: players sharing, kills, and mobs with solid drop rates.
- Updated drop data from the community.

## v0.12.12

- **Data wanted:** a new **Data wanted** button on the Farm tab (or `/gscout wanted`) lists the mobs near your
  level that still need kills before their drop rates are solid, counting every player's kills and yours, the
  ones in your zone first. Select one and press **Hunt** for a waypoint and a kill count; share your loot with
  GoldScout Companion and every player's rates get better. The same list for every level is on
  [wowgoldscout.com/data-wanted](https://wowgoldscout.com/data-wanted).
- **Zone goals and zone champions on the website:** each zone's page shows how close players are to solid drop
  rates for every mob there, and its top three contributors by kills in the zone. GoldScout Companion's
  leaderboard option is now **Show me on the public leaderboard and zone pages**: you're still anonymous unless
  you turn it on.
- **GoldScout Companion shares big exports again:** a long-time player's drop data could pass 60 KB, and the
  companion then stopped sharing it ("The export is larger than 60000 bytes"). It now shares exports up to
  250 KB. The share form on GitHub still takes up to 60 KB, so for more than that use the companion.
- Updated drop data from the community.

## v0.12.10

- **Hunting area on the world map:** while you hunt, the world map shades where you and other players have
  looted those mobs, or caught that fish, in green: the stronger the green, the more often. Turn it off in
  GoldScout's options or with `/gscout set map off`.
- Updated drop data from the community.

## v0.12.7

- **Farm tab, By mob view:** the new **By item** and **By mob** buttons switch the Farm list between one row per
  item (as before) and one row per mob. A mob's row adds up everything worth farming that it drops, so you can
  see which mob pays best to grind; click **+** to see each drop, with the mob's other loot on a line of its
  own when **Count all loot** is on. GoldScout remembers the view you picked.
- **Count all loot is steadier:** a mob's other loot now counts once players have looted it 15 times (was 10),
  and only items that have dropped at least 3 times, so one lucky recipe or green no longer inflates a mob's
  gold per hour. An item your auction house lists at more than 3 times the regional price counts at 3 times
  it, so a pile of listings nobody buys can't either. The tooltip now lists what the other loot is.
- Updated drop data from the community.

## v0.12.6

- **Contributor leaderboard:** everyone who shares drop data is ranked by their kills in the community data, on
  [wowgoldscout.com/leaderboard](https://wowgoldscout.com/leaderboard). You're anonymous unless you choose
  otherwise: GoldScout Companion's new **Leaderboard...** button shows your rank and lets you appear under a
  made-up name, or a name of your own once it's approved. With the companion, your rank also shows on
  GoldScout's minimap button.
- Updated drop data from the community.

## v0.12.4

- **Count all loot in gold per hour:** a new setting (Settings › Farm list, or `/gscout set allloot on`) that adds everything else a mob drops, vendor trash too, to its Farm rows' gold per hour, from your loot and other players'. The row's tooltip shows the extra per kill. Coin isn't recorded, so it isn't counted.
- Updated drop data from the community.

## v0.12.3

- **Mob tooltips show the community's loot:** how many times other players have looted that mob, and what its loot is worth per kill on average at your auction house's prices.
- Updated drop data from the community.

## v0.12.2

- Fixed a Lua error the Farm tab could hit while sorting what's caught at a fishing spot.
- **Community drop data now ships every day,** instead of once a week.
- GoldScout Companion's window has a **Check for updates** button, like the one in the tray menu.
- GoldScout Companion's desktop notice about a new version now comes at most once a week; its window shows **Update** whenever one is out.
- Updated drop data from the community.

## v0.12.1

- The Farm tab's checkboxes no longer run into the Hunt button; in longer languages their labels are shortened, with the full name in the tooltip.
- GoldScout Companion now reaches the GoldScout server at its own address, api.wowgoldscout.com. Older versions keep working.
- Updated drop data from the community.

## v0.12.0

- **GoldScout Companion for Mac:** a signed app, checked by Apple, for Apple
  silicon and Intel Macs. Download `GoldScoutCompanion-macOS.zip` from this
  release, open it and drag GoldScout Companion into Applications. It lives in
  the Dock instead of a tray; its window's **Settings** hold sharing, auction
  prices, **Open at login** and updates.
- GoldScout Companion bundles the latest Pillow image library, which fixes
  published security issues. The companion only uses it for its own tray icon.
- **Fishing on the Farm tab:** GoldScout now learns what you fish up, in which
  zone, and whether it came from open water or a fishing pool. Each zone's open
  water and each kind of pool gets its own row, valued from everything players
  have caught there; the tooltip lists the catch, and Hunt points you to where
  the fish are and counts your catches. Shared like your drop data, so the rows
  fill in as players fish. Set your pace with `/gscout set catches`.
- GoldScout's error log no longer keeps other addons' errors as its own.

## v0.11.0

- **The Farm list works the moment you install GoldScout:** until you have
  prices of your own, it uses regional estimates (the typical price across
  your region's auction houses, from Blizzard's data) that ship with each
  release. Your own scans and GoldScout Companion's prices replace them.
- **The welcome is now a setup checklist** that ticks itself off: prices,
  recipes (only if you craft) and your first Hunt.

## v0.10.1

- **A Settings page:** GoldScout now has its own page in Options › AddOns, with
  every setting in one place. Open it from the new gear at the top left of the
  GoldScout window, or with `/gscout options`.
- **A short welcome for new players** the first time they open GoldScout:
  what to do first and where things are. `/gscout welcome` shows it again.
- **Mob names always follow your game's language,** even for mobs you met
  while playing in another language. Mobs your game hasn't loaded yet get
  their name a moment later instead of "Mob #…".
- **Longer translations fit:** the filter checkboxes space themselves by their
  labels, and the profession line shortens instead of being cut off.
- **More translated:** the "Est. /hour" column and the confidence words in
  tooltips.
- Your saved data now upgrades safely from one version to the next.
- **GoldScout Companion sends error reports,** so bugs get fixed faster: only
  GoldScout's own errors, with folder paths removed. It's on if you share drop
  data; turn off **Send error reports** in the tray menu (Settings on a Mac)
  any time.
- Updated drop data from the community.

## v0.10.0

- **GoldScout in your language:** Deutsch, Français, 한국어 and 繁體中文, following
  your game's language. English stays the default. The translations are new;
  corrections are welcome on GitHub.
- **Mob names in your own language,** straight from the game.
- **Hunts remember where mobs are looted** (roughly, per zone), for a hunting
  area on the world map in a later version.
- GoldScout Companion 0.10.0 works with every newer GoldScout, so sharing
  never waits on a companion update.

## v0.9.0

- **Auction prices for EU, Korean and Taiwanese realms,** as well as US.
- **Hunting an item marks every mob that drops it in the zone,** not only the
  best one.
- **Auction houses are named the way players say them,** like "PvP Horde",
  instead of the realm's internal name.
- Regions without prices yet now say so.

## v0.8.0

- **Blackwater (goblin) auction houses are their own market:** scanning there
  never replaces your faction's prices, and tooltips add a Blackwater line.
  `/gscout set blackwater off` hides it.
- The Farm tab's companion tip now leads with hourly prices, and hides once
  the companion is saving prices for you.

Older releases: see [GitHub releases](https://github.com/Alkhara/GoldScout-WoW/releases).
