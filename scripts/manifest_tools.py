#!/usr/bin/env python3
"""Manifest wiring for the new-chapter skill. Writes manifest.json at indent=1
(house style). tracks.json sidecar shape: {"kid":[{...base...}], "adult":[...]}.

  add-sight --id ID --name NAME --day N --date DATE --note NOTE [--after SID] [--tracks PATH]
      Insert a whole new themed sight (e.g. a "Whisky" or "Literary" sight) from
      its tracks.json. Placed after --after, else after the last sight of --day.

  prepend  --sight SID [--tracks PATH]
      Insert the sidecar's base track at the FRONT of an existing sight (renumbers
      that sight's chapters). Use for "significance & overview" openers.

  append   --sight SID [--tracks PATH]
      Append the sidecar's base track to an existing sight (adds a later chapter).

For prepend/append the content dir is inferred from the sight's first existing
track; the sidecar defaults to tour/content/<contentdir>/tracks.json.
"""
import argparse, json, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tour"


def _load():
    return json.loads((ROOT / "manifest.json").read_text(), object_pairs_hook=collections.OrderedDict)


def _save(m):
    (ROOT / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")


def _sidecar(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=collections.OrderedDict)


def add_sight(a):
    m = _load()
    if any(s["id"] == a.id for s in m["sights"]):
        raise SystemExit("sight already exists")
    tr = _sidecar(a.tracks or ROOT / f"content/{a.id}/tracks.json")
    sight = collections.OrderedDict([
        ("id", a.id), ("name", a.name), ("day", a.day), ("date", a.date), ("note", a.note),
        ("tracks", collections.OrderedDict([("kid", tr["kid"]), ("adult", tr["adult"])]))])
    if a.after:
        i = next(i for i, s in enumerate(m["sights"]) if s["id"] == a.after)
        m["sights"].insert(i + 1, sight)
    else:
        idxs = [i for i, s in enumerate(m["sights"]) if s["day"] == a.day]
        m["sights"].insert((idxs[-1] + 1) if idxs else len(m["sights"]), sight)
    _save(m)
    print("added sight", a.id, "on day", a.day)


def _pp(a, front):
    m = _load()
    s = next(x for x in m["sights"] if x["id"] == a.sight)
    contentdir = Path(s["tracks"]["adult"][0]["file"]).parts[1]
    tr = _sidecar(a.tracks or ROOT / f"content/{contentdir}/tracks.json")
    for aud in ("kid", "adult"):
        base = tr[aud][0]
        slug = Path(base["file"]).name
        if any(t["file"].endswith(slug) for t in s["tracks"][aud]):
            raise SystemExit("track already present")
        s["tracks"][aud].insert(0, base) if front else s["tracks"][aud].append(base)
    _save(m)
    print(("prepended" if front else "appended"), "to", a.sight)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add-sight")
    for x in ("--id", "--name", "--date", "--note"):
        p.add_argument(x, required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--after")
    p.add_argument("--tracks")
    for name in ("prepend", "append"):
        q = sub.add_parser(name)
        q.add_argument("--sight", required=True)
        q.add_argument("--tracks")
    a = ap.parse_args()
    if a.cmd == "add-sight":
        add_sight(a)
    else:
        _pp(a, front=(a.cmd == "prepend"))


if __name__ == "__main__":
    main()
