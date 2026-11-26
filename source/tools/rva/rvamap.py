#!/usr/bin/env python3
"""Map D2Client.dll RVAs from one game version to another.

D2Android's mod hard-codes 243 addresses relative to D2Client.dll (1.13d).
1.13c was built from nearly the same source, so most of the DLL is byte
identical once relocations and absolute pointers are masked away. This tool:

  1. parses both PE32 images into RVA space,
  2. masks every byte that legitimately differs between builds
     (E8/E9/0F8x rel32 operands, absolute image pointers),
  3. finds long identical runs and turns them into a piecewise offset map
     (c_off - d_off per segment),
  4. maps each RVA from the manifest through that map.

Anything the run alignment cannot place is reported instead of guessed.

Usage:
    python3 rvamap.py --d 113d/D2Client.dll --c 113c/D2Client.dll \
        --manifest offsets/rva-113d.json --json offsets/rva-113c.json \
        --header mod/d2off_113c.h
"""
import argparse
import hashlib
import json
import struct
import sys

MASK = 1
MIN_RUN = 96          # bytes of identical masked code needed to trust a segment
HASH_STRIDE = 8
WINDOW = 64


# ---------------------------------------------------------------- PE32 loader
class PE:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            data = fh.read()
        if data[:2] != b"MZ":
            raise SystemExit(f"{path}: not an MZ file")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            raise SystemExit(f"{path}: not a PE file")
        machine, nsec, _ts, _sym, _nsym, optsize, _chars = struct.unpack_from("<HHIIIHH", data, pe + 4)
        if machine != 0x14C:
            raise SystemExit(f"{path}: machine 0x{machine:X}, expected i386 (0x14C)")
        opt = pe + 24
        magic = struct.unpack_from("<H", data, opt)[0]
        if magic != 0x10B:
            raise SystemExit(f"{path}: optional header magic 0x{magic:X}, expected PE32")
        self.image_base = struct.unpack_from("<I", data, opt + 28)[0]
        self.size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
        ndirs = struct.unpack_from("<I", data, opt + 92)[0]
        self.data_dirs = [struct.unpack_from("<II", data, opt + 96 + i * 8)
                          for i in range(min(ndirs, 16))]

        self.sections = []
        sec = opt + optsize
        for i in range(nsec):
            name, vsize, vaddr, rawsize, rawptr = struct.unpack_from("<8sIIII", data, sec + i * 40)
            self.sections.append((name.rstrip(b"\0").decode("latin-1"), vaddr, vsize, rawptr, rawsize))
        self.sections.sort(key=lambda s: s[1])

        self.image = bytearray(self.size_of_image)
        self.mapped = bytearray(self.size_of_image)   # 1 = backed by file bytes
        for _n, vaddr, vsize, rawptr, rawsize in self.sections:
            if rawptr == 0 or rawsize == 0:
                continue
            copy = min(vsize or rawsize, rawsize, self.size_of_image - vaddr)
            if copy <= 0:
                continue
            self.image[vaddr:vaddr + copy] = data[rawptr:rawptr + copy]
            self.mapped[vaddr:vaddr + copy] = b"\x01" * copy

    def data_dir(self, index):
        return self.data_dirs[index][0] if index < len(self.data_dirs) else 0

    def section_of(self, rva):
        for name, vaddr, vsize, _r, _rs in self.sections:
            if vaddr <= rva < vaddr + max(vsize, 1):
                return name
        return None

    def __repr__(self):
        return f"<PE {self.path} base=0x{self.image_base:X} size=0x{self.size_of_image:X}>"


def build_mask(pe):
    """Mark bytes that may differ between builds: relative operands + image pointers."""
    img = pe.image
    n = len(img)
    mask = bytearray(n)

    def mark(i, ln):
        if 0 <= i < n:
            mask[i:min(n, i + ln)] = b"\x01" * min(ln, n - i)

    # bytes that are not backed by the file (.bss, gaps) are never comparable
    for i in range(n):
        if not pe.mapped[i]:
            mask[i] = 1

    lo, hi = pe.image_base, pe.image_base + pe.size_of_image
    # relative operands of call/jmp/jcc
    for i in range(n - 5):
        if img[i] in (0xE8, 0xE9):
            mark(i + 1, 4)
        elif img[i] == 0x0F and 0x80 <= img[i + 1] <= 0x8F:
            mark(i + 2, 4)
    # absolute pointers into the image (data section, vtables, strings)
    for i in range(0, n - 3):
        v = struct.unpack_from("<I", img, i)[0]
        if lo <= v < hi:
            mark(i, 4)
    return mask


