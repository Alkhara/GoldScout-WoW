# GoldScout Privacy Policy

*Last updated: November 7, 2026*

This policy covers the GoldScout addon and the drop data players share with it.
GoldScout is maintained by GitHub user Alkhara ("we" below).

## The addon

The GoldScout addon doesn't send anything anywhere. It doesn't connect to the
internet (WoW addons can't), doesn't use addon chat messages, and doesn't share
data with other players. Everything it records stays in your own WoW folder, in
`WTF\Account\<account>\SavedVariables\GoldScout.lua` and the per-character
files next to it:

- auction house prices from your scans, per realm and faction
- vendor prices you've seen
- your characters' profession skills and known recipes
- what you've looted from creatures, how often, at what level and where
- your settings and recent Hunt mode sessions
- a short log of GoldScout's own errors (never shared; it's there for bug reports)

## GoldScout Companion

The companion app for Windows reads GoldScout's saved data file
(`GoldScout.lua` in each account's SavedVariables folder). It never changes game
files and never shows notifications.

When you first open it, it asks you to agree to the
[Contributor Terms](CONTRIBUTOR_TERMS.md). If you agree, it shares
automatically: whenever GoldScout saves a new export (when you log out or
/reload), the companion uploads it to the GoldScout upload service. If you
choose "Not now", nothing is uploaded; you can still share by hand through the
GitHub form. You can pause automatic sharing, or stop the companion starting
with Windows, at any time from its tray icon.

On your PC it stores, in `%APPDATA%\GoldScout Companion\config.json`: your WoW
folder location, whether you agreed to the terms and when, your settings, and
for each install the upload token and the last snapshot it uploaded.

## The upload service

The upload service runs on Cloudflare. For each install it keeps only the
newest export (the same content described below), the Contributor Terms version
you agreed to, a hash of the install's upload token, and when it was uploaded.
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

## Future services

If we launch a website or anything else that collects data differently, this
policy will be updated before it does.

## Contact

Open an issue at https://github.com/Alkhara/GoldScout-WoW/issues.
