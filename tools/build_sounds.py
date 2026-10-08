#!/usr/bin/env python3
"""Builds sounds/ from selected Freesound recordings.

The candidates are downloaded by tools/fetch_sound_candidates.py (see the
fetch-sounds workflow, branch `sound-candidates`). Every selected clip is
trimmed of silence, optionally shortened with a fade-out, normalised to the
same loudness and written as MP3; CREDITS.md lists authors and licenses.

Usage: python3 tools/build_sounds.py candidates_dir [candidates_dir ...]
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100
TARGET_LUFS = -14.0

# (output name, freesound id, options)
#   start/end: cut window in seconds (before silence trimming)
#   max:       maximum length, longer clips fade out
#   pattern:   list of (start, length) slices joined with short gaps
SELECTION = [
    ("01_Bič_(whiplash)", "529925", {}),
    ("02_Airhorn", "414208", {"pattern": [(0.0, 0.18), (0.0, 0.18), (0.0, 1.2)]}),
    ("03_Vine_boom", "785925", {"max": 3.0}),
    ("04_Bruh", "506582", {}),
    ("05_Ba-dum-tss", "534937", {"max": 3.0}),
    ("06_Sad_trombone", "73581", {}),
    ("07_Bow_chicka_wow_wow", "78422", {"max": 8.0}),
    ("08_Sexy_saxofon", "257413", {"max": 9.0}),
    ("09_Dun_dun_dunnn", "146434", {}),
    ("10_Cvrčci_(trapné_ticho)", "129678", {"max": 6.0}),
    ("11_Bonk", "573047", {}),
    ("12_Prd", "402628", {}),
    ("13_Boing", "345689", {}),
    ("14_Wow", "658569", {}),
    ("15_Správně", "421002", {}),
    ("16_Špatně", "810745", {}),
    ("17_Tadá", "850021", {}),
    ("18_Potlesk", "277022", {"max": 6.0}),
    ("19_Smích_publika", "371562", {"max": 6.0}),
    ("20_Ka-ching", "209578", {}),
    ("21_Vířivé_bubny", "850835", {"max": 6.0}),
]


def ff(*args, capture=False):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    return r.stderr if capture else None


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return float(out.strip())


def loudness(path):
    log = ff("-i", path, "-af", "ebur128=peak=true", "-f", "null", "-", capture=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    return float(m[-1]) if m else None


TRIM_SILENCE = (
    "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.01,"
    "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,areverse"
)


def process(src, dst, opts, tmp):
    stage = os.path.join(tmp, "stage.wav")
    filters = []
    if "start" in opts or "end" in opts:
        filters.append(f"atrim=start={opts.get('start', 0)}" + (f":end={opts['end']}" if "end" in opts else ""))
        filters.append("asetpts=PTS-STARTPTS")
    filters.append(TRIM_SILENCE)
    ff("-i", src, "-af", ",".join(filters), "-ar", str(SR), stage)

    if "pattern" in opts:
        parts = []
        for i, (start, length) in enumerate(opts["pattern"]):
            part = os.path.join(tmp, f"part{i}.wav")
            fade = min(0.04, length / 4)
            ff("-i", stage, "-af", f"atrim=start={start}:duration={length},asetpts=PTS-STARTPTS,"
               f"afade=t=out:st={length - fade}:d={fade},apad=pad_dur=0.07", part)
            parts.append(part)
        joined = os.path.join(tmp, "joined.wav")
        inputs = sum((["-i", p] for p in parts), [])
        ff(*inputs, "-filter_complex", f"concat=n={len(parts)}:v=0:a=1", joined)
        stage = joined

    length = duration(stage)
    shaped = os.path.join(tmp, "shaped.wav")
    post = ["afade=t=in:d=0.005"]
    if opts.get("max") and length > opts["max"]:
        fade = min(1.0, opts["max"] / 4)
        post += [f"atrim=end={opts['max']}", f"afade=t=out:st={opts['max'] - fade}:d={fade}"]
        length = opts["max"]
    else:
        post.append(f"afade=t=out:st={max(length - 0.03, 0)}:d=0.03")
    ff("-i", stage, "-af", ",".join(post), shaped)

    lufs = loudness(shaped)
    gain = TARGET_LUFS - lufs if lufs is not None and lufs > -70 else 0.0
    gain = max(min(gain, 24.0), -24.0)
    ff("-i", shaped, "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:attack=1:release=50:level=false",
       "-ar", str(SR), "-codec:a", "libmp3lame", "-q:a", "2", "-map_metadata", "-1", dst)
    return length, lufs, gain


def main():
    dirs = sys.argv[1:]
    manifest = {}
    for d in dirs:
        with open(os.path.join(d, "manifest.json")) as f:
            for items in json.load(f).values():
                for it in items:
                    manifest.setdefault(it["id"], {**it, "path": os.path.join(d, it["file"])})

    out_dir = os.path.join(ROOT, "sounds")
    for f in os.listdir(out_dir):
        if f.endswith(".mp3"):
            os.remove(os.path.join(out_dir, f))

    credits = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, sid, opts in SELECTION:
            if sid is None:
                print(f"skip {name}: no recording selected")
                continue
            info = manifest[sid]
            dst = os.path.join(out_dir, name + ".mp3")
            length, lufs, gain = process(info["path"], dst, opts, tmp)
            print(f"{name}: {length:.1f}s  source {lufs} LUFS, gain {gain:+.1f} dB  <- {info['title']}")
            lic = info["license"] or ""
            lic_name = "CC0 1.0" if lic.startswith("publicdomain/zero") else "CC BY " + lic.split("/")[-1]
            lic_url = f"https://creativecommons.org/{lic}/"
            title = re.sub(r"\s+by\s+\S+$", "", info["title"])
            credits.append(f"| {name.split('_', 1)[1].replace('_', ' ')} | [{title}]({info['url']}) | "
                           f"{info['user']} | [{lic_name}]({lic_url}) |")

    with open(os.path.join(ROOT, "CREDITS.md"), "w") as f:
        f.write("# Zvuky – autoři a licence\n\n"
                "Zvuky ve složce `sounds/` pocházejí z [Freesound.org](https://freesound.org). "
                "Byly oříznuté, zkrácené a srovnané na stejnou hlasitost "
                "(`tools/build_sounds.py`).\n\n"
                "| Tlačítko | Původní nahrávka | Autor | Licence |\n|---|---|---|---|\n")
        f.write("\n".join(credits) + "\n")


if __name__ == "__main__":
    main()
