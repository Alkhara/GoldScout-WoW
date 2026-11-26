"""Writes the gold guides' farm notes (site/farm_notes.json) with Claude, once a week (guide-notes.yml).

For every farm the guides show (the top NOTE_FARMS of each realm type and faction's ranking), Claude gets the
farm's fact sheet (site/farm_notes.py facts) and writes a few sentences on how to run it. Each note must pass
farm_notes.check: no number or name that isn't in the facts, no prices or chances, no claims about the game's
behaviour. A note that fails gets up to RETRIES rewrites with the problems listed; if those fail too, the farm keeps
no note (the guide shows its tables as before). Notes that still pass and are under MAX_AGE_DAYS old are kept,
so a week's run only writes what's new or stale.

  python tools/write_farm_notes.py            needs ANTHROPIC_API_KEY (or an `ant auth login` profile)
  python tools/write_farm_notes.py --dry-run  lists the farms it would write, calls nothing
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "site"))

import data_pages  # noqa: E402
import farm_notes  # noqa: E402
import guides  # noqa: E402
import merge_data  # noqa: E402

MODEL = "claude-opus-5-5"
NOTE_FARMS = 6          # per market: the top 3 and the next few, which can move up within a week
MAX_AGE_DAYS = 28
RETRIES = 2             # rewrites of a note that breaks the rules, each told what was wrong
SCHEMA = {
    "type": "object",
    "properties": {"note": {"type": "string"}},
    "required": ["note"],
    "additionalProperties": False,
}
SYSTEM = """You write short farming notes for GoldScout's gold-making guides for World of Warcraft: Forever.

Each note is 2 to 4 sentences (40 to 110 words) of practical advice on running one farm: which mob to kill \
for which item, in which zone, at what character level, where in the zone players loot it most (map \
coordinates), and what else it drops that's worth picking up. Write for a player reading the guide: direct, \
specific, friendly, no hype, no headings, no lists, no emoji. For where to go, give the busiest spot and at \
most one of the nearby spots, never a list of coordinates.

Use only the facts you're given. In particular:
- Name only the mob, item, zone and other drops in the facts, spelled exactly as given.
- The only numbers you may write are the levels and map coordinates in the facts. Never write prices, gold \
per hour, percentages, drop chances, kill counts or stack sizes: the guide shows those live beside your note.
- Don't describe how the game or the mob behaves (respawn times, patrols, elites, abilities, quests, \
dungeons), since nothing in the facts says so.
- You may mention GoldScout's Hunt button (it marks the mobs and shades the hunting area on the map) and \
its Drop rates window (right-click the mob's portrait)."""


def load_data():
    results = merge_data.load(ROOT / "data" / "submissions")
    merged = merge_data.merge([r.mobs for r in results], 1000)
    return data_pages.Dataset(results, merged, merge_data.merge_fish([r.fishing for r in results], 1000))


def farms_to_note(data, markets):
    """{key: farm} for every farm in the top NOTE_FARMS of any market (one farm per mob and item), leaving
    out mobs nobody's export has named yet (a note about "Mob 11783" reads badly)."""
    found = {}
    for market in markets:
        for farm in guides.top(guides.farms(data, market["prices"], market.get("usual")), NOTE_FARMS):
            if data.mobs[farm["npc"]]["names"]:
                found.setdefault(farm_notes.key(farm), farm)
    return found


def ask(client, sheet, retry=None):
    """One note for a fact sheet, or None if Claude declined. retry: (draft, problems) to fix."""
    content = "Facts (JSON):\n" + json.dumps(farm_notes.prompt_facts(sheet), ensure_ascii=False, indent=1)
    if retry:
        draft, problems = retry
        content += ("\n\nYour previous note broke the rules:\n- " + "\n- ".join(problems)
                    + "\n\nPrevious note:\n" + draft + "\n\nWrite it again, keeping to the rules.")
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",          # a declined request is retried on a fallback model in the same call
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if response.stop_reason == "refusal":
        return None
    text = next((block.text for block in response.content if block.type == "text"), "")
    return " ".join(str(json.loads(text).get("note", "")).split())


def write_note(client, sheet, known):
    """(note, problems): a note that passes farm_notes.check, or None with the last attempt's problems."""
    note = ask(client, sheet)
    for attempt in range(RETRIES + 1):
        if note is None:
            return None, ["declined"]
        problems = farm_notes.check(note, sheet, known)
        if not problems:
            return note, []
        if attempt < RETRIES:
            note = ask(client, sheet, (note, problems))
    return None, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="list the farms to write; call nothing")
    parser.add_argument("--all", action="store_true", help="rewrite every note, not only new or stale ones")
    args = parser.parse_args()

    data = load_data()
    markets = guides.fetch_markets()
    if not markets:
        print("No auction prices: nothing to rank, so no notes written.")
        return 1
    farms = farms_to_note(data, markets)
    notes = farm_notes.load()
    known = farm_notes.known_name_words(data)
    today = datetime.date.today()
    todo = []
    for farm_key, farm in sorted(farms.items()):
        note = notes.get(farm_key)
        written = note and note.get("written")
        fresh = (written and (today - datetime.date.fromisoformat(written)).days < MAX_AGE_DAYS)
        if args.all or not note or not fresh or farm_notes.check(note["text"], farm_notes.facts(data, farm), known):
            todo.append((farm_key, farm))
    print("%d farms in the guides, %d notes to write." % (len(farms), len(todo)))
    if args.dry_run:
        for farm_key, farm in todo:
            print("  %s: %s from %s" % (farm_key, data.item_name(farm["parts"][0]["item"]), data.mob_name(farm["npc"])))
        return 0

    import anthropic   # only needed here, so the site build and tests never need the SDK
    client = anthropic.Anthropic()
    wrote, failed = 0, []
    for farm_key, farm in todo:
        sheet = farm_notes.facts(data, farm)
        try:
            note, problems = write_note(client, sheet, known)
        except anthropic.RateLimitError:
            failed.append((farm_key, ["rate limited; next week's run will try again"]))
            break
        except (anthropic.APIStatusError, anthropic.APIConnectionError, ValueError) as error:
            failed.append((farm_key, ["%s: %s" % (type(error).__name__, error)]))
            continue
        if note:
            notes[farm_key] = {"text": note, "written": today.isoformat()}
            wrote += 1
        else:
            failed.append((farm_key, problems))
    # Notes for farms no longer in any guide go, so the file only holds what's shown.
    notes = {farm_key: note for farm_key, note in notes.items() if farm_key in farms}
    farm_notes.save(notes)
    print("Wrote %d notes; %d farms have a note." % (wrote, len(notes)))
    for farm_key, problems in failed:
        print("  no note for %s: %s" % (farm_key, "; ".join(problems)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
