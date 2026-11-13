# What's new in GoldScout

Each release's section here becomes its release notes on GitHub, CurseForge
and Wago. Add to **Unreleased** as changes land, written for players; when
releasing, rename it to the version (`## v1.2.3`). Daily community data
releases add their own line automatically.

## Unreleased

## v0.12.2

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
