"""Submit an API-format workflow to a local ComfyUI, wait, and record time / peak VRAM / outputs.

Usage:
  python scripts/run_workflow.py workflows/xxx_api.json --set 94.tags="..." --set 3.seed=1 \
      [--label name] [--log test_output/runs.jsonl] [--save-api path]

--set takes NODE.INPUT=VALUE; VALUE is parsed as JSON when possible, otherwise used as a string.
Peak VRAM is sampled from nvidia-smi (whole GPU, includes ~1GB desktop usage).
"""
import argparse, json, pathlib, subprocess, threading, time, urllib.request, uuid

SERVER = "http://127.0.0.1:8188"


def vram_used_mb():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return int(out[0]) if out else 0


def post(path, data):
    req = urllib.request.Request(SERVER + path, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))


def get(path):
    return json.load(urllib.request.urlopen(SERVER + path))


def apply_sets(api, sets):
    for s in sets:
        key, val = s.split("=", 1)
        nid, inp = key.split(".", 1)
        try:
            v = json.loads(val)
        except json.JSONDecodeError:
            v = val
        if nid not in api:
            raise SystemExit(f"node {nid} not in workflow")
        api[nid]["inputs"][inp] = v


def free_memory():
    try:
        post("/free", {"unload_models": True, "free_memory": True})
    except Exception:
        pass


def run(api, label, timeout=7200, keep=False):
    if not keep:   # --keep-models: back-to-back jobs of the same workflow reuse the loaded models
        free_memory()
        time.sleep(2)
    base = vram_used_mb()
    peak = [base]
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            peak[0] = max(peak[0], vram_used_mb())
            time.sleep(0.5)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    t0 = time.time()
    r = post("/prompt", {"prompt": api, "client_id": str(uuid.uuid4())})
    pid = r["prompt_id"]
    status, outputs, err = "timeout", [], None
    while time.time() - t0 < timeout:
        h = get(f"/history/{pid}")
        if pid in h:
            e = h[pid]
            st = e.get("status", {})
            status = st.get("status_str", "unknown")
            if status == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        err = {k: m[1].get(k) for k in ("node_id", "node_type", "exception_type", "exception_message")}
            for nid, o in e.get("outputs", {}).items():
                for kind in ("audio", "images", "gifs", "videos", "video"):
                    for f in o.get(kind, []) or []:
                        if isinstance(f, dict) and "filename" in f:
                            outputs.append(str(pathlib.Path(f.get("subfolder", "")) / f["filename"]))
            break
        time.sleep(1)
    elapsed = time.time() - t0
    stop.set()
    th.join()
    return {"label": label, "prompt_id": pid, "status": status, "seconds": round(elapsed, 1),
            "peak_vram_mb": peak[0], "baseline_vram_mb": base, "outputs": outputs, "error": err,
            "time": time.strftime("%Y-%m-%d %H:%M:%S")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workflow")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--label", default=None)
    ap.add_argument("--log", default="test_output/runs.jsonl")
    ap.add_argument("--save-api", default=None)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--keep-models", action="store_true")
    a = ap.parse_args()
    api = json.loads(pathlib.Path(a.workflow).read_text(encoding="utf-8"))
    for v in api.values():
        v.pop("_meta", None)
    apply_sets(api, a.set)
    if a.save_api:
        pathlib.Path(a.save_api).write_text(json.dumps(api, indent=2, ensure_ascii=False), encoding="utf-8")
    res = run(api, a.label or pathlib.Path(a.workflow).stem, a.timeout, a.keep_models)
    pathlib.Path(a.log).parent.mkdir(parents=True, exist_ok=True)
    with open(a.log, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
