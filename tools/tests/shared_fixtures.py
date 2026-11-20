"""The records and helpers more than one suite's tests share (review finding 58): their one home, which each suite's
fixtures module names and takes what its tests need from (tools/viewer/tests/viewer_fixtures.py,
tools/bake/tests/fixtures.py, tools/editor/tests/editor_fixtures.py), so that no suite reads another's folder or
imports another's tests. It imports none of the tools.

The DefaultMaps records' file stays beside tools/patch/tests/test_ship_record.ps1, the patch tool's test it was copied
for, which reads it there too (and the change ledger links it there); this module is the one place the Python tests
name it."""
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
RECORDS = HERE.parent / 'patch' / 'tests' / 'defaultmaps-records.txt'


def record(name):
    """The game's DefaultMaps.ini record of the map `name` (bar, templeship...), from
    tools/patch/tests/defaultmaps-records.txt."""
    for line in RECORDS.read_bytes().split(b'\n'):
        if line.startswith(name.encode() + b'\t'):
            return line.split(b'\t', 1)[1]
    raise KeyError(name)


def minimal_mesh(colours=None, stated=None):
    """colours: the colour stream's BGRA bytes (None: no stream); stated: the count its header gives, when not the
    array's own."""
    pack = lambda fmt,*v: struct.pack('<'+fmt,*v)
    array = lambda stride,count,raw: pack('2i',stride,count)+raw
    stream = pack('2I',0,0) if colours is None else (
        pack('2I',4,len(colours)//4 if stated is None else stated)+array(4,len(colours)//4,colours))
    # Original clockwise triangle, normal +Z. Y/Z reflection gives glTF CCW +Y.
    positions = pack('9f',0,0,0,0,1,0,1,0,0)
    vertices = b''.join(bytes([255,128,128,255,128,128,255,255])+pack('2e',0,0) for _ in range(3))
    return (pack('7fi',0,0,0,1,1,0,2,0)+bytes(24)+array(6,0,b'')+array(8,0,b'')+
            pack('5i',18,0,0,0,1)+pack('4i',0,0,0,0)+pack('i',1)+
            pack('4i4Ii',0,1,1,1,0,1,0,2,0)+pack('3iB',1,0,1,0)+
            pack('2I',12,3)+array(12,3,positions)+pack('4I',1,12,3,0)+array(12,3,vertices)+
            stream+pack('I',3)+array(2,3,pack('3H',0,1,2)))
