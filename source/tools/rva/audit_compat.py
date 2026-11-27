#!/usr/bin/env python3
"""Tell which features will actually switch on, site by site.

Mapping only says "this site moved to X".  The mod then compares the bytes that
1.13d had at that site before touching memory, and silently skips the feature if
they no longer match.  So for every mapped site we compare the two builds byte
for byte, skipping only the bytes that the mask calls version-dependent
(rel32 operands, embedded pointers).  What survives is the honest answer:
which patches are still applicable, which are dead, which we could not place.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rvamap import PE, build_mask  # noqa: E402

SIG = 96


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d-dir", required=True)
    ap.add_argument("--c-dir", required=True)
    ap.add_argument("--map-prefix", required=True, help="e.g. offsets/map-113c")
    ap.add_argument("--csv")
    args = ap.parse_args()

    def locate(directory, name):
        for f in os.listdir(directory):
            if f.lower() == name.lower():
                return os.path.join(directory, f)
        return None

    cache = {}

    def images(mod):
        if mod not in cache:
            d = locate(args.d_dir, mod)
            c = locate(args.c_dir, mod)
            if not d or not c:
                cache[mod] = None
            else:
                pd, pc = PE(d), PE(c)
                cache[mod] = (pd.image, build_mask(pd), pc.image, build_mask(pc))
        return cache[mod]

    rows = []
    for f in sorted(glob.glob(args.map_prefix + "-*.json")):
        mod = os.path.basename(f)[len(os.path.basename(args.map_prefix)) + 1:-5] + ".dll"
        j = json.load(open(f, encoding="utf-8"))
        imgs = images(mod)
        for m in j["mapped"]:
            rva, pos = m["rva_113d"], m["rva_target"]
            if imgs is None:
                rows.append({**m, "module": mod, "verdict": "no-binary", "diff": None})
                continue
            d_img, d_mask, c_img, c_mask = imgs
            end = SIG
            if rva + end > len(d_img) or pos + end > len(c_img):
                end = min(SIG, len(d_img) - rva, len(c_img) - pos)
            compared = diff = 0
            for k in range(end):
                if d_mask[rva + k] or c_mask[pos + k]:
                    continue
                compared += 1
                if d_img[rva + k] != c_img[pos + k]:
                    diff += 1
            if compared < 6:
                verdict = "no-evidence"
            elif diff == 0:
                verdict = "applies"
            elif diff * 4 <= compared:
                verdict = "minor-drift"
            else:
                verdict = "changed"
            rows.append({**m, "module": mod, "verdict": verdict,
                         "compared": compared, "diff": diff})
        for u in j["unmapped"]:
            rows.append({"name": u["name"], "rva_113d": u["value"], "rva_target": None,
                         "module": mod, "verdict": "unplaced"})

    by_file = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_file[r.get("file", "?")][r["verdict"]] += 1

    print(f"{'source file':22s} {'applies':>8s} {'drift':>6s} {'changed':>8s} {'unplaced':>9s} {'no-evid':>8s}  status")
    print("-" * 88)
    for f, c in sorted(by_file.items()):
        good = c["applies"] + c["minor-drift"]
        bad = c["changed"] + c["unplaced"]
        status = "OK" if bad == 0 else ("PARTIAL" if good else "DEAD")
        print(f"{f:22s} {c['applies']:8d} {c['minor-drift']:6d} {c['changed']:8d} "
              f"{c['unplaced']:9d} {c['no-evidence']:8d}  {status}")

    total = defaultdict(int)
    for r in rows:
        total[r["verdict"]] += 1
    n = len(rows)
    print(f"\ntotal {n}: " + ", ".join(f"{k} {v}" for k, v in sorted(total.items())))
    print(f"sites whose expected bytes still match: "
          f"{(total['applies'] + total['minor-drift']) / n:.0%}")

    if args.csv:
        import csv
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["file", "name", "module", "rva_113d", "rva_113c", "delta",
                        "verdict", "compared", "diff", "method", "confidence"])
            for r in rows:
                w.writerow([r.get("file", ""), r["name"], r["module"],
                            f"0x{r['rva_113d']:X}",
                            f"0x{r['rva_target']:X}" if r["rva_target"] is not None else "",
                            f"{r['rva_target'] - r['rva_113d']:+#x}" if r["rva_target"] is not None else "",
                            r["verdict"], r.get("compared", ""), r.get("diff", ""),
                            r.get("method", ""), r.get("confidence", "")])
        print("wrote", args.csv)


if __name__ == "__main__":
    main()
