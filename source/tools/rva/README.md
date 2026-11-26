# Version tables for the mod

The mod patches the game by `module base + RVA`. Upstream only carries the 1.13d table; `mod/d2off.h`
selects between `d2off_113d.h` and `d2off_113c.h` at compile time (`-DD2VER_113C`).

Everything in `offsets/` is generated from real binaries, never hand-edited. To change a value, change
the mapper and regenerate.

## Pipeline

```bash
# 1. collect every hard-coded RVA from mod/*.c (source of truth after the split)
python3 tools/rva/extract_rva.py mod --json tools/rva/offsets/rva-113d.json \
        --csv tools/rva/offsets/rva-113d.csv --header tools/rva/offsets/rva-113d.h

# 2. map 1.13d RVAs onto the 1.13c binaries, one module at a time
python3 tools/rva/map_all.py --d-dir <113d folder> --c-dir <113c folder> \
        --manifest tools/rva/offsets/rva-113d.json --header mod/d2off_113c.h \
        --json-prefix tools/rva/offsets/map-113c

# 3. verify what the mapped sites actually contain on both sides
python3 tools/rva/audit_compat.py --d-dir <113d folder> --c-dir <113c folder> \
        --map-prefix tools/rva/offsets/map-113c
```

`map_all.py` needs the 1.13d binaries as the reference. Both folders must be full installs (7 DLLs plus
`Game.exe`); a folder with a single `D2Client.dll` is not enough.

## What the mapper does

1. **Segment alignment** — match `.text` of each module by masked fingerprints, then map addresses by
   the offset of their containing segment.
2. **Site verification** — every mapped RVA is re-checked with a per-site byte mask; a mismatch is
   reported, not silently accepted.
3. **Reference recovery** — for data addresses that the segment pass cannot place, find instructions in
   1.13d that embed the address, map those instructions, and read the new operand. Seven independent
   references agreeing is treated as proof.
4. **Import-table matching** — RVAs that are `jmp [IAT]` thunks are resolved through the import tables of
   both modules by DLL and function name.
5. **`rel32` call recovery** — for code addresses, find callers, map them, and re-read the relative
   displacement. The opcode before the displacement must still match, otherwise the candidate is dropped.
6. **Geometry fallback** is reported separately and never counted as verified.

## Current state (1.13c)

| | count |
|---|---|
| offsets in the table | 243 |
| located | 226 (93%) |
| byte-identical, patch applies as-is | 143 |
| minor drift (likely the same site) | 8 |
| changed (the mod's own check rejects them) | 12 |
| in the zero-fill area, unverifiable statically | 63 |
| unlocated | 11 |
| no 1.13d reference (PlugY ×5, one cross-module) | 6 |

Of the 163 sites with byte evidence, 151 match (93%).

Known gaps:

- `d2biginv` — the stash write instruction changed shape in 1.13c (`imm 0x20` became something else).
  The data pointers are right (`0x9FA5C` / `0x9FA58`), the hook is not, so big stash stays off.
- 11 unlocated sites keep their 1.13d value with an `UNMAPPED` comment; the mod's site check refuses
  them at runtime, so nothing is written to a wrong address.
- PlugY offsets assume PlugY 14.0.3.0 on both sides and were not verified against a 1.13d build.

`offsets/compat-113c.csv` carries the per-site verdict, the evidence byte count and which method placed
it. Read that file before believing any single number above.

## Notes on the 1.13d side

The 1.13d table was extracted from the mod source and split into `mod/d2off_113d.h` by
`tools/rva/make_version_split.py`. The split was verified by rebuilding before and after: `.text`,
`.rdata`, `.data`, `.reloc` and `.tls` are byte-identical, so the refactor carries no semantic change.
