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
copy the text and open an issue with it. Exports contain mob and item IDs,
counts, levels and map positions; no character or account names.

## Development

| Path | What it is |
|---|---|
| `GoldScout/` | The addon itself: the folder that gets installed |
| `tools/luacheck_lite.py` | Lua 5.1 syntax checker that also lists the globals each file uses |
| `tools/deploy.py` | Runs the checker, then mirrors `GoldScout/` into your AddOns folder |
| `tools/merge_data.py` | Combines players' `/gscout export` strings into `GoldScout/Data_Community.lua` |

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

Save each player's `/gscout export` text as a `.txt` file in `submissions/`
(git ignores it), run `python tools/merge_data.py`, then commit the regenerated
`GoldScout/Data_Community.lua` with the next release. Only add data that
players collected in game. Don't copy from third-party database sites; their
terms forbid it.

### Releases

Pushing a tag such as `v0.1.0` runs `.github/workflows/release.yml`, which
packages the addon with the BigWigs packager and uploads it to GitHub, plus
CurseForge and Wago once their project IDs and API tokens are set (see the
comments in that file).

## License

MIT. See [LICENSE](LICENSE).
