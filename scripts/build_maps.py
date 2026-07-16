#!/usr/bin/env python3
"""Render static OpenStreetMap images with numbered story pins for the tour.

Outputs (committed, so the app stays fully offline):
  tour/maps/<sight-id>.png   sight map; numbered pins = base stories (N.0)
                             where per-story stops are defined, else one pin
  tour/maps/day-<N>.png      day overview; one pin per sight

Coordinates are deliberately approximate (a family orientation aid, not
navigation). Tiles (c) OpenStreetMap contributors, fetched once at build time.

Usage: ./venv/bin/python build_maps.py            # all
       ./venv/bin/python build_maps.py day06 ...  # filter by id prefix
"""
import json
import sys
from pathlib import Path

from staticmap import StaticMap, CircleMarker
from staticmap.staticmap import _lon_to_x, _lat_to_y
from PIL import ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tour"
OUT = ASSETS / "maps"
UA = "UKFamilyTour/1.0 (private family trip app; https://github.com/ifinkelstein/uk-family-tour)"

ACCENT = {"london": "#B3222E", "edinburgh": "#1F5FA8", "york": "#6B3FA0"}


def region(day):
    return "london" if day <= 7 else ("edinburgh" if day <= 12 else "york")


# sight-id -> center [lat, lon], and optional per-base-story stops keyed by
# the NN slug prefix of the base file (order comes from the manifest).
GEO = {
    "day02-richmond-park": {"c": [51.4444, -0.2733]},
    "day03-tower-of-london": {"c": [51.5081, -0.0759]},
    "day03-tower-bridge": {"c": [51.5055, -0.0754]},
    "day03-city-walk": {"c": [51.5118, -0.0890], "stops": {
        "01": [51.5097, -0.0796],   # St Dunstan-in-the-East
        "02": [51.5138, -0.0984],   # St Paul's
    }},
    "day04-greenwich": {"c": [51.4805, -0.0053], "stops": {
        "01": [51.4826, -0.0096],   # Cutty Sark
        "02": [51.4769, -0.0005],   # Prime Meridian / Observatory
        "03": [51.4769, -0.0005],   # Longitude clocks (Observatory)
        "04": [51.4772, -0.0009],   # Time ball
        "05": [51.4810, -0.0052],   # Maritime Museum
        "06": [51.4769, -0.0005],   # Timekeeping (Observatory)
    }},
    "day05-national-gallery": {"c": [51.5089, -0.1283]},
    "day05-british-museum": {"c": [51.5194, -0.1270]},
    "day06-buckingham-palace": {"c": [51.5014, -0.1419]},
    "day06-westminster-walk": {"c": [51.5030, -0.1290], "stops": {
        "08": [51.5065, -0.1290],   # Admiralty Arch / the Mall
        "03": [51.5025, -0.1340],   # St James's Park (Duck Island side)
        "07": [51.5045, -0.1273],   # Horse Guards
        "06": [51.5035, -0.1268],   # Whitehall / Downing St
        "01": [51.5007, -0.1246],   # Big Ben
        "02": [51.4995, -0.1248],   # Parliament
        "05": [51.5006, -0.1263],   # Parliament Square
        "04": [51.4993, -0.1273],   # Westminster Abbey
        "09": [51.5062, -0.1281],   # Red London (bus hop, Whitehall top)
    }},
    "day06-churchill-war-rooms": {"c": [51.5022, -0.1263]},
    "day07-hampton-court": {"c": [51.4036, -0.3378]},
    "day08-train-north": {"c": [54.5, -1.6], "zoom": 6},  # route overview
    "day09-edinburgh-castle": {"c": [55.9486, -3.1999]},
    "day09-royal-mile": {"c": [55.9502, -3.1870], "stops": {
        "01": [55.9486, -3.1999],   # Crag and tail (castle esplanade)
        "02": [55.9502, -3.1905],   # Gardyloo (Mary King's Close area)
        "03": [55.9469, -3.1900],   # Heart of Midlothian / Greyfriars Bobby
        "04": [55.9520, -3.1780],   # Canongate to Holyrood
        "05": [55.9497, -3.1935],   # Writers' Museum / Makars' Court
    }},
    "day10-inchcolm-island": {"c": [56.0300, -3.3010]},
    "day11-stirling-castle": {"c": [56.1240, -3.9470]},
    "day12-arthurs-seat": {"c": [55.9441, -3.1618]},
    "day13-york": {"c": [53.9599, -1.0873], "stops": {
        "01": [53.9525, -1.0870],   # Walls / Micklegate Bar
        "02": [53.9605, -1.0800],   # The Shambles
        "03": [53.9623, -1.0817],   # York Minster
        "04": [53.9585, -1.0800],   # Wars of the Roses (city centre)
    }},
    "day14-jorvik": {"c": [53.9583, -1.0803]},
}

W, H = 1000, 700


def font(size):
    for name in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_pin(img, x, y, label, color):
    d = ImageDraw.Draw(img)
    r = 17
    d.ellipse([x - r, y - r, x + r, y + r], fill=color, outline="white", width=3)
    f = font(15 if len(label) <= 2 else 12)
    bb = d.textbbox((0, 0), label, font=f)
    d.text((x - (bb[2] - bb[0]) / 2, y - (bb[3] - bb[1]) / 2 - bb[1]),
           label, fill="white", font=f)


def render(points, color, out, zoom=None):
    """points: list of (lat, lon, label). Renders tiles then draws pins."""
    smap = StaticMap(W, H, url_template="https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                     headers={"User-Agent": UA})
    # invisible markers set the auto-extent
    for lat, lon, _ in points:
        smap.add_marker(CircleMarker((lon, lat), "#00000000", 1))
    img = smap.render(zoom=zoom)
    for lat, lon, label in points:
        x = smap._x_to_px(_lon_to_x(lon, smap.zoom))
        y = smap._y_to_px(_lat_to_y(lat, smap.zoom))
        draw_pin(img, x, y, label, color)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(f"wrote {out.relative_to(ROOT)}")


def main():
    only = sys.argv[1:]
    man = json.loads((ASSETS / "manifest.json").read_text())
    by_day = {}
    for s in man["sights"]:
        g = GEO.get(s["id"])
        if not g:
            print(f"skip (no geo): {s['id']}")
            continue
        by_day.setdefault(s["day"], []).append((s, g))
        if only and not any(s["id"].startswith(o) for o in only):
            continue
        color = ACCENT[region(s["day"])]
        stops = g.get("stops")
        if stops:
            pts = []
            for i, t in enumerate(s["tracks"]["kid"], 1):
                nn = Path(t["file"]).name.split("-")[0]
                if nn in stops:
                    lat, lon = stops[nn]
                    pts.append((lat, lon, f"{i}"))
            render(pts, color, OUT / f"{s['id']}.png", g.get("zoom"))
        else:
            lat, lon = g["c"]
            render([(lat, lon, "•")], color, OUT / f"{s['id']}.png", g.get("zoom", 15))
    # day overviews (multi-sight days only)
    for day, sights in sorted(by_day.items()):
        if only and not any(f"day{day:02d}" .startswith(o) or o.startswith(f"day{day:02d}") for o in only):
            if only:
                continue
        if len(sights) < 2:
            continue
        color = ACCENT[region(day)]
        pts = [(g["c"][0], g["c"][1], str(i)) for i, (s, g) in enumerate(sights, 1)]
        render(pts, color, OUT / f"day-{day:02d}.png", None)


if __name__ == "__main__":
    main()
