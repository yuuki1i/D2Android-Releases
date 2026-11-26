#!/usr/bin/env python3
"""Dry-run audit: locate the upstream byte-checked patch sites in another build.

The mod validates almost every patch site by comparing literal bytes before it
touches memory.  Those literals are 1.13d's bytes, so they can be searched for
directly in any other build - no reference DLL needed.  What comes out is a
cheap upper bound on "how many of this mod's patch sites even exist in that
build", which is the first question to ask before promising compatibility.

    python3 tools/probe_sites.py --source <upstream>/source/mod \\
        --manifest offsets/rva-113d.json --dir work/113c_full
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rvamap import PE, find_sig  # noqa: E402

MODULE_OF = {
    "client": "D2Client.dll", "clientBase": "D2Client.dll", "biClient": "D2Client.dll",
    "game": "D2Game.dll", "gameBase": "D2Game.dll", "srvGame": "D2Game.dll",
    "L": "D2Launch.dll", "launch": "D2Launch.dll", "directLaunch": "D2Launch.dll",
    "common": "D2Common.dll", "biCommon": "D2Common.dll",
    "win": "D2Win.dll", "storm": "Storm.dll", "plugy": "PlugY.dll",
}
ARRAY_RE = re.compile(r"static const BYTE (\w+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\}\s*;", re.S)
USE_RE = re.compile(r"bytesAre\(\s*([^,]+?)\s*,\s*(\w+)\s*,\s*([^)]+?)\s*\)")


def parse_arrays(source_dir):
    out = {}
    for f in os.listdir(source_dir):
        if not f.endswith(".c"):
            continue
        text = open(os.path.join(source_dir, f), encoding="utf-8", errors="ignore").read()
        for m in ARRAY_RE.finditer(text):
            body = m.group(2)
            vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,2})\b", body)]
            if vals:
                out.setdefault(m.group(1), []).append(vals)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dir", required=True, help="build to probe (the one you want to support)")
    args = ap.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    rva = {d["name"]: (d["value"], d.get("module", "D2Client.dll")) for d in manifest["defines"]}
    arrays = {k: v[0] for k, v in parse_arrays(args.source).items()}

    pe_cache = {}

    def image(mod):
        if mod not in pe_cache:
            for f in os.listdir(args.dir):
                if f.lower() == mod.lower():
                    p = PE(os.path.join(args.dir, f))
                    pe_cache[mod] = (p.image, p.image_base, p.size_of_image)
                    break
            else:
                pe_cache[mod] = None
        return pe_cache[mod]

    rows = []
    for f in os.listdir(args.source):
        if not f.endswith(".c"):
            continue
        text = open(os.path.join(args.source, f), encoding="utf-8", errors="ignore").read()
        for m in USE_RE.finditer(text):
            expr, name, length = m.group(1), m.group(2), m.group(3)
            if name not in arrays:
                continue
            base_var = next((v for v in MODULE_OF if re.search(r"\b%s\b" % v, expr)), None)
            if not base_var:
                continue
            arr = arrays[name]
            n = len(arr) if "sizeof" in length else int(length)
            arr = arr[:n]

            # site = base + RVA_X (optionally - sizeof(array))
            mm = re.search(r"(RVA_[A-Za-z0-9_]+|0x[0-9A-Fa-f]+)", expr)
            if not mm:
                continue
            tok = mm.group(1)
            site = rva[tok][0] if tok.startswith("RVA_") else int(tok, 16)
            if re.search(r"-\s*sizeof\s*\(", expr):
                site -= len(arr)

            mod = MODULE_OF[base_var]
            img = image(mod)
            if not img:
                rows.append((f, name, mod, site, None, "module missing"))
                continue
            c_img, base, size = img

            # wildcard the 4-byte groups that look like pointers into either build
            mask = [0] * len(arr)
            for i in range(0, len(arr) - 3):
                v = int.from_bytes(bytes(arr[i:i + 4]), "little")
                if 0x6F000000 <= v <= 0x70000000 or 0x10000000 <= v <= 0x10100000:
                    for k in range(4):
                        mask[i + k] = 1
            hit = find_sig(c_img, bytes(mask), bytes(arr), bytes(mask))
            if not hit:
                rows.append((f, name, mod, site, None, "not found uniquely"))
            else:
                pos, how = hit
                rows.append((f, name, mod, site, pos, f"{how}, delta {pos - site:+#x}"))

    print(f"{'file':22s} {'pattern':22s} {'module':13s} {'1.13d site':>10s}  result")
    print("-" * 92)
    ok = 0
    for f, name, mod, site, pos, note in rows:
        print(f"{f:22s} {name:22s} {mod:13s} 0x{site:08X}  {note}")
        if pos is not None:
            ok += 1
    print(f"\nlocatable: {ok}/{len(rows)}  ({ok/len(rows):.0%})")


if __name__ == "__main__":
    main()
