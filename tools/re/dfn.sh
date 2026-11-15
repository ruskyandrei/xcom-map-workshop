#!/bin/sh
# dfn.sh <va> [exe copy] : disassemble function at va up to its first ret+padding
d=$(dirname "$0")
exe=${2:-$(python "$d/pe.py")}
r=$(python "$d/fn.py" $1 --exe "$exe")
set -- $r
sh "$d/dis.sh" $1 $2 "$exe"
