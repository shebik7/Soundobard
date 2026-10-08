#!/usr/bin/env python3
"""End-to-end test of the installed APK on an emulator, driven through adb.

Usage: python3 scripts/e2e.py path/to/app.apk output_dir

Checks that every bundled sound shows up as a button and really starts playing,
exercises the settings (rename, reorder, hide, columns, share import) and saves
screenshots plus a report into output_dir. Exits non-zero if any check fails.
"""
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PKG = "cz.soundobard"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_EXT = {"mp3", "ogg", "wav", "m4a", "aac", "flac"}

apk, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
results = []


def log(msg):
    print(msg, flush=True)
    with open(os.path.join(out, "report.txt"), "a") as f:
        f.write(msg + "\n")


def check(name, ok, detail=""):
    results.append((name, ok))
    log(f"{'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


def adb(*args, check_rc=True):
    r = subprocess.run(["adb", *args], capture_output=True, text=True)
    if check_rc and r.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def shell(cmd):
    return adb("shell", cmd)


def try_shell(cmd):
    return adb("shell", cmd, check_rc=False)


def screenshot(name):
    with open(os.path.join(out, name + ".png"), "wb") as f:
        f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True).stdout)


def ui_nodes(_dismissed=0):
    for _ in range(5):
        r = subprocess.run(["adb", "shell", "uiautomator dump /sdcard/ui.xml"], capture_output=True, text=True)
        if "dumped to" in r.stdout:
            xml = adb("exec-out", "cat /sdcard/ui.xml")
            nodes = []
            for n in ET.fromstring(xml).iter("node"):
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", n.get("bounds", ""))
                if not m:
                    continue
                x1, y1, x2, y2 = map(int, m.groups())
                nodes.append({
                    "text": n.get("text", ""),
                    "desc": n.get("content-desc", ""),
                    "bounds": (x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                })
            # The emulator's own launcher sometimes ANRs after boot; its system
            # dialog would cover the app, so wait it out and look again.
            if _dismissed < 3 and any("isn't responding" in n["text"] for n in nodes):
                wait_btn = find(nodes, text="Wait") or find(nodes, text="Close app")
                if wait_btn:
                    log("dismissing system 'isn't responding' dialog")
                    tap(wait_btn[0])
                    time.sleep(1.0)
                    return ui_nodes(_dismissed + 1)
            return nodes
        time.sleep(0.7)
    raise RuntimeError("uiautomator dump failed")


def find(nodes, text=None, desc=None):
    return [n for n in nodes if (text is None or n["text"] == text) and (desc is None or n["desc"] == desc)]


def tap(node):
    x, y = node["center"]
    shell(f"input tap {x} {y}")


def tap_text(text, wait=0.8):
    found = find(ui_nodes(), text=text)
    if not found:
        raise RuntimeError(f"no node with text {text!r}")
    tap(found[0])
    time.sleep(wait)


def tap_desc(desc, wait=0.8):
    found = find(ui_nodes(), desc=desc)
    if not found:
        raise RuntimeError(f"no node with content-desc {desc!r}")
    tap(found[0])
    time.sleep(wait)


def board_titles(nodes, expected):
    """Titles of sound buttons on screen, in reading order."""
    hits = [n for n in nodes if n["text"] in expected and n["bounds"][1] > 150]
    hits.sort(key=lambda n: (n["center"][1] // 60, n["bounds"][0]))
    seen, ordered = set(), []
    for n in hits:
        if n["text"] not in seen:
            seen.add(n["text"])
            ordered.append(n)
    return ordered


def back():
    shell("input keyevent KEYCODE_BACK")
    time.sleep(0.8)


def launch(clear=False):
    if clear:
        shell(f"pm clear {PKG}")
    shell(f"am force-stop {PKG}")
    shell(f"am start -W -n {PKG}/.MainActivity")
    time.sleep(2.5)


# --- audio state ------------------------------------------------------------

def app_uid():
    m = re.search(r"uid:(\d+)", shell(f"pm list packages -U {PKG}"))
    return m.group(1)


def player_states(uid):
    dump = shell("dumpsys audio")
    return re.findall(rf"u/pid:{uid}/\d+.*?state:(\w+)", dump)


def wait_for(predicate, timeout=4.0, step=0.25):
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


def started_count(uid):
    return player_states(uid).count("started")


# --- expected content ---------------------------------------------------------

def title_from_file(name):
    base = name.rsplit(".", 1)[0]
    base = re.sub(r"^\d{1,3}\s*[_.\- ]\s*", "", base)
    return base.replace("_", " ").strip() or name


bundled = sorted(
    (f for f in os.listdir(os.path.join(ROOT, "sounds")) if f.rsplit(".", 1)[-1].lower() in AUDIO_EXT),
    key=str.lower,
)
expected = [title_from_file(f) for f in bundled]
log(f"Bundled sounds: {len(expected)}")

# --- tests ----------------------------------------------------------------------

adb("install", "-r", apk)
try_shell("settings put system screen_off_timeout 1800000")
try_shell("svc power stayon true")
try_shell("input keyevent KEYCODE_WAKEUP")
try_shell("wm dismiss-keyguard")
try_shell("cmd uimode night no")
try_shell("cmd media_session volume --stream 3 --set 10")
adb("logcat", "-c")
uid = app_uid()

launch(clear=True)
nodes = ui_nodes()
screenshot("01_board")
on_board = [n["text"] for n in board_titles(nodes, set(expected))]
check("all bundled sounds shown as buttons", on_board == expected,
      f"{len(on_board)}/{len(expected)} in expected order" if on_board == expected else f"got {on_board}")

cells = board_titles(nodes, set(expected))
if cells:
    widths = {n["bounds"][2] - n["bounds"][0] for n in cells}
    first_row = [n for n in cells if abs(n["center"][1] - cells[0]["center"][1]) < 30]
    check("default layout has 3 columns", len(first_row) == 3, f"first row: {len(first_row)} buttons")
    last_bottom = max(n["bounds"][3] for n in cells)
    screen_h = int(re.search(r"(\d+)x(\d+)", shell("wm size")).group(2))
    check("all 21 buttons fit on one screen", last_bottom < screen_h, f"last button ends at y={last_bottom}/{screen_h}")

# Every sound must actually start playing.
for title in expected:
    node = find(ui_nodes(), text=title)
    if not node:
        check(f"play '{title}'", False, "button not found")
        continue
    tap(node[0])
    ok = wait_for(lambda: started_count(uid) >= 1, timeout=4)
    check(f"play '{title}'", bool(ok), "MediaPlayer reached state 'started'" if ok else f"states: {player_states(uid)}")
    stop = find(ui_nodes(), desc="Zastavit vše")
    if stop:
        tap(stop[0])
    wait_for(lambda: started_count(uid) == 0, timeout=3)

# Long sound: second tap stops it, and a new sound replaces the old one.
long_a, long_b = "Sexy saxofon", "Jazzový podkres"
if long_a in expected and long_b in expected:
    tap_text(long_a, 0.3)
    wait_for(lambda: started_count(uid) >= 1)
    screenshot("02_board_playing")
    tap_text(long_b, 0.3)
    time.sleep(0.8)
    check("new sound stops the previous one (overlap off)", started_count(uid) == 1, f"states: {player_states(uid)}")
    tap_text(long_b, 0.3)
    stopped = wait_for(lambda: started_count(uid) == 0, timeout=3)
    check("second tap on a playing button stops it", bool(stopped), f"states: {player_states(uid)}")

# Settings screen.
tap_desc("Nastavení", 1.0)
screenshot("03_settings_top")
nodes = ui_nodes()
check("settings screen opens", bool(find(nodes, text="Přidat zvuky z telefonu")))
shell("input swipe 540 1900 540 700 400")
time.sleep(0.8)
screenshot("04_settings_list")
for _ in range(4):
    shell("input swipe 540 700 540 1900 300")
time.sleep(1.0)

# Rename the first sound.
first = expected[0]
tap_text(first, 1.0)
screenshot("05_rename_dialog")
shell("input text Prejmenovany%sbic")
time.sleep(0.5)
screenshot("05b_rename_typed")
tap_text("Uložit", 1.0)
renamed = "Prejmenovany bic"
check("rename shows in settings", bool(find(ui_nodes(), text=renamed)))

# Reorder: drag the first row's handle below the third row.
def settings_rows(nodes):
    """(title, handle) pairs of list rows that are fully visible, top to bottom."""
    titles = [n for n in nodes if n["text"] in set(expected) | {renamed}]
    rows = []
    for h in sorted(find(nodes, desc="Přesunout"), key=lambda n: n["center"][1]):
        if h["bounds"][1] < 300:
            continue
        t = min(titles, key=lambda n: abs(n["center"][1] - h["center"][1]), default=None)
        if t and abs(t["center"][1] - h["center"][1]) < 80:
            rows.append((t["text"], h))
    return rows


rows = settings_rows(ui_nodes())
before = [t for t, _ in rows]
log(f"settings rows before drag: {before}")
if len(rows) >= 4:
    (x, y), (_, y3) = rows[0][1]["center"], rows[2][1]["center"]
    shell(f"input swipe {x} {y} {x} {y3 + 40} 1800")
    time.sleep(1.2)
    after = [t for t, _ in settings_rows(ui_nodes())]
    check("drag & drop reorders the list", after[:3] == [before[1], before[2], before[0]], f"before {before[:3]} after {after[:3]}")
    screenshot("06_settings_reordered")
else:
    check("drag & drop reorders the list", False, f"only {len(rows)} rows visible")

# Hide the 4th sound (bundled sounds can be hidden, not deleted).
nodes = ui_nodes()
hidden_title = None
target = find(nodes, text=expected[3])
eyes = find(nodes, desc="Skrýt")
if target and eyes:
    eye = min(eyes, key=lambda n: abs(n["center"][1] - target[0]["center"][1]))
    if abs(eye["center"][1] - target[0]["center"][1]) < 80:
        tap(eye)
        time.sleep(0.8)
        hidden_title = expected[3]
        screenshot("06b_settings_hidden")
        check("hidden row shows 'Zobrazit' toggle", bool(find(ui_nodes(), desc="Zobrazit")))
check("hide button available", hidden_title is not None)

back()
nodes = ui_nodes()
titles_now = [n["text"] for n in board_titles(nodes, set(expected) | {renamed})]
screenshot("07_board_after_settings")
check("renamed title shown on board", renamed in titles_now)
check("hidden sound not on board", hidden_title is not None and hidden_title not in titles_now)
check("board follows the new order", titles_now[:4] == [expected[1], expected[2], renamed, expected[4]],
      f"first four: {titles_now[:4]}")

# Settings persist across an app restart.
launch()
titles_restart = [n["text"] for n in board_titles(ui_nodes(), set(expected) | {renamed})]
check("order/rename/hide survive restart", titles_restart == titles_now)

# Columns: 4 per row.
tap_desc("Nastavení", 1.0)
tap_text("4", 0.6)
back()
cells = board_titles(ui_nodes(), set(expected) | {renamed})
first_row = [n for n in cells if abs(n["center"][1] - cells[0]["center"][1]) < 30]
check("4-column layout", len(first_row) == 4, f"first row: {len(first_row)}")
screenshot("08_board_4_columns")
tap_desc("Nastavení", 1.0)
tap_text("2", 0.6)
back()
screenshot("09_board_2_columns")
tap_desc("Nastavení", 1.0)
tap_text("3", 0.6)
back()

# Dark mode.
try_shell("cmd uimode night yes")
launch()
screenshot("10_board_dark")
tap_desc("Nastavení", 1.0)
screenshot("11_settings_dark")
back()
try_shell("cmd uimode night no")

# Import through the Android share sheet (content:// URI with a read grant).
src = os.path.join(ROOT, "sounds", bundled[1])
adb("push", src, "/sdcard/Download/import_test.mp3")
try_shell("am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/Download/import_test.mp3")
time.sleep(3)
row = shell("content query --uri content://media/external/audio/media --projection _id:_display_name")
m = re.search(r"_id=(\d+), _display_name=import_test\.mp3", row)
if m:
    uri = f"content://media/external/audio/media/{m.group(1)}"
    # The URI is also passed as data so --grant-read-uri-permission covers it.
    shell(f"am start -a android.intent.action.SEND -d {uri} -t audio/mpeg --eu android.intent.extra.STREAM {uri} "
          f"--grant-read-uri-permission -n {PKG}/.MainActivity")
    time.sleep(3)
    launch()
    nodes = ui_nodes()
    shared = find(nodes, text="import test")
    if not shared:
        shell("input swipe 540 1900 540 600 300")
        time.sleep(0.8)
        shared = find(ui_nodes(), text="import test")
    screenshot("12_board_after_share")
    check("sound shared from another app is added", bool(shared))
    if shared:
        tap(shared[0])
        ok = wait_for(lambda: started_count(uid) >= 1)
        check("imported sound plays", bool(ok), f"states: {player_states(uid)}")
        try:
            tap_desc("Zastavit vše", 0.5)
        except RuntimeError:
            pass  # short sound already finished
else:
    check("sound shared from another app is added", False, "media scanner did not index the test file")

crashes = adb("logcat", "-d", "-b", "crash")
check("no crashes in logcat", PKG not in crashes, crashes.strip()[-2000:])
with open(os.path.join(out, "logcat.txt"), "w") as f:
    f.write(adb("logcat", "-d"))

failed = [n for n, ok in results if not ok]
log(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
