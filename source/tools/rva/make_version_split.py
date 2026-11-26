#!/usr/bin/env python3
"""Split the hard-coded 1.13d addresses out of the mod sources.

Takes a pristine copy of the upstream source tree and produces a tree where
every `#define RVA_* 0x...` in mod/*.c is gone, replaced by one include of
`d2off.h`, which selects `d2off_113d.h` or `d2off_113c.h` at build time.

Usage:
    python3 make_version_split.py <upstream source dir> <output dir>
"""
import os
import re
import shutil
import sys

DEFINE_RE = re.compile(r"^#define[ \t]+RVA_[A-Za-z0-9_]+[ \t]+0x[0-9A-Fa-f]+[ \t]*\r?\n$")
INCLUDE_LINE = '#include "d2off.h"\n'


def copy_tree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "out"))


def strip_defines(mod_dir):
    removed = {}
    for name in sorted(os.listdir(mod_dir)):
        if not name.endswith((".c", ".h")):
            continue
        path = os.path.join(mod_dir, name)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        kept = [ln for ln in lines if not DEFINE_RE.match(ln)]
        n = len(lines) - len(kept)
        if n:
            removed[name] = n
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(kept)
    return removed


def add_include(mod_dir):
    path = os.path.join(mod_dir, "d2mod.c")
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if INCLUDE_LINE in text:
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("/* D2Android: version-specific D2Client offsets (see d2off.h) */\n")
        fh.write(INCLUDE_LINE)
        fh.write(text)
    return True


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    copy_tree(src, dst)
    mod = os.path.join(dst, "mod")
    removed = strip_defines(mod)
    print(f"removed {sum(removed.values())} defines from {len(removed)} files")
    print("include added:", add_include(mod))
    return 0


if __name__ == "__main__":
    sys.exit(main())
