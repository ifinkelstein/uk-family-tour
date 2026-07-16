#!/usr/bin/env python3
"""Inject curated cross-references between related chapters.

Source of truth is the LINKS table below. Running this script rebuilds, from
scratch, (a) every base track's `related` array in tour/manifest.json and
(b) the trailing "> Related listening:" callout lines in the source markdown.
Callout lines start with ">" so the TTS scripts never speak them; the reading
builds render them as blockquote notes. Idempotent — safe to rerun.
"""
import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "tour"

# Each entry: kid pair, adult pair, shared reason, direction ('both' or 'ab').
# Files are audience-matched base tracks; sight ids derive from the paths.
L = lambda kid, adult, why, dir="both": {"kid": kid, "adult": adult, "why": why, "dir": dir}
LINKS = [
    L(("content/day03-tower-of-london/kid/02-crown-jewels.md",
       "content/day09-edinburgh-castle/kid/03-crown-jewels-stone.md"),
      ("content/day03-tower-of-london/adult/02-crown-jewels.md",
       "content/day09-edinburgh-castle/adult/02-honours-stone.md"),
      "England's Crown Jewels and Scotland's older Honours, each with its own famous heist story."),

    L(("content/day06-westminster-walk/kid/04-abbey.md",
       "content/day09-edinburgh-castle/kid/03-crown-jewels-stone.md"),
      ("content/day06-westminster-walk/adult/04-abbey.md",
       "content/day09-edinburgh-castle/adult/02-honours-stone.md"),
      "The Stone of Destiny sat under the Abbey's Coronation Chair for seven hundred years before returning to Scotland."),

    L(("content/day03-tower-bridge/kid/01-opening-bridge.md",
       "content/day10-inchcolm-island/kid/01-forth-bridge.md"),
      ("content/day03-tower-bridge/adult/01-engineering.md",
       "content/day10-inchcolm-island/adult/01-forth-bridge.md"),
      "Two great Victorian bridges, opened four years apart: one dressed as a castle, one all bare steel."),

    L(("content/day02-richmond-park/kid/02-kings-mound.md",
       "content/day07-hampton-court/kid/01-henry-and-wolsey.md"),
      ("content/day02-richmond-park/adult/02-kings-mound.md",
       "content/day07-hampton-court/adult/01-wolsey-henry.md"),
      "The same Henry the Eighth of the mound legend took Hampton Court from Cardinal Wolsey."),

    L(("content/day03-tower-of-london/kid/04-prisoners.md",
       "content/day07-hampton-court/kid/03-ghosts.md"),
      ("content/day03-tower-of-london/adult/04-prisoners.md",
       "content/day07-hampton-court/adult/04-ghosts-legends.md"),
      "Two of Henry's queens link these places: accused at Hampton Court, executed at the Tower."),

    L(("content/day06-buckingham-palace/kid/03-royal-homes.md",
       "content/day03-tower-of-london/kid/01-white-tower.md"),
      ("content/day06-buckingham-palace/adult/03-royal-homes.md",
       "content/day03-tower-of-london/adult/01-white-tower.md"),
      "The royal address story starts at the Tower, the Conqueror's first London stronghold.", "ab"),

    L(("content/day06-buckingham-palace/kid/03-royal-homes.md",
       "content/day07-hampton-court/kid/01-henry-and-wolsey.md"),
      ("content/day06-buckingham-palace/adult/03-royal-homes.md",
       "content/day07-hampton-court/adult/01-wolsey-henry.md"),
      "Next stop on the royal-homes trail: Henry the Eighth's great palace at Hampton Court.", "ab"),

    L(("content/day03-city-walk/kid/02-st-pauls.md",
       "content/day06-churchill-war-rooms/kid/04-london-at-war.md"),
      ("content/day03-city-walk/adult/02-st-pauls.md",
       "content/day06-churchill-war-rooms/adult/04-london-at-war.md"),
      "The dome that survived the Blitz and the bunker that directed the fight are one story."),

    L(("content/day03-city-walk/kid/02-st-pauls.md",
       "content/day04-greenwich/kid/04-time-ball-and-museum.md"),
      ("content/day03-city-walk/adult/02-st-pauls.md",
       "content/day04-greenwich/adult/04-maritime-greenwich.md"),
      "Christopher Wren designed both the cathedral and Greenwich's riverside masterpiece."),

    L(("content/day03-city-walk/kid/02-st-pauls.md",
       "content/day07-hampton-court/kid/05-two-palaces.md"),
      ("content/day03-city-walk/adult/02-st-pauls.md",
       "content/day07-hampton-court/adult/03-baroque-wren.md"),
      "Wren again: fresh from St Paul's, he rebuilt half of Hampton Court for William and Mary."),

    L(("content/day04-greenwich/kid/04-time-ball-and-museum.md",
       "content/day06-westminster-walk/kid/03-park-and-lions.md"),
      ("content/day04-greenwich/adult/04-maritime-greenwich.md",
       "content/day06-westminster-walk/adult/03-park-and-square.md"),
      "Nelson's coat is at Greenwich; his column and lions preside over Trafalgar Square."),

    L(("content/day05-national-gallery/kid/03-fighting-temeraire.md",
       "content/day04-greenwich/kid/01-cutty-sark.md"),
      ("content/day05-national-gallery/adult/03-turner-vangogh.md",
       "content/day04-greenwich/adult/01-cutty-sark.md"),
      "Turner painted sail giving way to steam; Cutty Sark lived that same ending."),

    L(("content/day04-greenwich/kid/06-timekeeping.md",
       "content/day06-westminster-walk/kid/01-big-ben.md"),
      ("content/day04-greenwich/adult/06-timekeeping.md",
       "content/day06-westminster-walk/adult/01-big-ben.md"),
      "From Greenwich's master clocks to Britain's most famous public clock."),

    L(("content/day06-westminster-walk/kid/02-parliament.md",
       "content/day13-york/kid/02-shambles.md"),
      ("content/day06-westminster-walk/adult/02-parliament.md",
       "content/day13-york/adult/03-shambles-snickelways.md"),
      "Guy Fawkes, the man behind the Gunpowder Plot, was born and raised in York."),

    L(("content/day05-british-museum/kid/03-treasures-hunt.md",
       "content/day14-jorvik/kid/01-vikings-take-york.md"),
      ("content/day05-british-museum/adult/03-sutton-hoo-lewis.md",
       "content/day14-jorvik/adult/01-viking-york.md"),
      "The museum's buried ship and walrus-ivory chessmen set the stage for Viking York."),

    L(("content/day08-train-north/kid/02-crossing-the-border.md",
       "content/day14-jorvik/kid/04-end-of-viking-age.md"),
      ("content/day08-train-north/adult/02-border-and-arrival.md",
       "content/day14-jorvik/adult/04-end-of-viking-age.md"),
      "Holy Island, seen from the train, is where the Viking Age began in 793."),

    L(("content/day03-tower-of-london/kid/01-white-tower.md",
       "content/day14-jorvik/kid/04-end-of-viking-age.md"),
      ("content/day03-tower-of-london/adult/01-white-tower.md",
       "content/day14-jorvik/adult/04-end-of-viking-age.md"),
      "1066 joins them: the Viking Age ended near York the same year the Conqueror's Tower story began."),

    L(("content/day09-edinburgh-castle/kid/01-castle-rock.md",
       "content/day12-arthurs-seat/kid/01-climbing-a-volcano.md"),
      ("content/day09-edinburgh-castle/adult/01-rock-and-sieges.md",
       "content/day12-arthurs-seat/adult/01-hutton-deep-time.md"),
      "Castle Rock and Arthur's Seat are siblings, vents of the same ancient volcano field."),

    L(("content/day11-stirling-castle/kid/01-key-to-scotland.md",
       "content/day09-edinburgh-castle/kid/01-castle-rock.md"),
      ("content/day11-stirling-castle/adult/01-key-to-scotland.md",
       "content/day09-edinburgh-castle/adult/01-rock-and-sieges.md"),
      "Scotland's two great fortress rocks, contested in the same wars."),

    L(("content/day06-westminster-walk/kid/04-abbey.md",
       "content/day11-stirling-castle/kid/03-baby-queen-flying-man.md"),
      ("content/day06-westminster-walk/adult/04-abbey.md",
       "content/day11-stirling-castle/adult/03-mary-and-court-life.md"),
      "Mary, Queen of Scots was crowned at Stirling and lies buried in the Abbey."),

    L(("content/day09-royal-mile/kid/04-castle-to-palace.md",
       "content/day11-stirling-castle/kid/03-baby-queen-flying-man.md"),
      ("content/day09-royal-mile/adult/02-st-giles-covenant.md",
       "content/day11-stirling-castle/adult/03-mary-and-court-life.md"),
      "Mary, Queen of Scots again: crowned at Stirling, at home, and in trouble, at Holyrood."),

    L(("content/day10-inchcolm-island/kid/03-seals-and-war.md",
       "content/day06-churchill-war-rooms/kid/04-london-at-war.md"),
      ("content/day10-inchcolm-island/adult/03-fortress-island.md",
       "content/day06-churchill-war-rooms/adult/04-london-at-war.md"),
      "The same war on two fronts: London's bunker and the fortress island guarding the Forth."),

    L(("content/day08-train-north/kid/01-east-coast-line.md",
       "content/day13-york/kid/01-walls-and-romans.md"),
      ("content/day08-train-north/adult/01-east-coast-line.md",
       "content/day13-york/adult/01-eboracum-to-york.md"),
      "The line races right past York; you'll walk its walls in a few days.", "ab"),

    L(("content/day09-royal-mile/kid/01-crag-and-tail.md",
       "content/day12-arthurs-seat/kid/01-climbing-a-volcano.md"),
      ("content/day09-royal-mile/adult/01-old-town.md",
       "content/day12-arthurs-seat/adult/01-hutton-deep-time.md"),
      "The Old Town rides the volcano's tail; the climb takes you up the volcano itself."),

    L(("content/day07-hampton-court/kid/08-dont-miss.md",
       "content/day03-tower-of-london/kid/02-crown-jewels.md"),
      ("content/day07-hampton-court/adult/08-dont-miss.md",
       "content/day03-tower-of-london/adult/02-crown-jewels.md"),
      "Henry's crown, re-created at Hampton Court; the originals were melted down, and the Tower keeps what replaced them."),

    L(("content/day07-hampton-court/kid/08-dont-miss.md",
       "content/day06-buckingham-palace/kid/03-royal-homes.md"),
      ("content/day07-hampton-court/adult/08-dont-miss.md",
       "content/day06-buckingham-palace/adult/03-royal-homes.md"),
      "After the Georgians left Hampton Court, the royal-homes trail moved on to Buckingham House.", "ab"),
]

