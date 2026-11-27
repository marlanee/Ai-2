"""Rebuild Seoul ep2/ep3 (no track shared with earlier episodes) and the cyberpunk/dystopia videos (deduped pools).
Track names used by earlier episodes are read from their .edit.json and passed to build_long --exclude."""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
T = ROOT / "test_output"
P2, MM = r"C:\AI\ComfyUI\ComfyUI\output\pool2", r"C:\AI\ComfyUI\ComfyUI\output\mm3pool"


def used(edit):
    return [pathlib.Path(t["file"]).name for t in json.load(open(edit, encoding="utf-8"))["tracks"]]


def build(args):
    print(">>", args[-1] if args[-2] == "--title" else "", flush=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_long.py"), *args], capture_output=True, text=True, encoding="utf-8")
    print("\n".join(l for l in r.stdout.splitlines() if any(k in l for k in ("tracks", "master", "wrote"))), r.stderr[-800:] if r.returncode else "", flush=True)
    if r.returncode:
        sys.exit(1)


ex1 = used(T / "release/long_2h_final_v3.edit.json") + ["sa3h_pb_s504_00001.flac"]
e2 = T / "themes/seoul_ep2"
build(["--clip", str(e2 / "loop_abc_frozen.mp4"), "--pools", P2, MM, "--duration", "7200", "--out", str(e2 / "long_2h_ep2.mp4"),
       "--exclude", *ex1, "--ambience", str(e2 / "ambience_bed.flac"), "--listen-pack", "--seed", "22",
       "--title", "비 오는 80년대 서울, 다방 창가 | 공부·작업용 시티팝 로파이 2시간"])
ex2 = ex1 + used(e2 / "long_2h_ep2.edit.json")
e3 = T / "themes/seoul_ep3"
build(["--clip", str(e3 / "loop_abc.mp4"), "--pools", P2, MM, "--duration", "7200", "--out", str(e3 / "long_2h_ep3.mp4"),
       "--exclude", *ex2, "--ambience", str(e3 / "ambience_bed.flac"), "--listen-pack", "--seed", "33",
       "--title", "비 오는 80년대 서울, 막차 뒤 정류장 | 공부·작업용 시티팝 로파이 2시간"])
c = T / "themes/cyberpunk"
build(["--clip", str(c / "loop_abc.mp4"), "--pools", str(c / "music"), "--duration", "7200", "--out", str(c / "long_2h_cyberpunk.mp4"),
       "--ambience", str(c / "ambience_bed.flac"), "--listen-pack", "--seed", "5", "--theme", "cyberpunk",
       "--title", "Cyberpunk Lofi for Night Coding | Neon Rain City (2 Hours)"])
d = T / "themes/dystopia"
build(["--clip", str(d / "loop_abc.mp4"), "--pools", str(d / "music"), "--duration", "2700", "--out", str(d / "special_45min_dystopia.mp4"),
       "--ambience", str(d / "ambience_bed.flac"), "--listen-pack", "--seed", "9", "--theme", "dystopia", "--lead", "23",
       "--lead-free-min", "10", "--title", "Ambient Lofi for Writing & Reading | After the Fall (45 min)"])
# overlap report
s1, s2, s3 = set(used(T / "release/long_2h_final_v3.edit.json")), set(used(e2 / "long_2h_ep2.edit.json")), set(used(e3 / "long_2h_ep3.edit.json"))
print("overlap 1-2", len(s1 & s2), "1-3", len(s1 & s3), "2-3", len(s2 & s3))
for e in (c / "long_2h_cyberpunk.edit.json", d / "special_45min_dystopia.edit.json"):
    u = used(e); print(e.stem, "tracks", len(u), "unique", len(set(u)))
print("REBUILD UNIQUE DONE")
