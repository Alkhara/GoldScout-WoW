# Contributing to GoldScout

Thanks for helping! For bugs and ideas, open an
[issue](https://github.com/Alkhara/GoldScout-WoW/issues), or say hi on the
[GoldScout Discord](https://discord.gg/rJdZcuepzN). To share drop data,
use the [Share drop data](https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml)
form instead of a pull request.

## Project layout

| Path | What it is |
|---|---|
| `GoldScout/` | The addon itself: the folder that gets installed |
| `tools/luacheck_lite.py` | Lua 5.1 syntax checker that also lists the globals each file uses |
| `tools/deploy.py` | Runs the checker, then copies `GoldScout/` into your AddOns folder |
| `tools/submission.py` | Validates drop data exports |
| `tools/merge_data.py` | Combines accepted exports into `GoldScout/Data_Community.lua` |
| `data/submissions/` | Accepted exports, one file per contributor |
| `companion/` | GoldScout Companion, the Windows tray app that shares saved drop data |
| `site/` | The website: `python site/build.py` writes it to `site/dist/` (Cloudflare Pages builds it on every push) |
| `server/` | The upload service the companion sends data to (Cloudflare Worker + D1) |
| `tools/check.py` | Runs every check (also used by CI and the pre-push hook) |
| `tools/release.py` | Releases with every check: Tests passed, server ready, tag, follow, verify |
| `tools/verify_release.py` | Verifies a release's files, or that the upload server accepts this build's exports |
| `tools/errors.py` | Prints the errors GoldScout recorded in your saved data |
| `tests/` | Tests for the data pipeline: `python -m unittest discover -s tests` |

## Working on the addon

You need Python 3 and WoW Forever.

1. Fork and clone the repository, then edit the files in `GoldScout/`.
2. Preview a deploy: `python tools/deploy.py --dry-run`
3. Deploy: `python tools/deploy.py`
4. In game, type `/reload`. If you added a new file (and listed it in
   `GoldScout.toc`), restart the game fully instead.

`deploy.py` copies to the default Forever install,
`C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns`. If yours is
elsewhere, put its path in a `.addons-path` file at the repository root (git
ignores it), set the `GOLDSCOUT_ADDONS` environment variable, or pass
`--addons PATH`.

For Lua error popups in game, use `/console scriptErrors 1` or BugSack.
`/gscout skills` shows the skills and recipes GoldScout has read.

## Guidelines

- **Stay within Blizzard's addon rules.** GoldScout only shows information. No
  automation of movement, targeting, combat, looting or clicks, and no working
  around values the game hides from addons.
- **No third-party data.** Never copy drop rates, spawn points or other data
  from Wowhead or similar sites; their terms forbid it. Data comes only from
  players through the submission form.
- **Don't edit `Data_Community.lua` by hand.** It's generated from
  `data/submissions/`.
- **Tell players what changed.** Add a line for each change players will notice
  under "Unreleased" in [CHANGELOG.md](CHANGELOG.md), written for them; each
  release's section becomes its notes on GitHub, CurseForge and Wago.
- **Every piece of text the addon shows is translated.** Write it as
  `L["Whole sentence with %s"]` (not pieces joined around a value), and add
  the same English text with a translation to each `GoldScout/Locale_*.lua`.
  `python tools/l10n.py check` finds untranslated or broken text, and
  `python tools/l10n.py missing deDE` lists what a language still needs.
  Mob names go through `ns.MobName`, so each player sees their own language.
- Run `python tools/check.py` before opening a pull request: it checks the Lua,
  lints the Python, validates the community data and runs every test.
  `pip install -r tests/requirements.txt` first to get all of it (the Lua tests load the
  addon's own files in Lua 5.1). To run it before every push automatically:
  `git config core.hooksPath tools/hooks`.

By contributing code you agree it's released under the MIT License. Community
data is covered by the [GoldScout Data License](DATA_LICENSE.md).
