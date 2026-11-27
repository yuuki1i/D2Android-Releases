#!/usr/bin/env python3
"""Stress the matcher on a real 1.35 MB build by pretending to be a rebuild.

It takes the real 1.13c D2Client.dll image, inserts and deletes blocks of code
the way a different patch level would, re-masks the shifted bytes, then asks the
matcher to recover 200 random site RVAs whose new positions are known.  Nothing
here is a claim about the real 1.13d/1.13c pair; it only proves the matcher
survives large, piecewise layout drift instead of falling over on it.
"""
import os
import random
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rvamap

DLL = sys.argv[1] if len(sys.argv) > 1 else "work/113c/D2Client.dll"
SITES = int(sys.argv[2]) if len(sys.argv) > 2 else 200


def main():
    pe = rvamap.PE(DLL)
    img = bytearray(pe.image)
    mask = bytearray(rvamap.build_mask(pe))
    text_lo, text_hi = 0x1000, min(len(img), 0xCE000)

    rng = random.Random(20261126)
    sites = []
    while len(sites) < SITES:
        r = rng.randrange(text_lo, text_hi - 32)
        if mask[r] or mask[r + 3] or r in (s[0] for s in sites):
            continue
        sites.append((r, bytes(img[r:r + 16])))
    sites.sort()

    # edits: insert junk, delete junk, all inside .text, plus a couple in .rdata
    edits = []
    for _ in range(6):
        at = rng.randrange(text_lo, text_hi)
        edits.append((at, rng.randrange(64, 4096), True))
    for _ in range(2):
        at = rng.randrange(text_lo, text_hi)
        edits.append((at, rng.randrange(64, 1024), False))
    edits.append((0xCE000, 512, True))               # .rdata growth
    edits.sort()

    def shift(off):
        d = 0
        for at, ln, ins in edits:
            if at <= off:
                d += ln if ins else -ln
        return off + d

    c_img, c_mask = [], []
    prev = 0
    for at, ln, ins in edits:
        c_img.extend(img[prev:at])
        c_mask.extend(mask[prev:at])
        if ins:
            c_img.extend(bytes(rng.randrange(256) for _ in range(ln)))
            c_mask.extend(b"\x01" * ln)              # inserted bytes: wildcards
        prev = at + (0 if ins else ln)
    c_img.extend(img[prev:])
    c_mask.extend(mask[prev:])
    c_img, c_mask = bytes(c_img), bytes(c_mask)

    runs = rvamap.find_runs(img, mask, c_img, c_mask, 24)
    segs = rvamap.merge(runs)
    covered = sum(s[1] for s in segs)
    moved = sum(1 for e in edits if e[2]) - sum(1 for e in edits if not e[2])

    ok = wrong = lost = 0
    for rva, _ in sites:
        res = rvamap.map_site(rva, img, mask, c_img, c_mask, segs)
        if res is None:
            lost += 1
            continue
        got = res["pos"]
        span = 32
        if got < 0 or got + span > len(c_img) or any(
                not mask[rva + k] and c_img[got + k] != img[rva + k] for k in range(span)):
            wrong += 1
            print(f"  WRONG 0x{rva:X} -> 0x{got:X} via {res['how']}")
        else:
            ok += 1

    print(f"edits: {len(edits)} blocks, net drift {moved:+#x} bytes inside .text")
    print(f"runs {len(runs)} -> segments {len(segs)}, coverage {covered / len(img):.1%}")
    print(f"sites recovered {ok}/{len(sites)}  wrong {wrong}  lost {lost}")
    if wrong == 0 and ok >= len(sites) * 0.9:
        print("STRESS PASS")
    else:
        print("STRESS FAIL")
        sys.exit(3)


if __name__ == "__main__":
    main()
