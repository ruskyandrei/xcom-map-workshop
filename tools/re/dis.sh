#!/bin/sh
# dis.sh <start> <end> [exe copy] : dumpbin disassembly of a range of the exe copy (read-only)
# The copy: the third argument, else <lab>\re\XComEW-copy.exe (pe.py). dumpbin: $DUMPBIN, else on PATH, else
# Visual Studio 2022 Community's.
exe=${3:-$(python "$(dirname "$0")/pe.py")}
D=${DUMPBIN:-$(command -v dumpbin.exe)}
D=${D:-"$PROGRAMFILES/Microsoft Visual Studio/2022/Community/SDK/ScopeCppSDK/vc15/VC/bin/dumpbin.exe"}
"$D" //disasm:nobytes //range:$1,$2 "$exe" 2>&1 | grep -E "^  [0-9A-F]{8}:"