MARK = "> Related listening:"


def main():
    man = json.loads((ASSETS / "manifest.json").read_text())
    sights = {s["id"]: s for s in man["sights"]}
    tracks = {}  # file -> (sight, track)
    for s in man["sights"]:
        for aud in ("kid", "adult"):
            for t in s["tracks"][aud]:
                tracks[t["file"]] = (s, t)

    def sight_of(file):
        return re.match(r"content/([^/]+)/", file).group(1)

    # expand LINKS into directed links: src_file -> (dst_file, why)
    directed = []
    for lk in LINKS:
        for aud in ("kid", "adult"):
            a, b = lk[aud]
            for f in (a, b):
                assert f in tracks, f"not a base track in manifest: {f}"
            directed.append((a, b, lk["why"]))
            if lk["dir"] == "both":
                directed.append((b, a, lk["why"]))

    # rebuild manifest `related` arrays from scratch
    for s, t in tracks.values():
        t.pop("related", None)
    for src, dst, why in directed:
        ds, dt = tracks[dst]
        tracks[src][1].setdefault("related", []).append({
            "sight": ds["id"], "file": dst, "title": dt["title"], "note": why,
        })
    (ASSETS / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n")

    # rebuild markdown callout blocks
    by_src = {}
    for src, dst, why in directed:
        by_src.setdefault(src, []).append((dst, why))
    touched = 0
    for src, targets in by_src.items():
        p = ASSETS / src
        body = p.read_text()
        body = "\n".join(l for l in body.splitlines() if not l.startswith(MARK)).rstrip()
        ss = tracks[src][0]
        outlines = []
        for dst, why in targets:
            ds, dt = tracks[dst]
            when = ("Coming up" if ds["day"] > ss["day"] else
                    "Listen back" if ds["day"] < ss["day"] else "Also today")
            outlines.append(f"{MARK} {why} {when} — “{dt['title']}” ({ds['name']}, Day {ds['day']}).")
        p.write_text(body + "\n\n" + "\n".join(outlines) + "\n")
        touched += 1
    print(f"{len(directed)} directed links across {touched} markdown files")


if __name__ == "__main__":
    main()
