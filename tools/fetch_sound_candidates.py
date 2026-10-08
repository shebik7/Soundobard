#!/usr/bin/env python3
"""Downloads candidate recordings from Freesound.org for every board slot.

For each category it searches Freesound for freely licensed sounds (CC0 or
CC-BY), most downloaded first, and saves the MP3 previews of the top hits plus
a manifest with title, author, license and URL. Runs on GitHub Actions
(.github/workflows/fetch-sounds.yml), which has open internet access.

Usage: python3 tools/fetch_sound_candidates.py out_dir [per_query]
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

CATEGORIES = {
    "whip": ["whip crack", "whip"],
    "airhorn": ["air horn", "mlg airhorn"],
    "vine_boom": ["vine boom", "boom bass impact meme"],
    "rimshot": ["rimshot", "ba dum tss"],
    "sad_trombone": ["sad trombone", "wah wah wah fail"],
    "bow_chicka": ["bow chicka wow wow", "wah guitar funk porn"],
    "sexy_sax": ["sexy saxophone", "smooth sax"],
    "jazz": ["smooth jazz loop", "elevator music"],
    "dramatic": ["dun dun dun dramatic", "dramatic sting"],
    "crickets": ["crickets", "crickets awkward silence"],
    "bonk": ["bonk", "cartoon bonk"],
    "fart": ["fart", "fart funny"],
    "boing": ["boing", "cartoon boing spring"],
    "correct": ["correct answer", "correct ding"],
    "wrong": ["wrong answer buzzer", "game show buzzer wrong"],
    "tada": ["tada", "ta da"],
    "fanfare": ["victory fanfare", "fanfare trumpet win"],
    "applause": ["applause", "clapping crowd"],
    "cash": ["cash register", "ka ching"],
    "laugh": ["sitcom laugh track", "audience laughing"],
    "drumroll": ["drum roll", "drumroll cymbal"],
    "record_scratch": ["record scratch", "vinyl scratch stop"],
    "bruh": ["bruh", "bruh meme"],
    "wow": ["wow", "anime wow"],
}

LICENSES = {
    "cc0": 'license:"Creative Commons 0"',
    "by": 'license:"Attribution"',
}

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    time.sleep(0.6)
    return data if binary else data.decode("utf-8", "replace")


def search(query, license_filter):
    ids = []
    for sort in ("Downloads (most first)", "num_downloads desc"):
        params = urllib.parse.urlencode({
            "q": query,
            "f": f"{license_filter} duration:[0 TO 20]",
            "s": sort,
        })
        url = f"https://freesound.org/search/?{params}"
        try:
            page = get(url)
        except Exception as e:  # noqa: BLE001
            print(f"  search failed ({sort}): {e}")
            continue
        for user, sid in re.findall(r'href="/people/([^/"]+)/sounds/(\d+)/"', page):
            if (user, sid) not in ids:
                ids.append((user, sid))
        if ids:
            break
    return ids


def sound_info(user, sid):
    page = get(f"https://freesound.org/people/{user}/sounds/{sid}/")
    meta = dict(re.findall(r'<meta\s+property="og:([a-z:_]+)"\s+content="([^"]*)"', page))
    preview = meta.get("audio") or next(iter(re.findall(r'(https://cdn\.freesound\.org/previews/[^"\']+-hq\.mp3)', page)), None)
    lic = re.search(r'creativecommons\.org/(publicdomain/zero|licenses/by(?:-nc)?)/([\d.]+)', page)
    downloads = re.search(r'([\d,]+)\s*downloads', page)
    duration = re.search(r'"duration"\s*:\s*"?([\d.]+)', page) or re.search(r'Duration</dt>\s*<dd[^>]*>\s*([^<]+)', page)
    return {
        "id": sid,
        "user": user,
        "title": html.unescape(meta.get("title", "")),
        "url": f"https://freesound.org/people/{user}/sounds/{sid}/",
        "preview": preview,
        "license": (lic.group(1) + "/" + lic.group(2)) if lic else None,
        "downloads": int(downloads.group(1).replace(",", "")) if downloads else None,
        "duration": duration.group(1).strip() if duration else None,
    }


def main():
    out = sys.argv[1]
    per_query = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    os.makedirs(out, exist_ok=True)
    manifest = {}
    for key, queries in CATEGORIES.items():
        print(f"[{key}]")
        seen, picked = set(), []
        for query in queries:
            for lic_name, lic_filter in LICENSES.items():
                for user, sid in search(query, lic_filter)[:per_query]:
                    if sid in seen:
                        continue
                    seen.add(sid)
                    try:
                        info = sound_info(user, sid)
                    except Exception as e:  # noqa: BLE001
                        print(f"  {sid}: page failed: {e}")
                        continue
                    if not info["preview"] or (info["license"] or "").startswith("licenses/by-nc"):
                        print(f"  {sid}: skipped ({info['license']}, preview={bool(info['preview'])})")
                        continue
                    info["query"] = query
                    info["file"] = f"{key}/{len(picked):02d}_{sid}.mp3"
                    os.makedirs(os.path.join(out, key), exist_ok=True)
                    try:
                        with open(os.path.join(out, info["file"]), "wb") as f:
                            f.write(get(info["preview"], binary=True))
                    except Exception as e:  # noqa: BLE001
                        print(f"  {sid}: download failed: {e}")
                        continue
                    picked.append(info)
                    print(f"  + {sid} {info['title']!r} by {user} [{info['license']}] dl={info['downloads']}")
        manifest[key] = picked
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
