"""Where an export's tagged properties start (props.props_start), and the bounded walk of them (props.tags). Synthetic
exports; no game data."""
from pathlib import Path
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import props  # noqa: E402

NAMES = ['StaticMesh', 'ObjectProperty', 'None', 'Other']
NONE = NAMES.index('None')


def tag(name, kind, value):
    """One tagged property: name, type, size, slot, value."""
    return struct.pack('<6i', NAMES.index(name), 0, NAMES.index(kind), 0, len(value), 0) + value


def export(blob, at=16):
    """The blob as an export at `at` in a file, with no state frame."""
    data = bytes(at) + blob + bytes(8)
    return data, dict(off=at, size=len(blob), flags=0)


class PropsStart(unittest.TestCase):
    PROPERTY = tag('StaticMesh', 'ObjectProperty', struct.pack('<i', 7))
    CLOSE = struct.pack('<2i', NONE, 0)

    def start(self, blob):
        data, e = export(blob)
        return props.props_start(data, e, NAMES) - e['off']

    def test_an_actors_properties_follow_its_net_index(self):
        self.assertEqual(self.start(struct.pack('<i', 5) + self.PROPERTY + self.CLOSE), 4)

    def test_a_components_properties_follow_its_second_field(self):
        self.assertEqual(self.start(struct.pack('<2i', 0, -3) + self.PROPERTY + self.CLOSE), 8)

    def test_a_template_components_properties_follow_its_name(self):
        self.assertEqual(self.start(struct.pack('<4i', 0, -3, 3, 0) + self.PROPERTY + self.CLOSE), 16)

    def test_an_export_without_properties_starts_at_its_closing_none(self):
        self.assertEqual(self.start(struct.pack('<i', 5) + self.CLOSE + bytes(12)), 4)
        self.assertEqual(self.start(struct.pack('<2i', 0, -3) + self.CLOSE + bytes(12)), 8)

    def test_a_field_that_equals_nones_place_in_the_name_table_is_not_the_closing_none(self):
        """URB_CommercialStreet_Terror's StaticMeshComponent_115: the field before its properties is 2315, where the
        map's name table has None, and the first property's name follows it where the None's number would be."""
        blob = struct.pack('<2i', 0, NONE) + tag('Other', 'ObjectProperty', struct.pack('<i', 7)) + self.CLOSE
        self.assertEqual(self.start(blob), 8)

    def test_a_kind_whose_name_carries_a_number_is_not_a_tag(self):
        """EWI_ExaltHQAssault_Stream's TriggerVolume_0.BrushComponent_15: 4 bytes before its first tag the bytes read
        as a tag too, the net index as the name and the property's own name's number (0) as the kind, the name table's
        first entry being a kind there. The kind's number, where the real kind's name index lies, gives it away."""
        names = ['IntProperty', 'StaticMesh', 'None', 'Other', 'ObjectProperty']
        blob = (struct.pack('<2i', -3, 3) + struct.pack('<6i', 1, 0, 4, 0, 4, 0) + struct.pack('<i', 7)
                + struct.pack('<2i', 2, 0))
        data, e = export(blob)
        self.assertEqual(props.props_start(data, e, names) - e['off'], 8)


class Tags(unittest.TestCase):
    """props.tags, the one bounded walk of tagged properties (review finding 52), and the readers on it."""
    WALK = NAMES + ['BoolProperty', 'StructProperty', 'Vector', 'bHidden']
    CLOSE = struct.pack('<2i', WALK.index('None'), 0)

    def tag(self, name, kind, value, size=None, sub=None, number=0):
        head = struct.pack('<6i', self.WALK.index(name), number, self.WALK.index(kind), 0,
                           len(value) if size is None else size, 0)
        return head + (struct.pack('<2i', self.WALK.index(sub), 0) if sub else b'') + value

    def blob(self):
        return (self.tag('StaticMesh', 'ObjectProperty', struct.pack('<i', 7), number=3)
                + self.tag('bHidden', 'BoolProperty', b'\x01', size=0)
                + self.tag('Other', 'StructProperty', struct.pack('<3f', 1, 2, 3), sub='Vector') + self.CLOSE)

    def test_each_property_where_its_value_lies_and_the_end_after_the_none(self):
        b = self.blob()
        rows, end = props.read_tags(b, 0, len(b), self.WALK)
        self.assertEqual(rows, [('StaticMesh_2', 'ObjectProperty', None, 0, 24, 4),
                                ('bHidden', 'BoolProperty', None, 0, 52, 1),
                                ('Other', 'StructProperty', 'Vector', 0, 85, 12)])
        self.assertEqual(end, len(b))

    def test_what_would_be_read_through_is_refused(self):
        b = self.blob()
        bad = {'a name the table lacks': struct.pack('<2i', 99, 0) + b[8:],
               'a negative number': struct.pack('<2i', 0, -1) + b[8:],
               'a negative size': b[:16] + struct.pack('<i', -4) + b[20:],
               'a value past the end': b[:16] + struct.pack('<i', 400) + b[20:],
               'no closing None': b[:-8]}
        for what, data in bad.items():
            with self.assertRaises(ValueError, msg=what):
                props.read_tags(data, 0, len(data), self.WALK)
        with self.assertRaises(ValueError):          # bounded by `end`, not by the buffer
            props.read_tags(b, 0, len(b) - 8, self.WALK)

    def test_the_kismet_reader_walks_with_it(self):
        import kismet_links
        b = self.blob()
        p = kismet_links.P(b, self.WALK, [], [])
        found, end = p.props(0, len(b))
        self.assertEqual(found, {'StaticMesh_2': ('ObjectProperty', 24, 4, None), 'bHidden': ('BoolProperty', 52, 1, None),
                                 'Other': ('StructProperty', 85, 12, 'Vector')})
        self.assertEqual(end, len(b))
        damaged = struct.pack('<2i', 99, 0) + b[8:]
        with self.assertRaises(ValueError):          # before, an unknown name read on as '?99'
            p.b = damaged
            p.props(0, len(damaged))


if __name__ == '__main__':
    unittest.main()
