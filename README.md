# GoldScout

A World of Warcraft: Forever addon that scans the auction house and ranks the
most profitable things to farm or craft for the character you're playing: its
level, class, faction and professions.

See [GoldScout/README.md](GoldScout/README.md) for everything it does in game,
including Hunt mode and how it learns drop rates from your loot.

## Install

Download the latest release from CurseForge, Wago or this repository's
Releases page, and unzip the `GoldScout` folder into
`World of Warcraft\_forever_\Interface\AddOns\`. Restart the game fully the
first time.

GoldScout is free, and every in-game feature is the same for everyone.

## Sharing drop data

GoldScout ships no drop rates or spawn points from other sites. Everything comes
from players looting in game. To share yours, type `/gscout export` in game,
copy the text and paste it into the [Share drop data](https://github.com/Alkhara/GoldScout-WoW/issues/new?template=data-submission.yml) form.
Exports contain mob and item IDs, counts, levels and map positions; no character
or account names. A bot checks every submission, and accepted ones go into the
next release. See the [Contributor Terms](docs/CONTRIBUTOR_TERMS.md) and
[Privacy Policy](docs/PRIVACY.md).

## Development

| Path | What it is |
|---|---|
| `GoldScout/` | The addon itself: the folder that gets installed |
| `tools/luacheck_lite.py` | Lua 5.1 syntax checker that also lists the globals each file uses |
| `tools/deploy.py` | Runs the checker, then mirrors `GoldScout/` into your AddOns folder |
| `tools/merge_data.py` | Combines players' `/gscout export` strings into `GoldScout/Data_Community.lua` |
| `tools/submission.py` | Validates exports: format, ranges, impossible counts, and rates far from other players' |
| `tools/data_bot.py` | Used by the data workflows to check submission issues and collect accepted ones |
| `data/submissions/` | Accepted exports, one file per contributor (GitHub user ID) |

Workflow:

1. Edit the files in `GoldScout/`.
2. Preview a deploy: `python tools/deploy.py --dry-run`
3. Deploy: `python tools/deploy.py`
4. In game, type `/reload`. If you added a new file (and listed it in
   `GoldScout.toc`), restart the game fully instead.

The deploy target is the default Forever install,
`C:\Program Files (x86)\World of Warcraft\_forever_\Interface\AddOns`. If yours is
elsewhere, put its path in a `.addons-path` file at the repository root (git
ignores it), set the `GOLDSCOUT_ADDONS` environment variable, or pass `--addons PATH`.

For Lua error popups in game, use `/console scriptErrors 1` or BugSack.
`/gscout skills` shows the skills and recipes GoldScout has read for your character.

### Community data

1. A player submits the issue form. `.github/workflows/data-check.yml` validates
   it and labels it `data-valid`, `data-needs-review` (valid, but some drop
   rates differ sharply from other players') or `data-invalid`, with a comment
   explaining why.
2. For `data-needs-review`, look at the rates in the bot's comment and add
   `data-approved` if they're believable. Editing an issue removes that label.
3. Daily, `.github/workflows/data-merge.yml` re-validates every open
   `data-valid` or `data-approved` issue, stores each player's latest export in
   `data/submissions/`, regenerates `GoldScout/Data_Community.lua`, and opens a
   pull request. Review and merge it; that closes the issues. Run it any time
   from the Actions tab.

One player's kills of a mob count up to 1000, so a single export can't
outweigh everyone else. To merge by hand: `python tools/merge_data.py`.
Only add data players collected in game; never copy from third-party database
sites, whose terms forbid it.

The merge workflow needs **Settings → Actions → General → Allow GitHub Actions
to create and approve pull requests** turned on.

### Releases

Pushing a tag such as `v0.1.0` runs `.github/workflows/release.yml`, which
packages the addon with the BigWigs packager and uploads it to GitHub, plus
CurseForge and Wago once their project IDs and API tokens are set (see the
comments in that file).

## License

The source code is MIT-licensed; see [LICENSE](LICENSE). The community drop
data (`GoldScout/Data_Community.lua` and `data/`) is covered by the
[GoldScout Data License](DATA_LICENSE.md): it can be used in GoldScout, but not
extracted or reused elsewhere without permission.
