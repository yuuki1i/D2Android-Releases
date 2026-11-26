#!/usr/bin/env python3
"""Recover a patch site by translating the addresses embedded in it.

A site like `mov [InvTable], eax; cmp [InvCount], 32` cannot be matched before its
data addresses are known, and cannot be mapped by segment alignment when the code
around it moved. Once the addresses are mapped, rebuild the 1.13d bytes with the
1.13c absolutes substituted and search for that exact string in the target.
"""
import argparse, glob, json, os, struct
import capstone

def sections(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, e + 6)[0]
    opt = struct.unpack_from('<H', d, e + 20)[0]
    img = struct.unpack_from('<I', d, e + 24 + 28)[0]
    base = e + 24 + opt
    out = {}
    for i in range(n):
        o = base + i * 40
        name = d[o:o + 8].rstrip(b'\0').decode('latin1')
        vsz, va, rawsz, raw = struct.unpack_from('<IIII', d, o + 8)
        out[name] = {'va': img + va, 'vsz': vsz, 'raw': raw, 'rawsz': rawsz, 'data': d}
    return img, out

def find(directory, mod):
    for name in os.listdir(directory):
        if name.lower() == mod.lower():
            return os.path.join(directory, name)
    raise SystemExit('module %s not found in %s' % (mod, directory))

def load_maps(prefix):
    table = {}
    for path in glob.glob(prefix + '-*.json'):
        m = json.load(open(path))
        mod = m['module']
        for e in m['mapped']:
            table[(mod, e['rva_113d'])] = (mod, e['rva_target'])
    return table

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--d-dir', required=True)
    ap.add_argument('--c-dir', required=True)
    ap.add_argument('--map-prefix', required=True)
    ap.add_argument('--site', action='append', required=True,
                    help='module:0xRVA, repeatable')
    ap.add_argument('--span', type=int, default=16)
    a = ap.parse_args()

    table = load_maps(a.map_prefix)
    for spec in a.site:
        mod, rvas = spec.split(':', 1)
        rva = int(rvas, 16)
        dimg, dsecs = sections(find(a.d_dir, mod))
        cimg, csecs = sections(find(a.c_dir, mod))
        dtext, ctext = dsecs['.text'], csecs['.text']
        site = dimg + rva
        off = dtext['raw'] + (site - dtext['va'])
        raw = bytearray(dtext['data'][off:off + a.span])
        subs = 0
        for o in range(0, len(raw) - 3):
            v = struct.unpack_from('<I', raw, o)[0]
            hit = table.get((mod, v - dimg))
            if hit:
                raw[o:o + 4] = struct.pack('<I', cimg + hit[1])
                subs += 1
        hits = []
        blob = ctext['data'][ctext['raw']:ctext['raw'] + ctext['rawsz']]
        needle = bytes(raw)
        i = 0
        while True:
            i = blob.find(needle, i)
            if i < 0:
                break
            hits.append(ctext['va'] + i)
            i += 1
        print('%-16s 0x%06X  %d absolute(s) rewritten -> %s' %
              (mod, rva, subs, ' '.join('0x%06X(RVA)' % (h - cimg) for h in hits) or 'no hit'))

main()