# ---------------------------------------------------------------- run matching
def find_runs(d_img, d_mask, c_img, c_mask, min_run=MIN_RUN):
    """Anchor two builds by voting on byte-delta, then verify each segment.

    Masked bytes (rel32 operands, image pointers, unmapped regions) are set to
    zero on both sides so they act as wildcards.  A real recompilation shows up
    as one delta carried by thousands of identical 16-byte windows; identical
    windows that appear at many unrelated places vote for nonsense deltas and
    are outvoted.
    """
    import numpy as np

    W, S = 16, 4          # window / stride in bytes
    d = np.frombuffer(bytes(d_img), dtype=np.uint8).copy()
    c = np.frombuffer(bytes(c_img), dtype=np.uint8).copy()
    for arr, mask in ((d, d_mask), (c, c_mask)):
        arr[np.frombuffer(bytes(mask), dtype=np.uint8) != 0] = 0

    def index(arr):
        out = {}
        n = len(arr)
        for o in range(0, n - W, S):
            win = arr[o:o + W].tobytes()
            if len(set(win)) <= 2:       # padding / zero fill: matches everywhere
                continue
            key = hashlib.blake2b(win, digest_size=8).digest()
            lst = out.get(key)
            if lst is None:
                out[key] = [o]
            elif len(lst) < 3:           # a window repeated everywhere is noise
                lst.append(o)
        return out

    d_index = index(d)
    votes, seeds = {}, []
    for oc in range(0, len(c) - W, S):
        key = hashlib.blake2b(c[oc:oc + W].tobytes(), digest_size=8).digest()
        for od in d_index.get(key, ()):
            if c[oc:oc + W].tobytes() != d[od:od + W].tobytes():
                continue
            delta = oc - od
            votes[delta] = votes.get(delta, 0) + 1
            seeds.append((od, oc, delta))

    need = max(6, min_run // S)
    good = {k for k, v in votes.items() if v >= need}
    if not good:
        return []

    segs = []
    for delta in sorted(good):
        mine = sorted((od, oc) for od, oc, dl in seeds if dl == delta)
        cur = [mine[0][0], mine[0][1]]
        prev = mine[0]
        for od, oc in mine[1:]:
            if od - prev[0] <= 4 * S:
                prev = (od, oc)
                continue
            segs.append((cur[0], cur[1], prev[0] - cur[0] + W, delta))
            cur, prev = [od, oc], (od, oc)
        segs.append((cur[0], cur[1], prev[0] - cur[0] + W, delta))

    # exact extension on the neutralised streams, then drop overlaps
    def extend(ds, cs, ln):
        right = ln
        step = 4096
        while ds + right < len(d) and cs + right < len(c):
            n = min(step, len(d) - ds - right, len(c) - cs - right)
            eq = (d[ds + right:ds + right + n] == c[cs + right:cs + right + n])
            bad = np.flatnonzero(~eq)
            if bad.size:
                right += int(bad[0])
                break
            right += n
        return right

    out = []
    for ds, cs, ln, _ in segs:
        if ln < min_run:
            continue
        out.append((ds, cs, extend(ds, cs, ln)))
    out.sort(key=lambda r: -r[2])
    chosen = []
    for od, oc, ln in out:
        if any(not (od + ln <= cd or od >= cd + cl) or
               not (oc + ln <= cc or oc >= cc + cl)
               for cd, cc, cl in chosen):
            continue
        chosen.append((od, oc, ln))
    chosen.sort()
    return chosen


def merge(chosen, limit=64):
    segs = []
    for d_off, c_off, ln in chosen:
        delta = c_off - d_off
        if segs and segs[-1][2] == delta and segs[-1][0] + segs[-1][1] >= d_off - limit:
            d0, l0, dl = segs[-1]
            end = max(d0 + l0, d_off + ln)
            segs[-1] = (d0, end - d0, dl)
        else:
            segs.append([d_off, ln, delta])
    return [tuple(s) for s in segs]


# ---------------------------------------------------------------- imports / calls
def rva_to_off(pe, rva):
    for name, va, vs, raw, rs in pe.sections:
        if va <= rva < va + max(vs, rs):
            return raw + (rva - va)
    return None


def parse_imports(pe):
    """(IAT slot RVA, dll name, func name or #ordinal) for every import."""
    out = []
    imp_rva = pe.data_dir(1)
    if not imp_rva:
        return out
    off = rva_to_off(pe, imp_rva)
    if off is None:
        return out
    img, size = pe.image, pe.size_of_image
    while True:
        desc = img[off:off + 20]
        if len(desc) < 20 or desc == b"\x00" * 20:
            break
        oft, _, _, name_rva, ft = (int.from_bytes(desc[i:i + 4], "little") for i in (0, 4, 8, 12, 16))
        if not name_rva:
            break
        noff = rva_to_off(pe, name_rva)
        dll = img[noff:noff + 64].split(b"\x00")[0].decode("ascii", "ignore") if noff else "?"
        thunk_off = rva_to_off(pe, oft or ft)
        iat_off = rva_to_off(pe, ft)
        if thunk_off is None or iat_off is None:
            off += 20
            continue
        k = 0
        while True:
            t = int.from_bytes(img[thunk_off + k * 4:thunk_off + k * 4 + 4], "little")
            if t == 0:
                break
            if t & 0x80000000:
                func = "#%d" % (t & 0xFFFF)
            else:
                hnoff = rva_to_off(pe, t + 2)
                func = img[hnoff:hnoff + 64].split(b"\x00")[0].decode("ascii", "ignore") if hnoff else "?"
            out.append((ft + k * 4, dll, func))
            k += 1
        off += 20
    return out


def iat_lookup(rva, d_imports, c_imports):
    """Same DLL + same function name => same import, new slot address."""
    for slot, dll, func in d_imports:
        if slot <= rva < slot + 4:
            for slot_c, dll_c, func_c in c_imports:
                if dll.lower() == dll_c.lower() and func == func_c:
                    return slot_c, f"{dll}!{func}"
    return None, None


def build_call_index(d_img, d_base, lo, hi):
    """target VA -> positions of every call/jmp that reaches it."""
    idx = {}
    for i in range(lo, min(hi, len(d_img) - 5)):
        b = d_img[i]
        if b == 0xE8 or b == 0xE9:
            rel = struct.unpack_from("<i", d_img, i + 1)[0]
            target = d_base + i + 5 + rel
            idx.setdefault(target, []).append(i)
    return idx


def recover_by_call(rva, d_img, c_img, segs, d_base, c_base, c_size, call_index):
    """A code address has no bytes of its own; the calls that reach it do."""
    from collections import Counter

    votes = Counter()
    for at in call_index.get(d_base + rva, ()):
        hit = seg_lookup(segs, at)
        pos = (at + hit[0]) if hit else interp_position(segs, at)
        if pos is None or pos < 0 or pos + 5 > len(c_img):
            continue
        if c_img[pos] != d_img[at]:           # still the same call/jmp opcode?
            continue
        rel = struct.unpack_from("<i", c_img, pos + 1)[0]
        target = c_base + pos + 5 + rel
        if c_base <= target < c_base + c_size:
            votes[target - c_base] += 1
    if votes:
        best, n = votes.most_common(1)[0]
        return best, n
    return None, 0


# ---------------------------------------------------------------- site verify
def seg_lookup(segs, rva):
    for d0, ln, delta in segs:
        if d0 <= rva < d0 + ln:
            return delta, rva - d0, ln
    return None


def interp_position(segs, rva):
    prev = nxt = None
    for d0, ln, delta in segs:
        if d0 + ln <= rva:
            if prev is None or d0 + ln >= prev[0]:
                prev = (d0 + ln, d0 + ln + delta)
        elif d0 > rva and nxt is None:
            nxt = (d0, d0 + delta)
    if prev and nxt:
        lo_d, lo_t = prev
        hi_d, hi_t = nxt
        span = hi_d - lo_d
        if span <= 0 or abs(hi_t - lo_t) > 0x40000:
            return lo_t + (rva - lo_d)
        return lo_t + round((hi_t - lo_t) * (rva - lo_d) / span)
    if prev:
        return prev[1] + (rva - prev[0])
    if nxt:
        return nxt[1] - (nxt[0] - rva)
    return None


def sig_agrees(c_img, sig, sig_mask, pos):
    if pos is None or pos < 0 or pos + len(sig) > len(c_img):
        return False
    return all(sig_mask[k] or c_img[pos + k] == sig[k] for k in range(len(sig)))
SIG_LEN = 64


def recover_by_reference(rva, d_img, c_img, segs, d_base, c_base, c_size, d_text):
    """Find the new address of static data by following the code that uses it.

    A .bss global or an .rdata string is zero or unique-looking on both sides,
    so its bytes cannot anchor it.  But the instructions that reference it are
    ordinary code, and those *are* anchored.  Read the operand out of the
    moved instruction and the data address falls out.
    """
    from collections import Counter

    needle = (d_base + rva).to_bytes(4, "little")
    votes = Counter()
    at = d_img.find(needle, 0, d_text)
    while at >= 0:
        hit = seg_lookup(segs, at)
        pos = (at + hit[0]) if hit else interp_position(segs, at)
        if pos is not None and 0 <= pos <= len(c_img) - 4 and at >= 1 and pos >= 1:
            # the byte right in front of the operand is the opcode (A3/B8/3D...);
            # it must still be that instruction, otherwise this is just four bytes
            # that happen to look like an address.
            if d_img[at - 1] != c_img[pos - 1]:
                at = d_img.find(needle, at + 1)
                continue
            val = int.from_bytes(c_img[pos:pos + 4], "little")
            if c_base <= val < c_base + c_size:
                votes[val - c_base] += 1
        at = d_img.find(needle, at + 1)
    if not votes:
        return None, 0
    best, n = votes.most_common(1)[0]
    return best, n


def map_site(rva, d_img, d_mask, c_img, c_mask, segs, d_base=None, c_base=None,
             c_size=None, d_text=None, is_code=True, call_index=None,
             d_imports=None, c_imports=None):
    """Resolve one patch site: segment geometry first, unique fingerprint as proof."""
    hit = seg_lookup(segs, rva)
    guess = (rva + hit[0]) if hit else interp_position(segs, rva)
    sig, sig_mask = masked_sig(d_img, d_mask, rva)
    evidence = len(sig) - sig_mask.count(1)

    pos, how = None, None
    if sig_agrees(c_img, sig, sig_mask, guess):
        pos, how = guess, ("segment" if hit else "interpolated")
    else:
        pos, how = find_sig(c_img, c_mask, sig, sig_mask, near=guess) or (None, None)
        if pos is None and guess is not None:
            pos, how = find_sig(c_img, c_mask, sig, sig_mask) or (None, None)
    if pos is None and evidence < 6 and guess is not None:
        # nothing comparable at this site (pure data, an IAT slot, a zero table):
        # the only thing left is the geometry, and the runtime byte check will
        # reject it if the guess is wrong.
        return {"pos": guess, "how": "geometry", "evidence": evidence,
                "inside": hit[1] if hit else 0, "seg_len": hit[2] if hit else 0,
                "geometry_only": True}
    # Static data (.data/.rdata/.bss) often aligns by geometry while still being
    # wrong, and the mod writes through those addresses.  Follow the referring
    # instruction instead whenever the bytes themselves prove nothing.
    if (not is_code or evidence < 6) and None not in (d_base, c_base, c_size, d_text):
        alt, votes = recover_by_reference(rva, d_img, c_img, segs, d_base, c_base,
                                          c_size, d_text)
        if alt is not None and votes >= (1 if (not is_code and evidence < 6) else 2):
            return {"pos": alt, "how": "reference", "evidence": votes,
                    "inside": 0, "seg_len": 0, "votes": votes,
                    "conflict": pos if (pos is not None and pos != alt) else None}

    if pos is None and None not in (d_base, c_base, c_size, d_text):
        alt, votes = recover_by_reference(rva, d_img, c_img, segs, d_base, c_base,
                                          c_size, d_text)
        if alt is not None:
            return {"pos": alt, "how": "reference", "evidence": votes,
                    "inside": 0, "seg_len": 0, "votes": votes}
    if pos is None and d_imports is not None and c_imports is not None:
        slot, who = iat_lookup(rva, d_imports, c_imports)
        if slot is not None:
            return {"pos": slot, "how": "import", "evidence": 99, "inside": 0,
                    "seg_len": 0, "who": who}

    if pos is None and call_index is not None:
        alt, votes = recover_by_call(rva, d_img, c_img, segs, d_base, c_base,
                                     c_size, call_index)
        if alt is not None and votes >= 1:
            return {"pos": alt, "how": "call", "evidence": votes, "inside": 0,
                    "seg_len": 0, "votes": votes}

    if pos is None:
        return None
    return {"pos": pos, "how": how, "evidence": evidence,
            "inside": hit[1] if hit else 0, "seg_len": hit[2] if hit else 0}


def masked_sig(img, mask, rva, length=SIG_LEN):
    """Bytes around a patch site plus the mask, grown until there is real evidence."""
    n = len(img)
    while True:
        end = min(n, rva + length)
        sig = bytes(img[rva:end])
        m = bytes(mask[rva:end])
        unmasked = len(sig) - m.count(1)
        if unmasked >= 20 or end >= n or length >= 512:
            return sig, m
        length *= 2


def find_sig(c_img, c_mask, sig, sig_mask, near=None, slack=0x8000):
    """Find positions in the target where every unmasked byte agrees.

    Returns (pos, how) for a unique answer, None when ambiguous.
    """
    best_anchor = (0, 0, 0)
    i, n = 0, len(sig)
    while i < n:
        if sig_mask[i]:
            i += 1
            continue
        j = i
        while j < n and not sig_mask[j]:
            j += 1
        if j - i > best_anchor[0]:
            best_anchor = (j - i, i, j)
        i = j
    ln, a, b = best_anchor
    if ln < 6:
        return None
    anchor = sig[a:b]

    cands, at = [], c_img.find(anchor)
    while at >= 0 and len(cands) < 256:
        pos = at - a
        if pos >= 0:
            cands.append(pos)
        at = c_img.find(anchor, at + 1)
    if not cands:
        return None

    def agrees(pos):
        if pos < 0 or pos + len(sig) > len(c_img):
            return False
        for k in range(len(sig)):
            if not sig_mask[k] and c_img[pos + k] != sig[k]:
                return False
        return True

    good = [p for p in cands if agrees(p)]
    if near is not None and len(good) > 1:
        near_good = [p for p in good if abs(p - near) <= slack]
        if len(near_good) == 1:
            return near_good[0], "near-guess"
        if near_good:
            good = near_good
    if len(good) == 1:
        return good[0], "unique"
    return None


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--d", required=True, help="D2Client.dll of the version the mod targets (1.13d)")
    ap.add_argument("--c", required=True, help="D2Client.dll of the version to map to (1.13c)")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--module", help="only map the defines belonging to this DLL, e.g. D2Client.dll")
    ap.add_argument("--json")
    ap.add_argument("--header")
    ap.add_argument("--append", action="store_true", help="append to --header instead of truncating")
    ap.add_argument("--min-run", type=int, default=MIN_RUN)
    args = ap.parse_args()

    d, c = PE(args.d), PE(args.c)
    print(d)
    print(c)
    d_mask, c_mask = build_mask(d), build_mask(c)
    runs = find_runs(d.image, d_mask, c.image, c_mask, args.min_run)
    segs = merge(runs)
    print(f"anchored runs: {len(runs)} -> merged segments: {len(segs)}")
    if segs:
        covered = sum(s[1] for s in segs)
        print(f"covered: {covered / len(d.image):.1%} of the image")

    with open(args.manifest, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    defines = manifest["defines"]
    if args.module:
        defines = [d for d in defines
               if "/" not in str(d.get("module", ""))
               and (args.module in str(d.get("module", "")).split("/") or not args.module)]
        print(f"module filter {args.module}: {len(defines)} defines")
    elif any("/" in d.get("module", "") or d.get("module") not in (None, "D2Client.dll")
             for d in defines):
        print("WARNING: manifest covers several DLLs and no --module was given; "
              "mapping them all against one PE is meaningless")

    d_img, c_img = d.image, c.image
    d_imports, c_imports = parse_imports(d), parse_imports(c)
    call_idx = build_call_index(
        d_img, d.image_base,
        next((sec[1] for sec in d.sections if sec[0] == ".text"), 0),
        next((sec[1] + sec[2] for sec in d.sections if sec[0] == ".text"), len(d_img)))
    mapped, missing = [], []
    for item in defines:
        rva = item["value"]
        text_sec = next((sec for sec in d.sections if sec[0] == ".text"), None)
        d_text = (text_sec[1] + text_sec[2]) if text_sec else len(d_img)
        text_lo = text_sec[1] if text_sec else 0
        res = map_site(rva, d_img, d_mask, c_img, c_mask, segs,
                       d.image_base, c.image_base, c.size_of_image, d_text,
                       is_code=(text_lo <= rva < d_text), call_index=call_idx,
                       d_imports=d_imports, c_imports=c_imports)
        if res is None:
            missing.append({**item, "reason": "no segment, no unique fingerprint match"})
            continue
        pos, how, evidence = res["pos"], res["how"], res["evidence"]
        if how == "segment" and evidence >= 8:
            conf = "high"
        elif how == "import":
            conf = "high"
        elif how == "call" and evidence >= 2:
            conf = "high"
        elif how == "call":
            conf = "medium"
        elif how == "reference" and evidence >= 2:
            conf = "high"
        elif how in ("unique", "near-guess") and evidence >= 12:
            conf = "high"
        elif evidence >= 6:
            conf = "medium"
        else:
            conf = "low"
        mapped.append({
            "name": item["name"], "rva_113d": rva, "rva_target": pos,
            "file": item.get("file", "?"), "line": item.get("line", 0),
            "delta": pos - rva, "method": how, "evidence_bytes": evidence,
            "offset_in_segment": res["inside"], "segment_len": res["seg_len"],
            "confidence": conf,
            "geometry_only": res.get("geometry_only", False),
            "votes": res.get("votes", 0),
            "conflict": res.get("conflict"),
            "who": res.get("who"),
        })

    high = sum(1 for m in mapped if m["confidence"] == "high")
    print(f"mapped: {len(mapped)}/{len(defines)} (high confidence {high}, "
          f"low {len(mapped) - high}), unmapped {len(missing)}")
    if missing:
        print("unmapped:", ", ".join(m["name"] for m in missing[:20]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"source": args.d, "target": args.c, "module": args.module,
                       "segments": [{"d": s[0], "len": s[1], "delta": s[2]} for s in segs],
                       "mapped": mapped, "unmapped": missing}, fh, indent=2)
        print("wrote", args.json)

    if args.header:
        by_name = {m["name"]: m for m in mapped}
        with open(args.header, "a" if args.append else "w", encoding="utf-8") as fh:
            if not args.append:
                fh.write("/* generated by tools/rvamap.py from real game binaries - do not edit */\n")
                fh.write(f"/* target RTM: {args.c} */\n")
            fh.write(f"\n/* ===== {args.module or 'all modules'} ===== */\n")
            last = None
            for item in defines:
                m = by_name.get(item["name"])
                if item["file"] != last:
                    fh.write(f"\n/* {item['file']} */\n")
                    last = item["file"]
                if m:
                    note = "" if m["confidence"] == "high" else "  /* low confidence */"
                    fh.write(f"#define {item['name']} 0x{m['rva_target']:X}{note}\n")
                else:
                    # keep the file compilable: fall back to the 1.13d value, which
                    # the upstream byte check will reject at runtime instead of
                    # patching the wrong place.
                    fh.write(f"#define {item['name']} 0x{item['value']:X}"
                             "  /* UNMAPPED: 1.13d value kept, runtime byte check should reject */\n")
        print("wrote", args.header)

    if missing:
        sys.exit(3)


if __name__ == "__main__":
    main()
