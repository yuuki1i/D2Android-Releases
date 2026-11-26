/* selects the D2Client offset table for the build: -DD2VER_113C for 1.13c, default 1.13d */
#ifndef D2OFF_H
#define D2OFF_H

#if defined(D2VER_113C)
#  if __has_include("d2off_113c.h")
#    include "d2off_113c.h"
#  else
#    error "D2VER_113C is set but d2off_113c.h is missing: run tools/rvamap.py first"
#  endif
#else
#  include "d2off_113d.h"
#endif

#endif
