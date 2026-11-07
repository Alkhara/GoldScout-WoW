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

## GoldScout Companion

The companion app for Windows reads GoldScout's saved data file
(`GoldScout.lua` in each account's SavedVariables folder) to show what you've
learned and build an export. It never changes game files. It doesn't connect to
the internet: when you click Share, it opens the submission form in your
browser with the export filled in, and nothing is sent until you submit the
form yourself. It stores your WoW folder location and when you last shared in
`%APPDATA%\GoldScout Companion\config.json` on your PC.

## Sharing drop data

Nothing leaves your computer unless you choose to share it. `/gscout export`
shows only your loot records: creature IDs, names and levels, kill and
pickpocket counts, item drops, and the average map position where you looted
each creature. It doesn't include character names, account names, realm names,
prices, professions or settings.

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

We don't collect email addresses, payment details, IP addresses or analytics
through the addon or the submission process, and we don't sell personal
information. GitHub, which hosts the repository and issues, processes data as
described in its own privacy statement.

## Removal

To have your submission file removed from the repository, or your submission
issue deleted, open an issue asking us to. Data already combined into a release
can't be separated from other players' data.

## Future services

If we launch a website, an upload service or anything else that collects data
differently, this policy will be updated before it does.

## Contact

Open an issue at https://github.com/Alkhara/GoldScout-WoW/issues.
