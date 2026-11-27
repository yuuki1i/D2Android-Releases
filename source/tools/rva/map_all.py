#!/usr/bin/env python3
"""Map every module of a build pair and emit one version header.

The mod patches several DLLs, not just D2Client.dll, and each DLL has its own
address space.  So the mapping has to be run once per module against that
module's own 1.13d/1.13c pair, then the results concatenated into one header.

    python3 tools/map_all.py --d-dir work/dll113d --c-dir work/dll113c \\
        --manifest offsets/rva-113d.json --header mod/d2off_113c.h \\
        --json-prefix work/map113c

Any module whose two binaries are not both present is reported as missing and
left out of the header, so a partial hand-off still produces a usable file.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
RVAMAP = os.path.join(HERE, "rvamap.py")


def locate(directory, name):
    """Windows binaries arrive with whatever case the packer used."""
    if not directory or not os.path.isdir(directory):
        return None
    for f in os.listdir(directory):
        if f.lower() == name.lower():
            return os.path.join(directory, f)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d-dir", required=True, help="dir holding the 1.13d DLLs")
    ap.add_argument("--c-dir", required=True, help="dir holding the 1.13c DLLs")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--header", required=True)
    ap.add_argument("--json-prefix")
    ap.add_argument("--min-run", type=int, default=24)
    args = ap.parse_args()

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    groups = OrderedDict()
    ambiguous = []
    for d in manifest["defines"]:
        mod = d.get("module", "D2Client.dll")
        if "/" in mod:
            ambiguous.append(d["name"])
            continue
        groups.setdefault(mod, []).append(d)

    print(f"modules in manifest: {', '.join(f'{m}({len(v)})' for m, v in groups.items())}")
    if ambiguous:
        print(f"ambiguous, skipped: {', '.join(ambiguous)}")

    summary, failed = [], []
    first = True
    for mod, items in groups.items():
        d_path, c_path = locate(args.d_dir, mod), locate(args.c_dir, mod)
        if not (d_path and c_path):
            summary.append((mod, len(items), None,
                            "missing " + mod + (" (1.13d)" if not d_path else " (1.13c)")))
            continue
        out_json = f"{args.json_prefix}-{mod.replace('.dll','')}.json" if args.json_prefix else None
        cmd = [sys.executable, RVAMAP, "--d", d_path, "--c", c_path,
               "--manifest", args.manifest, "--module", mod,
               "--header", args.header, "--min-run", str(args.min_run)]
        if not first:
            cmd.append("--append")
        if out_json:
            cmd += ["--json", out_json]
        res = subprocess.run(cmd, capture_output=True, text=True)
        first = False
        line = next((l for l in res.stdout.splitlines() if l.startswith("mapped:")), "?")
        cov = next((l for l in res.stdout.splitlines() if l.startswith("covered:")), "?")
        summary.append((mod, len(items), line, cov))
        if res.returncode not in (0, 3):
            failed.append(mod)
            print(res.stdout, res.stderr)

    # modules we could not map at all still have to exist in the header, or the
    # mod will not compile: keep the 1.13d values, flagged.
    leftover = [d for mod in summary if mod[2] is None for d in groups.get(mod[0], [])]
    leftover += [d for d in manifest["defines"] if "/" in str(d.get("module", ""))]
    if leftover:
        with open(args.header, "a", encoding="utf-8") as fh:
            fh.write("\n/* ===== not mapped in this build: 1.13d values, flagged ===== */\n")
            for d in leftover:
                fh.write(f"#define {d['name']} 0x{d['value']:X}"
                         f"  /* UNMAPPED ({d.get('module')}) */\n")
        print(f"leftover defines written: {len(leftover)}")

    print("\n%-16s %6s  %s" % ("module", "defines", "result"))
    for mod, n, line, cov in summary:
        print("%-16s %6d  %s  %s" % (mod, n, line, cov))
    if failed:
        print("\nFAILED:", ", ".join(failed))
    print(f"\nheader: {args.header}")
    sys.exit(3 if any(s[2] is None or "unmapped" in str(s[2]) for s in summary) else 0)


if __name__ == "__main__":
    main()
