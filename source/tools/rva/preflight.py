#!/usr/bin/env python3
"""Preflight one side of the pair before spending time on a full mapping.

For every module in the manifest it answers: is the file here, does it parse as
PE32, and do the 1.13d RVAs land in believable sections of this build.  A module
whose sites all fall into .reloc or .rsrc is either shifted far enough that the
attribution must be re-checked, or attributed to the wrong DLL.

    python3 tools/preflight.py --manifest offsets/rva-113d.json --c-dir work/113c_full
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rvamap import PE  # noqa: E402

SUSPECT = {".reloc", ".rsrc"}


def locate(directory, name):
    if not directory or not os.path.isdir(directory):
        return None
    for f in os.listdir(directory):
        if f.lower() == name.lower():
            return os.path.join(directory, f)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--c-dir", help="the build being mapped to (1.13c)")
    ap.add_argument("--d-dir", help="the build the offsets came from (1.13d)")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    groups = {}
    for d in manifest["defines"]:
        mod = str(d.get("module", "D2Client.dll"))
        groups.setdefault(mod, []).append(d)

    print(f"{'module':22s} {'n':>3s}  {'1.13d':5s} {'1.13c':5s}  sections of this build")
    print("-" * 96)
    problems = 0
    for mod, items in sorted(groups.items()):
        tag = " (cross-module)" if "/" in mod else ""
        d_path = locate(args.d_dir, mod) if "/" not in mod else None
        c_path = locate(args.c_dir, mod) if "/" not in mod else None
        have = f"{'yes' if d_path else '-':5s} {'yes' if c_path else '-':5s}"
        if not c_path:
            print(f"{mod:22s} {len(items):3d}  {have}  file missing{tag}")
            problems += 1
            continue
        try:
            pe = PE(c_path)
        except Exception as e:
            print(f"{mod:22s} {len(items):3d}  {have}  PE parse failed: {e}")
            problems += 1
            continue
        where = Counter()
        for it in items:
            r = it["value"]
            sec = next((s[0] for s in pe.sections if s[1] <= r < s[1] + s[2]), "<outside>")
            where[sec] += 1
        dist = ", ".join(f"{k}x{v}" for k, v in where.most_common())
        bad = sum(v for k, v in where.items() if k in SUSPECT or k == "<outside>")
        flag = ""
        if bad > len(items) * 0.4:
            flag = "  <-- attribution/layout suspect"
            problems += 1
        print(f"{mod:22s} {len(items):3d}  {have}  {dist}{flag}{tag}")
        md5 = hashlib.md5(open(c_path, "rb").read()).hexdigest()
        print(f"{'':22s}      base 0x{pe.image_base:08X}  image 0x{pe.size_of_image:X}  md5 {md5}")

    print(f"\nproblems: {problems}")
    sys.exit(3 if problems else 0)


if __name__ == "__main__":
    main()
