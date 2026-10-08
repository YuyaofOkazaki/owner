import json
import struct
import tempfile
import unittest
from pathlib import Path

from modal_sketch.cli import main
from modal_sketch.export import to_record_sequence_notes, to_smf
from modal_sketch.melody import BAR_TICKS, PPQ, Note, generate_line
from modal_sketch.modes import MODES, degree_of, parse_tonic, rank_modes
from modal_sketch.timbres import PRESETS, get_timbre, timbre_from_dict


def _read_vlq(data: bytes, i: int) -> tuple[int, int]:
    value = 0
    while True:
        b = data[i]
        i += 1
        value = (value << 7) | (b & 0x7F)
        if not b & 0x80:
            return value, i


def parse_smf_notes(data: bytes) -> tuple[int, list[tuple[int, int, int]]]:
    """(mpqn, [(pitch, start, duration)]) を返す最小限のパーサ。"""
    assert data[:4] == b"MThd"
    _, fmt, ntrks, ppq = struct.unpack(">IHHH", data[4:14])
    assert (fmt, ntrks, ppq) == (0, 1, PPQ)
    assert data[14:18] == b"MTrk"
    (length,) = struct.unpack(">I", data[18:22])
    track = data[22:22 + length]
    i, tick, mpqn = 0, 0, None
    on: dict[int, int] = {}
    notes = []
    while i < len(track):
        delta, i = _read_vlq(track, i)
        tick += delta
        status = track[i]
        if status == 0xFF:
            kind = track[i + 1]
            ln, j = _read_vlq(track, i + 2)
            if kind == 0x51:
                mpqn = int.from_bytes(track[j:j + 3], "big")
            i = j + ln
        elif status & 0xF0 == 0x90:
            on[track[i + 1]] = tick
            i += 3
        elif status & 0xF0 == 0x80:
            p = track[i + 1]
            notes.append((p, on.pop(p), tick))
            i += 3
        else:
            raise AssertionError(f"unexpected status {status:#x}")
    assert not on
    return mpqn, [(p, s, e - s) for p, s, e in notes]


class ModeTests(unittest.TestCase):
    def test_parse_tonic(self):
        self.assertEqual(parse_tonic("D"), 2)
        self.assertEqual(parse_tonic("bb"), 10)
        self.assertEqual(parse_tonic("F#"), 6)
        with self.assertRaises(ValueError):
            parse_tonic("H")

    def test_bright_timbre_prefers_bright_modes(self):
        top = rank_modes(get_timbre("bell"))[0][0].name
        self.assertIn(top, {"lydian", "ionian"})

    def test_dark_warm_timbre_prefers_dark_modes(self):
        top = [m.name for m, _ in rank_modes(get_timbre("cello"))[:2]]
        self.assertTrue(set(top) <= {"aeolian", "dorian", "phrygian"})

    def test_invalid_timbre_rejected(self):
        with self.assertRaises(ValueError):
            timbre_from_dict({"name": "x", "brightness": 2, "warmth": 0, "attack": 0,
                              "sustain": 0, "breath": 0, "low": 60, "high": 80})


class MelodyTests(unittest.TestCase):
    def test_lines_follow_modal_rules(self):
        tonic = parse_tonic("D")
        for timbre in PRESETS.values():
            for mode in MODES.values():
                for seed in range(5):
                    with self.subTest(timbre=timbre.name, mode=mode.name, seed=seed):
                        bars = 4
                        notes = generate_line(timbre, mode, tonic, bars, seed)
                        # 単旋律: 重なりなし、小節数ちょうどで終わる
                        for a, b in zip(notes, notes[1:]):
                            self.assertLessEqual(a.start + a.duration, b.start)
                        self.assertEqual(notes[-1].start + notes[-1].duration, bars * BAR_TICKS)
                        # 全音がモード内・音域内
                        for n in notes:
                            self.assertIsNotNone(degree_of(n.pitch, tonic, mode))
                            self.assertTrue(timbre.low <= n.pitch <= timbre.high)
                        # 主音で終止し、終止音は2拍以上
                        self.assertEqual(notes[-1].pitch % 12, tonic)
                        self.assertGreaterEqual(notes[-1].duration, PPQ * 2)

    def test_deterministic_by_seed(self):
        t, m = get_timbre("flute"), MODES["dorian"]
        self.assertEqual(generate_line(t, m, 2, 4, 7), generate_line(t, m, 2, 4, 7))


class ExportTests(unittest.TestCase):
    def test_smf_round_trip(self):
        notes = [Note(62, 0, 480, 90), Note(64, 480, 240, 80), Note(62, 960, 960, 70)]
        mpqn, parsed = parse_smf_notes(to_smf(notes, 120))
        self.assertEqual(mpqn, 500_000)
        self.assertEqual(parsed, [(62, 0, 480), (64, 480, 240), (62, 960, 960)])

    def test_record_sequence_format(self):
        notes = [Note(62, 0, 480, 90), Note(64, 480, 240, 80)]
        self.assertEqual(to_record_sequence_notes(notes, 120), "62,0,500,90,1;64,500,250,80,1")


class CliTests(unittest.TestCase):
    def test_generate_writes_manifest_and_midi(self):
        with tempfile.TemporaryDirectory() as d:
            rc = main(["generate", "--timbre", "shakuhachi", "--tonic", "E", "--count", "2",
                       "--top-modes", "2", "--out", d])
            self.assertEqual(rc, 0)
            manifest = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["candidates"]), 4)
            for c in manifest["candidates"]:
                self.assertTrue((Path(d) / c["midi_file"]).exists())
                self.assertEqual(len(c["record_sequence"]["notes"].split(";")), c["note_count"])


if __name__ == "__main__":
    unittest.main()
