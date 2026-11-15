#!/usr/bin/env python3
"""Builds the website's zone map images (site/maps/<uiMapID>.webp) from the game's own
world map art, exported from your WoW Forever install with wow.export.

  python tools/zone_maps.py EXPORT_DIR [uiMapID ...]

EXPORT_DIR is wow.export's export folder, holding these tables exported as CSV from
its Data tab (UiMapXMapArt, UiMapArtTile, WorldMapOverlay, WorldMapOverlayTile) and
the map textures they name, exported as PNG with "export named files" off (so each
file is <FileDataID>.png). Without uiMapIDs it builds every zone the website has
area data for (tools/zone_maps.py --list prints them; site/data_pages.py).

Each map is the zone's base art (4x3 tiles of 256 px) with every explored-area
overlay drawn on top, as a fully explored map looks in game, cropped to the
1002x668 the game shows. Map coordinates (0-1, as the addon records them) cover
exactly that area, so the website draws its squares straight on top.
"""
import argparse
import csv
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "maps"
TILE = 256
WIDTH, HEIGHT = 1002, 668      # the part of the 1024x768 art the game's map frame shows
QUALITY = 60


def table(folder, name):
    with open(folder / (name + ".csv"), encoding="utf-8") as handle:
        return [{key: int(value) if value.lstrip("-").isdigit() else value for key, value in row.items()}
                for row in csv.DictReader(handle, delimiter=";")]


def textures(folder):
    """FileDataID -> exported PNG path."""
    return {int(path.stem): path for path in folder.rglob("*.png") if path.stem.isdigit()}


def build(folder, map_ids):
    art_of = {row["UiMapID"]: row["UiMapArtID"] for row in table(folder, "UiMapXMapArt") if row["PhaseID"] == 0}
    tiles = table(folder, "UiMapArtTile")
    overlays = table(folder, "WorldMapOverlay")
    overlay_tiles = table(folder, "WorldMapOverlayTile")
    files = textures(folder)
    OUT.mkdir(parents=True, exist_ok=True)
    built, missing = [], []
    for map_id in map_ids:
        art = art_of.get(map_id)
        base = [row for row in tiles if row["UiMapArtID"] == art and row["LayerIndex"] == 0]
        if not base or any(row["FileDataID"] not in files for row in base):
            missing.append(map_id)
            continue
        canvas = Image.new("RGBA", (4 * TILE, 3 * TILE))
        for row in base:
            canvas.alpha_composite(Image.open(files[row["FileDataID"]]).convert("RGBA"),
                                   (row["ColIndex"] * TILE, row["RowIndex"] * TILE))
        for overlay in (row for row in overlays if row["UiMapArtID"] == art):
            for piece in (row for row in overlay_tiles if row["WorldMapOverlayID"] == overlay["ID"]):
                if piece["FileDataID"] in files:
                    canvas.alpha_composite(Image.open(files[piece["FileDataID"]]).convert("RGBA"),
                                           (overlay["OffsetX"] + piece["ColIndex"] * TILE,
                                            overlay["OffsetY"] + piece["RowIndex"] * TILE))
        path = OUT / ("%d.webp" % map_id)
        canvas.crop((0, 0, WIDTH, HEIGHT)).convert("RGB").save(path, "WEBP", quality=QUALITY, method=6)
        built.append((map_id, path.stat().st_size))
    return built, missing


def site_maps():
    sys.path.insert(0, str(ROOT / "site"))
    sys.path.insert(0, str(ROOT / "tools"))
    import data_pages
    import merge_data
    results = merge_data.load(ROOT / "data" / "submissions")
    data = data_pages.Dataset(results, merge_data.merge([r.mobs for r in results], 1000),
                              merge_data.merge_fish([r.fishing for r in results], 1000))
    return sorted(set(data.ground) & set(data.map_names))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("export_dir", nargs="?", type=Path)
    parser.add_argument("maps", nargs="*", type=int)
    parser.add_argument("--list", action="store_true", help="print the uiMapIDs the website needs")
    args = parser.parse_args()
    if args.list:
        print(" ".join(map(str, site_maps())))
        return
    if not args.export_dir:
        parser.error("give wow.export's export folder")
    built, missing = build(args.export_dir, args.maps or site_maps())
    for map_id, size in built:
        print("ok   %d.webp  %d KB" % (map_id, size // 1024))
    for map_id in missing:
        print("skip %d: its map art isn't in the export" % map_id)


if __name__ == "__main__":
    main()
