#!/usr/bin/env python3
"""Media-drawer helper for the new-chapter skill.

Two modes:
  search <term> [--limit N]   list Wikimedia Commons file candidates (pick good ones)
  build  <spec.json>          download images, resolve licences, write media.json + CREDITS

The build spec (see .claude/skills/new-chapter/SKILL.md) is:
  {
    "sight": "day09-whisky", "name": "...", "title": "...", "note": "...",
    "chapters": [{"n":1,"label":"..."}],            # optional; defaults to one
    "items": [
      {"type":"image","slug":"01-x","commons":"File:...","chapter":1,
       "caption":"...","kidcaption":"..."},
      {"type":"video","slug":"vid","youtube":"ID","chapter":2,
       "title":"...","caption":"...","kidcaption":"..."},
      {"type":"audio","slug":"reading-x","file":"reading-x.m4a","chapter":3,
       "title":"...","caption":"...","license":"...","source":"..."}
    ]
  }
Images are fetched from Commons WITH attribution (author, licence, source url).
Videos are linked (attribution via oEmbed). Audio items reference files already
placed under tour/media/<sight>/audio/.
"""
import argparse, json, html, re, os, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "tour" / "media"
UA = {"User-Agent": "UKFamilyTour/1.0 (private family trip app; https://github.com/ifinkelstein/uk-family-tour)"}


def _commons(params):
    params = {**params, "format": "json"}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))


def search(term, limit=25):
    d = _commons({"action": "query", "list": "search", "srsearch": term,
                  "srnamespace": "6", "srlimit": str(limit)})
    return [m["title"] for m in d.get("query", {}).get("search", [])]


def _strip(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def imageinfo(title, width=1100):
    d = _commons({"action": "query", "titles": title, "prop": "imageinfo",
                  "iiprop": "url|extmetadata|mime", "iiurlwidth": str(width)})
    ii = next(iter(d["query"]["pages"].values()))["imageinfo"][0]
    ext = ii.get("extmetadata", {})
    g = lambda k: _strip((ext.get(k) or {}).get("value", ""))
    return {"thumburl": ii.get("thumburl") or ii.get("url"), "descurl": ii.get("descriptionurl"),
            "artist": g("Artist") or g("Credit"), "license": g("LicenseShortName"),
            "licenseurl": (ext.get("LicenseUrl") or {}).get("value", "")}


def yt_oembed(vid):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20))
        return {"credit": d.get("author_name", ""), "title": d.get("title", ""), "ok": True}
    except Exception as e:
        return {"ok": False, "err": str(e)}


def build(spec_path):
    spec = json.load(open(spec_path))
    sid = spec["sight"]
    imgdir = MEDIA / sid / "images"
    imgdir.mkdir(parents=True, exist_ok=True)
    items, credits = [], []
    for it in spec["items"]:
        t = it["type"]
        if t == "image":
            info = imageinfo(it["commons"])
            ext = os.path.splitext(info["thumburl"])[1].split("?")[0] or ".jpg"
            dest = imgdir / (it["slug"] + ext)
            dest.write_bytes(urllib.request.urlopen(
                urllib.request.Request(info["thumburl"], headers=UA), timeout=60).read())
            items.append({"type": "image", "id": it["slug"], "chapter": it.get("chapter", 1),
                          "file": "images/" + dest.name, "caption": it["caption"],
                          "kidcaption": it.get("kidcaption", ""), "credit": info["artist"],
                          "license": info["license"], "license_url": info["licenseurl"],
                          "source": info["descurl"]})
            credits.append((it["slug"], "images/" + dest.name, info["artist"], info["license"], info["descurl"]))
            print(f"img  {it['slug']:22} {info['license']:14} {info['artist'][:34]}")
            time.sleep(0.4)
        elif t == "video":
            oe = yt_oembed(it["youtube"])
            if not oe["ok"]:
                print(f"VID FAIL {it['youtube']}: {oe.get('err')}")
                continue
            vid = it["youtube"]
            items.append({"type": "video", "id": "vid-" + vid, "chapter": it.get("chapter", 1),
                          "provider": "youtube", "youtube_id": vid,
                          "url": f"https://www.youtube.com/watch?v={vid}",
                          "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                          "title": it.get("title") or oe["title"], "caption": it["caption"],
                          "kidcaption": it.get("kidcaption", ""), "credit": it.get("credit") or oe["credit"],
                          "license": "Linked on YouTube (not redistributed)",
                          "source": f"https://www.youtube.com/watch?v={vid}"})
            print(f"vid  {vid:22} {(it.get('credit') or oe['credit'])[:34]}")
        elif t == "audio":
            items.append({"type": "audio", "id": it["slug"], "chapter": it.get("chapter", 1),
                          "file": "audio/" + it["file"], "title": it.get("title", ""),
                          "caption": it["caption"], "kidcaption": it.get("kidcaption", ""),
                          "credit": it.get("credit", ""), "license": it.get("license", ""),
                          "source": it.get("source", "")})
            print(f"aud  {it['slug']}")
    rank = {"image": 0, "video": 1, "audio": 2}
    items.sort(key=lambda x: (x["chapter"], rank[x["type"]], x["id"]))
    counts = {k: sum(1 for i in items if i["type"] == k) for k in ("image", "video", "audio")}
    media = {"sight": sid, "name": spec["name"], "title": spec.get("title", ""),
             "note": spec.get("note", ""),
             "chapters": spec.get("chapters", [{"n": 1, "label": spec["name"]}]),
             "counts": counts, "items": items}
    (MEDIA / f"{sid}.json").write_text(json.dumps(media, indent=1, ensure_ascii=False) + "\n")
    L = [f"# {spec['name']} — media credits & licences\n",
         "Gathered for the UK Family Tour app (private family use). Images are free-licensed",
         "from Wikimedia Commons, reused WITH attribution. Videos are linked, not copied.\n"]
    for slug, f, artist, lic, src in credits:
        L += [f"### {slug}", f"- File: `{f}`", f"- Author: {artist or '-'}",
              f"- Licence: {lic}", f"- Source: {src}", ""]
    (MEDIA / f"{sid}-CREDITS.md").write_text("\n".join(L))
    print(f"\nwrote media/{sid}.json  counts={counts}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("term")
    s.add_argument("--limit", type=int, default=25)
    b = sub.add_parser("build")
    b.add_argument("spec")
    a = ap.parse_args()
    if a.cmd == "search":
        for t in search(a.term, a.limit):
            if not t.lower().endswith((".pdf", ".djvu")):
                print(t)
    else:
        build(a.spec)


if __name__ == "__main__":
    main()
