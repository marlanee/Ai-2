"""ComfyUI UI-format workflow (template) -> API-format prompt converter.

Uses the running server's /object_info to map widgets_values to input names.
Handles PrimitiveNode, Reroute, bypassed (mode 4) / muted (mode 2) nodes and subgraphs.

Usage:
  python scripts/ui_to_api.py <template_or_ui.json> <out_api.json> [--server http://127.0.0.1:8188]
"""
import argparse, json, pathlib, sys, urllib.request

DYNAMIC_COMBO = "COMFY_DYNAMICCOMBO_V3"
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", DYNAMIC_COMBO}
VIRTUAL = {"PrimitiveNode", "Reroute", "Note", "MarkdownNote"}


def is_widget(spec):
    t = spec[0]
    opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    # multi-type inputs such as "FLOAT,INT" declare their widget via widgetType
    return isinstance(t, list) or t in WIDGET_TYPES or opts.get("widgetType") in WIDGET_TYPES


def has_control(name, spec):
    opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "control_after_generate" in opts:
        return bool(opts["control_after_generate"])
    return spec[0] == "INT" and name in ("seed", "noise_seed")


def link_table(links):
    out = {}
    for l in links or []:
        if isinstance(l, dict):
            out[l["id"]] = (l["origin_id"], l["origin_slot"], l["target_id"], l["target_slot"])
        else:
            out[l[0]] = (l[1], l[2], l[3], l[4])
    return out


class Converter:
    def __init__(self, ui, object_info):
        self.ui = ui
        self.oi = object_info
        self.subgraphs = {sg["id"]: sg for sg in ui.get("definitions", {}).get("subgraphs", [])}
        self.real = {}      # fid -> (node, {input_name: src})
        self.alias = {}     # (fid, slot) -> src
        self.warnings = []

    # src = ("ref", fid, slot) | ("const", value)
    def scope(self, nodes, links, prefix, sg_in):
        lt = link_table(links)

        def src_of(link_id):
            o, os_, _, _ = lt[link_id]
            if o == -10:
                return sg_in.get(os_, ("const", None))
            return ("ref", f"{prefix}{o}", os_)

        for n in nodes:
            fid = f"{prefix}{n['id']}"
            t = n.get("type")
            mode = n.get("mode", 0)
            if t in ("Note", "MarkdownNote") or mode == 2:
                continue
            ins = n.get("inputs", []) or []
            linked = {}
            for idx, i in enumerate(ins):
                if i.get("link") is not None and i["link"] in lt:
                    linked[idx] = src_of(i["link"])
            if t == "PrimitiveNode":
                wv = n.get("widgets_values") or [None]
                self.alias[(fid, 0)] = ("const", wv[0])
                continue
            if t == "Reroute":
                self.alias[(fid, 0)] = linked.get(0, ("const", None))
                continue
            if mode == 4:  # bypass: pass through first input of matching type
                for oslot, o in enumerate(n.get("outputs", []) or []):
                    for idx, i in enumerate(ins):
                        if i.get("type") == o.get("type") and idx in linked:
                            self.alias[(fid, oslot)] = linked[idx]
                            break
                continue
            if t in self.subgraphs:
                sg = self.subgraphs[t]
                inner_in = {}
                for k, sgi in enumerate(sg.get("inputs", [])):
                    # match outer input by name; only real links are carried in.
                    # Unlinked promoted widgets keep the inner node's own widget value
                    # (the outer widgets_values order is not reliable across frontend versions).
                    idx = next((j for j, i in enumerate(ins) if i.get("name") == sgi.get("name")), None)
                    if idx is not None and idx in linked:
                        inner_in[k] = linked[idx]
                self.scope(sg.get("nodes", []), sg.get("links", []), f"{fid}:", inner_in)
                sl = link_table(sg.get("links", []))
                for lid, (o, os_, tg, ts) in sl.items():
                    if tg == -20:
                        self.alias[(fid, ts)] = ("ref", f"{fid}:{o}", os_) if o != -10 else inner_in.get(os_, ("const", None))
                continue
            self.real[fid] = (n, {ins[idx]["name"]: s for idx, s in linked.items()})

    def resolve(self, src, depth=0):
        while src[0] == "ref" and (src[1], src[2]) in self.alias and depth < 100:
            src = self.alias[(src[1], src[2])]
            depth += 1
        return src

    def build(self):
        self.scope(self.ui["nodes"], self.ui.get("links"), "", {})
        api = {}
        for fid, (n, linked) in self.real.items():
            t = n["type"]
            if t not in self.oi:
                self.warnings.append(f"unknown node type {t} ({fid}) - skipped")
                continue
            info = self.oi[t]
            specs = {}
            for sec in ("required", "optional"):
                specs.update(info["input"].get(sec, {}))
            order = info.get("input_order", {})
            names = order.get("required", []) + order.get("optional", [])
            wv = n.get("widgets_values")
            inputs = {}
            if isinstance(wv, dict):
                for k, v in wv.items():
                    if k in specs:
                        inputs[k] = v
            else:
                wv = list(wv or [])
                for name in names:
                    spec = specs.get(name)
                    if spec is None or not is_widget(spec):
                        continue
                    if wv:
                        inputs[name] = wv.pop(0)
                        if has_control(name, spec) and wv and wv[0] in ("fixed", "increment", "decrement", "randomize"):
                            wv.pop(0)
                        if spec[0] == DYNAMIC_COMBO:
                            # selected option's sub-widgets follow, keyed as "name.sub" in API format
                            opt = next((o for o in spec[1].get("options", []) if o.get("key") == inputs[name]), None)
                            if opt:
                                sub = {}
                                for sec in ("required", "optional"):
                                    sub.update(opt.get("inputs", {}).get(sec, {}))
                                for sname, sspec in sub.items():
                                    if is_widget(sspec) and wv:
                                        inputs[f"{name}.{sname}"] = wv.pop(0)
            for name, s in linked.items():
                s = self.resolve(s)
                if s[0] == "const":
                    if s[1] is not None:
                        inputs[name] = s[1]
                else:
                    inputs[name] = [s[1], s[2]]
            api[fid] = {"class_type": t, "inputs": inputs, "_meta": {"title": n.get("title") or t}}
        # drop references to nodes that do not exist (muted)
        for fid, node in api.items():
            for k, v in list(node["inputs"].items()):
                if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] not in api:
                    self.warnings.append(f"{fid}.{k} -> missing node {v[0]} (removed)")
                    del node["inputs"][k]
        return api


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    a = ap.parse_args()
    p = pathlib.Path(a.src)
    if not p.exists():
        import comfyui_workflow_templates_json as m  # type: ignore
        p = pathlib.Path(m.__file__).parent / "templates" / (a.src if a.src.endswith(".json") else a.src + ".json")
    ui = json.loads(p.read_text(encoding="utf-8"))
    oi = json.load(urllib.request.urlopen(f"{a.server}/object_info"))
    c = Converter(ui, oi)
    api = c.build()
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_text(json.dumps(api, indent=2, ensure_ascii=False), encoding="utf-8")
    for w in c.warnings:
        print("WARN", w, file=sys.stderr)
    print(f"wrote {a.out}: {len(api)} nodes")


if __name__ == "__main__":
    main()
