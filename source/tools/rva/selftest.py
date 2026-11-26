#!/usr/bin/env python3
"""Self-test for rvamap.py: build two synthetic PE32 images that differ by an
insertion plus patched call targets, and check the recovered offset map."""
import json
import os
import random
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE_BASE = 0x10000000
TEXT_RVA = 0x1000
TEXT_RAW = 0x200


def make_pe(code):
    size_of_image = TEXT_RVA + ((len(code) + 0xFFF) // 0x1000) * 0x1000
    dos = bytearray(0x40)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x40)

    coff = struct.pack("<HHIIIHH", 0x14C, 1, 0, 0, 0, 0xE0, 0x0102)
    opt = bytearray(0xE0)
    struct.pack_into("<H", opt, 0, 0x10B)
    struct.pack_into("<I", opt, 16, TEXT_RVA)          # AddressOfEntryPoint
    struct.pack_into("<I", opt, 28, IMAGE_BASE)        # ImageBase
    struct.pack_into("<I", opt, 32, 0x1000)            # SectionAlignment
    struct.pack_into("<I", opt, 36, 0x200)             # FileAlignment
    struct.pack_into("<I", opt, 56, size_of_image)     # SizeOfImage
    struct.pack_into("<I", opt, 60, 0x200)             # SizeOfHeaders
    struct.pack_into("<H", opt, 68, 3)                 # Subsystem: console
    struct.pack_into("<I", opt, 92, 16)                # NumberOfRvaAndSizes

    sec = struct.pack("<8sIIIIIIHHI", b".text",
                      len(code), TEXT_RVA, len(code), TEXT_RAW,
                      0, 0,               # reloc/line pointers
                      0, 0,               # counts
                      0x60000020)         # code | execute | read

    head = bytes(dos) + b"PE\0\0" + coff + bytes(opt) + sec
    pad = b"\x00" * (TEXT_RAW - len(head))
    return head + pad + bytes(code)


def build_code(n, ptrs):
    rnd = random.Random(1234)
    code = bytearray(rnd.randrange(256) for _ in range(n))
    for i in range(0, n - 8, 61):                     # sprinkle call rel32
        code[i] = 0xE8
        struct.pack_into("<i", code, i + 1, rnd.randrange(-0x1000, 0x1000))
    for off in ptrs:                                  # absolute image pointers
        if off + 4 < n:
            struct.pack_into("<I", code, off, IMAGE_BASE + TEXT_RVA + off)
    return bytes(code)


def main():
    n = 20000
    ptrs = [100, 3000, 7999, 12000]
    a = build_code(n, ptrs)
    insert_at = 8000
    b = a[:insert_at] + bytes(random.Random(7).randrange(256) for _ in range(200)) + a[insert_at:]
    # "new build" patches two call targets (masked, must not break matching)
    bl = bytearray(b)
    for i in (2000, 15000):
        struct.pack_into("<i", bl, i + 1, 0x1234)
    b = bytes(bl)

    tmp = tempfile.mkdtemp()
    p_d, p_c = os.path.join(tmp, "d.dll"), os.path.join(tmp, "c.dll")
    open(p_d, "wb").write(make_pe(a))
    open(p_c, "wb").write(make_pe(b))

    # manifest: RVAs on both sides of the insertion point
    defs = []
    for off in (0x40, 0x1000, 0x2000, 0x2050 - 0x10, 0x2500, 0x4000):
        defs.append({"name": f"SITE_{off:X}", "value": TEXT_RVA + off, "file": "self", "line": 0})
    manifest = {"image": "client", "defines": defs}
    mpath = os.path.join(tmp, "m.json")
    json.dump(manifest, open(mpath, "w"))

    out = os.path.join(tmp, "out.json")
    rc = subprocess.call([sys.executable, os.path.join(HERE, "rvamap.py"),
                          "--d", p_d, "--c", p_c, "--manifest", mpath, "--json", out])
    result = json.load(open(out))
    for m in result["mapped"]:
        print(f"{m['name']:>12} 0x{m['rva_113d']:X} -> 0x{m['rva_target']:X} "
              f"delta {m['delta']:+6d} {m['confidence']}")
    exp_before = TEXT_RVA
    ok = True
    for m in result["mapped"]:
        want = m["rva_113d"] if m["rva_113d"] < TEXT_RVA + insert_at else m["rva_113d"] + 200
        if m["rva_target"] != want:
            ok = False
            print(f"FAIL {m['name']}: got 0x{m['rva_target']:X}, want 0x{want:X}")
    print("SELFTEST", "PASS" if ok and not result["unmapped"] else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
