# GoldScout Privacy Policy

*Last updated: November 10, 2026*

This policy covers the GoldScout addon and the drop data players share with it.
GoldScout is maintained by GitHub user Alkhara ("we" below).

## The addon

The GoldScout addon doesn't send anything anywhere. It doesn't connect to the
internet (WoW addons can't), doesn't use addon chat messages, and doesn't share
data with other players. Everything it records stays in your own WoW folder, in
`WTF\Account\<account>\SavedVariables\GoldScout.lua` and the per-character
files next to it:

- auction house prices from your scans, per realm and faction
- which realms and factions you've played, and when (so GoldScout Companion
  knows which auction houses' prices to save for you)
- vendor prices you've seen
- your characters' profession skills and known recipes
- what you've looted from creatures, how often, at what level and where
- your settings and recent Hunt mode sessions
- a short log of GoldScout's own errors (never shared; it's there for bug reports)

## GoldScout Companion

The companion app for Windows and macOS reads GoldScout's saved data file
(`GoldScout.lua` in each account's SavedVariables folder). Its only notification
says a new version is out, and only while World of Warcraft isn't running. The
only thing it changes in your WoW folder is the `GoldScout_Prices` addon folder
described below.

When you first open it, it asks you to agree to the
[Contributor Terms](CONTRIBUTOR_TERMS.md). If you agree, it shares
automatically: whenever GoldScout saves a new export (when you log out or
/reload), the companion uploads it to the GoldScout upload service. If you
choose "Not now", nothing is uploaded; you can still share by hand through the
GitHub form. You can pause automatic sharing, or stop the companion starting
when you log in, at any time from its tray icon (on macOS, from Settings in its
window). On macOS, starting at login is a file in
`~/Library/LaunchAgents/com.wowgoldscout.companion.plist`, removed when you turn
it off.

To offer updates, the companion asks GitHub for the latest GoldScout release
shortly after it starts and every few hours (the request carries only the
companion's version). It downloads an update only when you click Update, and
uses it only if the file matches the release's published hash and is code-signed
by GoldScout's publisher (on macOS: signed with GoldScout's Apple Developer ID
and notarized by Apple). GitHub sees your IP address for these requests, as
described in its [privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).

**Auction prices.** About once an hour the companion downloads current auction
house prices from the GoldScout server for the realms and factions you've played
in the last 30 days, and saves them in `Interface\AddOns\GoldScout_Prices`, so
GoldScout can show them in game. These downloads work whether or not you share
drop data, and send nothing about you: the request names only an auction house
number. Your realm names stay on your PC. To find your auction house when the
server doesn't know your realm yet, the companion compares your own recent
GoldScout scan with each auction house, on your PC. The prices come from
Blizzard's Game Data API, and the companion removes them once they're more than
30 days old. You can turn this off from the tray icon (on macOS, from Settings),
which also removes the folder.

On your computer it stores, in `%APPDATA%\GoldScout Companion\config.json`
(on macOS, `~/Library/Application Support/GoldScout Companion/config.json`): your WoW
folder location, whether you agreed to the terms and when, your settings, for
each install the upload token and the last snapshot it uploaded, and for auction
prices which auction house matches each of your realms and when it last saved
them.

## The upload service

The upload service runs on Cloudflare. For each install it keeps only the
newest export (the same content described below), the Contributor Terms version
you agreed to, a hash of the install's upload token, when it was uploaded, how
many times, and which companion version uploaded it last.
The token stops anyone else replacing your install's data. Like any website,
Cloudflare sees your IP address when the companion connects; we don't store it.
To limit abuse, the service keeps a salted, one-way hash of the address for two
days when a new install registers, then deletes it. Cloudflare processes data
as described in its own [privacy policy](https://www.cloudflare.com/privacypolicy/).

Accepted uploads are added to the public repository like form submissions, in
`data/submissions/` under a file named after the install ID. Uploads from the
companion aren't linked to any GitHub account.

## Sharing drop data

Nothing leaves your computer unless you choose to share it. `/gscout export`
shows only your loot records: creature IDs, names and levels, kill and
pickpocket counts, item drops, the average map position where you looted
each creature, the names of those items and zones as your game shows them, and
the IDs of items your characters' professions can make. It doesn't include
character names, account names, realm names, prices, skill levels or settings.

Each export also starts with an install ID: 12 random letters and digits that
GoldScout generates once per WoW account, plus a snapshot number. The ID isn't
derived from your account, character or computer. It's published in the
community data file so your own GoldScout can recognize the snapshot you shared
and avoid counting your loot twice.

When you submit an export through the "Share drop data" issue form on GitHub:

- **It's public.** The issue, including the export and your GitHub username, is
  visible to anyone, under GitHub's own [privacy statement](https://docs.github.com/site-policy/privacy-policies/github-general-privacy-statement).
- **We store it in the repository.** Accepted exports are saved in
  `data/submissions/`, in a file named after your numeric GitHub user ID, so a
  newer export from you replaces your older one.
- **We combine it.** Your data is merged with other players' into GoldScout's
  community data and may be used as described in the
  [Contributor Terms](CONTRIBUTOR_TERMS.md), including in paid products.

Loot positions and kill counts could in principle hint at when and where you
played. If that matters to you, don't share.

## What we don't do

We don't collect email addresses, payment details or analytics through the
addon, the companion or the submission process, we don't store IP addresses
(beyond the short-lived hash above), and we don't sell personal information.
GitHub, which hosts the repository and issues, processes data as described in
its own privacy statement.

## Removal

To have your submission file removed from the repository, your submission
issue deleted, or your uploads deleted from the upload service (tell us your
install ID, shown in your exports), open an issue asking us to. Pausing
automatic sharing in the companion stops new uploads. Data already combined into a release
can't be separated from other players' data.

## The website

wowgoldscout.com has no accounts, cookies, analytics or ads. Its farm, mob,
reagent and zone pages load current auction house prices from the GoldScout
server (goldscout-api.cawley22.workers.dev), as the companion does. Like any
website, Cloudflare sees your IP address for those requests; we don't store it. The realm type
and faction you pick for prices is remembered in your own browser (local
storage); it only decides which auction house's prices your browser downloads.

The prices are public auction house listings from Blizzard's Game Data API,
reduced to the lowest buyout and quantity per item. They contain no player
names or other player data, and we keep each auction house's newest snapshot
for at most 30 days.

## Future services

If we launch anything else that collects data differently, this policy will be
updated before it does.

## Contact

Open an issue at https://github.com/Alkhara/GoldScout-WoW/issues.
